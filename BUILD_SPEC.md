# BUILD_SPEC.md

Build and audit specification for ResearchOS. Give this file to Claude Code with this instruction:

> Read BUILD_SPEC.md, SKILL.md and AGENTS.md. If the repository is empty, scaffold it as specified. If code already exists, do **not** rewrite it: compare it to this spec, list every difference, and fix only what the Audit section requires. Show me the diff before committing.

**Scope.** This spec covers only what ResearchOS does: DeepSeek Flash through its OpenAI-compatible API, Wikipedia, Google News RSS through `feedparser`, Streamlit and `python-docx`. It adds no other frameworks, no local model runners and no MCP servers.

Sections 5.1 to 5.7 describe the code **as it exists**. Section 5.8 lists additions that do not exist yet and are marked *Add*.

---

## 1. Repository tree

```
researchos/
  app.py
  config.py
  research_planner.py
  source_gatherer.py
  synthesizer.py
  exporter.py
  topic_watchdog.py
  requirements.txt
  .env.example
  .gitignore
  LICENSE
  README.md
  SKILL.md
  AGENTS.md
  BUILD_SPEC.md
  tests/                      # Add
    __init__.py
    test_config.py
    test_planner.py
    test_gatherer.py
    test_synthesizer.py
    test_exporter.py
    test_watchdog.py
```

Created at runtime and git-ignored: `watchdog_state.json`, `digest_log.json`, `report_*.md`, `report_*.docx`, `test_report.md`, `test_report.docx`.

Forbidden file names (they shadow installed packages): `watchdog.py`, `requests.py`, `docx.py`, `streamlit.py`, `feedparser.py`, `openai.py`.

---

## 2. `requirements.txt`

```
streamlit
openai
requests
feedparser
python-docx
```

`openai` is the client library for the OpenAI-compatible DeepSeek endpoint. After the first successful audit run, pin exact versions from `pip freeze`.

---

## 3. `.env.example`

```
# Copy this file to .env and fill in your own key. Never commit .env.
DEEPSEEK_API_KEY=your_key_here
```

---

## 4. `.gitignore`

```
# Secrets: never commit
.env
.env.*
!.env.example
*.key
*.pem
secrets.*
.streamlit/secrets.toml

# Python
__pycache__/
*.py[cod]
venv/
.venv/
*.egg-info/
.pytest_cache/

# Runtime state, memory, logs
watchdog_state.json
digest_log.json
lessons.jsonl
data/
memory/
logs/
*.log
*.sqlite
*.db

# Generated reports
report_*.md
report_*.docx
test_report.md
test_report.docx

# Recordings and editor/OS files
*.mp4
*.mkv
.vscode/
.idea/
.DS_Store
Thumbs.db
```

---

## 5. Script specifications

### 5.1 `config.py`

- `load_env(path=".env")`: if the file is missing, return silently. Skip blank lines, lines starting with `#`, and lines without `=`. Use `os.environ.setdefault` so real environment variables win. Called once at import.
- Exports `DEEPSEEK_API_KEY` (from the environment, default `""`), `DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"`, `DEEPSEEK_MODEL = "deepseek-v4-flash"`.
- The `.env` path is relative, so the app must be started from the project folder.
- Must not print or log the key.

### 5.2 `research_planner.py`

- `build_research_plan(topic: str) -> list`.
- Client: `OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)`; temperature 0.3.
- System prompt asks for 3 to 5 subtopics, each with a 3 to 6 word search query, as a JSON array of `{"subtopic", "search_query"}` and nothing else.
- Strips accidental Markdown code fences, then `json.loads`.
- Keeps only dict items that have both keys; stringifies and strips them.
- Fallback `[{"subtopic": topic, "search_query": topic}]` when the key is missing, the call or parsing fails, or no valid item remains. Prints a warning. Never raises.
- `__main__`: plans a topic from `sys.argv` (default `EV battery recycling market`) and prints it.

### 5.3 `source_gatherer.py`

- Constants: Wikipedia search API `https://en.wikipedia.org/w/api.php`, summary API `https://en.wikipedia.org/api/rest_v1/page/summary/{title}`, news RSS `https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en`.
- `fetch_wikipedia_for_subtopic(search_query) -> dict | None`: search with `srlimit=1`, then fetch the summary; discard extracts shorter than 30 characters; timeout 10 s; `User-Agent: ResearchOS/1.0`; return `{source_type: "wikipedia", title, content, url, published_date: None, retrieved_at}` or `None`; print and return `None` on `requests.RequestException`.
- `fetch_news_for_subtopic(search_query, max_articles=3) -> list`: `feedparser.parse` on the URL with `quote(search_query)`; skip entries without a title; `content` is the summary or the title; `source_type: "news_rss"`; `published_date` from the entry; return `[]` on error.
- `gather_sources_for_plan(plan, log_fn=print) -> list`: for each plan item gather Wikipedia then news, add `subtopic` to each record, log one line per step and a final total. Never raises.

### 5.4 `synthesizer.py`

- `build_citation_map(sources) -> (numbered_sources, references)`: one number per unique URL (or `source_type:title` if there is no URL), in order of first appearance; `references` is `[(num, source_type, title, url)]`.
- `synthesize_report(topic, sources) -> dict` with `intro`, `sections`, `references`.
- Groups numbered sources by subtopic; each source is sent as `[num] (source_type) title: content[:600]`.
- System prompt: use only the provided sources, do not invent facts, return JSON `{"intro", "sections": [{"heading", "body"}]}`, cite with inline `[n]`, pull out specific numbers where the sources give them.
- Temperature 0.3; strips code fences; `json.loads`.
- If there is no key or no sources: no model call; sections are raw excerpts (`[num] content[:200]`); `intro` explains.
- On any exception: same raw-excerpt fallback with the error text in `intro`.

### 5.5 `exporter.py`

- `export_to_markdown(topic, report) -> str`: `# topic`, a UTC generation line, `## Introduction`, one `## heading` per section, `## References` with `[n] source_type: [title](url)` (or without a link if there is no URL).
- `save_markdown(topic, report, path) -> str`.
- `export_to_docx(topic, report, path) -> str`: `python-docx`; centred title, "ResearchOS Report" subtitle, Introduction, one heading per section, References with bold numbers; saves and returns the path.
- `safe_filename(text, max_len=50) -> str`: keep alphanumerics and spaces, join words with `_`, truncate.
- `PermissionError` on save must propagate to the caller.

### 5.6 `app.py`

- `st.set_page_config(page_title="ResearchOS", layout="wide")`.
- If `DEEPSEEK_API_KEY` is empty: `st.error` with the `.env` instruction, then `st.stop()`.
- `st.session_state` keys: `plan`, `sources`, `report`, `topic`, initialised once.
- Two tabs, **Research** and **Export**.
- Research: topic input (placeholder `e.g. EV battery recycling market`); button **Run research pipeline** disabled when the topic is empty; `st.status` block with the three step messages and counts; then the plan, expandable sources (`[subtopic] source_type: title`, first 500 characters, URL caption) and the report with references.
- Export: info message if no report; otherwise Markdown and DOCX download buttons (DOCX written to `report_<safe_filename>.docx` in the working folder) and a Markdown preview.

### 5.7 `topic_watchdog.py`

- Constants `STATE_PATH = "watchdog_state.json"`, `DIGEST_PATH = "digest_log.json"`.
- `check_topic(topic, log_fn=print) -> dict`: load state; run `build_research_plan` and `gather_sources_for_plan` inside `try/except` (a failure means zero sources, logged); compute `new_sources` as sources whose URL is not in the saved `known_urls`; build the digest entry (`timestamp`, `topic`, `sources_checked`, `new_sources_found`, `new_sources`); save state (`known_urls` union, `last_checked`); append the entry to the digest log; log a summary line.
- `show_digest_log()`: prints each entry with its new sources.
- CLI: `check "<topic>"` and `digest`; other input prints usage and exits with code 1.
- Must not import Streamlit.

### 5.8 Additions (*Add*)

1. **Citation check.** In `synthesizer.py`, after the model call, find every `[n]` in the intro and sections and compare with the reference numbers. Report or strip unknown markers.
2. **Atomic watchdog writes.** Write `*.tmp` then `os.replace`, and save state only after the digest entry is saved.
3. **News timeout.** Fetch the RSS with `requests` (timeout 10 s) and pass the content to `feedparser.parse`, or set a socket timeout, so a stalled request cannot hang the app.
4. **Tests**, using `unittest` and `unittest.mock`, no real network or model:

| File | Must cover |
|---|---|
| `test_config.py` | Missing `.env` does not raise; value loaded from `.env`; real environment variable wins |
| `test_planner.py` | Valid JSON; JSON in code fences; invalid JSON falls back; empty reply falls back; missing key falls back; malformed items dropped |
| `test_gatherer.py` | Wikipedia search-then-summary order; one source failing does not stop the rest; empty plan returns `[]`; entries without a title skipped |
| `test_synthesizer.py` | Numbering is one per unique URL; empty sources makes no model call; model failure returns the raw-excerpt fallback; unknown `[n]` detected (after addition 1) |
| `test_exporter.py` | Markdown contains every reference; DOCX file is created and non-empty; `safe_filename` on awkward input |
| `test_watchdog.py` | Three simulated checks report 2, 1 and 0 new sources; first check reports all as new; fetch failure records zero new sources |

---

## 6. Acceptance commands

```bash
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
python topic_watchdog.py check "EV battery recycling market"
python topic_watchdog.py digest
```

All tests pass, the app starts without `ImportError`, and `git status` does not list the two watchdog JSON files.

---

## 7. Audit checklist (for Claude Code)

Run every item, report pass or fail, and fix only failures.

**Secrets**

- [ ] `git grep -nEi "sk-[a-z0-9]{16,}"` finds nothing
- [ ] `git grep -nEi "api[_-]?key *= *['\"][^'\"]+['\"]"` finds nothing
- [ ] `git ls-files | grep -E "(^|/)\.env($|\.)"` lists only `.env.example`
- [ ] `git log -p` shows no key in history. If one does, stop and tell the owner to revoke it before publishing
- [ ] No code prints, logs or exports `DEEPSEEK_API_KEY`
- [ ] `git check-ignore -v .env watchdog_state.json digest_log.json report_x.docx __pycache__` ignores all five

**Scope and honesty**

- [ ] No import or use of Ollama, LangChain, LlamaIndex, a vector database or an MCP server
- [ ] README, SKILL.md and AGENTS.md describe MCP and the learning loop only as *Planned*
- [ ] No company-internal names, endpoints, keys or rules anywhere in code, docs or git history
- [ ] No accuracy or performance figures without a script that produces them
- [ ] The README of any older copy of this project has no unfilled bracketed placeholders (an earlier README draft contained one about FreeBuff)

**Correctness**

- [ ] No file named `watchdog.py`, `requests.py`, `docx.py`, `streamlit.py`, `feedparser.py` or `openai.py`
- [ ] Contracts in `AGENTS.md` section 2 match the real return values
- [ ] The app is started from the project folder and still finds `.env`
- [ ] Every `requests` call has a timeout; the RSS fetch is covered by addition 3
- [ ] Failures are logged or shown, never swallowed silently

**Packaging**

- [ ] `requirements.txt` lists exactly what the code imports
- [ ] `.env.example` contains only a placeholder value
- [ ] `LICENSE` is MIT with the right year and holder
- [ ] The README quickstart works from a fresh clone on Windows PowerShell and on macOS/Linux

---

## 8. `LICENSE`

```
MIT License

Copyright (c) 2026 Uzain Mohid

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 9. First publish

```bash
git init
git add .
git status        # confirm .env, watchdog_state.json and digest_log.json are NOT listed
git commit -m "Initial commit: ResearchOS"
git branch -M main
git remote add origin https://github.com/uzainmohid/researchos.git
git push -u origin main
```

Before the first push, revoke and replace any key or bot token that was ever pasted into a chat, a screenshot or a file, even if it was later deleted.
