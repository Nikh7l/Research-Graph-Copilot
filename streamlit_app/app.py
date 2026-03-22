"""
AI Research Intelligence Copilot — Streamlit Frontend

Multi-page app for exploring agent tool-call reliability research.
"""

import tempfile

import httpx
import streamlit as st
from pyvis.network import Network

API_BASE = "http://localhost:8000"
DEFAULT_TOPIC = "agent tool-call reliability"


def api_get(path: str) -> dict | list | None:
    """GET request to the backend API."""
    try:
        resp = httpx.get(f"{API_BASE}{path}", timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, data: dict) -> dict | None:
    """POST request to the backend API."""
    try:
        resp = httpx.post(f"{API_BASE}{path}", json=data, timeout=120.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def render_query_result(result: dict) -> None:
    """Render a query response consistently across pages."""
    search_mode = result.get("search_mode", "unknown")
    st.markdown(
        f'<span class="search-mode-tag">{search_mode} search</span>',
        unsafe_allow_html=True,
    )

    st.markdown("### Answer")
    st.markdown(result.get("answer", "No answer."))

    methods = result.get("related_methods", [])
    if methods:
        st.markdown("### Related Methods")
        badges = " ".join(f'<span class="method-badge">{m}</span>' for m in methods)
        st.markdown(badges, unsafe_allow_html=True)

    evidence = result.get("evidence", [])
    if evidence:
        st.markdown("### 📚 Evidence")
        for item in evidence:
            with st.container(border=True):
                title = item.get("title", "Untitled")
                st.markdown(f"**{title}**")
                citation = item.get("citation", "")
                st.caption(citation)
                if item.get("score"):
                    st.progress(
                        min(item["score"], 1.0),
                        text=(f"Relevance: {item['score']:.3f}"),
                    )

    graph_paths = result.get("graph_paths", [])
    if graph_paths:
        st.markdown("### 🕸️ Graph Paths")
        for path in graph_paths:
            st.code(" -> ".join(path))

    tool_trace = result.get("tool_trace", [])
    if tool_trace:
        st.markdown("### 🛠️ MCP Tool Trace")
        for item in tool_trace:
            with st.expander(item.get("tool_name", "tool"), expanded=False):
                st.json(
                    {
                        "arguments": item.get("arguments", {}),
                        "result": item.get("result", {}),
                    }
                )

    note = result.get("confidence_note")
    if note:
        st.info(f"ℹ️ {note}")


def get_active_topic() -> str:
    topic = st.session_state.get("active_corpus_topic", DEFAULT_TOPIC)
    return topic or DEFAULT_TOPIC


# ── Page Config ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Research Intelligence Copilot",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────

st.html("""
<style>
    @import url(
        'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
    );
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    .stat-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-label {
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }
    .evidence-card {
        background: rgba(99, 102, 241, 0.08);
        border-left: 3px solid #6366f1;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 8px;
    }
    .method-badge {
        display: inline-block;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        font-weight: 500;
        margin: 2px;
    }
    .search-mode-tag {
        display: inline-block;
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""")

# ── Sidebar ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 Research Copilot")
    st.caption("Agent Tool-Call Reliability")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "📊 Overview",
            "📄 Paper Explorer",
            "🧬 Methods & Claims",
            "🧪 Benchmark Eval",
            "🕸️ Graph Viewer",
            "💬 Query Interface",
            "⚙️ Pipeline",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v0.1.0 • GraphRAG")

st.session_state.setdefault("active_corpus_topic", DEFAULT_TOPIC)

# ── Pages ─────────────────────────────────────────────────────────────


def page_overview():
    """Corpus overview with stats and topic summary."""
    st.markdown("# 📊 Corpus Overview")
    st.caption("Real-time statistics from your knowledge graph")

    stats = api_get("/api/stats")
    if not stats:
        st.info("No data yet. Run the pipeline from the ⚙️ Pipeline page to ingest papers.")
        return

    # Stats cards
    cols = st.columns(4)
    labels = ["Papers", "Methods", "Claims", "Authors"]
    keys = ["papers", "methods", "claims", "authors"]
    icons = ["📄", "🧬", "💡", "👤"]

    for col, label, key, icon in zip(cols, labels, keys, icons, strict=True):
        val = stats.get(key, 0)
        col.markdown(
            f"""<div class="stat-card">
                <div class="stat-number">{val}</div>
                <div class="stat-label">{icon} {label}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Topic summary
    st.markdown("### 🏷️ Topic Summary")
    topic = st.text_input(
        "Topic",
        value=get_active_topic(),
        label_visibility="collapsed",
    )
    st.session_state["active_corpus_topic"] = topic
    summary = api_get(f"/api/topics/{topic}")
    if summary:
        if summary.get("methods"):
            st.markdown("**Key Methods:**")
            badges = " ".join(f'<span class="method-badge">{m}</span>' for m in summary["methods"])
            st.markdown(badges, unsafe_allow_html=True)

        if summary.get("claims"):
            st.markdown("**Top Claims:**")
            for claim in summary["claims"][:8]:
                st.markdown(f"- {claim}")

        st.metric("Papers in corpus", summary.get("paper_count", 0))


def page_papers():
    """Paper explorer — browse ingested papers."""
    st.markdown("# 📄 Paper Explorer")
    st.caption("Browse papers in the knowledge graph")

    # Quick search via query
    search = st.text_input(
        "🔍 Search papers by keyword",
        placeholder="e.g. structured outputs, retry...",
    )

    if search:
        result = api_post(
            "/api/query",
            {
                "question": f"List papers about {search}",
                "search_mode": "entity",
            },
        )
        if result and result.get("evidence"):
            for item in result["evidence"]:
                with st.container(border=True):
                    st.markdown(f"**{item.get('title', 'Untitled')}**")
                    st.caption(item.get("citation", ""))
                    if item.get("score"):
                        st.progress(
                            min(item["score"], 1.0),
                            text=f"Relevance: {item['score']:.3f}",
                        )
        elif result:
            st.info(result.get("answer", "No results found."))
    else:
        st.info(
            "Enter a search term to find papers, or use the "
            "💬 Query Interface for more complex questions."
        )


def page_methods():
    """Methods and claims explorer."""
    st.markdown("# 🧬 Methods & Claims")
    st.caption("Explore extracted methods and claims")

    topic = get_active_topic()
    summary = api_get(f"/api/topics/{topic}")

    if not summary or not summary.get("methods"):
        st.info("No methods extracted yet. Run the pipeline from ⚙️ Pipeline to populate.")
        return

    # Methods
    st.markdown("### Methods")
    for method in summary["methods"]:
        with st.expander(f"🧬 {method}", expanded=False):
            result = api_post(
                "/api/query",
                {
                    "question": (f"What papers discuss {method} and what do they claim?"),
                    "search_mode": "entity",
                },
            )
            if result:
                st.markdown(result.get("answer", ""))
                if result.get("evidence"):
                    st.markdown("**Evidence:**")
                    for item in result["evidence"][:5]:
                        st.markdown(
                            f'<div class="evidence-card">📄 {item.get("title", "")}</div>',
                            unsafe_allow_html=True,
                        )

    # Claims
    if summary.get("claims"):
        st.markdown("### 💡 Top Claims")
        for i, claim in enumerate(summary["claims"][:10], 1):
            st.markdown(f"{i}. {claim}")


def page_query():
    """Query interface — ask questions about the corpus."""
    st.markdown("# 💬 Query Interface")
    st.caption("Ask questions — hybrid graph + vector retrieval")
    st.caption(f"Active topic context: {get_active_topic()}")

    # Search mode selector
    col1, col2 = st.columns([3, 1])
    with col1:
        question = st.text_area(
            "Ask a question about agent tool-call reliability",
            height=100,
            placeholder=("e.g. What retry strategies reduce tool-call errors most effectively?"),
        )
    with col2:
        mode = st.selectbox(
            "Search Mode",
            ["auto", "entity", "theme", "comparative"],
            help=(
                "Auto detects the best mode. "
                "Entity = vector search, "
                "Theme = date-bounded, "
                "Comparative = side-by-side methods."
            ),
        )
        start_date = st.date_input("From", value=None)
        end_date = st.date_input("To", value=None)

    if st.button("🔍 Search", type="primary", use_container_width=True):
        if not question:
            st.warning("Please enter a question.")
            return

        with st.spinner("Searching knowledge graph..."):
            payload = {
                "question": question,
                "search_mode": mode,
            }
            if start_date:
                payload["start_date"] = str(start_date)
            if end_date:
                payload["end_date"] = str(end_date)

            result = api_post("/api/query", payload)

        if not result:
            return

        render_query_result(result)

    # Briefing generator
    st.markdown("---")
    st.markdown("### 📋 Generate Briefing")
    brief_col1, brief_col2, brief_col3 = st.columns(3)
    with brief_col1:
        brief_topic = st.text_input(
            "Briefing topic",
            value=get_active_topic(),
        )
    with brief_col2:
        brief_start = st.text_input("Start date", value="2025-01-01")
    with brief_col3:
        brief_end = st.text_input("End date", value="2026-03-22")

    if st.button("📋 Generate Briefing"):
        with st.spinner("Generating briefing..."):
            result = api_post(
                "/api/briefings",
                {
                    "topic": brief_topic,
                    "start_date": brief_start,
                    "end_date": brief_end,
                },
            )
        if result:
            st.markdown("### Briefing")
            st.markdown(result.get("summary", ""))
            citations = result.get("citations", [])
            if citations:
                st.markdown("**Sources:**")
                for c in citations:
                    st.markdown(f"- {c}")


def page_benchmark():
    """Benchmark corpus and gold question runner."""
    st.markdown("# 🧪 Benchmark Evaluation")
    st.caption("Seeded papers and gold questions for stable demos and regression checks")

    manifest = api_get("/api/benchmark/papers")
    questions = api_get("/api/evaluation/questions")

    left, right = st.columns([1.1, 1.9])

    with left:
        st.markdown("### Seed Papers")
        if not manifest:
            st.info("No benchmark manifest found.")
        else:
            for paper in manifest:
                with st.expander(paper.get("title", "Untitled"), expanded=False):
                    st.caption(paper.get("semantic_scholar_id", ""))
                    st.markdown(paper.get("reason", ""))
                    expected_methods = paper.get("expected_methods", [])
                    if expected_methods:
                        badges = " ".join(
                            f'<span class="method-badge">{method}</span>'
                            for method in expected_methods
                        )
                        st.markdown(badges, unsafe_allow_html=True)

    with right:
        st.markdown("### Gold Questions")
        if not questions:
            st.info("No gold questions found.")
            return

        selected_id = st.selectbox(
            "Choose a benchmark question",
            options=[question["id"] for question in questions],
            format_func=lambda item: next(
                question["question"] for question in questions if question["id"] == item
            ),
        )
        selected = next(question for question in questions if question["id"] == selected_id)

        st.markdown("**Question**")
        st.markdown(selected["question"])
        st.caption(f"Expected search mode: {selected.get('search_mode', 'auto')}")

        expected_papers = selected.get("expected_paper_ids", [])
        if expected_papers:
            st.markdown("**Expected Paper IDs**")
            for paper_id in expected_papers:
                st.code(paper_id)

        expected_relationships = selected.get("expected_relationships", [])
        if expected_relationships:
            st.markdown("**Expected Relationships**")
            st.write(", ".join(expected_relationships))

        expected_tools = selected.get("expected_tools", [])
        if expected_tools:
            st.markdown("**Expected Tools**")
            st.write(", ".join(expected_tools))

        if st.button("▶️ Run Benchmark Question", use_container_width=True):
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


def page_pipeline():
    """Pipeline management — trigger ingestion."""
    st.markdown("# ⚙️ Pipeline Management")
    st.caption("Ingest, extract, embed, and load papers")

    # Current stats
    stats = api_get("/api/stats")
    if stats:
        cols = st.columns(4)
        for col, (k, v) in zip(cols, stats.items(), strict=False):
            col.metric(k.title(), v)
        st.divider()

    st.markdown("### Run Ingestion Pipeline")
    st.markdown(
        "Choose a topic, date window, corpus mode, and paper budget. "
        "The pipeline will fetch papers from Semantic Scholar and arXiv, "
        "extract methods and claims using GPT-4o-mini, generate embeddings, "
        "and load everything into Neo4j."
    )

    config_col1, config_col2 = st.columns(2)
    with config_col1:
        topic = st.text_input(
            "Topic",
            value=get_active_topic(),
            help="Use a narrow topic phrase for the cleanest graph.",
        )
        start_date = st.date_input("Start date", value=None, key="pipeline_start_date")
        target_papers = st.slider("Target papers", min_value=10, max_value=150, value=100, step=10)
    with config_col2:
        corpus_mode = st.selectbox(
            "Corpus mode",
            ["auto", "latest", "benchmark", "hybrid"],
            help=(
                "Auto uses the benchmark seed set only for the default topic. "
                "Custom topics fall back to latest to avoid unrelated benchmark papers."
            ),
        )
        end_date = st.date_input("End date", value=None, key="pipeline_end_date")

    st.info(
        "Benchmark and hybrid modes are intended for the default agent tool-call "
        "reliability corpus. For custom topics, use auto or latest."
    )
    st.warning("⚠️ Expect 10–15 minutes for 100 papers because of extraction and embedding calls.")

    if st.button(
        "🚀 Run Pipeline",
        type="primary",
        use_container_width=True,
    ):
        if not topic.strip():
            st.warning("Please enter a topic before running the pipeline.")
            return

        with st.spinner("Running pipeline... This may take a while."):
            payload = {
                "topic": topic.strip(),
                "target_papers": target_papers,
                "corpus_mode": corpus_mode,
            }
            if start_date:
                payload["start_date"] = str(start_date)
            if end_date:
                payload["end_date"] = str(end_date)
            result = api_post("/api/ingest/run", payload)

        if result:
            st.session_state["active_corpus_topic"] = topic.strip()
            st.success("✅ Pipeline completed!")
            st.json(result)

    # Health check
    st.divider()
    st.markdown("### System Health")
    health = api_get("/health")
    if health:
        st.success(f"API Status: {health.get('status', '?')}")
    else:
        st.error("API is not responding")


def page_graph():
    """Interactive graph visualization using pyvis."""
    st.markdown("# 🕸️ Knowledge Graph")
    st.caption("Interactive visualization of papers, methods, claims, and authors")

    col1, col2 = st.columns([1, 3])
    with col1:
        limit = st.slider("Papers to show", 5, 100, 25, step=5)
        show_authors = st.checkbox("Show authors", value=False)
        show_claims = st.checkbox("Show claims", value=False)
        show_methods = st.checkbox("Show methods", value=True)

    data = api_get(f"/api/graph?limit={limit}")
    if not data or not data.get("nodes"):
        st.info("No graph data yet. Run the pipeline first.")
        return

    # Color map for node types
    colors = {
        "paper": "#6366f1",
        "method": "#10b981",
        "claim": "#f59e0b",
        "author": "#ec4899",
    }
    sizes = {
        "paper": 20,
        "method": 30,
        "claim": 12,
        "author": 15,
    }
    shapes = {
        "paper": "dot",
        "method": "diamond",
        "claim": "triangle",
        "author": "star",
    }

    # Filter nodes based on checkboxes
    skip_types = set()
    if not show_authors:
        skip_types.add("author")
    if not show_claims:
        skip_types.add("claim")
    if not show_methods:
        skip_types.add("method")

    visible_ids = set()
    for node in data["nodes"]:
        if node["type"] not in skip_types:
            visible_ids.add(node["id"])

    # Build pyvis network
    net = Network(
        height="650px",
        width="100%",
        bgcolor="#0e1117",
        font_color="#e2e8f0",
    )
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.3,
        spring_length=120,
    )

    for node in data["nodes"]:
        if node["id"] not in visible_ids:
            continue
        ntype = node["type"]
        net.add_node(
            node["id"],
            label=node["label"],
            color=colors.get(ntype, "#888"),
            size=sizes.get(ntype, 15),
            shape=shapes.get(ntype, "dot"),
            title=(f"{ntype.upper()}: {node['label']}"),
        )

    for edge in data["edges"]:
        if edge["from"] in visible_ids and edge["to"] in visible_ids:
            net.add_edge(
                edge["from"],
                edge["to"],
                title=edge["label"],
                color="#475569",
                width=1,
            )

    # Render to temp HTML and display
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        net.save_graph(f.name)
        tmp_path = f.name

    with open(tmp_path) as fh:
        html = fh.read()

    with col2:
        st.components.v1.html(html, height=680, scrolling=False)

    # Legend
    legend_cols = st.columns(4)
    legend_items = [
        ("🔵 Paper", colors["paper"]),
        ("💎 Method", colors["method"]),
        ("🔺 Claim", colors["claim"]),
        ("⭐ Author", colors["author"]),
    ]
    for col, (label, color) in zip(legend_cols, legend_items, strict=True):
        col.markdown(
            f'<span style="color:{color}; font-weight:600">{label}</span>',
            unsafe_allow_html=True,
        )

    edge_count = sum(
        1 for e in data["edges"] if e["from"] in visible_ids and e["to"] in visible_ids
    )
    st.caption(f"Showing {len(visible_ids)} nodes, {edge_count} edges")


# ── Page Router ───────────────────────────────────────────────────────

if page == "📊 Overview":
    page_overview()
elif page == "📄 Paper Explorer":
    page_papers()
elif page == "🧬 Methods & Claims":
    page_methods()
elif page == "🧪 Benchmark Eval":
    page_benchmark()
elif page == "🕸️ Graph Viewer":
    page_graph()
elif page == "💬 Query Interface":
    page_query()
elif page == "⚙️ Pipeline":
    page_pipeline()
