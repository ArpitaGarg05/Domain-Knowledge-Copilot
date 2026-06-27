import os
import time
from datetime import datetime, timedelta
from html import escape
from typing import Any, Optional

import extra_streamlit_components as stx
import requests
import streamlit as st

from styles import (
    empty_state,
    format_bytes,
    inject_styles,
    metric_grid,
    page_header,
    section_title,
    status_badge,
)


st.set_page_config(
    page_title="Knowledge Co-Pilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_styles()

API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
AUTH_COOKIE_NAME = "dkc_access_token"
AUTH_LOGGED_OUT_VALUE = "__logged_out__"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "").lower() in {
    "1",
    "true",
    "yes",
}
PAGES = [
    "Corpus Dashboard",
    "Corpus Detail",
    "Corpus Chat",
    "Compare Documents",
    "Chat History",
    "Settings",
]
st.session_state.setdefault("comfortable_density", True)
st.session_state.setdefault("reduce_motion", False)
st.session_state.setdefault("default_workspace", "Corpus Dashboard")
st.session_state.setdefault("auth_tab", "Login")
cookie_manager = stx.CookieManager(key="auth_cookie_manager")


def inject_preference_styles() -> None:
    rules: list[str] = []
    if st.session_state.get("reduce_motion", False):
        rules.append(
            "*,*::before,*::after{animation:none!important;"
            "transition:none!important;scroll-behavior:auto!important}"
        )
    if not st.session_state.get("comfortable_density", True):
        rules.append(
            ".main .block-container{padding-top:1rem!important}"
            ".dk-metric{min-height:92px!important;padding:.75rem!important}"
            "[data-testid=stChatMessage]{padding:.75rem .9rem!important}"
        )
    if rules:
        st.markdown(f"<style>{''.join(rules)}</style>", unsafe_allow_html=True)


inject_preference_styles()


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def auth_headers() -> dict[str, str]:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def request_json(
    method: str,
    path: str,
    *,
    timeout: int = 10,
    **kwargs: Any,
) -> Any:
    headers = dict(kwargs.pop("headers", {}))
    headers.update(auth_headers())
    response = requests.request(
        method,
        api_url(path),
        headers=headers,
        timeout=timeout,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def register_user(email: str, display_name: str, password: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
        timeout=8,
    )


def login_user(email: str, password: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/auth/login",
        json={"email": email, "password": password},
        timeout=8,
    )


def fetch_current_user() -> dict[str, Any]:
    return request_json("GET", "/auth/me")


def update_profile(display_name: str) -> dict[str, Any]:
    return request_json(
        "PATCH",
        "/auth/profile",
        json={"display_name": display_name},
    )


def fetch_corpora() -> list[dict[str, Any]]:
    return request_json("GET", "/corpora")


def fetch_history(
    corpus_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if corpus_id is not None:
        params["corpus_id"] = corpus_id
    if conversation_id is not None:
        params["conversation_id"] = conversation_id
    return request_json("GET", "/history", params=params)["messages"]


def fetch_corpus_documents(corpus_id: int) -> dict[str, Any]:
    return request_json("GET", f"/corpora/{corpus_id}/documents")


def create_corpus(name: str, description: str) -> dict[str, Any]:
    return request_json(
        "POST",
        "/corpora",
        json={"name": name, "description": description},
    )


def delete_corpus(corpus_id: int) -> dict[str, Any]:
    return request_json("DELETE", f"/corpora/{corpus_id}")


def upload_pdf(corpus_id: int, uploaded_file: Any) -> dict[str, Any]:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/pdf",
        )
    }
    return request_json(
        "POST",
        f"/corpora/{corpus_id}/upload",
        files=files,
        timeout=180,
    )


def answer_question(
    corpus_id: int,
    question: str,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    return request_json(
        "POST",
        "/answer",
        json={
            "corpus_id": corpus_id,
            "question": question,
            "limit": 5,
            "conversation_id": conversation_id,
        },
        timeout=60,
    )


def create_comparison(document_ids: list[int]) -> dict[str, Any]:
    return request_json(
        "POST",
        "/comparisons",
        json={"document_ids": document_ids},
        timeout=180,
    )


def fetch_comparisons() -> list[dict[str, Any]]:
    return request_json("GET", "/comparisons")["comparisons"]


def fetch_comparison(comparison_id: int) -> dict[str, Any]:
    return request_json("GET", f"/comparisons/{comparison_id}")


def ask_comparison_question(comparison_id: int, question: str) -> dict[str, Any]:
    return request_json(
        "POST",
        f"/comparisons/{comparison_id}/ask",
        json={"question": question},
        timeout=90,
    )


def store_auth_session(auth_response: dict[str, Any]) -> None:
    st.session_state.access_token = auth_response["access_token"]
    st.session_state.current_user = auth_response["user"]
    st.session_state.logout_in_progress = False
    st.session_state.auth_cookie_action = "set"
    st.session_state.auth_validation_complete = True
    st.session_state.pending_page = st.session_state.get(
        "default_workspace",
        "Corpus Dashboard",
    )


def clear_auth_session() -> None:
    preserved = {
        "reduce_motion": st.session_state.get("reduce_motion", False),
        "comfortable_density": st.session_state.get("comfortable_density", True),
        "default_workspace": st.session_state.get(
            "default_workspace",
            "Corpus Dashboard",
        ),
        "auth_cookie_action": "delete",
        "auth_validation_complete": True,
        "logout_in_progress": True,
    }
    st.session_state.clear()
    st.session_state.update(preserved)


def process_auth_cookie_action() -> None:
    action = st.session_state.pop("auth_cookie_action", None)
    if action == "set":
        token = st.session_state.get("access_token")
        if token:
            cookie_manager.set(
                AUTH_COOKIE_NAME,
                token,
                key="persist_auth_cookie",
                expires_at=datetime.now()
                + timedelta(seconds=AUTH_COOKIE_MAX_AGE_SECONDS),
                max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
                secure=AUTH_COOKIE_SECURE,
                same_site="strict",
            )
    elif action == "delete":
        cookie_manager.set(
            AUTH_COOKIE_NAME,
            AUTH_LOGGED_OUT_VALUE,
            key="clear_auth_cookie",
            expires_at=datetime.now()
            + timedelta(seconds=AUTH_COOKIE_MAX_AGE_SECONDS),
            max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
            secure=AUTH_COOKIE_SECURE,
            same_site="strict",
        )


def restore_auth_session() -> bool:
    if st.session_state.get("logout_in_progress"):
        if cookie_manager.get(AUTH_COOKIE_NAME) == AUTH_LOGGED_OUT_VALUE:
            st.session_state.logout_in_progress = False
        return False

    if st.session_state.get("access_token"):
        if st.session_state.get("current_user"):
            return True
        try:
            st.session_state.current_user = fetch_current_user()
            return True
        except requests.RequestException:
            clear_auth_session()
            process_auth_cookie_action()
            return False

    persisted_token = cookie_manager.get(AUTH_COOKIE_NAME)
    if not persisted_token or persisted_token == AUTH_LOGGED_OUT_VALUE:
        return False

    st.session_state.access_token = persisted_token
    try:
        st.session_state.current_user = fetch_current_user()
        st.session_state.pending_page = "Corpus Dashboard"
        return True
    except requests.RequestException:
        clear_auth_session()
        process_auth_cookie_action()
        return False


def render_auth_loading() -> None:
    st.markdown(
        """
        <div class="dk-auth-loading">
          <div class="dk-auth-loading__mark">◇</div>
          <h2>Restoring secure session</h2>
          <p>Validating identity · Hydrating workspace</p>
          <div class="dk-auth-loading__bar"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_authenticated_user() -> Optional[bool]:
    process_auth_cookie_action()
    if st.session_state.get("access_token"):
        st.session_state.auth_validation_complete = True
        return restore_auth_session()

    persisted_token = cookie_manager.get(AUTH_COOKIE_NAME)
    if persisted_token and persisted_token != AUTH_LOGGED_OUT_VALUE:
        st.session_state.auth_validation_complete = True
        return restore_auth_session()

    attempts = int(st.session_state.get("auth_validation_attempts", 0))
    if not st.session_state.get("auth_validation_complete") and attempts < 2:
        st.session_state.auth_validation_attempts = attempts + 1
        render_auth_loading()
        time.sleep(0.4)
        st.rerun()

    st.session_state.auth_validation_complete = True
    return False


def queue_navigation(
    page: str,
    corpus_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
) -> None:
    st.session_state.pending_page = page
    if corpus_id is not None:
        st.session_state.pending_selected_corpus_id = corpus_id
    if conversation_id is not None:
        st.session_state.pending_conversation_id = conversation_id


def apply_pending_navigation(corpora: list[dict[str, Any]]) -> None:
    if "pending_page" in st.session_state:
        st.session_state.active_page = st.session_state.pop("pending_page")

    if "pending_selected_corpus_id" in st.session_state:
        pending = st.session_state.pop("pending_selected_corpus_id")
        if any(str(corpus["id"]) == str(pending) for corpus in corpora):
            st.session_state.selected_corpus_id = pending

    if "pending_conversation_id" in st.session_state:
        st.session_state.active_conversation_id = st.session_state.pop(
            "pending_conversation_id"
        )

    valid_ids = {str(corpus["id"]) for corpus in corpora}
    current = st.session_state.get("selected_corpus_id")
    if corpora and str(current) not in valid_ids:
        st.session_state.selected_corpus_id = corpora[0]["id"]
    if not corpora:
        st.session_state.pop("selected_corpus_id", None)


def selected_corpus(corpora: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    selected_id = st.session_state.get("selected_corpus_id")
    return next(
        (
            corpus
            for corpus in corpora
            if str(corpus["id"]) == str(selected_id)
        ),
        corpora[0] if corpora else None,
    )


def render_api_error(error: requests.RequestException) -> None:
    detail = str(error)
    if isinstance(error, requests.Timeout):
        detail = "The service took too long to respond."
    elif isinstance(error, requests.HTTPError) and error.response is not None:
        try:
            detail = error.response.json().get("detail", detail)
        except ValueError:
            detail = error.response.text.strip() or detail
    st.error(detail)


def set_auth_tab(tab: str) -> None:
    st.session_state.auth_tab = tab


def render_auth_page() -> None:
    st.markdown(
        """
        <div class="dk-auth-shell">
          <h1>Knowledge Co-Pilot</h1>
          <p>● &nbsp; Precision Intelligence Secured</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.05, 1])
    with center:
        with st.container(key="auth_card"):
            st.markdown('<div class="dk-auth-marker"></div>', unsafe_allow_html=True)
            auth_tab = st.segmented_control(
                "Authentication",
                ["Login", "Sign-Up"],
                key="auth_tab",
                label_visibility="collapsed",
                width="stretch",
            )

            if auth_tab == "Login":
                st.caption("Authenticate to enter the research environment.")
                with st.form("login-form"):
                    email = st.text_input(
                        "Email",
                        placeholder="name@corporation.com",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="••••••••••••",
                    )
                    submitted = st.form_submit_button(
                        "Login",
                        type="primary",
                        use_container_width=True,
                    )
                if submitted:
                    try:
                        with st.spinner("Establishing secure session..."):
                            auth_response = login_user(email.strip(), password)
                        store_auth_session(auth_response)
                        st.rerun()
                    except requests.RequestException as error:
                        render_api_error(error)
                st.button(
                    "Don't have an account? Register",
                    key="auth_show_signup",
                    use_container_width=True,
                    on_click=set_auth_tab,
                    args=("Sign-Up",),
                )

            else:
                st.caption("Initialize your secure research environment.")
                with st.form("register-form"):
                    display_name = st.text_input(
                        "User name",
                        placeholder="Full name",
                    )
                    email = st.text_input(
                        "User email",
                        placeholder="name@organization.ai",
                        key="register_email",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="Minimum 8 characters",
                        key="register_password",
                    )
                    submitted = st.form_submit_button(
                        "Register",
                        type="primary",
                        use_container_width=True,
                    )
                if submitted:
                    try:
                        with st.spinner("Provisioning account..."):
                            auth_response = register_user(
                                email.strip(),
                                display_name.strip(),
                                password,
                            )
                        store_auth_session(auth_response)
                        st.rerun()
                    except requests.RequestException as error:
                        render_api_error(error)
                st.button(
                    "Already have an account? Login",
                    key="auth_show_login",
                    use_container_width=True,
                    on_click=set_auth_tab,
                    args=("Login",),
                )

    st.markdown(
        """
        <div class="dk-system-strip">
          <span><b>● Server core active</b></span>
          <span>Encrypted transport · Session isolation</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def handle_workspace_change() -> None:
    if st.session_state.get("active_page") == "Corpus Chat":
        st.session_state.pop("active_conversation_id", None)


def handle_corpus_change() -> None:
    st.session_state.pop("active_conversation_id", None)


def render_sidebar(corpora: list[dict[str, Any]]) -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="dk-brand">
              <div class="dk-brand__title">Knowledge<br>Co-Pilot</div>
              <div class="dk-brand__sub">Precision Intelligence</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("＋  New Corpus", type="primary", use_container_width=True):
            queue_navigation("Corpus Dashboard")
            st.session_state.show_create_corpus = True
            st.rerun()

        st.markdown(
            '<div class="dk-sidebar-label">Workspace</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Workspace",
            PAGES,
            key="active_page",
            label_visibility="collapsed",
            on_change=handle_workspace_change,
        )

        if corpora:
            st.markdown(
                '<div class="dk-sidebar-label">Active corpus</div>',
                unsafe_allow_html=True,
            )
            st.selectbox(
                "Active corpus",
                options=[corpus["id"] for corpus in corpora],
                format_func=lambda corpus_id: next(
                    corpus["name"]
                    for corpus in corpora
                    if corpus["id"] == corpus_id
                ),
                key="selected_corpus_id",
                label_visibility="collapsed",
                on_change=handle_corpus_change,
            )

        user = st.session_state.get("current_user", {})
        initial = escape(str(user.get("display_name", "U"))[:1].upper())
        st.markdown(
            f"""
            <div class="dk-user">
              <div class="dk-avatar">{initial}</div>
              <div>
                <strong>{escape(str(user.get("display_name", "Operator")))}</strong>
                <span>{escape(str(user.get("email", "")))}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("End Session", use_container_width=True):
            clear_auth_session()
            st.rerun()
    return page


def render_corpus_card(corpus: dict[str, Any], index: int) -> None:
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="dk-corpus-card">
              <div class="dk-corpus-card__top">
                <span class="dk-chip">Corpus {int(corpus["id"]):02d}</span>
                {status_badge("Active")}
              </div>
              <h3>{escape(str(corpus["name"]))}</h3>
              <p>{escape(str(corpus.get("description") or "No description supplied."))}</p>
              <div class="dk-corpus-card__footer">
                <span>{int(corpus["document_count"]):02d} documents</span>
                <span>Private workspace</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Open Corpus  →",
            key=f"open-corpus-{index}",
            use_container_width=True,
            on_click=queue_navigation,
            args=("Corpus Detail", int(corpus["id"])),
        )


def render_create_corpus(form_key: str) -> None:
    with st.container(border=True):
        st.markdown('<div class="dk-label">Provision corpus</div>', unsafe_allow_html=True)
        st.subheader("Create a knowledge workspace")
        with st.form(form_key, clear_on_submit=True):
            name = st.text_input("Corpus name", placeholder="Research intelligence")
            description = st.text_area(
                "Description",
                placeholder="What domain knowledge will this corpus contain?",
            )
            submitted = st.form_submit_button(
                "Create Corpus",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            if not name.strip():
                st.warning("Enter a corpus name.")
            else:
                try:
                    created = create_corpus(name.strip(), description.strip())
                    st.session_state.show_create_corpus = False
                    queue_navigation("Corpus Detail", int(created["id"]))
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)


def render_dashboard(corpora: list[dict[str, Any]]) -> None:
    page_header(
        "Knowledge workspace",
        "Corpus Dashboard",
        "Organize private document collections and monitor the intelligence layer.",
    )
    metric_grid(
        [
            ("Active corpora", str(len(corpora)), "Private research spaces", "primary"),
            (
                "Indexed documents",
                str(sum(int(c["document_count"]) for c in corpora)),
                "Across all corpora",
                "success",
            ),
        ]
    )

    if st.session_state.get("show_create_corpus", False) or not corpora:
        render_create_corpus("create-corpus-primary-form")

    section_title("Knowledge corpora", f"{len(corpora)} workspaces")
    if not corpora:
        empty_state(
            "No corpora provisioned",
            "Create a corpus to begin indexing domain documents.",
            "＋",
        )
        return

    columns = st.columns(2)
    for index, corpus in enumerate(corpora):
        with columns[index % 2]:
            render_corpus_card(corpus, index)

    with st.expander("Create another corpus"):
        render_create_corpus("create-corpus-secondary-form")


def document_row(document: dict[str, Any]) -> None:
    uploaded = format_datetime(document.get("uploaded_at"), "%d %b %Y · %H:%M")
    status = str(document.get("indexing_status", "indexed"))
    st.markdown(
        f"""
        <div class="dk-document">
          <div class="dk-document__name">
            <div class="dk-file-icon">PDF</div>
            <div>
              <strong title="{escape(str(document["filename"]))}">{escape(str(document["filename"]))}</strong>
              <small>Uploaded {escape(uploaded)}</small>
            </div>
          </div>
          <div class="dk-doc-stat"><label>Pages</label><span>{int(document["page_count"])}</span></div>
          <div class="dk-doc-stat"><label>Chunks</label><span>{int(document["chunk_count"])}</span></div>
          <div class="dk-doc-stat"><label>Storage</label><span>{escape(format_bytes(int(document["file_size_bytes"])))}</span></div>
          <div>{status_badge(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_corpus_detail(corpora: list[dict[str, Any]]) -> None:
    corpus = selected_corpus(corpora)
    if corpus is None:
        page_header("Corpus control", "Corpus Detail", "Manage an indexed knowledge workspace.")
        empty_state("No active corpus", "Create a corpus from the dashboard first.")
        return

    try:
        detail = fetch_corpus_documents(int(corpus["id"]))
    except requests.RequestException as error:
        render_api_error(error)
        return

    page_header(
        f"Corpus {int(corpus['id']):02d} / Active",
        str(corpus["name"]),
        str(corpus.get("description") or "Private domain knowledge corpus."),
    )
    metrics = [
        ("Documents", str(detail["total_documents"]), "Uploaded source files", "primary"),
        ("Pages", f'{int(detail["total_pages"]):,}', "Extracted and searchable", None),
        ("Vector chunks", f'{int(detail["total_embeddings"]):,}', "Available for retrieval", "success"),
        ("Storage", format_bytes(int(detail["total_storage_bytes"])), "Uploaded PDF footprint", None),
    ]
    metric_grid(metrics)

    inventory, action = st.columns([1.65, 0.85], gap="large")
    with inventory:
        section_title("Document inventory", f'{detail["total_documents"]} indexed')
        if detail["documents"]:
            for document in detail["documents"]:
                document_row(document)
        else:
            empty_state(
                "Corpus is waiting for source material",
                "Upload a text-based PDF to initialize retrieval.",
                "PDF",
            )

    with action:
        section_title("Data ingestion", "PDF pipeline")
        with st.container(border=True):
            st.markdown(
                """
                <div class="dk-label">Upload action area</div>
                <h3 style="margin:.45rem 0 .25rem">Index new material</h3>
                <p style="font-size:13px;margin:0 0 .8rem">
                  Text is extracted page-by-page, chunked, embedded, and added
                  to this corpus's private vector collection.
                </p>
                """,
                unsafe_allow_html=True,
            )
            uploaded_pdf = st.file_uploader(
                "Source document",
                type=["pdf"],
                accept_multiple_files=False,
                key=f"detail-upload-{corpus['id']}",
            )
            if st.button(
                "Upload & Index",
                type="primary",
                use_container_width=True,
                disabled=uploaded_pdf is None,
            ):
                try:
                    with st.spinner("Extracting, chunking, and vectorizing..."):
                        document = upload_pdf(int(corpus["id"]), uploaded_pdf)
                    st.success(
                        f"{document['filename']} indexed into "
                        f"{document['chunk_count']} chunks."
                    )
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="dk-label">Index health</div>
                <h3 style="margin:.45rem 0 .75rem">Retrieval readiness</h3>
                <div style="display:grid;gap:.7rem">
                  <div style="display:flex;justify-content:space-between">
                    <span style="color:#918fa1;font-size:12px">Vector store</span>
                    {status_badge("Connected")}
                  </div>
                  <div style="display:flex;justify-content:space-between">
                    <span style="color:#918fa1;font-size:12px">Embeddings</span>
                    <code style="color:#c3c0ff">{int(detail["total_embeddings"]):,}</code>
                  </div>
                  <div style="display:flex;justify-content:space-between">
                    <span style="color:#918fa1;font-size:12px">Isolation</span>
                    <code style="color:#d4e4fa">corpus_{int(corpus["id"])}</code>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_citations(sources: list[dict[str, Any]]) -> None:
    if not sources:
        return
    st.markdown(
        f"""
        <div class="dk-section-title" style="margin:.9rem 0 .45rem">
          <h2 style="font-size:14px">Retrieved sources</h2>
          <span>{len(sources)} evidence chunks · retrieval complete</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for index, source in enumerate(sources, start=1):
        chunk_text = str(source.get("text", "")).strip()
        label = f"Expand_chunk_{index:02d}"
        with st.expander(label, expanded=False):
            st.markdown(
                f"""
                <div class="dk-source-head">
                  <div class="dk-source-index">[{index:02d}]</div>
                  <div class="dk-source-copy">
                    <strong>{escape(str(source.get("filename", "Unknown source")))}</strong>
                    <p>Retrieved source evidence</p>
                  </div>
                  <span class="dk-page-chip">PAGE {int(source.get("page_number", 0))}</span>
                </div>
                <div class="dk-source-text">{escape(chunk_text)}</div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                f"Source document: {source.get('filename', 'Unknown source')} · "
                f"Page {source.get('page_number', 0)} · "
                f"Chunk {source.get('chunk_reference', source.get('chunk_index'))}"
            )


def render_chat(corpora: list[dict[str, Any]]) -> None:
    corpus = selected_corpus(corpora)
    if corpus is None:
        page_header("Research interface", "Corpus Chat", "Ask grounded questions.")
        empty_state("No active corpus", "Create and index a corpus before starting research.")
        return

    page_header(
        "Research interface / Grounded mode",
        f"Chat with {corpus['name']}",
        "Answers are constrained to retrieved corpus evidence and include page-level citations.",
    )

    conversation_id = st.session_state.get("active_conversation_id")
    if conversation_id:
        try:
            messages = fetch_history(
                int(corpus["id"]),
                conversation_id=conversation_id,
                limit=50,
            )
        except requests.RequestException as error:
            render_api_error(error)
            messages = []
    else:
        messages = []

    if conversation_id:
        if st.button("＋ Start New Conversation", key="start-new-conversation"):
            st.session_state.pop("active_conversation_id", None)
            st.rerun()

    if not messages:
        with st.chat_message("assistant"):
            st.write(
                "The corpus is connected. Ask a question and I’ll retrieve the "
                "most relevant source chunks before answering."
            )

    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("created_at"):
                st.caption(format_datetime(message["created_at"], "%d %b · %H:%M"))
            if message["role"] == "assistant":
                render_citations(message.get("citations", []))

    question = st.chat_input(f"Query {corpus['name']}…")
    if question:
        try:
            with st.spinner("Retrieving evidence and synthesizing answer..."):
                response = answer_question(
                    int(corpus["id"]),
                    question,
                    conversation_id=conversation_id,
                )
            st.session_state.active_conversation_id = response["conversation_id"]
            st.rerun()
        except requests.RequestException as error:
            render_api_error(error)


def format_datetime(value: Any, pattern: str = "%d %b %Y · %H:%M") -> str:
    if not value:
        return "Unknown time"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime(pattern)
    except ValueError:
        return str(value)


def build_conversations(
    messages: list[dict[str, Any]],
    corpora: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    corpus_names = {int(corpus["id"]): str(corpus["name"]) for corpus in corpora}
    grouped: dict[str, dict[str, Any]] = {}
    legacy_by_corpus: dict[int, str] = {}

    for message in messages:
        corpus_id = int(message["corpus_id"])
        conversation_id = message.get("conversation_id")
        if not conversation_id:
            if message["role"] == "user" or corpus_id not in legacy_by_corpus:
                legacy_by_corpus[corpus_id] = f"legacy-{message['id']}"
            conversation_id = legacy_by_corpus[corpus_id]

        conversation = grouped.setdefault(
            str(conversation_id),
            {
                "conversation_id": str(conversation_id),
                "corpus_id": corpus_id,
                "corpus_name": corpus_names.get(
                    corpus_id,
                    f"Corpus {corpus_id}",
                ),
                "question": "",
                "answer": "",
                "created_at": message.get("created_at"),
                "updated_at": message.get("created_at"),
                "messages": 0,
            },
        )
        conversation["messages"] += 1
        conversation["updated_at"] = message.get("created_at")
        if message["role"] == "user" and not conversation["question"]:
            conversation["question"] = str(message["content"])
        if message["role"] == "assistant":
            conversation["answer"] = str(message["content"])

    return sorted(
        grouped.values(),
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )


def render_history(corpora: list[dict[str, Any]]) -> None:
    page_header(
        "Chat archive",
        "Previous Conversations",
        "Search prior research threads and return to the relevant corpus context.",
    )
    try:
        messages = fetch_history(limit=50)
    except requests.RequestException as error:
        render_api_error(error)
        return

    conversations = build_conversations(messages, corpora)
    search_col, filter_col = st.columns([1.6, 0.7])
    with search_col:
        search = st.text_input(
            "Search conversations",
            placeholder="Search questions, answers, or corpus names…",
        )
    with filter_col:
        options: list[Any] = ["All corpora"] + [corpus["id"] for corpus in corpora]
        corpus_filter = st.selectbox(
            "Filter by corpus",
            options,
            format_func=lambda value: (
                value
                if value == "All corpora"
                else next(c["name"] for c in corpora if c["id"] == value)
            ),
        )

    filtered = conversations
    if corpus_filter != "All corpora":
        filtered = [
            item for item in filtered if item["corpus_id"] == int(corpus_filter)
        ]
    if search.strip():
        needle = search.strip().lower()
        filtered = [
            item
            for item in filtered
            if needle
            in " ".join(
                [item["corpus_name"], item["question"], item["answer"]]
            ).lower()
        ]

    metric_grid(
        [
            ("Conversation turns", str(len(conversations)), "Available in recent history", "primary"),
            ("Matching results", str(len(filtered)), "Current search and filter", None),
            ("Corpora represented", str(len({c["corpus_id"] for c in conversations})), "Research contexts", None),
            ("Archive state", "Synced", "Backed by chat history", "success"),
        ]
    )

    section_title("Conversation index", f"{len(filtered)} results")
    if not filtered:
        empty_state("No conversations found", "Adjust the search or corpus filter.", "⌕")
        return

    for index, conversation in enumerate(filtered):
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="dk-history-card">
                  <div class="dk-history-card__top">
                    <span class="dk-chip">{escape(conversation["corpus_name"])}</span>
                    <h3>{escape(conversation["question"])}</h3>
                    <time>{escape(format_datetime(conversation["created_at"], "%d %b · %H:%M"))}</time>
                  </div>
                  <p>{escape(conversation["answer"] or "Awaiting assistant response.")}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Resume Conversation  →",
                key=f"resume-{index}-{conversation['conversation_id']}",
                on_click=queue_navigation,
                args=(
                    "Corpus Chat",
                    conversation["corpus_id"],
                    conversation["conversation_id"],
                ),
            )


def fetch_all_documents(corpora: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for corpus in corpora:
        detail = fetch_corpus_documents(int(corpus["id"]))
        for document in detail.get("documents", []):
            document["corpus_name"] = corpus["name"]
            documents.append(document)
    return documents


def evidence_for_statement(
    evidence_items: list[dict[str, Any]],
    statement: str,
) -> Optional[dict[str, Any]]:
    normalized = statement.strip().lower()
    for evidence_item in evidence_items:
        evidence_statement = str(evidence_item.get("statement", "")).strip().lower()
        if (
            evidence_statement == normalized
            or normalized in evidence_statement
            or evidence_statement in normalized
        ):
            return evidence_item
    return None


def highlight_relevant_paragraph(paragraph: str, statement: str) -> str:
    sentences = re_split_sentences(paragraph)
    statement_tokens = {
        token
        for token in re_words(statement)
        if len(token) > 4
    }
    if not sentences or not statement_tokens:
        return escape(paragraph)

    best_sentence = max(
        sentences,
        key=lambda sentence: len(statement_tokens & set(re_words(sentence))),
    )
    if not best_sentence.strip():
        return escape(paragraph)

    highlighted = escape(paragraph).replace(
        escape(best_sentence),
        f"<mark>{escape(best_sentence)}</mark>",
        1,
    )
    return highlighted


def re_words(value: str) -> list[str]:
    import re

    return re.findall(r"\b\w+\b", value.lower())


def re_split_sentences(value: str) -> list[str]:
    import re

    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]


def render_statement_evidence(
    evidence_item: Optional[dict[str, Any]],
    statement: str,
) -> None:
    citations = evidence_item.get("citations", []) if evidence_item else []
    if not citations:
        st.caption("No chunk-level evidence was stored for this statement.")
        return

    st.markdown('<div class="dk-evidence-timeline">', unsafe_allow_html=True)
    for citation in citations:
        paragraph = str(citation.get("relevant_paragraph", "")).strip()
        st.markdown(
            f"""
            <div class="dk-evidence-card">
              <div class="dk-evidence-card__rail"></div>
              <div class="dk-evidence-card__body">
                <div class="dk-evidence-card__top">
                  <strong>{escape(str(citation.get("document", "Unknown document")))}</strong>
                  <span>Score {float(citation.get("score", 0)):.2f}</span>
                </div>
                <div class="dk-evidence-meta">
                  Page {int(citation.get("page", 0))} · Chunk {escape(str(citation.get("chunk", "unknown")))}
                </div>
                <details>
                  <summary>View Evidence</summary>
                  <p>{highlight_relevant_paragraph(paragraph, statement)}</p>
                </details>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def comparison_list(
    title: str,
    items: list[Any],
    evidence_items: Optional[list[dict[str, Any]]] = None,
    key_prefix: str = "comparison-point",
) -> None:
    if not items:
        st.caption(f"No {title.lower()} returned.")
        return
    for index, item in enumerate(items):
        statement = str(item)
        evidence_item = evidence_for_statement(evidence_items or [], statement)
        with st.expander(statement, expanded=False):
            st.markdown(
                '<div class="dk-label">Supported By</div>',
                unsafe_allow_html=True,
            )
            render_statement_evidence(evidence_item, statement)


def comparison_topic_map(
    title: str,
    topic_map: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> None:
    section_title(title, f"{len(topic_map)} documents")
    if not topic_map:
        empty_state("No document-specific topics", "The comparison did not return a document map.", "≋")
        return
    columns = st.columns(2)
    for index, (document_name, topics) in enumerate(topic_map.items()):
        with columns[index % 2]:
            st.markdown(
                f"""
                <div class="dk-comparison-doc-card">
                  <span class="dk-chip">Document</span>
                  <h3 title="{escape(str(document_name))}">{escape(str(document_name))}</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )
            statements = []
            for topic in topics if isinstance(topics, list) else []:
                if title == "Unique Topics":
                    statements.append(f"{topic} is unique to {document_name}.")
                elif title == "Missing Concepts":
                    statements.append(f"{topic} is missing from {document_name}.")
                else:
                    statements.append(str(topic))
            comparison_list(
                "Topics",
                statements,
                evidence_items=evidence_items,
                key_prefix=f"{title}-{document_name}",
            )


def render_comparison_result(result: dict[str, Any]) -> None:
    comparison_id = result.get("comparison_id") or result.get("id")
    evidence_items = result.get("evidence", [])
    st.markdown(
        f"""
        <div class="dk-comparison-hero">
          <div>
            <span class="dk-chip">Comparison {int(comparison_id):02d}</span>
            <h2>{escape(str(result.get("title") or "Document comparison"))}</h2>
            <p>{escape(str(result.get("overall_summary") or "No summary returned."))}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    documents = result.get("documents", [])
    if documents:
        section_title("Compared documents", f"{len(documents)} selected")
        st.markdown(
            "<div class=\"dk-comparison-docs\">"
            + "".join(
                (
                    "<div class=\"dk-comparison-doc-pill\">"
                    f"<strong>{escape(str(document.get('filename', 'Document')))}</strong>"
                    f"<span>{escape(str(document.get('corpus_name', 'Corpus')))}</span>"
                    "</div>"
                )
                for document in documents
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Why this overall summary?", expanded=False):
        render_statement_evidence(
            evidence_for_statement(evidence_items, str(result.get("overall_summary", ""))),
            str(result.get("overall_summary", "")),
        )

    summary, common = st.columns([1.2, 1], gap="large")
    with summary:
        section_title("Major Differences", "Conceptual deltas")
        comparison_list(
            "Major differences",
            result.get("major_differences", []),
            evidence_items=evidence_items,
            key_prefix=f"major-{comparison_id}",
        )
    with common:
        section_title("Common Topics", "Shared ground")
        comparison_list(
            "Common topics",
            result.get("common_topics", []),
            evidence_items=evidence_items,
            key_prefix=f"common-{comparison_id}",
        )

    comparison_topic_map("Unique Topics", result.get("unique_topics", {}), evidence_items)
    comparison_topic_map("Missing Concepts", result.get("missing_concepts", {}), evidence_items)

    beginner, comprehensive = st.columns(2, gap="large")
    with beginner:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Beginner fit</div>', unsafe_allow_html=True)
            st.subheader(result.get("beginner_document") or "Not specified")
            st.caption("Document most suitable for first-pass learning.")
            with st.expander("View evidence", expanded=False):
                render_statement_evidence(
                    evidence_for_statement(
                        evidence_items,
                        f"{result.get('beginner_document')} is most suitable for beginners.",
                    ),
                    f"{result.get('beginner_document')} is most suitable for beginners.",
                )
    with comprehensive:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Coverage</div>', unsafe_allow_html=True)
            st.subheader(result.get("most_comprehensive_document") or "Not specified")
            st.caption("Document with the broadest or deepest treatment.")
            with st.expander("View evidence", expanded=False):
                render_statement_evidence(
                    evidence_for_statement(
                        evidence_items,
                        f"{result.get('most_comprehensive_document')} is the most comprehensive document.",
                    ),
                    f"{result.get('most_comprehensive_document')} is the most comprehensive document.",
                )

    section_title("Final Recommendation", "Decision support")
    st.markdown(
        f"""
        <div class="dk-recommendation">
          {escape(str(result.get("recommendation") or "No recommendation returned."))}
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Why this recommendation?", expanded=False):
        render_statement_evidence(
            evidence_for_statement(evidence_items, str(result.get("recommendation", ""))),
            str(result.get("recommendation", "")),
        )

    render_comparison_chat(result)


def render_comparison_answer_sources(sections: list[dict[str, Any]]) -> None:
    if not sections:
        return
    st.markdown(
        f"""
        <div class="dk-section-title" style="margin:.9rem 0 .45rem">
          <h2 style="font-size:14px">Referenced sections</h2>
          <span>{len(sections)} grounded chunks</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for index, section in enumerate(sections, start=1):
        with st.expander(f"Compare_chunk_{index:02d}", expanded=False):
            st.markdown(
                f"""
                <div class="dk-source-head">
                  <div class="dk-source-index">[{index:02d}]</div>
                  <div class="dk-source-copy">
                    <strong>{escape(str(section.get("filename", "Unknown source")))}</strong>
                    <p>Comparison evidence section</p>
                  </div>
                  <span class="dk-page-chip">PAGE {int(section.get("page_number", 0))}</span>
                </div>
                <div class="dk-source-text">{escape(str(section.get("text", "")).strip())}</div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                f"Source document: {section.get('filename', 'Unknown source')} · "
                f"Page {section.get('page_number', 0)} · "
                f"Chunk {section.get('chunk_reference', 'unknown')}"
            )


def submit_comparison_question(comparison_id: int, question: str) -> None:
    try:
        with st.spinner("Retrieving chunks across compared documents..."):
            ask_comparison_question(comparison_id, question)
        st.session_state.pop("latest_comparison_result", None)
        st.session_state.active_comparison_id = comparison_id
        st.rerun()
    except requests.RequestException as error:
        render_api_error(error)


def render_comparison_chat(result: dict[str, Any]) -> None:
    comparison_id = int(result.get("id") or result.get("comparison_id"))
    section_title("Ask about these documents", "Grounded comparison chat")
    st.markdown(
        """
        <div class="dk-comparison-ask-shell">
          Ask targeted questions across only the PDFs in this comparison. Answers cite
          retrieved chunks and stay inside the selected documents.
        </div>
        """,
        unsafe_allow_html=True,
    )

    examples = [
        "What concepts are common?",
        "Which PDF explains this topic better?",
        "What exists only in the last PDF?",
        "Compare scheduling algorithms.",
    ]
    example_columns = st.columns(4)
    for index, example in enumerate(examples):
        with example_columns[index]:
            if st.button(
                example,
                key=f"comparison-example-{comparison_id}-{index}",
                use_container_width=True,
            ):
                submit_comparison_question(comparison_id, example)

    questions = result.get("questions", [])
    if not questions:
        with st.chat_message("assistant"):
            st.write(
                "I’m ready to compare these documents. Ask what overlaps, what differs, "
                "or which PDF explains a concept more clearly."
            )

    for item in questions:
        with st.chat_message("user"):
            st.write(item.get("question", ""))
            if item.get("created_at"):
                st.caption(format_datetime(item["created_at"], "%d %b · %H:%M"))
        with st.chat_message("assistant"):
            st.write(item.get("answer", ""))
            support = item.get("supporting_documents", [])
            confidence = item.get("confidence", "medium")
            st.caption(
                f"Confidence: {confidence.title()} · "
                f"Supporting documents: {', '.join(support) if support else 'No specific support'}"
            )
            if item.get("evidence"):
                with st.expander("Why this answer?", expanded=False):
                    for evidence_item in item.get("evidence", []):
                        st.markdown(
                            f"""
                            <div class="dk-evidence-statement">
                              {escape(str(evidence_item.get("statement", "")))}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        render_statement_evidence(
                            evidence_item,
                            str(evidence_item.get("statement", "")),
                        )
            render_comparison_answer_sources(item.get("referenced_sections", []))

    question = st.chat_input(
        "Ask about these compared documents…",
        key=f"comparison-chat-input-{comparison_id}",
    )
    if question:
        submit_comparison_question(comparison_id, question)


def render_compare_documents(corpora: list[dict[str, Any]]) -> None:
    page_header(
        "Comparative intelligence",
        "Compare Documents",
        "Select two or more uploaded PDFs and generate a structured summary-to-summary comparison.",
    )

    if not corpora:
        empty_state("No corpora available", "Create a corpus and upload PDFs before comparing documents.", "PDF")
        return

    try:
        documents = fetch_all_documents(corpora)
        comparisons = fetch_comparisons()
    except requests.RequestException as error:
        render_api_error(error)
        return

    metric_grid(
        [
            ("Uploaded PDFs", str(len(documents)), "Available for comparison", "primary"),
            ("Previous comparisons", str(len(comparisons)), "Saved analyses", None),
            ("Active corpora", str(len(corpora)), "Document sources", "success"),
        ]
    )

    if len(documents) < 2:
        empty_state(
            "At least two PDFs are required",
            "Upload another document in Corpus Detail to unlock comparison.",
            "≋",
        )
        return

    compare_panel, archive_panel = st.columns([1.45, 0.9], gap="large")
    documents_by_id = {int(document["id"]): document for document in documents}

    with compare_panel:
        section_title("New comparison", "2+ documents")
        with st.container(border=True):
            st.markdown(
                """
                <div class="dk-label">Document set</div>
                <h3 style="margin:.45rem 0 .35rem">Select PDFs to compare</h3>
                <p style="font-size:13px;margin:0 0 .8rem">
                  The backend summarizes each document first, then compares only the summaries.
                </p>
                """,
                unsafe_allow_html=True,
            )
            selected_document_ids = st.multiselect(
                "Uploaded documents",
                options=[int(document["id"]) for document in documents],
                format_func=lambda document_id: (
                    f"{documents_by_id[document_id]['filename']} · "
                    f"{documents_by_id[document_id]['corpus_name']}"
                ),
                placeholder="Choose two or more indexed PDFs",
            )
            selected_count = len(selected_document_ids)
            st.caption(f"{selected_count} document{'s' if selected_count != 1 else ''} selected.")
            if st.button(
                "Compare Documents",
                type="primary",
                use_container_width=True,
                disabled=selected_count < 2,
            ):
                try:
                    with st.spinner("Summarizing documents and generating comparison..."):
                        result = create_comparison(selected_document_ids)
                    st.session_state.active_comparison_id = result["comparison_id"]
                    st.session_state.latest_comparison_result = result
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)

    with archive_panel:
        section_title("Comparison archive", f"{len(comparisons)} saved")
        if not comparisons:
            empty_state("No comparisons yet", "Run your first comparison to create an archive item.", "◇")
        else:
            for comparison in comparisons[:6]:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="dk-history-card">
                          <div class="dk-history-card__top">
                            <span class="dk-chip">{int(comparison["document_count"])} docs</span>
                            <h3>{escape(str(comparison["title"]))}</h3>
                          </div>
                          <time>{escape(format_datetime(comparison.get("created_at"), "%d %b · %H:%M"))}</time>
                          <p>{escape(str(comparison.get("overall_summary") or "Open for details."))}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Open Comparison  →",
                        key=f"open-comparison-{comparison['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.active_comparison_id = comparison["id"]
                        st.session_state.pop("latest_comparison_result", None)
                        st.rerun()

    result: Optional[dict[str, Any]] = st.session_state.get("latest_comparison_result")
    active_id = st.session_state.get("active_comparison_id")
    if active_id and (
        not result
        or int(result.get("comparison_id", result.get("id", 0))) != int(active_id)
        or "documents" not in result
    ):
        try:
            result = fetch_comparison(int(active_id))
        except requests.RequestException as error:
            render_api_error(error)
            result = None

    if result:
        section_title("Comparison output", "Structured JSON rendered")
        render_comparison_result(result)


def render_settings(corpora: list[dict[str, Any]]) -> None:
    user = st.session_state.get("current_user", {})
    page_header(
        "Account control",
        "Settings",
        "Manage operator identity, interface behavior, and session preferences.",
    )

    profile, preferences = st.columns(2, gap="large")
    with profile:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Profile</div>', unsafe_allow_html=True)
            st.subheader("Operator identity")
            st.caption("Identity attached to private corpora and chat history.")
            with st.form("profile-form"):
                display_name = st.text_input(
                    "Display name",
                    value=str(user.get("display_name", "")),
                )
                st.text_input(
                    "Corporate email",
                    value=str(user.get("email", "")),
                    disabled=True,
                )
                submitted = st.form_submit_button(
                    "Save Profile",
                    type="primary",
                    use_container_width=True,
                )
            if submitted:
                try:
                    updated = update_profile(display_name.strip())
                    st.session_state.current_user = updated
                    st.success("Operator profile updated.")
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)

        with st.container(border=True):
            st.markdown('<div class="dk-label">Security</div>', unsafe_allow_html=True)
            st.subheader("Session controls")
            st.markdown(
                f"""
                <div style="display:grid;gap:.7rem;margin:.7rem 0 1rem">
                  <div style="display:flex;justify-content:space-between">
                    <span style="color:#918fa1">API connection</span>
                    {status_badge("Connected")}
                  </div>
                  <div style="display:flex;justify-content:space-between;gap:1rem">
                    <span style="color:#918fa1">Endpoint</span>
                    <code style="color:#c3c0ff;overflow:hidden;text-overflow:ellipsis">{escape(API_BASE_URL)}</code>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("End Current Session", use_container_width=True):
                clear_auth_session()
                st.rerun()

    with preferences:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Interface</div>', unsafe_allow_html=True)
            st.subheader("Research preferences")
            st.caption("Preferences apply immediately to this browser session.")
            st.toggle(
                "Comfortable information density",
                key="comfortable_density",
                help="Reserve more breathing room around long-form content.",
            )
            st.toggle(
                "Reduce interface motion",
                key="reduce_motion",
                help="Minimize decorative transitions and status animation.",
            )
            st.selectbox(
                "Default workspace",
                ["Corpus Dashboard", "Corpus Chat", "Compare Documents", "Chat History"],
                key="default_workspace",
            )

        with st.container(border=True):
            st.markdown('<div class="dk-label">Workspace data</div>', unsafe_allow_html=True)
            st.subheader("Corpus footprint")
            st.caption("Account-scoped resources visible to the current operator.")
            metric_grid(
                [
                    ("Corpora", str(len(corpora)), "Private workspaces", "primary"),
                    (
                        "Documents",
                        str(sum(int(c["document_count"]) for c in corpora)),
                        "Indexed sources",
                        "success",
                    ),
                ]
            )

            corpus = selected_corpus(corpora)
            if corpus:
                st.markdown(
                    f"""
                    <div style="padding:.75rem;border-radius:8px;background:#010f1f">
                      <div class="dk-label">Danger zone</div>
                      <p style="font-size:12px;margin:.4rem 0 .8rem">
                        Permanently remove <strong>{escape(str(corpus["name"]))}</strong>,
                        its documents, chat messages, and vector collection.
                      </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                confirm = st.checkbox(
                    f"I understand that deleting {corpus['name']} cannot be undone",
                    key=f"confirm-delete-{corpus['id']}",
                )
                if st.button(
                    "Delete Active Corpus",
                    disabled=not confirm,
                    use_container_width=True,
                ):
                    try:
                        delete_corpus(int(corpus["id"]))
                        st.session_state.pop("selected_corpus_id", None)
                        queue_navigation("Corpus Dashboard")
                        st.rerun()
                    except requests.RequestException as error:
                        render_api_error(error)


if not require_authenticated_user():
    render_auth_page()
    st.stop()

try:
    corpora = fetch_corpora()
except requests.RequestException as error:
    if isinstance(error, requests.HTTPError) and error.response is not None:
        if error.response.status_code == 401:
            clear_auth_session()
            st.rerun()
    render_api_error(error)
    st.stop()

apply_pending_navigation(corpora)
page = render_sidebar(corpora)

if page == "Corpus Dashboard":
    render_dashboard(corpora)
elif page == "Corpus Detail":
    render_corpus_detail(corpora)
elif page == "Corpus Chat":
    render_chat(corpora)
elif page == "Compare Documents":
    render_compare_documents(corpora)
elif page == "Chat History":
    render_history(corpora)
else:
    render_settings(corpora)
