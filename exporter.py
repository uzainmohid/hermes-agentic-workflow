"""Exporter: render a report to Markdown or DOCX. PermissionError propagates."""
from datetime import datetime, timezone

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def export_to_markdown(topic: str, report: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {topic}", "", f"_Generated {now}_", "", "## Introduction", "",
             report.get("intro", ""), ""]
    for s in report.get("sections", []):
        lines += [f"## {s['heading']}", "", s["body"], ""]
    lines += ["## References", ""]
    for num, stype, title, url in report.get("references", []):
        link = f"[{title}]({url})" if url else title
        lines.append(f"[{num}] {stype}: {link}")
        lines.append("")
    return "\n".join(lines)


def save_markdown(topic: str, report: dict, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(export_to_markdown(topic, report))
    return path


def export_to_docx(topic: str, report: dict, path: str) -> str:
    doc = Document()
    title = doc.add_heading(topic, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("ResearchOS Report")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_heading("Introduction", level=1)
    doc.add_paragraph(report.get("intro", ""))
    for s in report.get("sections", []):
        doc.add_heading(s["heading"], level=1)
        doc.add_paragraph(s["body"])
    doc.add_heading("References", level=1)
    for num, stype, title_, url in report.get("references", []):
        p = doc.add_paragraph()
        p.add_run(f"[{num}] ").bold = True
        p.add_run(f"{stype}: {title_}" + (f" - {url}" if url else ""))
    doc.save(path)
    return path


def safe_filename(text: str, max_len: int = 50) -> str:
    """Keep alphanumerics and spaces, join words with '_', truncate."""
    kept = "".join(c for c in text if c.isalnum() or c == " ")
    return "_".join(kept.split())[:max_len] or "report"
