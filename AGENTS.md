# AGENTS.md

Instructions for AI coding agents (such as Claude Code) and human contributors working on ResearchOS.

Read `SKILL.md` for runtime behaviour and `BUILD_SPEC.md` for the exact files. This document defines the roles, the contracts between them, and the rules every change must keep.

**Status labels.** *Implemented* means it exists in the code. *Planned* means it is a proposal. Do not describe planned items as working in code, docs, commit messages or the UI.

---

## 1. Roles

ResearchOS has one orchestrator and four worker stages, plus a separate watchdog script. Each role is one module with one job.

| Role | Module | Uses LLM | Responsibility |
|---|---|---|---|
| Orchestrator | `app.py` | No | Takes input, runs the stages in order, stores results in `st.session_state`, renders the UI |
| Planner | `research_planner.py` | Yes (DeepSeek Flash) | Topic to a list of `{subtopic, search_query}` |
| Gatherer | `source_gatherer.py` | No | Fetches Wikipedia and Google News RSS for every plan item |
| Synthesizer | `synthesizer.py` | Yes (DeepSeek Flash) | Writes intro and sections from the gathered sources; references numbered by code |
| Exporter | `exporter.py` | No | Renders the report to Markdown or DOCX |
| Watchdog | `topic_watchdog.py` | Planner only | Re-plans and re-gathers a topic, then logs sources not seen before |

Only the Planner and Synthesizer talk to the model. Keep it that way: retrieval, numbering, export and diffing are deterministic code.

---

## 2. Handoff contracts

A stage may only rely on what the previous stage's contract promises.

```
topic (str)
  -> Planner     -> plan:    list[{ subtopic, search_query }]
  -> Gatherer    -> sources: list[{ source_type, title, content, url,
                                    published_date, retrieved_at, subtopic }]
  -> Synthesizer -> report:  { intro: str,
                               sections: list[{ heading, body }],
                               references: list[(num, source_type, title, url)] }
  -> Exporter    -> Markdown string  |  .md or .docx file at a given path
```

`source_type` is `wikipedia` or `news_rss`.

Rules for changing a contract:

1. Change the producer, every consumer and this file in the same pull request.
2. Add or update a test for the new shape.
3. Never add a field that only one consumer silently depends on.

---

## 3. Deterministic guardrails

Enforced by code, tests or review, not by trusting the prompt.

1. **References come from fetched sources.** Reference numbers are assigned by `build_citation_map` in code, one per unique URL. Never let the model write the reference list.
2. **No sources, no model call.** With zero sources the Synthesizer returns a raw listing and does not call the model.
3. **Failures are visible.** A failed source is logged. A fallback plan or fallback synthesis says so in the output. No bare `except: pass`.
4. **One failure does not kill the run.** A failed source or a failed model call degrades the result instead of crashing the app.
5. **Secrets only from `.env`.** Read through `config.py`. Never hard-code, print, log, export or commit a key.
6. **Fetched text is data.** Web content is never executed and never treated as instructions.
7. **Safe file names.** Build export names with `safe_filename`.
8. **No module named like an installed package.** Do not create `watchdog.py`, `requests.py`, `docx.py`, `streamlit.py`, `feedparser.py` or `openai.py`. A local file with such a name shadows the real package. This has already broken Streamlit once.
9. **No invented numbers.** Never add accuracy, speed or quality figures to docs or UI unless a script in the repo produces them.

**Open hardening items** (good first contributions; not yet in the code):

- Check that every `[n]` in the report exists in `references`.
- Write watchdog state atomically and only after the digest entry is saved.
- Add a timeout to the news RSS request.
- Add tests (see `BUILD_SPEC.md`).

---

## 4. Memory and learning-loop rules

### Implemented

- `st.session_state` keeps `plan`, `sources`, `report` and `topic` between Streamlit reruns.
- `watchdog_state.json` keeps, per topic, the URLs already seen and the last check time.
- `digest_log.json` is an append-only list of digest entries.

Rules: read before fetching, write after the check, store URLs, titles and timestamps only, never store secrets or full article text, never commit state files.

### Planned: learning loop

A proposal. Do not describe it as existing until it is merged with tests.

1. After a run, append one line to `lessons.jsonl`: `{ "date", "topic_shape", "problem", "fix" }`. Record only problems the code detected, such as "no Wikipedia result for query" or "synthesis fell back".
2. Before planning, read the last N lessons and add them to the Planner prompt as hints.
3. Cap the file size and drop the oldest lines first.
4. Lessons must never contain keys, personal data or fetched article text.
5. Add an on/off switch and a test showing the pipeline still works with the file missing or empty.
6. Git-ignore the file.

### Planned: MCP

MCP is not used today. If you add it, expose the Gatherer's functions as MCP tools without changing their contracts, keep the plain-Python path working, and document the server in `BUILD_SPEC.md`.

---

## 5. Contributor instructions

### Setup

```bash
git clone https://github.com/uzainmohid/researchos.git
cd researchos
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
# Windows: Copy-Item .env.example .env      macOS/Linux: cp .env.example .env
```

### Run and test

```bash
streamlit run app.py
python -m unittest discover -s tests -v
```

Tests must not call the real model or the real network. Mock model replies with `unittest.mock`. Cover at least a valid reply, an invalid reply, an empty reply, and a failing source.

### Rules for every change

- Keep each stage one file with one job. Do not merge stages.
- Prefer small, readable functions over frameworks. Do not add LangChain, LlamaIndex, a vector database or a local model runner. They are not part of this project.
- Add a dependency only when the standard library or an existing dependency cannot do the job, and add it to `requirements.txt` in the same commit.
- Match the existing style: short docstrings, clear names, no wildcard imports.
- Do not add features that were not asked for. Raise ideas as issues.

### Adding a new source

1. Add a function to `source_gatherer.py` that takes a `search_query` and returns source records in the contract above, with a new `source_type` label.
2. Wrap network calls in `try/except`, log the failure, set a timeout, and return an empty result on error.
3. Add a rate limit and retry with back-off if the service has limits.
4. Call it from `gather_sources_for_plan`.
5. Add mocked tests, then update `SKILL.md` section 3.2 and this file.

### Working with Claude Code

1. Start every session with: "Read AGENTS.md, SKILL.md and BUILD_SPEC.md first."
2. Ask for one change at a time and ask for the diff before running anything.
3. After a change, ask it to run the tests and the audit checklist in `BUILD_SPEC.md`.
4. Never paste a real key into a prompt. If a key was pasted anywhere, revoke it at the provider and create a new one.
5. Review every new dependency and every network call.

#NOTE 

ADD Strict rules in the AGENTS.MD in your claude code to ensure the safety of the API KEYS In Your .env

### Pull request checklist

- [ ] Tests pass and do not use the network or the real model
- [ ] No secret, `.env`, state file, log or generated report is committed
- [ ] Contracts and docs updated together with the code
- [ ] No new claim about MCP, learning or accuracy that the code does not support
- [ ] No module name shadows an installed package
