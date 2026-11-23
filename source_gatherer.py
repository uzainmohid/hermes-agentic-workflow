"""Gatherer: fetch Wikipedia and Google News RSS for each plan item. No LLM."""
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import requests

WIKI_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
HEADERS = {"User-Agent": "ResearchOS/1.0"}
TIMEOUT = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_wikipedia_for_subtopic(search_query: str):
    """Search for the best page title, then fetch its summary. None on failure."""
    try:
        r = requests.get(
            WIKI_SEARCH_API,
            params={"action": "query", "list": "search", "srsearch": search_query,
                    "srlimit": 1, "format": "json"},
            headers=HEADERS, timeout=TIMEOUT,
        )
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            print(f"[gatherer] No Wikipedia result for '{search_query}'")
            return None
        title = hits[0]["title"]
        r = requests.get(
            WIKI_SUMMARY_API.format(title=quote(title.replace(" ", "_"), safe="")),
            headers=HEADERS, timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        extract = data.get("extract", "") or ""
        if len(extract) < 30:
            return None
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        return {
            "source_type": "wikipedia",
            "title": data.get("title", title),
            "content": extract,
            "url": url,
            "published_date": None,
            "retrieved_at": _now(),
        }
    except (requests.RequestException, ValueError) as exc:
        print(f"[gatherer] Wikipedia failed for '{search_query}': {exc}")
        return None


def fetch_news_for_subtopic(search_query: str, max_articles: int = 3) -> list:
    """Fetch news via requests (with timeout) and parse with feedparser."""
    try:
        r = requests.get(NEWS_RSS.format(query=quote(search_query)),
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        results = []
        for entry in feed.entries:
            title = entry.get("title")
            if not title:
                continue
            results.append({
                "source_type": "news_rss",
                "title": title,
                "content": entry.get("summary") or title,
                "url": entry.get("link", ""),
                "published_date": entry.get("published"),
                "retrieved_at": _now(),
            })
            if len(results) >= max_articles:
                break
        return results
    except Exception as exc:  # noqa: BLE001 - logged, returns empty
        print(f"[gatherer] News failed for '{search_query}': {exc}")
        return []


def gather_sources_for_plan(plan: list, log_fn=print) -> list:
    """Gather sources for every plan item. Never raises."""
    sources = []
    for item in plan or []:
        try:
            sub = item["subtopic"]
            query = item["search_query"]
        except (KeyError, TypeError):
            log_fn(f"Skipping malformed plan item: {item!r}")
            continue
        try:
            wiki = fetch_wikipedia_for_subtopic(query)
            if wiki:
                wiki["subtopic"] = sub
                sources.append(wiki)
                log_fn(f"[{sub}] Wikipedia: {wiki['title']}")
            else:
                log_fn(f"[{sub}] Wikipedia: no result")
            news = fetch_news_for_subtopic(query)
            for n in news:
                n["subtopic"] = sub
            sources.extend(news)
            log_fn(f"[{sub}] News: {len(news)} article(s)")
        except Exception as exc:  # noqa: BLE001 - one item must not kill the run
            log_fn(f"[{sub}] failed: {exc}")
    log_fn(f"Total sources gathered: {len(sources)}")
    return sources
