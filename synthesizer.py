"""Synthesizer: write a cited report from gathered sources. References are built by code."""
import json
import re

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = (
    "You are a research writer. Use ONLY the provided sources; do not invent facts. "
    "Cite with inline [n] markers using the source numbers given. "
    "Pull out specific numbers where the sources give them. "
    'Return ONLY JSON: {"intro": "...", "sections": [{"heading": "...", "body": "..."}]}.'
)


def build_citation_map(sources: list):
    """One number per unique URL (or source_type:title), in order of first appearance."""
    key_to_num = {}
    references = []
    numbered = []
    for s in sources:
        key = s.get("url") or f"{s.get('source_type')}:{s.get('title')}"
        if key not in key_to_num:
            num = len(key_to_num) + 1
            key_to_num[key] = num
            references.append((num, s.get("source_type", ""), s.get("title", ""), s.get("url", "")))
        item = dict(s)
        item["num"] = key_to_num[key]
        numbered.append(item)
    return numbered, references


def find_unknown_citations(report: dict) -> list:
    """Return sorted [n] numbers used in the text that are not in references."""
    valid = {r[0] for r in report.get("references", [])}
    texts = [report.get("intro", "")] + [s.get("body", "") for s in report.get("sections", [])]
    used = set()
    for t in texts:
        used.update(int(m) for m in re.findall(r"\[(\d+)\]", t or ""))
    return sorted(used - valid)


def strip_unknown_citations(report: dict, unknown: list) -> dict:
    """Remove [n] markers for unknown numbers."""
    bad = {str(n) for n in unknown}

    def clean(text):
        return re.sub(r"\[(\d+)\]", lambda m: "" if m.group(1) in bad else m.group(0), text or "")

    report["intro"] = clean(report.get("intro", ""))
    for s in report.get("sections", []):
        s["body"] = clean(s.get("body", ""))
    return report


def _raw_fallback(numbered, references, intro):
    sections = [{"heading": s.get("subtopic", "Sources"),
                 "body": f"[{s['num']}] {s.get('content', '')[:200]}"} for s in numbered]
    return {"intro": intro, "sections": sections, "references": references}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def synthesize_report(topic: str, sources: list) -> dict:
    """Return {intro, sections, references}. Never raises."""
    numbered, references = build_citation_map(sources)
    if not numbered:
        return _raw_fallback(numbered, references,
                             "No sources were found, so no report was generated (model not called).")
    if not DEEPSEEK_API_KEY:
        return _raw_fallback(numbered, references,
                             "No API key configured; showing raw source excerpts instead of a synthesis.")
    try:
        groups = {}
        for s in numbered:
            groups.setdefault(s.get("subtopic", "General"), []).append(s)
        blocks = []
        for sub, items in groups.items():
            lines = [f"[{s['num']}] ({s['source_type']}) {s['title']}: {s['content'][:600]}" for s in items]
            blocks.append(f"## {sub}\n" + "\n".join(lines))
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Topic: {topic}\n\nSources:\n\n" + "\n\n".join(blocks)},
            ],
        )
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        sections = [{"heading": str(s["heading"]), "body": str(s["body"])}
                    for s in data.get("sections", [])
                    if isinstance(s, dict) and "heading" in s and "body" in s]
        report = {"intro": str(data.get("intro", "")), "sections": sections, "references": references}
        unknown = find_unknown_citations(report)
        if unknown:
            print(f"[synthesizer] WARNING: removed unknown citation(s): {unknown}")
            report = strip_unknown_citations(report, unknown)
            report["intro"] += f"\n\n(Note: removed unknown citation marker(s) {unknown}.)"
        return report
    except Exception as exc:  # noqa: BLE001 - degrade visibly
        print(f"[synthesizer] WARNING: synthesis failed: {exc}")
        return _raw_fallback(numbered, references,
                             f"Synthesis failed ({type(exc).__name__}: {exc}); showing raw source excerpts.")
