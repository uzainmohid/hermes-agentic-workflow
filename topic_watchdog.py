"""Watchdog: re-check a topic and log sources not seen before. No Streamlit."""
import json
import os
import sys
from datetime import datetime, timezone

from research_planner import build_research_plan
from source_gatherer import gather_sources_for_plan

STATE_PATH = "watchdog_state.json"
DIGEST_PATH = "digest_log.json"


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        print(f"[watchdog] WARNING: could not read {path}: {exc}")
        return default


def _save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def check_topic(topic: str, log_fn=print) -> dict:
    state = _load_json(STATE_PATH, {})
    known = set(state.get(topic, {}).get("known_urls", []))
    first_check = topic not in state
    log_fn(f"Checking topic: {topic}")
    try:
        plan = build_research_plan(topic)
        sources = gather_sources_for_plan(plan, log_fn=log_fn)
    except Exception as exc:  # noqa: BLE001 - failure means zero sources, logged
        log_fn(f"Fetch failed: {exc}")
        sources = []

    new_sources = [s for s in sources if s.get("url") and s["url"] not in known]
    seen = set()
    unique_new = []
    for s in new_sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique_new.append(s)
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": now,
        "topic": topic,
        "sources_checked": len(sources),
        "new_sources_found": len(unique_new),
        "new_sources": [{"title": s.get("title", ""), "source_type": s.get("source_type", ""),
                         "url": s["url"], "subtopic": s.get("subtopic", "")} for s in unique_new],
    }
    # Digest first, state second: an interruption cannot lose a digest entry.
    digest = _load_json(DIGEST_PATH, [])
    digest.append(entry)
    _save_json_atomic(DIGEST_PATH, digest)
    state[topic] = {"known_urls": sorted(known | {s["url"] for s in sources if s.get("url")}),
                    "last_checked": now}
    _save_json_atomic(STATE_PATH, state)

    if unique_new:
        note = " (first check: everything counts as new)" if first_check else ""
        log_fn(f"Digest: {len(unique_new)} new source(s) found for '{topic}'.{note}")
    else:
        log_fn(f"No new sources for '{topic}' since last check.")
    return entry


def show_digest_log() -> None:
    digest = _load_json(DIGEST_PATH, [])
    if not digest:
        print("Digest log is empty.")
        return
    for e in digest:
        print(f"{e['timestamp']} | {e['topic']} | checked {e['sources_checked']} | "
              f"new {e['new_sources_found']}")
        for s in e.get("new_sources", []):
            print(f"    - [{s['source_type']}] {s['title']} ({s['url']})")


def main(argv) -> int:
    if len(argv) >= 3 and argv[1] == "check":
        check_topic(" ".join(argv[2:]))
        return 0
    if len(argv) == 2 and argv[1] == "digest":
        show_digest_log()
        return 0
    print('Usage: python topic_watchdog.py check "<topic>" | digest')
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
