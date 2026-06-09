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


def delete_corpus(corpus_id: int) -> dict[str, object]:
    response = requests.delete(api_url(f"/corpora/{corpus_id}"), timeout=5)
    response.raise_for_status()
    return response.json()


def upload_pdf(corpus_id: int, uploaded_file: object) -> dict[str, object]:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/pdf",
        )
    }
    response = requests.post(
        api_url(f"/corpora/{corpus_id}/upload"),
        files=files,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def load_backend_data() -> tuple[list[dict[str, object]], list[str]]:
    with st.spinner("Loading backend data..."):
        return fetch_corpora(), fetch_history()


def render_api_error(error: requests.RequestException) -> None:
    st.error("Backend request failed.")
    st.caption(f"Backend URL: {API_BASE_URL}")

    if isinstance(error, requests.HTTPError) and error.response is not None:
        try:
            detail = error.response.json().get("detail", str(error))
        except ValueError:
            detail = error.response.text or str(error)
        st.caption(f"{error.response.status_code}: {detail}")
    else:
        st.caption(str(error))


def get_selected_corpus(corpora: list[dict[str, object]]) -> dict[str, object]:
    if not corpora:
        return {}

    selected_id = st.session_state.get("selected_corpus_id")
    matching_corpus = next(
        (corpus for corpus in corpora if str(corpus["id"]) == str(selected_id)),
        None,
    )
    return matching_corpus or corpora[0]


def render_sidebar(corpora: list[dict[str, object]]) -> str:
    st.sidebar.title("Domain Knowledge Copilot")
    st.sidebar.caption(f"API: {API_BASE_URL}")

    if corpora:
        st.sidebar.selectbox(
            "Corpus",
            options=[corpus["id"] for corpus in corpora],
            format_func=lambda corpus_id: next(
                corpus["name"] for corpus in corpora if corpus["id"] == corpus_id
            ),
            key="selected_corpus_id",
        )
    else:
        st.sidebar.info("No corpora yet.")

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
    st.caption("Backend-connected overview using SQLite-backed corpus data.")

    upload_message = st.session_state.pop("upload_message", None)
    if upload_message:
        st.success(upload_message)

    summary_cols = st.columns(3)
    summary_cols[0].metric("Corpora", len(corpora))
    summary_cols[1].metric(
        "Documents",
        sum(int(corpus["document_count"]) for corpus in corpora),
    )
    summary_cols[2].metric("Selected Corpus", selected_corpus.get("name", "None"))

    st.divider()

    heading_col, action_col = st.columns([3, 1])
    with heading_col:
        st.header("Corpus List")
    with action_col:
        if selected_corpus:
            uploaded_pdf = st.file_uploader(
                "Upload PDF",
                type=["pdf"],
                accept_multiple_files=False,
            )
            if st.button(
                "Upload",
                use_container_width=True,
                disabled=uploaded_pdf is None,
            ):
                try:
                    with st.spinner("Uploading PDF..."):
                        document = upload_pdf(int(selected_corpus["id"]), uploaded_pdf)
                    st.session_state.upload_message = (
                        f"Uploaded {document['filename']} to {selected_corpus['name']} "
                        f"and extracted {document['page_count']} page(s)."
                    )
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)
        else:
            st.button("Upload", use_container_width=True, disabled=True)
            st.caption("Create a corpus first")

    if corpora:
        for corpus in corpora:
            render_corpus_card(corpus)
    else:
        st.info("No corpora found. Create one from Corpus Settings.")

    st.divider()
    st.header("Recent History")
    for item in history:
        st.write(f"- {item}")


def render_chat(corpora: list[dict[str, object]]) -> None:
    selected_corpus = get_selected_corpus(corpora)

    st.title("Corpus Chat")

    if not selected_corpus:
        st.info("Create a corpus before using the chat preview.")
        return

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
    if selected_corpus:
        st.caption(f"Settings placeholder for {selected_corpus['name']}.")
    else:
        st.caption("Create a corpus to populate the database.")

    with st.container(border=True):
        st.subheader("Corpus Details")
        st.text_input(
            "Corpus name",
            value=str(selected_corpus.get("name", "")),
            disabled=True,
        )
        st.text_area(
            "Description",
            value=str(selected_corpus.get("description", "")),
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
        st.caption("Creates a SQLite-backed corpus through the FastAPI backend.")

        with st.form("create-corpus-form"):
            name = st.text_input("Name", placeholder="Example corpus")
            description = st.text_area("Description", placeholder="Short description")
            submitted = st.form_submit_button("Create Corpus")

        if submitted:
            if not name.strip():
                st.warning("Enter a corpus name before submitting.")
            else:
                try:
                    with st.spinner("Creating corpus..."):
                        created = create_corpus(name.strip(), description.strip())
                    st.session_state.selected_corpus_id = created["id"]
                    st.success(f"Created corpus: {created['name']}")
                    st.json(created)
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)

    with st.container(border=True):
        st.subheader("Delete Corpus")
        if selected_corpus:
            st.caption(f"Selected corpus ID: {selected_corpus['id']}")
            if st.button("Delete Selected Corpus", type="secondary"):
                try:
                    with st.spinner("Deleting corpus..."):
                        delete_corpus(int(selected_corpus["id"]))
                    remaining = [
                        corpus for corpus in corpora if corpus["id"] != selected_corpus["id"]
                    ]
                    if remaining:
                        st.session_state.selected_corpus_id = remaining[0]["id"]
                    else:
                        st.session_state.pop("selected_corpus_id", None)
                    st.success(f"Deleted corpus: {selected_corpus['name']}")
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)
        else:
            st.info("No corpus is selected.")

    st.info("Settings controls are placeholders. Corpus create/delete calls the backend.")


try:
    corpora, history = load_backend_data()
except requests.RequestException as error:
    st.title("Domain Knowledge Copilot")
    render_api_error(error)
    st.stop()

if corpora and (
    "selected_corpus_id" not in st.session_state
    or not any(str(corpus["id"]) == str(st.session_state.selected_corpus_id) for corpus in corpora)
):
    st.session_state.selected_corpus_id = corpora[0]["id"]

page = render_sidebar(corpora)

if page == "Dashboard":
    render_dashboard(corpora, history)
elif page == "Corpus Chat":
    render_chat(corpora)
else:
    render_settings(corpora)
