"""
AI Research Intelligence Copilot — Streamlit Frontend
"""

from __future__ import annotations

import tempfile
from datetime import date

import httpx
import streamlit as st
from pyvis.network import Network

API_BASE = "http://localhost:8000"
DEFAULT_TOPIC = "agent tool-call reliability"


def api_get(path: str) -> dict | list | None:
    try:
        response = httpx.get(f"{API_BASE}{path}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        response = httpx.post(f"{API_BASE}{path}", json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def render_query_result(result: dict) -> None:
    search_mode = result.get("search_mode", "unknown")
    st.markdown(
        f'<span class="search-mode-tag">{search_mode} search</span>',
        unsafe_allow_html=True,
    )

    st.markdown("### Answer")
    st.markdown(result.get("answer", "No answer available."))

    methods = result.get("related_methods", [])
    if methods:
        st.markdown("### Related Methods")
        badges = " ".join(f'<span class="method-badge">{method}</span>' for method in methods)
        st.markdown(badges, unsafe_allow_html=True)

    evidence = result.get("evidence", [])
    if evidence:
        st.markdown("### Evidence")
        for item in evidence:
            with st.container(border=True):
                st.markdown(f"**{item.get('title', 'Untitled')}**")
                st.caption(item.get("citation", ""))
                snippet = item.get("snippet")
                if snippet:
                    st.write(snippet)
                score = item.get("score")
                if score:
                    st.progress(min(score, 1.0), text=f"Relevance: {score:.3f}")

    graph_paths = result.get("graph_paths", [])
    if graph_paths:
        st.markdown("### Graph Paths")
        for path in graph_paths:
            st.code(" -> ".join(path))

    tool_trace = result.get("tool_trace", [])
    if tool_trace:
        st.markdown("### MCP Tool Trace")
        for item in tool_trace:
            with st.expander(item.get("tool_name", "tool")):
                st.json(
                    {
                        "arguments": item.get("arguments", {}),
                        "result": item.get("result", {}),
                    }
                )

    note = result.get("confidence_note")
    if note:
        st.info(note)


def get_active_topic() -> str:
    return st.session_state.get("active_corpus_topic", DEFAULT_TOPIC) or DEFAULT_TOPIC


def set_active_topic(topic: str) -> None:
    st.session_state["active_corpus_topic"] = topic.strip() or DEFAULT_TOPIC


def render_stats(stats: dict) -> None:
    cards = [
        ("Papers", stats.get("papers", 0)),
        ("Methods", stats.get("methods", 0)),
        ("Claims", stats.get("claims", 0)),
        ("Authors", stats.get("authors", 0)),
    ]
    columns = st.columns(4)
    for column, (label, value) in zip(columns, cards, strict=True):
        column.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-value">{value}</div>
                <div class="stat-label">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_overview() -> None:
    st.markdown("# Overview")
    st.caption("Corpus health, topic summary, and the main demo flow.")

    stats = api_get("/api/stats")
    if not stats:
        st.warning("No graph data yet. Run an ingestion job from the Ingest page first.")
        return

    render_stats(stats)
    st.markdown("---")

    topic = get_active_topic()
    st.markdown("### Active Topic")
    st.markdown(f"**{topic}**")

    summary = api_get(f"/api/topics/{topic}")
    if summary:
        left, right = st.columns([1.2, 1])
        with left:
            st.markdown("#### Top Methods")
            methods = summary.get("methods", [])
            if methods:
                badges = " ".join(
                    f'<span class="method-badge">{method}</span>' for method in methods[:12]
                )
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.info("No extracted methods yet.")

        with right:
            st.markdown("#### Corpus Coverage")
            st.metric("Papers in topic summary", summary.get("paper_count", 0))
            if summary.get("date_range"):
                st.caption(summary["date_range"])

        claims = summary.get("claims", [])
        if claims:
            st.markdown("#### Top Claims")
            for claim in claims[:6]:
                st.markdown(f"- {claim}")

    st.markdown("---")
    st.markdown("### Recommended Demo Questions")
    prompts = [
        "Compare retry strategies and structured outputs for reducing tool-call failures.",
        "Which papers support structured reflection, and what claims are connected to it?",
        "Show a graph path from the Atomix paper to a retry-related method.",
    ]
    for prompt in prompts:
        st.code(prompt)


def page_query() -> None:
    st.markdown("# Ask")
    st.caption("Run evidence-backed research queries against the active topic corpus.")

    with st.container(border=True):
        st.markdown(f"**Active topic:** {get_active_topic()}")

    col1, col2 = st.columns([3, 1])
    with col1:
        question = st.text_area(
            "Question",
            height=120,
            placeholder=(
                "Compare retry strategies and structured outputs "
                "for reducing tool-call failures."
            ),
        )
    with col2:
        mode = st.selectbox("Mode", ["auto", "entity", "theme", "comparative"])
        start_date = st.date_input("From", value=None, key="query_start")
        end_date = st.date_input("To", value=None, key="query_end")

    if st.button("Run Query", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Enter a question first.")
            return

        payload = {"question": question.strip(), "search_mode": mode}
        if start_date:
            payload["start_date"] = str(start_date)
        if end_date:
            payload["end_date"] = str(end_date)

        with st.spinner("Querying the graph..."):
            result = api_post("/api/query", payload)

        if result:
            render_query_result(result)

    st.markdown("---")
    st.markdown("### Generate Briefing")
    brief_col1, brief_col2, brief_col3 = st.columns(3)
    with brief_col1:
        briefing_topic = st.text_input("Topic", value=get_active_topic(), key="briefing_topic")
    with brief_col2:
        briefing_start = st.text_input("Start date", value="2025-01-01")
    with brief_col3:
        briefing_end = st.text_input("End date", value="2026-03-22")

    if st.button("Generate Briefing", use_container_width=True):
        with st.spinner("Generating briefing..."):
            result = api_post(
                "/api/briefings",
                {
                    "topic": briefing_topic,
                    "start_date": briefing_start,
                    "end_date": briefing_end,
                },
            )
        if result:
            st.markdown("### Briefing")
            st.write(result.get("summary", ""))
            citations = result.get("citations", [])
            if citations:
                st.markdown("**Sources**")
                for citation in citations:
                    st.markdown(f"- {citation}")


def page_benchmark() -> None:
    st.markdown("# Benchmarks")
    st.caption("Run gold questions against the benchmark corpus and inspect the evidence trail.")

    manifest = api_get("/api/benchmark/papers")
    questions = api_get("/api/evaluation/questions")

    if not questions:
        st.info("No benchmark questions found.")
        return

    selected_id = st.selectbox(
        "Benchmark question",
        options=[question["id"] for question in questions],
        format_func=lambda value: next(
            question["question"] for question in questions if question["id"] == value
        ),
    )
    selected = next(question for question in questions if question["id"] == selected_id)

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("### Question")
        st.write(selected["question"])
        st.caption(f"Expected search mode: {selected.get('search_mode', 'auto')}")

        if st.button("Run Benchmark Query", type="primary", use_container_width=True):
            with st.spinner("Running benchmark question..."):
                result = api_post(
                    "/api/query",
                    {
                        "question": selected["question"],
                        "search_mode": selected.get("search_mode", "auto"),
                    },
                )
            if result:
                render_query_result(result)

    with right:
        st.markdown("### Expected Targets")
        tools = selected.get("expected_tools", [])
        if tools:
            st.markdown("**Tools**")
            st.write(", ".join(tools))

        relationships = selected.get("expected_relationships", [])
        if relationships:
            st.markdown("**Relationships**")
            st.write(", ".join(relationships))

        papers = selected.get("expected_paper_ids", [])
        if papers:
            st.markdown("**Paper IDs**")
            for paper_id in papers:
                st.code(paper_id)

    if manifest:
        st.markdown("---")
        st.markdown("### Seed Papers")
        for paper in manifest:
            with st.expander(paper.get("title", "Untitled")):
                st.caption(paper.get("semantic_scholar_id", ""))
                reason = paper.get("reason")
                if reason:
                    st.write(reason)


def page_graph() -> None:
    st.markdown("# Graph")
    st.caption("Inspect the graph structure behind the retrieval layer.")

    controls, canvas = st.columns([1, 3])
    with controls:
        limit = st.slider("Paper nodes", 5, 100, 25, step=5)
        show_authors = st.checkbox("Authors", value=False)
        show_claims = st.checkbox("Claims", value=False)
        show_methods = st.checkbox("Methods", value=True)

        relationship_counts = api_get("/api/stats")
        if relationship_counts:
            st.markdown("### Corpus Stats")
            for key, value in relationship_counts.items():
                st.caption(f"{key.title()}: {value}")

    data = api_get(f"/api/graph?limit={limit}")
    if not data or not data.get("nodes"):
        st.info("No graph data yet. Run the ingestion pipeline first.")
        return

    hidden_types = set()
    if not show_authors:
        hidden_types.add("author")
    if not show_claims:
        hidden_types.add("claim")
    if not show_methods:
        hidden_types.add("method")

    visible_ids = {
        node["id"] for node in data["nodes"] if node.get("type") not in hidden_types
    }

    colors = {
        "paper": "#2563eb",
        "method": "#059669",
        "claim": "#d97706",
        "author": "#db2777",
    }
    sizes = {"paper": 18, "method": 26, "claim": 12, "author": 14}
    shapes = {"paper": "dot", "method": "diamond", "claim": "triangle", "author": "star"}

    network = Network(height="680px", width="100%", bgcolor="#0f172a", font_color="#e2e8f0")
    network.barnes_hut(gravity=-3000, central_gravity=0.25, spring_length=110)

    for node in data["nodes"]:
        if node["id"] not in visible_ids:
            continue
        node_type = node["type"]
        network.add_node(
            node["id"],
            label=node["label"],
            color=colors.get(node_type, "#94a3b8"),
            size=sizes.get(node_type, 14),
            shape=shapes.get(node_type, "dot"),
            title=f"{node_type.upper()}: {node['label']}",
        )

    for edge in data["edges"]:
        if edge["from"] in visible_ids and edge["to"] in visible_ids:
            network.add_edge(
                edge["from"],
                edge["to"],
                title=edge["label"],
                color="#475569",
                width=1,
            )

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as handle:
        network.save_graph(handle.name)
        temp_path = handle.name

    with open(temp_path, encoding="utf-8") as handle:
        html = handle.read()

    with canvas:
        st.components.v1.html(html, height=700, scrolling=False)

    edge_count = sum(
        1 for edge in data["edges"] if edge["from"] in visible_ids and edge["to"] in visible_ids
    )
    st.caption(f"Showing {len(visible_ids)} nodes and {edge_count} edges.")


def page_ingest() -> None:
    st.markdown("# Ingest")
    st.caption("Create or refresh a topic corpus.")

    with st.container(border=True):
        st.markdown(
            "Use a narrow topic for the cleanest graph. Benchmark and hybrid modes are intended "
            "for the default topic corpus."
        )

    topic_col, config_col = st.columns(2)
    with topic_col:
        topic = st.text_input("Topic", value=get_active_topic())
        start_date = st.date_input("Start date", value=date(2025, 1, 1))
        target_papers = st.slider("Target papers", min_value=10, max_value=150, value=100, step=10)
    with config_col:
        corpus_mode = st.selectbox("Corpus mode", ["auto", "latest", "benchmark", "hybrid"])
        end_date = st.date_input("End date", value=date(2026, 3, 22))

    if st.button("Run Ingestion", type="primary", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic first.")
            return

        payload = {
            "topic": topic.strip(),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "target_papers": target_papers,
            "corpus_mode": corpus_mode,
        }
        with st.spinner("Running ingestion pipeline..."):
            result = api_post("/api/ingest/run", payload)

        if result:
            set_active_topic(topic)
            st.success("Pipeline completed.")
            st.json(result)

    st.markdown("---")
    st.markdown("### System Health")
    health = api_get("/health")
    stats = api_get("/api/stats")
    left, right = st.columns(2)
    with left:
        if health:
            st.success(f"API: {health.get('status', '?')}")
        else:
            st.error("API is not responding.")
    with right:
        if stats:
            st.caption(
                f"Papers: {stats.get('papers', 0)} • Methods: {stats.get('methods', 0)} • "
                f"Claims: {stats.get('claims', 0)}"
            )


st.set_page_config(
    page_title="AI Research Intelligence Copilot",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { font-family: 'Inter', sans-serif; }
        .stat-card {
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 14px;
            padding: 18px;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.92));
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .stat-label {
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
            margin-top: 6px;
        }
        .method-badge {
            display: inline-block;
            background: #1d4ed8;
            color: white;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            margin: 0 6px 6px 0;
        }
        .search-mode-tag {
            display: inline-block;
            background: rgba(37, 99, 235, 0.16);
            color: #60a5fa;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 10px;
        }
    </style>
    """
)

st.session_state.setdefault("active_corpus_topic", DEFAULT_TOPIC)

with st.sidebar:
    st.markdown("## AI Research Copilot")
    st.caption("Graph-backed retrieval for research intelligence")
    st.divider()

    active_topic = st.text_input("Active topic", value=get_active_topic())
    if active_topic != get_active_topic():
        set_active_topic(active_topic)

    page = st.radio(
        "Navigation",
        ["Overview", "Ask", "Benchmarks", "Graph", "Ingest"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Neo4j • MCP • OpenRouter • Streamlit")

if page == "Overview":
    page_overview()
elif page == "Ask":
    page_query()
elif page == "Benchmarks":
    page_benchmark()
elif page == "Graph":
    page_graph()
elif page == "Ingest":
    page_ingest()
