import requests
import streamlit as st
import os

st.set_page_config(
    page_title="Domain Knowledge Copilot",
    page_icon="D",
    layout="wide",
)

API_BASE_URL = os.getenv(
    "BACKEND_URL",
    "http://localhost:8000"
)


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def auth_headers() -> dict[str, str]:
    token = st.session_state.get("access_token")
    if not token:
        return {}

    return {"Authorization": f"Bearer {token}"}


def register_user(email: str, display_name: str, password: str) -> dict[str, object]:
    response = requests.post(
        api_url("/auth/register"),
        json={
            "email": email,
            "display_name": display_name,
            "password": password,
        },
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def login_user(email: str, password: str) -> dict[str, object]:
    response = requests.post(
        api_url("/auth/login"),
        json={"email": email, "password": password},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def store_auth_session(auth_response: dict[str, object]) -> None:
    st.session_state.access_token = auth_response["access_token"]
    st.session_state.current_user = auth_response["user"]


def clear_auth_session() -> None:
    for key in (
        "access_token",
        "current_user",
        "selected_corpus_id",
        "pending_selected_corpus_id",
    ):
        st.session_state.pop(key, None)


def queue_selected_corpus(corpus_id: object) -> None:
    st.session_state.pending_selected_corpus_id = corpus_id


def apply_pending_selected_corpus(corpora: list[dict[str, object]]) -> None:
    if "pending_selected_corpus_id" in st.session_state:
        pending_id = st.session_state.pop("pending_selected_corpus_id")
        if any(str(corpus["id"]) == str(pending_id) for corpus in corpora):
            st.session_state.selected_corpus_id = pending_id
        else:
            st.session_state.pop("selected_corpus_id", None)

    if corpora and (
        "selected_corpus_id" not in st.session_state
        or not any(
            str(corpus["id"]) == str(st.session_state.selected_corpus_id)
            for corpus in corpora
        )
    ):
        st.session_state.selected_corpus_id = corpora[0]["id"]


def fetch_corpora() -> list[dict[str, object]]:
    response = requests.get(api_url("/corpora"), headers=auth_headers(), timeout=5)
    response.raise_for_status()
    return response.json()


def fetch_history() -> list[str]:
    response = requests.get(api_url("/history"), headers=auth_headers(), timeout=5)
    response.raise_for_status()
    return response.json()["items"]


def fetch_chat_history(corpus_id: int, limit: int = 20) -> list[dict[str, object]]:
    response = requests.get(
        api_url("/history"),
        params={"corpus_id": corpus_id, "limit": limit},
        headers=auth_headers(),
        timeout=5,
    )
    response.raise_for_status()
    return response.json()["messages"]


def create_corpus(name: str, description: str) -> dict[str, object]:
    response = requests.post(
        api_url("/corpora"),
        json={"name": name, "description": description},
        headers=auth_headers(),
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def delete_corpus(corpus_id: int) -> dict[str, object]:
    response = requests.delete(
        api_url(f"/corpora/{corpus_id}"),
        headers=auth_headers(),
        timeout=5,
    )
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
        headers=auth_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def answer_question(corpus_id: int, question: str) -> dict[str, object]:
    response = requests.post(
        api_url("/answer"),
        json={"corpus_id": corpus_id, "question": question, "limit": 5},
        headers=auth_headers(),
        timeout=60,
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
        status_code = error.response.status_code
        content_type = error.response.headers.get("content-type", "")
        if status_code >= 500 and "text/html" in content_type:
            st.caption(
                f"{status_code}: Backend service is unavailable. "
                "Check the backend deployment logs on Render."
            )
            return

        try:
            detail = error.response.json().get("detail", str(error))
        except ValueError:
            detail = (error.response.text or str(error)).strip()
            if len(detail) > 500:
                detail = f"{detail[:500]}..."
        st.caption(f"{status_code}: {detail}")
    else:
        st.caption(str(error))


def render_auth_page() -> None:
    st.title("Domain Knowledge Copilot")
    st.caption("Sign in to manage your corpora and chat history.")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login-form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            try:
                with st.spinner("Signing in..."):
                    auth_response = login_user(email.strip(), password)
                store_auth_session(auth_response)
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)

    with register_tab:
        with st.form("register-form"):
            display_name = st.text_input("Display name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input(
                "Password",
                type="password",
                key="register_password",
            )
            submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            try:
                with st.spinner("Creating account..."):
                    auth_response = register_user(
                        email=email.strip(),
                        display_name=display_name.strip(),
                        password=password,
                    )
                store_auth_session(auth_response)
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)


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
    current_user = st.session_state.get("current_user", {})
    if current_user:
        st.sidebar.caption(f"Signed in as {current_user.get('email')}")
        if st.sidebar.button("Logout", use_container_width=True):
            clear_auth_session()
            st.rerun()

    st.sidebar.divider()

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
        f"Ask questions about {selected_corpus['name']}."
    )

    with st.container(border=True):
        st.write(f"Active corpus: **{selected_corpus['name']}**")
        st.write(str(selected_corpus["description"]))
        st.caption(f"Documents: {selected_corpus['document_count']}")

    try:
        with st.spinner("Loading chat history..."):
            messages = fetch_chat_history(int(selected_corpus["id"]))
    except requests.RequestException as error:
        render_api_error(error)
        messages = []

    if not messages:
        messages = [
            {
                "role": "assistant",
                "content": "Ask a question about the selected corpus.",
                "citations": [],
                "created_at": None,
            }
        ]

    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("created_at"):
                st.caption(f"Sent: {message['created_at']}")
            if message["role"] == "assistant" and message.get("citations"):
                render_citations(message["citations"])

    question = st.chat_input("Ask a question about this corpus")
    if question:
        try:
            with st.spinner("Retrieving sources and generating answer..."):
                answer_question(int(selected_corpus["id"]), question)
            st.rerun()
        except requests.RequestException as error:
            render_api_error(error)


def render_citations(sources: list[dict[str, object]]) -> None:
    st.caption("Citations")
    for source in sources:
        citation = (
            f"{source['filename']} | page {source['page_number']} | "
            f"{source['chunk_reference']}"
        )
        st.markdown(f"- `{citation}`")

    with st.expander("View retrieved sources"):
        for source in sources:
            st.markdown(
                (
                    f"**{source['filename']}**  \n"
                    f"Page {source['page_number']} | "
                    f"Chunk `{source['chunk_reference']}`"
                )
            )
            st.write(source["text"])
            st.divider()


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
                    queue_selected_corpus(created["id"])
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
                        queue_selected_corpus(remaining[0]["id"])
                    else:
                        queue_selected_corpus(None)
                    st.success(f"Deleted corpus: {selected_corpus['name']}")
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)
        else:
            st.info("No corpus is selected.")

    st.info("Settings controls are placeholders. Corpus create/delete calls the backend.")


if "access_token" not in st.session_state:
    render_auth_page()
    st.stop()

try:
    corpora, history = load_backend_data()
except requests.RequestException as error:
    st.title("Domain Knowledge Copilot")
    if isinstance(error, requests.HTTPError) and error.response is not None:
        if error.response.status_code == 401:
            clear_auth_session()
            st.warning("Your session expired. Please sign in again.")
            render_auth_page()
            st.stop()
    render_api_error(error)
    st.stop()

apply_pending_selected_corpus(corpora)

page = render_sidebar(corpora)

if page == "Dashboard":
    render_dashboard(corpora, history)
elif page == "Corpus Chat":
    render_chat(corpora)
else:
    render_settings(corpora)
