"""Planner: topic -> list of {subtopic, search_query}."""
import json
import re
import sys

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = (
    "You are a research planner. Break the topic into 3 to 5 subtopics. "
    "For each, give a search query of 3 to 6 words. "
    'Return ONLY a JSON array of objects: [{"subtopic": "...", "search_query": "..."}]. '
    "No commentary."
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _fallback(topic: str) -> list:
    return [{"subtopic": topic, "search_query": topic}]


def build_research_plan(topic: str) -> list:
    """Return a non-empty plan. Never raises; falls back to the raw topic."""
    if not DEEPSEEK_API_KEY:
        print("[planner] WARNING: no API key; using fallback plan.")
        return _fallback(topic)
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": topic},
            ],
        )
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        plan = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "subtopic" in item and "search_query" in item:
                    sub = str(item["subtopic"]).strip()
                    query = str(item["search_query"]).strip()
                    if sub and query:
                        plan.append({"subtopic": sub, "search_query": query})
        if plan:
            return plan
        print("[planner] WARNING: no valid plan items; using fallback plan.")
    except Exception as exc:  # noqa: BLE001 - degrade, but visibly
        print(f"[planner] WARNING: planning failed ({type(exc).__name__}: {exc}); using fallback plan.")
    return _fallback(topic)


if __name__ == "__main__":
    t = " ".join(sys.argv[1:]) or "EV battery recycling market"
    for i, item in enumerate(build_research_plan(t), 1):
        print(f"{i}. {item['subtopic']} - search: {item['search_query']}")
