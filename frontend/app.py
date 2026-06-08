import streamlit as st

st.set_page_config(
    page_title="Domain Knowledge Copilot",
    page_icon="D",
    layout="wide",
)

MOCK_CORPORA = [
    {
        "name": "Product Docs",
        "description": "Reference material for product usage, releases, and support notes.",
        "documents": 42,
        "last_updated": "Jun 4, 2026",
        "status": "Ready",
    },
    {
        "name": "Research Notes",
        "description": "Collected whitepapers, meeting notes, and domain research summaries.",
        "documents": 18,
        "last_updated": "May 29, 2026",
        "status": "Indexing paused",
    },
    {
        "name": "Policy Library",
        "description": "Internal policy references and operating procedure drafts.",
        "documents": 27,
        "last_updated": "Jun 1, 2026",
        "status": "Ready",
    },
]

MOCK_MESSAGES = [
    {
        "role": "assistant",
        "content": "Select a corpus and ask a question. This is a mock chat preview.",
    },
    {
        "role": "user",
        "content": "Which documents were updated most recently?",
    },
    {
        "role": "assistant",
        "content": "Mock response: the most recent update appears in the selected corpus summary.",
    },
]


def get_selected_corpus() -> dict[str, object]:
    return next(
        corpus
        for corpus in MOCK_CORPORA
        if corpus["name"] == st.session_state.selected_corpus
    )


def render_sidebar() -> str:
    st.sidebar.title("Domain Knowledge Copilot")

    st.sidebar.selectbox(
        "Corpus",
        options=[corpus["name"] for corpus in MOCK_CORPORA],
        key="selected_corpus",
    )

    st.sidebar.divider()

    return st.sidebar.radio(
        "Navigation",
        options=["Dashboard", "Corpus Chat", "Corpus Settings"],
        key="active_page",
    )


def render_corpus_card(corpus: dict[str, object]) -> None:
    with st.container(border=True):
        top_line, status_line = st.columns([3, 1])
        with top_line:
            st.subheader(str(corpus["name"]))
            st.write(str(corpus["description"]))
        with status_line:
            st.metric("Documents", corpus["documents"])
            st.caption(str(corpus["status"]))
        st.caption(f"Last updated: {corpus['last_updated']}")


def render_dashboard() -> None:
    selected_corpus = get_selected_corpus()

    st.title("Dashboard")
    st.caption("Mock overview for corpus activity and document readiness.")

    summary_cols = st.columns(3)
    summary_cols[0].metric("Corpora", len(MOCK_CORPORA))
    summary_cols[1].metric("Documents", sum(corpus["documents"] for corpus in MOCK_CORPORA))
    summary_cols[2].metric("Selected Corpus", selected_corpus["name"])

    st.divider()

    heading_col, action_col = st.columns([3, 1])
    with heading_col:
        st.header("Corpus List")
    with action_col:
        st.button("Upload Documents", use_container_width=True, disabled=True)
        st.caption("Placeholder only")

    for corpus in MOCK_CORPORA:
        render_corpus_card(corpus)


def render_chat() -> None:
    selected_corpus = get_selected_corpus()

    st.title("Corpus Chat")
    st.caption(f"Chat preview for {selected_corpus['name']}. Responses are mock data only.")

    with st.container(border=True):
        st.write(f"Active corpus: **{selected_corpus['name']}**")
        st.write(str(selected_corpus["description"]))

    for message in MOCK_MESSAGES:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.chat_input("Ask a question about this corpus", disabled=True)
    st.caption("Chat input is disabled in this UI-only prototype.")


def render_settings() -> None:
    selected_corpus = get_selected_corpus()

    st.title("Corpus Settings")
    st.caption(f"Settings placeholder for {selected_corpus['name']}.")

    with st.container(border=True):
        st.subheader("Corpus Details")
        st.text_input("Corpus name", value=str(selected_corpus["name"]), disabled=True)
        st.text_area(
            "Description",
            value=str(selected_corpus["description"]),
            disabled=True,
        )
        st.selectbox(
            "Visibility",
            options=["Private", "Team", "Organization"],
            index=1,
            disabled=True,
        )
        st.button("Save Settings", disabled=True)

    st.info("Settings controls are placeholders and are not connected to any service.")


if "selected_corpus" not in st.session_state:
    st.session_state.selected_corpus = MOCK_CORPORA[0]["name"]

page = render_sidebar()

if page == "Dashboard":
    render_dashboard()
elif page == "Corpus Chat":
    render_chat()
else:
    render_settings()
