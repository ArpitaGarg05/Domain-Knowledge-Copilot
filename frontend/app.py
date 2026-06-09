import requests
import streamlit as st

st.set_page_config(
    page_title="Domain Knowledge Copilot",
    page_icon="D",
    layout="wide",
)

API_BASE_URL = "http://localhost:8000"

MOCK_MESSAGES = [
    {
        "role": "assistant",
        "content": "Select a corpus and ask a question. Chat responses are still mock-only.",
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


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def fetch_corpora() -> list[dict[str, object]]:
    response = requests.get(api_url("/corpora"), timeout=5)
    response.raise_for_status()
    return response.json()


def fetch_history() -> list[str]:
    response = requests.get(api_url("/history"), timeout=5)
    response.raise_for_status()
    return response.json()["items"]


def create_corpus(name: str, description: str) -> dict[str, object]:
    response = requests.post(
        api_url("/corpora"),
        json={"name": name, "description": description},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def load_backend_data() -> tuple[list[dict[str, object]], list[str]]:
    with st.spinner("Loading backend data..."):
        return fetch_corpora(), fetch_history()


def render_api_error(error: requests.RequestException) -> None:
    st.error("Could not reach the FastAPI backend.")
    st.caption(f"Backend URL: {API_BASE_URL}")
    st.caption(str(error))


def get_selected_corpus(corpora: list[dict[str, object]]) -> dict[str, object]:
    selected_id = st.session_state.get("selected_corpus_id")
    matching_corpus = next(
        (corpus for corpus in corpora if corpus["id"] == selected_id),
        None,
    )
    return matching_corpus or corpora[0]


def render_sidebar(corpora: list[dict[str, object]]) -> str:
    st.sidebar.title("Domain Knowledge Copilot")
    st.sidebar.caption(f"API: {API_BASE_URL}")

    st.sidebar.selectbox(
        "Corpus",
        options=[corpus["id"] for corpus in corpora],
        format_func=lambda corpus_id: next(
            corpus["name"] for corpus in corpora if corpus["id"] == corpus_id
        ),
        key="selected_corpus_id",
    )

    st.sidebar.divider()

    return st.sidebar.radio(
        "Navigation",
        options=["Dashboard", "Corpus Chat", "Corpus Settings"],
        key="active_page",
    )


def render_corpus_card(corpus: dict[str, object]) -> None:
    with st.container(border=True):
        top_line, metric_line = st.columns([3, 1])
        with top_line:
            st.subheader(str(corpus["name"]))
            st.write(str(corpus["description"]))
        with metric_line:
            st.metric("Documents", corpus["document_count"])
        st.caption(f"Corpus ID: {corpus['id']}")


def render_dashboard(corpora: list[dict[str, object]], history: list[str]) -> None:
    selected_corpus = get_selected_corpus(corpora)

    st.title("Dashboard")
    st.caption("Backend-connected overview using dummy FastAPI responses.")

    summary_cols = st.columns(3)
    summary_cols[0].metric("Corpora", len(corpora))
    summary_cols[1].metric(
        "Documents",
        sum(int(corpus["document_count"]) for corpus in corpora),
    )
    summary_cols[2].metric("Selected Corpus", selected_corpus["name"])

    st.divider()

    heading_col, action_col = st.columns([3, 1])
    with heading_col:
        st.header("Corpus List")
    with action_col:
        st.button("Upload Documents", use_container_width=True, disabled=True)
        st.caption("Placeholder only")

    for corpus in corpora:
        render_corpus_card(corpus)

    st.divider()
    st.header("Recent History")
    for item in history:
        st.write(f"- {item}")


def render_chat(corpora: list[dict[str, object]]) -> None:
    selected_corpus = get_selected_corpus(corpora)

    st.title("Corpus Chat")
    st.caption(
        f"Chat preview for {selected_corpus['name']}. Corpus metadata comes from FastAPI."
    )

    with st.container(border=True):
        st.write(f"Active corpus: **{selected_corpus['name']}**")
        st.write(str(selected_corpus["description"]))
        st.caption(f"Documents: {selected_corpus['document_count']}")

    for message in MOCK_MESSAGES:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.chat_input("Ask a question about this corpus", disabled=True)
    st.caption("Chat input is disabled in this UI-only prototype.")


def render_settings(corpora: list[dict[str, object]]) -> None:
    selected_corpus = get_selected_corpus(corpora)

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

    with st.container(border=True):
        st.subheader("Create Corpus")
        st.caption("This calls the dummy FastAPI POST route and does not persist data.")

        with st.form("create-corpus-form"):
            name = st.text_input("Name", placeholder="Example corpus")
            description = st.text_area("Description", placeholder="Short description")
            submitted = st.form_submit_button("Create Dummy Corpus")

        if submitted:
            if not name.strip():
                st.warning("Enter a corpus name before submitting.")
            else:
                try:
                    with st.spinner("Sending dummy corpus request..."):
                        created = create_corpus(name.strip(), description.strip())
                    st.success(f"Created dummy corpus: {created['name']}")
                    st.json(created)
                except requests.RequestException as error:
                    render_api_error(error)

    st.info("Settings controls are placeholders and are not connected to any service.")


try:
    corpora, history = load_backend_data()
except requests.RequestException as error:
    st.title("Domain Knowledge Copilot")
    render_api_error(error)
    st.stop()

if not corpora:
    st.title("Domain Knowledge Copilot")
    st.warning("The backend returned no corpora.")
    st.stop()

if "selected_corpus_id" not in st.session_state:
    st.session_state.selected_corpus_id = str(corpora[0]["id"])

page = render_sidebar(corpora)

if page == "Dashboard":
    render_dashboard(corpora, history)
elif page == "Corpus Chat":
    render_chat(corpora)
else:
    render_settings(corpora)
