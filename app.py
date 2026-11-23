"""Orchestrator: Streamlit UI that runs plan -> gather -> synthesize -> export."""
import streamlit as st

from config import DEEPSEEK_API_KEY
from exporter import export_to_docx, export_to_markdown, safe_filename
from research_planner import build_research_plan
from source_gatherer import gather_sources_for_plan
from synthesizer import synthesize_report

st.set_page_config(page_title="ResearchOS", layout="wide")
st.title("ResearchOS")

if not DEEPSEEK_API_KEY:
    st.error("DEEPSEEK_API_KEY not found. Copy .env.example to .env, add your key, "
             "and start the app from the project folder.")
    st.stop()

for key, default in (("plan", None), ("sources", None), ("report", None), ("topic", "")):
    st.session_state.setdefault(key, default)

tab_research, tab_export = st.tabs(["Research", "Export"])

with tab_research:
    topic = st.text_input("Topic", placeholder="e.g. EV battery recycling market").strip()
    if st.button("Run research pipeline", disabled=not topic):
        with st.status("Running pipeline...", expanded=True) as status:
            st.write("Step 1: Research Planner - decomposing topic into subtopics...")
            plan = build_research_plan(topic)
            st.write(f"{len(plan)} subtopics planned")
            st.write("Step 2: Source Gatherer - fetching Wikipedia + news RSS...")
            sources = gather_sources_for_plan(plan, log_fn=st.write)
            st.write(f"{len(sources)} sources gathered")
            st.write("Step 3: Synthesizer - writing the report with citations...")
            report = synthesize_report(topic, sources)
            st.write(f"Report written ({len(report['sections'])} sections, "
                     f"{len(report['references'])} references)")
            status.update(label="Pipeline complete", state="complete")
        st.session_state.update(plan=plan, sources=sources, report=report, topic=topic)

    if st.session_state["plan"]:
        st.subheader("Plan")
        for i, item in enumerate(st.session_state["plan"], 1):
            st.write(f"{i}. {item['subtopic']} - search: {item['search_query']}")
    if st.session_state["sources"] is not None:
        st.subheader("Sources")
        for s in st.session_state["sources"]:
            with st.expander(f"[{s['subtopic']}] {s['source_type']}: {s['title']}"):
                st.write(s["content"][:500])
                st.caption(s["url"])
    if st.session_state["report"]:
        rep = st.session_state["report"]
        st.subheader("Report")
        st.write(rep["intro"])
        for sec in rep["sections"]:
            st.markdown(f"### {sec['heading']}")
            st.write(sec["body"])
        st.markdown("### References")
        for num, stype, title, url in rep["references"]:
            st.markdown(f"[{num}] {stype}: [{title}]({url})" if url else f"[{num}] {stype}: {title}")

with tab_export:
    if not st.session_state["report"]:
        st.info("Run the research pipeline first.")
    else:
        t, rep = st.session_state["topic"], st.session_state["report"]
        md = export_to_markdown(t, rep)
        name = safe_filename(t)
        st.download_button("Download Markdown", md, file_name=f"report_{name}.md")
        try:
            path = export_to_docx(t, rep, f"report_{name}.docx")
            with open(path, "rb") as f:
                st.download_button("Download DOCX", f.read(), file_name=f"report_{name}.docx")
        except PermissionError:
            st.error("Cannot write the DOCX file. Close it in Word and retry.")
        st.markdown("---")
        st.markdown(md)
