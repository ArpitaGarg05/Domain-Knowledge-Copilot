import json
import os
import re 
import time
from datetime import datetime, timedelta
from html import escape
from typing import Any, Optional

import extra_streamlit_components as stx
import requests
import streamlit as st
import streamlit.components.v1 as components

from styles import (
    empty_state,
    format_bytes,
    inject_styles,
    metric_grid,
    page_header,
    section_title,
    status_badge,
)
from state_utils import replace_corpus_in_list


st.set_page_config(
    page_title="Knowledge Co-Pilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_styles()

API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_STORAGE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
CORPUS_NAME_MIN_LENGTH = 3
CORPUS_NAME_MAX_LENGTH = 100


def parse_storage_limit() -> int:
    try:
        return int(os.getenv("MAX_STORAGE_BYTES", str(DEFAULT_STORAGE_LIMIT_BYTES)))
    except ValueError:
        return DEFAULT_STORAGE_LIMIT_BYTES


MAX_STORAGE_BYTES = parse_storage_limit()
AUTH_COOKIE_NAME = "dkc_access_token"
AUTH_LOGGED_OUT_VALUE = "__logged_out__"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "").lower() in {
    "1",
    "true",
    "yes",
}
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
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
if st.session_state.auth_tab == "Sign-Up":
    st.session_state.auth_tab = "Sign Up"
st.session_state.setdefault("upload_nonce", 0)
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


def rename_corpus(corpus_id: int, name: str) -> dict[str, Any]:
    return request_json(
        "PATCH",
        f"/api/corpora/{corpus_id}",
        json={"name": name},
    )


def is_valid_corpus_name(name: str) -> bool:
    return validate_corpus_name(name) is None


def validate_corpus_name(name: str) -> Optional[str]:
    normalized = name.strip()
    if not normalized:
        return "Corpus name is required."
    if len(normalized) < CORPUS_NAME_MIN_LENGTH:
        return f"Corpus name must be at least {CORPUS_NAME_MIN_LENGTH} characters."
    if len(normalized) > CORPUS_NAME_MAX_LENGTH:
        return f"Corpus name must be at most {CORPUS_NAME_MAX_LENGTH} characters."
    if not re.search(r"[A-Za-z]", normalized):
        return "Corpus name must contain at least one letter."
    return None


def delete_corpus(corpus_id: int) -> dict[str, Any]:
    return request_json("DELETE", f"/api/corpora/{corpus_id}")


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


def document_preview_url(corpus_id: int, document_id: int) -> str:
    return api_url(f"/api/corpora/{corpus_id}/documents/{document_id}/preview")


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
          <p>Checking your account · Loading your workspace</p>
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
    if page == "Corpus Detail":
        st.session_state.upload_nonce = int(st.session_state.get("upload_nonce", 0)) + 1
    if corpus_id is not None:
        st.session_state.pending_selected_corpus_id = corpus_id
    if conversation_id is not None:
        st.session_state.pending_conversation_id = conversation_id


def request_corpus_delete(corpus_id: int) -> None:
    st.session_state.pending_delete_corpus_id = corpus_id


def request_corpus_rename(corpus_id: int) -> None:
    st.session_state.pending_rename_corpus_id = corpus_id
    st.session_state.pop(f"rename-corpus-name-{corpus_id}", None)


def request_document_preview(corpus_id: int, document: dict[str, Any]) -> None:
    st.session_state.pending_preview_document = {
        "corpus_id": corpus_id,
        "document": document,
    }


def complete_corpus_rename(corpus_id: int, name: str) -> None:
    updated = rename_corpus(corpus_id, name.strip())
    st.session_state.pop("pending_rename_corpus_id", None)
    st.session_state.renamed_corpus = updated
    st.session_state.corpus_rename_success = "Corpus renamed successfully."
    if str(st.session_state.get("selected_corpus_id")) == str(corpus_id):
        st.session_state.selected_corpus_id = updated["id"]


def complete_corpus_delete(corpus_id: int) -> None:
    response = delete_corpus(corpus_id)
    if str(st.session_state.get("selected_corpus_id")) == str(corpus_id):
        st.session_state.pop("selected_corpus_id", None)
    st.session_state.pop("active_conversation_id", None)
    st.session_state.pop("active_comparison_id", None)
    st.session_state.pop("latest_comparison_result", None)
    st.session_state.pop("pending_delete_corpus_id", None)
    st.session_state.corpus_delete_success = response.get(
        "message",
        "Corpus permanently deleted.",
    )
    queue_navigation("Corpus Dashboard")


@st.dialog("PDF Preview")
def render_pdf_preview_dialog(corpus_id: int, document: dict[str, Any]) -> None:
    document_id = int(document["id"])
    filename = str(document.get("filename", "Document.pdf"))
    preview_url = document_preview_url(corpus_id, document_id)
    token = st.session_state.get("access_token", "")
    uploaded_at = format_datetime(document.get("uploaded_at"))
    file_size = format_bytes(int(document.get("file_size_bytes") or 0))
    page_count = int(document.get("page_count") or 0)

    st.markdown(
        f"""
        <div class="dk-preview-meta">
          <h3 title="{escape(filename)}">{escape(filename)}</h3>
          <div>
            <span>{escape(file_size)}</span>
            <span>Uploaded {escape(uploaded_at)}</span>
            <span>{page_count:,} page{'s' if page_count != 1 else ''}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_pdf_viewer_component(
        preview_url=preview_url,
        token=token,
        filename=filename,
    )
    if st.button(
        "Close",
        key=f"close-preview-{corpus_id}-{document_id}",
        use_container_width=True,
    ):
        st.session_state.pop("pending_preview_document", None)
        st.rerun()


def render_pending_pdf_preview_dialog() -> None:
    pending = st.session_state.get("pending_preview_document")
    if not pending:
        return
    render_pdf_preview_dialog(
        int(pending["corpus_id"]),
        pending["document"],
    )


def render_pdf_viewer_component(
    *,
    preview_url: str,
    token: str,
    filename: str,
) -> None:
    component_id = f"pdf-preview-{abs(hash(preview_url))}"
    components.html(
        f"""
        <div id="{component_id}" class="pdf-preview-shell">
          <div class="pdf-preview-toolbar">
            <button id="prevPage" type="button">Previous</button>
            <span id="pageInfo">Loading PDF...</span>
            <button id="nextPage" type="button">Next</button>
            <span class="divider"></span>
            <button id="zoomOut" type="button">−</button>
            <button id="zoomIn" type="button">+</button>
            <button id="fitWidth" type="button">Fit Width</button>
            <button id="fitPage" type="button">Fit Page</button>
            <button id="rotate" type="button">Rotate</button>
            <button id="fullscreen" type="button">Full Screen</button>
            <button id="downloadPdf" type="button">Download</button>
          </div>
          <div id="loadingState" class="pdf-preview-loading">Fetching and rendering PDF...</div>
          <div id="errorState" class="pdf-preview-error" hidden></div>
          <div id="viewer" class="pdf-preview-canvas-wrap">
            <canvas id="pdfCanvas"></canvas>
          </div>
        </div>
        <style>
          .pdf-preview-shell {{
            min-height: 720px;
            border: 1px solid rgba(70,69,85,.72);
            border-radius: 14px;
            background: #010f1f;
            overflow: hidden;
            color: #d4e4fa;
            font-family: Geist, system-ui, sans-serif;
          }}
          .pdf-preview-toolbar {{
            position: sticky;
            top: 0;
            z-index: 3;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid rgba(70,69,85,.72);
            background: rgba(13,28,45,.96);
          }}
          .pdf-preview-toolbar button {{
            border: 1px solid #464555;
            border-radius: 8px;
            background: #0d1c2d;
            color: #d4e4fa;
            min-height: 34px;
            padding: 0 10px;
            font-weight: 600;
            cursor: pointer;
          }}
          .pdf-preview-toolbar button:hover {{
            border-color: #c3c0ff;
            color: #c3c0ff;
          }}
          .pdf-preview-toolbar button:disabled {{
            opacity: .45;
            cursor: not-allowed;
          }}
          #pageInfo {{
            min-width: 112px;
            text-align: center;
            color: #c7c4d8;
            font: 600 12px/1.4 monospace;
          }}
          .divider {{
            width: 1px;
            align-self: stretch;
            background: rgba(70,69,85,.72);
          }}
          .pdf-preview-loading,
          .pdf-preview-error {{
            margin: 16px;
            padding: 12px 14px;
            border-radius: 10px;
            background: rgba(18,33,49,.78);
            color: #c7c4d8;
          }}
          .pdf-preview-error {{
            border: 1px solid rgba(255,180,171,.35);
            color: #ffb4ab;
          }}
          .pdf-preview-canvas-wrap {{
            height: 660px;
            overflow: auto;
            display: grid;
            place-items: start center;
            padding: 18px;
          }}
          #pdfCanvas {{
            background: white;
            border-radius: 4px;
            box-shadow: 0 20px 45px rgba(0,0,0,.35);
          }}
          @media (max-width: 720px) {{
            .pdf-preview-shell {{ min-height: 560px; }}
            .pdf-preview-canvas-wrap {{ height: 500px; padding: 10px; }}
          }}
        </style>
        <script type="module">
          import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs";

          const shell = document.getElementById({json.dumps(component_id)});
          const viewer = shell.querySelector("#viewer");
          const canvas = shell.querySelector("#pdfCanvas");
          const context = canvas.getContext("2d");
          const pageInfo = shell.querySelector("#pageInfo");
          const loadingState = shell.querySelector("#loadingState");
          const errorState = shell.querySelector("#errorState");
          const buttons = {{
            prev: shell.querySelector("#prevPage"),
            next: shell.querySelector("#nextPage"),
            zoomIn: shell.querySelector("#zoomIn"),
            zoomOut: shell.querySelector("#zoomOut"),
            fitWidth: shell.querySelector("#fitWidth"),
            fitPage: shell.querySelector("#fitPage"),
            rotate: shell.querySelector("#rotate"),
            fullscreen: shell.querySelector("#fullscreen"),
            download: shell.querySelector("#downloadPdf"),
          }};

          pdfjsLib.GlobalWorkerOptions.workerSrc =
            "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";

          let pdfDoc = null;
          let pageNumber = 1;
          let scale = 1.15;
          let rotation = 0;
          let rendering = false;
          const pageCache = new Map();
          const url = {json.dumps(preview_url)};
          const token = {json.dumps(token)};
          const filename = {json.dumps(filename)};

          function showError(message) {{
            loadingState.hidden = true;
            errorState.hidden = false;
            errorState.textContent = message || "The PDF could not be loaded.";
          }}

          function cacheKey() {{
            return `${{pageNumber}}:${{scale.toFixed(2)}}:${{rotation}}`;
          }}

          async function renderPage() {{
            if (!pdfDoc || rendering) return;
            rendering = true;
            loadingState.hidden = false;
            errorState.hidden = true;
            buttons.prev.disabled = pageNumber <= 1;
            buttons.next.disabled = pageNumber >= pdfDoc.numPages;
            pageInfo.textContent = `Page ${{pageNumber}} of ${{pdfDoc.numPages}}`;

            const key = cacheKey();
            const cached = pageCache.get(key);
            if (cached) {{
              const image = new Image();
              image.onload = () => {{
                canvas.width = cached.width;
                canvas.height = cached.height;
                context.drawImage(image, 0, 0);
                loadingState.hidden = true;
                rendering = false;
              }};
              image.src = cached.dataUrl;
              return;
            }}

            try {{
              const page = await pdfDoc.getPage(pageNumber);
              const viewport = page.getViewport({{ scale, rotation }});
              canvas.width = viewport.width;
              canvas.height = viewport.height;
              await page.render({{ canvasContext: context, viewport }}).promise;
              pageCache.set(key, {{
                dataUrl: canvas.toDataURL("image/png"),
                width: canvas.width,
                height: canvas.height,
              }});
              loadingState.hidden = true;
            }} catch (error) {{
              showError("This page could not be rendered.");
            }} finally {{
              rendering = false;
            }}
          }}

          async function loadPdf() {{
            try {{
              pdfDoc = await pdfjsLib.getDocument({{
                url,
                httpHeaders: {{ Authorization: `Bearer ${{token}}` }},
                withCredentials: false,
                rangeChunkSize: 65536,
              }}).promise;
              pageNumber = Math.min(pageNumber, pdfDoc.numPages || 1);
              await renderPage();
            }} catch (error) {{
              showError("The PDF could not be loaded. Please check your access or try again.");
            }}
          }}

          buttons.prev.addEventListener("click", () => {{
            if (pageNumber > 1) {{
              pageNumber -= 1;
              renderPage();
            }}
          }});
          buttons.next.addEventListener("click", () => {{
            if (pdfDoc && pageNumber < pdfDoc.numPages) {{
              pageNumber += 1;
              renderPage();
            }}
          }});
          buttons.zoomIn.addEventListener("click", () => {{
            scale = Math.min(scale + .15, 3);
            renderPage();
          }});
          buttons.zoomOut.addEventListener("click", () => {{
            scale = Math.max(scale - .15, .45);
            renderPage();
          }});
          buttons.fitWidth.addEventListener("click", async () => {{
            if (!pdfDoc) return;
            const page = await pdfDoc.getPage(pageNumber);
            const viewport = page.getViewport({{ scale: 1, rotation }});
            scale = Math.max((viewer.clientWidth - 36) / viewport.width, .3);
            renderPage();
          }});
          buttons.fitPage.addEventListener("click", async () => {{
            if (!pdfDoc) return;
            const page = await pdfDoc.getPage(pageNumber);
            const viewport = page.getViewport({{ scale: 1, rotation }});
            const widthScale = Math.max((viewer.clientWidth - 36) / viewport.width, .3);
            const heightScale = Math.max((viewer.clientHeight - 36) / viewport.height, .3);
            scale = Math.min(widthScale, heightScale);
            renderPage();
          }});
          buttons.rotate.addEventListener("click", () => {{
            rotation = (rotation + 90) % 360;
            renderPage();
          }});
          buttons.fullscreen.addEventListener("click", () => {{
            if (shell.requestFullscreen) shell.requestFullscreen();
          }});
          buttons.download.addEventListener("click", async () => {{
            try {{
              const response = await fetch(url, {{
                headers: {{ Authorization: `Bearer ${{token}}` }},
              }});
              if (!response.ok) throw new Error("download failed");
              const blob = await response.blob();
              const objectUrl = URL.createObjectURL(blob);
              const anchor = document.createElement("a");
              anchor.href = objectUrl;
              anchor.download = filename;
              anchor.click();
              setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
            }} catch (error) {{
              showError("The PDF could not be downloaded.");
            }}
          }});

          loadPdf();
        </script>
        """,
        height=820,
        scrolling=False,
    )


@st.dialog("Rename Corpus")
def render_corpus_rename_dialog(corpus: dict[str, Any]) -> None:
    corpus_id = int(corpus["id"])
    original_name = str(corpus["name"])
    input_key = f"rename-corpus-name-{corpus_id}"
    st.caption("Current corpus name")
    st.markdown(f"**{escape(original_name)}**")
    proposed_name = st.text_input(
        "Corpus name",
        value=original_name,
        key=input_key,
        max_chars=CORPUS_NAME_MAX_LENGTH,
    )
    normalized_original = original_name.strip()
    normalized_proposed = proposed_name.strip()
    validation_error = validate_corpus_name(proposed_name)
    modified = normalized_proposed != normalized_original
    if validation_error:
        st.error(validation_error)

    enhance_corpus_rename_dialog()
    save, cancel = st.columns(2)
    with save:
        if st.button(
            "Save",
            type="primary",
            disabled=bool(validation_error) or not modified,
            use_container_width=True,
            key=f"rename-dialog-save-{corpus_id}",
        ):
            try:
                with st.spinner("Renaming corpus..."):
                    complete_corpus_rename(corpus_id, proposed_name)
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)
    with cancel:
        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"rename-dialog-cancel-{corpus_id}",
        ):
            st.session_state.pop("pending_rename_corpus_id", None)
            st.rerun()


@st.dialog("Delete Corpus")
def render_corpus_delete_dialog(corpus: dict[str, Any]) -> None:
    corpus_id = int(corpus["id"])
    st.warning(
        "This action is permanent and cannot be undone. Deleting this corpus "
        "will remove uploaded PDFs, extracted text, searchable sections, "
        "embeddings, vector data, chat history, document comparisons, generated "
        "summaries, cached responses, and temporary files associated with this "
        "workspace."
    )
    st.markdown(f"**Workspace:** {corpus['name']}")
    confirm = st.checkbox(
        "I understand this deletion is irreversible.",
        key=f"delete-dialog-confirm-{corpus_id}",
    )
    action, cancel = st.columns(2)
    with action:
        if st.button(
            "🗑️ Permanently Delete",
            type="primary",
            disabled=not confirm,
            use_container_width=True,
            key=f"delete-dialog-submit-{corpus_id}",
        ):
            try:
                with st.spinner("Deleting corpus and reclaiming storage..."):
                    complete_corpus_delete(corpus_id)
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)
    with cancel:
        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"delete-dialog-cancel-{corpus_id}",
        ):
            st.session_state.pop("pending_delete_corpus_id", None)
            st.rerun()


def render_pending_corpus_delete_dialog(corpora: list[dict[str, Any]]) -> None:
    pending_id = st.session_state.get("pending_delete_corpus_id")
    if pending_id is None:
        return
    corpus = next(
        (item for item in corpora if str(item["id"]) == str(pending_id)),
        None,
    )
    if corpus is None:
        st.session_state.pop("pending_delete_corpus_id", None)
        return
    render_corpus_delete_dialog(corpus)


def render_pending_corpus_rename_dialog(corpora: list[dict[str, Any]]) -> None:
    pending_id = st.session_state.get("pending_rename_corpus_id")
    if pending_id is None:
        return
    corpus = next(
        (item for item in corpora if str(item["id"]) == str(pending_id)),
        None,
    )
    if corpus is None:
        st.session_state.pop("pending_rename_corpus_id", None)
        return
    render_corpus_rename_dialog(corpus)


def enhance_corpus_rename_dialog() -> None:
    components.html(
        """
        <script>
          setTimeout(() => {
            const doc = window.parent.document;
            const inputs = Array.from(doc.querySelectorAll('input[aria-label="Corpus name"]'));
            const input = inputs[inputs.length - 1];
            if (!input) return;
            input.focus();
            input.select();
            input.addEventListener("keydown", (event) => {
              const buttons = Array.from(doc.querySelectorAll("button"));
              if (event.key === "Escape") {
                const cancel = buttons.reverse().find((button) => button.innerText.trim() === "Cancel");
                if (cancel) cancel.click();
              }
              if (event.key === "Enter") {
                const save = buttons.reverse().find((button) => button.innerText.trim() === "Save" && !button.disabled);
                if (save) save.click();
              }
            }, { once: true });
          }, 120);
        </script>
        """,
        height=0,
        width=0,
    )


def render_flash_messages() -> None:
    rename_success = st.session_state.pop("corpus_rename_success", None)
    if rename_success:
        st.toast(rename_success, icon="✅")
        st.session_state.pop("renamed_corpus", None)
    success = st.session_state.pop("corpus_delete_success", None)
    if success:
        st.success(success)


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
    detail = "Something went wrong. Please try again."
    if isinstance(error, requests.Timeout):
        detail = "The service took too long to respond."
    elif isinstance(error, requests.HTTPError) and error.response is not None:
        try:
            payload = error.response.json()
            detail = humanize_api_error(payload.get("detail", detail))
        except ValueError:
            detail = humanize_api_error(error.response.text.strip() or detail)
    elif str(error):
        detail = humanize_api_error(str(error))
    st.error(detail)


def humanize_api_error(detail: Any) -> str:
    if isinstance(detail, dict):
        if "msg" in detail:
            return humanize_api_error(detail["msg"])
        if "message" in detail:
            return humanize_api_error(detail["message"])
        if "detail" in detail:
            return humanize_api_error(detail["detail"])
        return "Please check your input and try again."

    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict):
                location = item.get("loc", [])
                field = str(location[-1]).replace("_", " ") if location else "Input"
                message = clean_validation_message(str(item.get("msg", "is invalid")))
                if field.lower() == "email":
                    messages.append("Please enter a valid email address.")
                    continue
                if message.lower().startswith(field.lower()) or "corpus name" in message.lower():
                    messages.append(message)
                else:
                    messages.append(f"{field.title()} {message}.")
            else:
                messages.append(str(item))
        return " ".join(messages) if messages else "Please check your input."

    message = str(detail).strip()
    if not message:
        return "Something went wrong. Please try again."
    if message.startswith("{") and "detail" in message:
        try:
            return humanize_api_error(json.loads(message).get("detail"))
        except (ValueError, AttributeError):
            pass

    normalized = message.lower()
    if "invalid email or password" in normalized or "incorrect username or password" in normalized:
        return "Incorrect email or password."
    if "valid email" in normalized or "email address" in normalized:
        return "Please enter a valid email address."
    if "corpus with this name already exists" in normalized:
        return "A corpus with this name already exists."
    if "user with this email already exists" in normalized or "already exists" in normalized:
        return "An account with this email already exists."
    if "field required" in normalized:
        return "Please complete all required fields."
    return message.rstrip(".") + "."


def clean_validation_message(message: str) -> str:
    cleaned = message.strip()
    if cleaned.lower().startswith("value error,"):
        cleaned = cleaned.split(",", 1)[1].strip()
    return cleaned.rstrip(".") + "."


def is_valid_email(email: str) -> bool:
    value = email.strip()
    if not value or " " in value:
        return False
    local_part = value.split("@", 1)[0] if "@" in value else ""
    if (
        local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
    ):
        return False
    return bool(EMAIL_PATTERN.fullmatch(value))


def render_email_error(email: str, *, submitted: bool) -> bool:
    has_value = bool(email.strip())
    invalid = (has_value or submitted) and not is_valid_email(email)
    if invalid:
        st.error("Please enter a valid email address.")
    return invalid


def enhance_email_inputs(invalid_placeholders: list[str]) -> None:
    placeholders = json.dumps(invalid_placeholders)
    components.html(
        f"""
        <script>
          const invalidPlaceholders = new Set({placeholders});
          const doc = window.parent.document;
          const authEmailPlaceholders = [
            "name@example.com",
            "name@organization.ai"
          ];

          authEmailPlaceholders.forEach((placeholder) => {{
            const input = doc.querySelector(`input[placeholder="${{placeholder}}"]`);
            if (!input) return;
            input.setAttribute("type", "email");
            input.setAttribute("inputmode", "email");
            input.setAttribute("autocomplete", "email");
            input.classList.toggle(
              "dk-email-invalid",
              invalidPlaceholders.has(placeholder)
            );
            input.setAttribute(
              "aria-invalid",
              invalidPlaceholders.has(placeholder) ? "true" : "false"
            );
          }});

          doc.querySelectorAll('input[aria-label="Email"], input[aria-label="User email"]').forEach((input) => {{
            input.setAttribute("type", "email");
            input.setAttribute("inputmode", "email");
            input.setAttribute("autocomplete", "email");
          }});
        </script>
        """,
        height=0,
        width=0,
    )


def set_auth_tab(tab: str) -> None:
    st.session_state.auth_tab = tab


def render_auth_page() -> None:
    st.markdown(
        """
        <div class="dk-auth-shell">
          <h1>Knowledge Co-Pilot</h1>
          <p>● &nbsp; Your document assistant</p>
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
                ["Login", "Sign Up"],
                key="auth_tab",
                label_visibility="collapsed",
                width="stretch",
            )

            if auth_tab == "Login":
                st.caption("Log in to continue.")
                email = st.text_input(
                    "Email",
                    placeholder="name@example.com",
                    key="login_email",
                )
                login_email_invalid = render_email_error(
                    email,
                    submitted=bool(st.session_state.get("login_email_attempted")),
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="••••••••••••",
                    key="login_password",
                )
                submitted = st.button(
                    "Login",
                    type="primary",
                    use_container_width=True,
                    key="login-submit",
                )
                enhance_email_inputs(["name@example.com"] if login_email_invalid else [])
                if submitted:
                    if not is_valid_email(email):
                        st.session_state.login_email_attempted = True
                        st.rerun()
                    try:
                        with st.spinner("Logging in..."):
                            auth_response = login_user(email.strip(), password)
                        store_auth_session(auth_response)
                        st.rerun()
                    except requests.RequestException as error:
                        render_api_error(error)
                st.button(
                    "Don't have an account? Sign Up",
                    key="auth_show_signup",
                    use_container_width=True,
                    on_click=set_auth_tab,
                    args=("Sign Up",),
                )

            else:
                st.caption("Create your account to get started.")
                display_name = st.text_input(
                    "User name",
                    placeholder="Full name",
                    key="register_display_name",
                )
                email = st.text_input(
                    "User email",
                    placeholder="name@organization.ai",
                    key="register_email",
                )
                register_email_invalid = render_email_error(
                    email,
                    submitted=bool(st.session_state.get("register_email_attempted")),
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Minimum 8 characters",
                    key="register_password",
                )
                submitted = st.button(
                    "Sign Up",
                    type="primary",
                    use_container_width=True,
                    key="register-submit",
                )
                enhance_email_inputs(
                    ["name@organization.ai"] if register_email_invalid else []
                )
                if submitted:
                    if not is_valid_email(email):
                        st.session_state.register_email_attempted = True
                        st.rerun()
                    try:
                        with st.spinner("Signing up..."):
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
          <span><b>● App ready</b></span>
          <span>Secure connection · Saved session</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def handle_workspace_change() -> None:
    if st.session_state.get("active_page") == "Corpus Chat":
        st.session_state.pop("active_conversation_id", None)
    if st.session_state.get("active_page") == "Corpus Detail":
        st.session_state.upload_nonce = int(st.session_state.get("upload_nonce", 0)) + 1


def handle_corpus_change() -> None:
    st.session_state.pop("active_conversation_id", None)
    st.session_state.upload_nonce = int(st.session_state.get("upload_nonce", 0)) + 1
    st.session_state.blur_active_corpus_select = True


def blur_active_corpus_select() -> None:
    if not st.session_state.pop("blur_active_corpus_select", False):
        return
    components.html(
        """
        <script>
          setTimeout(() => {
            const doc = window.parent.document;
            const active = doc.activeElement;
            if (active && typeof active.blur === "function") active.blur();
            doc.querySelectorAll('[data-baseweb="popover"]').forEach((node) => {
              node.style.display = "none";
            });
          }, 80);
        </script>
        """,
        height=0,
        width=0,
    )


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
            blur_active_corpus_select()

        user = st.session_state.get("current_user", {})
        initial = escape(str(user.get("display_name", "U"))[:1].upper())
        st.markdown(
            f"""
            <div class="dk-user">
              <div class="dk-avatar">{initial}</div>
              <div>
                <strong>{escape(str(user.get("display_name", "User")))}</strong>
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
    description = str(corpus.get("description") or "").strip()
    storage_bytes = int(corpus.get("total_storage_bytes") or 0)
    updated_at = corpus.get("updated_at")
    updated_label = format_datetime(updated_at, "%d %b %Y") if updated_at else ""
    document_count = int(corpus["document_count"])
    document_label = f"{document_count} indexed document{'s' if document_count != 1 else ''}"
    meta_items = [
        f"<span>{escape(document_label)}</span>",
        f"<span>{escape(format_bytes(storage_bytes))}</span>",
    ]
    if updated_label:
        meta_items.append(f"<span>Updated {escape(updated_label)}</span>")

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="dk-corpus-card">
              <div class="dk-corpus-card__top">
                <h3>{escape(str(corpus["name"]))}</h3>
                {status_badge("Active")}
              </div>
              {f'<p>{escape(description)}</p>' if description else ''}
              <div class="dk-corpus-card__footer">
                {"".join(meta_items)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        open_action, delete_action = st.columns([1, 0.72])
        with open_action:
            st.button(
                "Open Workspace",
                key=f"open-corpus-{corpus['id']}-{index}",
                use_container_width=True,
                on_click=queue_navigation,
                args=("Corpus Detail", int(corpus["id"])),
            )
        with delete_action:
            with st.popover("⋮", use_container_width=True):
                st.button(
                    "Rename",
                    key=f"rename-corpus-card-{corpus['id']}-{index}",
                    use_container_width=True,
                    on_click=request_corpus_rename,
                    args=(int(corpus["id"]),),
                )
                st.button(
                    "🗑️ Delete",
                    key=f"delete-corpus-card-{corpus['id']}-{index}",
                    use_container_width=True,
                    on_click=request_corpus_delete,
                    args=(int(corpus["id"]),),
                )


def render_create_corpus(form_key: str) -> None:
    with st.container(border=True):
        st.markdown(
            """
            <div class="dk-create-corpus-card">
              <h2>Create New Corpus</h2>
              <p>Create a workspace for a set of related documents.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        name_key = f"{form_key}-name"
        description_key = f"{form_key}-description"
        name = st.text_input(
            "Corpus Name",
            placeholder="Project documents",
            key=name_key,
        )
        description = st.text_area(
            "Description",
            placeholder="What domain knowledge will this corpus contain?",
            key=description_key,
        )
        name_has_value = bool(name.strip())
        name_error = validate_corpus_name(name) if name_has_value else None
        name_is_valid = name_error is None
        if name_error:
            st.warning(name_error)
        if st.button(
            "Create Corpus",
            type="primary",
            use_container_width=True,
            disabled=not name_has_value or not name_is_valid,
            key=f"{form_key}-submit",
        ):
            try:
                created = create_corpus(name.strip(), description.strip())
                queue_navigation("Corpus Detail", int(created["id"]))
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)


def corpus_matches_search(corpus: dict[str, Any], query: str) -> bool:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return True
    searchable_text = " ".join(
        [
            str(corpus.get("name") or ""),
            str(corpus.get("description") or ""),
        ]
    ).lower()
    return normalized_query in searchable_text


def render_dashboard(corpora: list[dict[str, Any]]) -> None:
    page_header(
        "Knowledge workspace",
        "Corpus Dashboard",
        "Organize your documents and access them whenever you need.",
    )
    metric_grid(
        [
            ("Active corpora", str(len(corpora)), "Document workspaces", "primary"),
            (
                "Indexed documents",
                str(sum(int(c["document_count"]) for c in corpora)),
                "Across all corpora",
                "success",
            ),
        ]
    )

    render_create_corpus("create-corpus-dashboard-form")

    section_title("Existing Workspaces", f"{len(corpora)} total")
    if not corpora:
        empty_state(
            "No workspaces yet",
            "Create a new corpus to begin indexing documents.",
            "＋",
        )
        return

    search_query = st.text_input(
        "Search workspaces",
        placeholder="🔍 Search workspaces...",
        key="dashboard-corpus-search",
        label_visibility="collapsed",
    )
    filtered_corpora = [
        corpus for corpus in corpora if corpus_matches_search(corpus, search_query)
    ]

    if not filtered_corpora:
        empty_state(
            "No workspaces found.",
            "Try a different search term or create a new workspace.",
            "⌕",
        )
        return

    columns = st.columns(2)
    for index, corpus in enumerate(filtered_corpora):
        with columns[index % 2]:
            render_corpus_card(corpus, index)


def document_row(corpus_id: int, document: dict[str, Any]) -> None:
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
          <div class="dk-doc-stat"><label>Sections</label><span>{int(document["chunk_count"])}</span></div>
          <div class="dk-doc-stat"><label>Storage</label><span>{escape(format_bytes(int(document["file_size_bytes"])))}</span></div>
          <div>{status_badge(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(
        "👁 Preview",
        key=f"preview-document-{corpus_id}-{document['id']}",
        use_container_width=True,
        on_click=request_document_preview,
        args=(corpus_id, document),
    )


def storage_usage_metric(total_storage_bytes: int) -> tuple[str, str, str, Optional[str]]:
    if MAX_STORAGE_BYTES <= 0:
        return ("Storage", format_bytes(total_storage_bytes), "No storage limit", None)

    percentage = min((total_storage_bytes / MAX_STORAGE_BYTES) * 100, 100)
    return (
        "Storage",
        f"{format_bytes(total_storage_bytes)} / {format_bytes(MAX_STORAGE_BYTES)}",
        f"{percentage:.1f}% used",
        None,
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
        str(corpus.get("description") or "Domain knowledge corpus."),
    )
    total_storage_bytes = int(detail["total_storage_bytes"])
    metrics = [
        ("Documents", str(detail["total_documents"]), "Uploaded source files", "primary"),
        ("Pages", f'{int(detail["total_pages"]):,}', "Extracted and searchable", None),
        ("Search sections", f'{int(detail["total_embeddings"]):,}', "Ready for search", "success"),
        storage_usage_metric(total_storage_bytes),
    ]
    metric_grid(metrics)
    rename_action, delete_action = st.columns([0.18, 0.18])
    with rename_action:
        st.button(
            "Rename Corpus",
            key=f"rename-corpus-detail-{corpus['id']}",
            use_container_width=True,
            on_click=request_corpus_rename,
            args=(int(corpus["id"]),),
        )
    with delete_action:
        st.button(
            "🗑️ Delete Corpus",
            key=f"delete-corpus-detail-{corpus['id']}",
            use_container_width=True,
            on_click=request_corpus_delete,
            args=(int(corpus["id"]),),
        )

    inventory, action = st.columns([1.45, 1], gap="large")
    with inventory:
        section_title("Document inventory", f'{detail["total_documents"]} indexed')
        if detail["documents"]:
            for document in detail["documents"]:
                document_row(int(corpus["id"]), document)
        else:
            empty_state(
                "Corpus is waiting for source material",
                "Upload a text-based PDF to initialize retrieval.",
                "PDF",
            )

    with action:
        section_title("Add documents", "Upload PDFs")
        with st.container(border=True):
            st.markdown(
                """
                <h3 style="margin:.1rem 0 .35rem">Upload and Index Documents</h3>
                <p style="font-size:13px;margin:0 0 .8rem">
                  Upload PDF documents to make them searchable and available for
                  AI-powered chat and document comparison.
                </p>
                <p style="font-size:12px;margin:0 0 .8rem;color:#918fa1">
                  Supported format: PDF (.pdf)
                </p>
                """,
                unsafe_allow_html=True,
            )
            uploaded_pdf = st.file_uploader(
                "+ Upload PDF",
                type=["pdf"],
                accept_multiple_files=False,
                key=f"detail-upload-{corpus['id']}-{st.session_state.upload_nonce}",
            )
            if st.button(
                "Upload & Index",
                type="primary",
                use_container_width=True,
                disabled=uploaded_pdf is None,
            ):
                try:
                    with st.spinner("Uploading and indexing document..."):
                        document = upload_pdf(int(corpus["id"]), uploaded_pdf)
                    st.success(
                        f"{document['filename']} indexed into "
                        f"{document['chunk_count']} searchable sections."
                    )
                    st.session_state.upload_nonce += 1
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)


def render_citations(sources: list[dict[str, Any]]) -> None:
    if not sources:
        return
    st.markdown(
        f"""
        <div class="dk-section-title" style="margin:.9rem 0 .45rem">
          <h2 style="font-size:14px">Retrieved sources</h2>
          <span>{len(sources)} sources found</span>
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
                    <p>Source evidence</p>
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
                f"Section {source.get('chunk_reference', source.get('chunk_index'))}"
            )


def render_chat(corpora: list[dict[str, Any]]) -> None:
    corpus = selected_corpus(corpora)
    if corpus is None:
        page_header("Document chat", "Corpus Chat", "Ask questions about your documents.")
        empty_state("No active corpus", "Create and index a corpus before chatting.")
        return

    page_header(
        "Document chat",
        f"Chat with {corpus['name']}",
        "Answers use your uploaded documents and include page-level citations.",
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
                "most relevant sources before answering."
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
            with st.spinner("Finding sources and writing an answer..."):
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
        st.caption("No saved evidence for this statement.")
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
                  Page {int(citation.get("page", 0))} · Section {escape(str(citation.get("chunk", "unknown")))}
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
        st.markdown(
            f"""
            <div class="dk-simple-point">
              <span>•</span>
              <p>{escape(statement)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if evidence_item:
            with st.expander("View evidence", expanded=False):
                render_statement_evidence(evidence_item, statement)


def render_topic_tags(topics: list[Any]) -> None:
    if not topics:
        st.caption("No common topics returned.")
        return
    st.markdown(
        '<div class="dk-topic-tags">'
        + "".join(f"<span>{escape(str(topic))}</span>" for topic in topics)
        + "</div>",
        unsafe_allow_html=True,
    )


def comparison_topic_map(
    title: str,
    topic_map: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> None:
    if not topic_map:
        st.caption("No document-specific topics returned.")
        return
    columns = st.columns(2)
    for index, (document_name, topics) in enumerate(topic_map.items()):
        with columns[index % 2]:
            st.markdown(
                f"""
                <div class="dk-unique-topic-card">
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
            <h2>Step 2 · Comparison Summary</h2>
            <p>{escape(str(result.get("overall_summary") or "No summary returned."))}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    documents = result.get("documents", [])
    if documents:
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

    section_title("Step 3 · Key Differences")
    comparison_list(
        "Key differences",
        result.get("major_differences", []),
        evidence_items=evidence_items,
        key_prefix=f"major-{comparison_id}",
    )

    section_title("Step 4 · Common Topics")
    render_topic_tags(result.get("common_topics", []))

    section_title("Step 5 · Unique Topics")
    comparison_topic_map("Unique Topics", result.get("unique_topics", {}), evidence_items)

    section_title("Step 6 · Recommendation")
    beginner_document = result.get("beginner_document") or "Not specified"
    comprehensive_document = result.get("most_comprehensive_document") or "Not specified"
    st.markdown(
        f"""
        <div class="dk-recommendation-card">
          <div>
            <span>Best for Beginners</span>
            <h3>{escape(str(beginner_document))}</h3>
            <p>{escape(str(result.get("recommendation") or "No recommendation returned."))}</p>
          </div>
          <div>
            <span>Most Comprehensive</span>
            <h3>{escape(str(comprehensive_document))}</h3>
          </div>
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
          <h2 style="font-size:14px">Sources</h2>
          <span>{len(sections)} source sections</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for index, section in enumerate(sections, start=1):
        with st.expander(f"Source {index:02d}", expanded=False):
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
                f"Section {section.get('chunk_reference', 'unknown')}"
            )


def submit_comparison_question(comparison_id: int, question: str) -> None:
    try:
        with st.spinner("Finding the best sources..."):
            ask_comparison_question(comparison_id, question)
        st.session_state.pop("latest_comparison_result", None)
        st.session_state.active_comparison_id = comparison_id
        st.rerun()
    except requests.RequestException as error:
        render_api_error(error)


def render_comparison_chat(result: dict[str, Any]) -> None:
    comparison_id = int(result.get("id") or result.get("comparison_id"))
    section_title("Step 7 · Ask Questions")
    st.markdown(
        """
        <div class="dk-comparison-ask-shell">
          Ask follow-up questions about the documents in this comparison.
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
                f"Sources: {', '.join(support) if support else 'No specific source'}"
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
        "Documents",
        "Compare Documents",
        "Choose documents, compare what they cover, and ask follow-up questions.",
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

    if len(documents) < 2:
        empty_state(
            "At least two PDFs are required",
            "Upload another document in Corpus Detail to unlock comparison.",
            "≋",
        )
        return

    documents_by_id = {int(document["id"]): document for document in documents}

    section_title("Step 1 · Select Documents")
    with st.container(border=True):
        st.markdown(
            """
            <div class="dk-compare-select-card">
              <h3>Select documents to compare</h3>
              <p>Choose at least two PDFs. You can compare more if needed.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected_document_ids = st.multiselect(
            "Documents",
            options=[int(document["id"]) for document in documents],
            format_func=lambda document_id: (
                f"{documents_by_id[document_id]['filename']} · "
                f"{documents_by_id[document_id]['corpus_name']}"
            ),
            placeholder="Choose documents",
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
                with st.spinner("Comparing documents..."):
                    result = create_comparison(selected_document_ids)
                st.session_state.active_comparison_id = result["comparison_id"]
                st.session_state.latest_comparison_result = result
                st.rerun()
            except requests.RequestException as error:
                render_api_error(error)

    with st.expander("Previous Comparisons", expanded=False):
        if not comparisons:
            st.caption("No previous comparisons yet.")
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
        render_comparison_result(result)


def render_settings(corpora: list[dict[str, Any]]) -> None:
    user = st.session_state.get("current_user", {})
    page_header(
        "Account control",
        "Settings",
        "Manage your profile, interface behavior, and workspace preferences.",
    )

    profile, preferences = st.columns(2, gap="large")
    with profile:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Profile</div>', unsafe_allow_html=True)
            st.subheader("User identity")
            with st.form("profile-form"):
                display_name = st.text_input(
                    "Display name",
                    value=str(user.get("display_name", "")),
                )
                st.text_input(
                    "Email",
                    value=str(user.get("email", "")),
                    disabled=True,
                )
                submitted = st.form_submit_button(
                    "Save Profile",
                    type="primary",
                    use_container_width=True,
                )
            enhance_email_inputs([])
            if submitted:
                try:
                    updated = update_profile(display_name.strip())
                    st.session_state.current_user = updated
                    st.success("User profile updated.")
                    st.rerun()
                except requests.RequestException as error:
                    render_api_error(error)

        with st.container(border=True):
            st.markdown('<div class="dk-label">Workspace data</div>', unsafe_allow_html=True)
            st.subheader("Corpus footprint")
            st.caption("Documents and corpora available in your workspace.")
            metric_grid(
                [
                    ("Corpora", str(len(corpora)), "Workspaces", "primary"),
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
                        its documents, chat messages, and saved search data.
                      </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                confirm = st.checkbox(
                    f"I understand that deleting {corpus['name']} cannot be undone",
                    key=f"confirm-delete-{corpus['id']}",
                )
                st.button(
                    "Delete Active Corpus",
                    disabled=not confirm,
                    use_container_width=True,
                    on_click=request_corpus_delete,
                    args=(int(corpus["id"]),),
                    key=f"settings-delete-active-{corpus['id']}",
                )

    with preferences:
        with st.container(border=True):
            st.markdown('<div class="dk-label">Interface</div>', unsafe_allow_html=True)
            st.subheader("Interface preferences")
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

if st.session_state.get("renamed_corpus"):
    corpora = replace_corpus_in_list(corpora, st.session_state["renamed_corpus"])

apply_pending_navigation(corpora)
page = render_sidebar(corpora)
render_flash_messages()
render_pending_pdf_preview_dialog()
render_pending_corpus_rename_dialog(corpora)
render_pending_corpus_delete_dialog(corpora)

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
