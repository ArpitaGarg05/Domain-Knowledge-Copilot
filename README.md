# Domain Knowledge Copilot

Domain Knowledge Copilot is a document intelligence application that allows authenticated users to create document workspaces, upload PDF files, ask grounded questions, inspect citations, review chat history, and compare multiple PDFs. The project is designed as an academic capstone submission for the New Age Software Engineering Program by iHUB DivyaSampark.

## Problem Statement

Students, researchers, and professionals often manage large collections of PDF documents. Finding precise information across those documents is time-consuming, and generic AI chat tools may answer without source grounding. This project addresses the need for a workspace-based assistant that retrieves relevant document sections before generating answers and exposes supporting evidence to the user.

## Objectives

- Provide secure user accounts with isolated document workspaces.
- Enable PDF upload, text extraction, chunking, embedding, and indexing.
- Support retrieval-augmented question answering over uploaded PDFs.
- Display page-level citations and expandable evidence.
- Preserve previous conversations for later access.
- Provide an advanced PDF comparison workflow for two or more documents.
- Keep the user interface approachable through a dark, professional productivity-style design.

## Key Features

- Email/password sign up and login.
- Persistent session restoration through a frontend auth cookie.
- Corpus dashboard with workspace creation, search, and summary metrics.
- PDF upload and indexing.
- Per-corpus chat with retrieved sources.
- Conversation history with corpus filtering and resume behavior.
- Multi-document PDF comparison.
- Comparison follow-up questions across selected documents.
- Evidence cards with document, page, section, similarity score, and relevant paragraph.
- Settings for user profile and interface preferences.

## System Overview

The application has a Streamlit frontend and a FastAPI backend. The backend stores relational data with SQLAlchemy, manages migrations with Alembic, stores PDF files on disk, stores vectors in ChromaDB, and uses Groq for LLM responses. Embeddings default to a deterministic hash-based backend, with optional Sentence Transformers support.

```mermaid
flowchart LR
    User["User"] --> UI["Streamlit Frontend"]
    UI --> API["FastAPI Backend"]
    API --> DB["SQLite/PostgreSQL"]
    API --> Files["Uploaded PDFs"]
    API --> Extract["PDF Extraction + Chunking"]
    Extract --> Embed["Embedding Service"]
    Embed --> Chroma["ChromaDB Vector Store"]
    API --> Groq["Groq LLM"]
    Chroma --> API
    Groq --> API
    API --> UI
```

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit, Requests, extra-streamlit-components |
| Backend | FastAPI, Uvicorn, Pydantic |
| Database | SQLAlchemy, Alembic, SQLite default, PostgreSQL supported |
| Authentication | Custom HMAC-signed JWT-style bearer token, PBKDF2 password hashing |
| PDF Processing | pypdf |
| Chunking | Character-based overlapping chunks |
| Embeddings | Hash embeddings by default; optional Sentence Transformers |
| Vector Database | ChromaDB persistent collections |
| LLM | Groq SDK, default model `llama-3.3-70b-versatile` |
| Deployment Config | `backend/render.yaml`; Railway-compatible environment variables |

## Architecture Overview

The backend follows a layered structure:

- API routes validate requests and enforce user ownership.
- CRUD modules perform database operations.
- Services encapsulate PDF extraction, chunking, embeddings, vector retrieval, LLM prompts, and comparison logic.
- SQLAlchemy models define relational persistence.
- Alembic migrations evolve the schema.

The frontend is a single Streamlit application with page-level render functions for dashboard, corpus detail, corpus chat, comparison, history, and settings.

## Installation

```bash
git clone <repository-url>
cd Domain-Knowledge-Copilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | No | `sqlite:///./domain_knowledge_copilot.db` | SQLAlchemy database URL. Use PostgreSQL in production. |
| `GROQ_API_KEY` | Yes for LLM answers | None | API key for Groq completion requests. |
| `JWT_SECRET_KEY` | Yes in production | `development-only-change-me` | Secret used to sign tokens. |
| `EMBEDDING_BACKEND` | No | `hash` | Use `hash` or `sentence-transformers`. |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Sentence Transformer model name when enabled. |
| `BACKEND_URL` | Frontend | `http://localhost:8000` | Backend API base URL used by Streamlit. |
| `AUTH_COOKIE_SECURE` | Production recommended | false | Enables secure auth cookie behavior in HTTPS deployments. |
| `MAX_STORAGE_BYTES` | Frontend optional | 2 GB | Display limit for storage usage cards. |

## Running Backend

```bash
cd backend
export GROQ_API_KEY="your-groq-api-key"
export JWT_SECRET_KEY="replace-with-a-secure-secret"
uvicorn app.main:app --reload
```

The backend is available at `http://localhost:8000`.

## Running Frontend

```bash
cd frontend
export BACKEND_URL="http://localhost:8000"
streamlit run app.py
```

The frontend usually opens at `http://localhost:8501`.

## Database Setup

The backend runs migration logic during FastAPI startup. For manual migration:

```bash
cd backend
alembic upgrade head
```

Fresh databases are created from SQLAlchemy metadata and stamped at Alembic head. Existing databases are upgraded through Alembic. PostgreSQL startup uses an advisory lock to reduce concurrent migration conflicts.

## API Overview

Most endpoints require `Authorization: Bearer <access_token>`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Login |
| `GET` | `/auth/me` | Return current user |
| `PATCH` | `/auth/profile` | Update display name |
| `GET` | `/corpora` | List user corpora |
| `POST` | `/corpora` | Create corpus |
| `DELETE` | `/corpora/{corpus_id}` | Delete corpus |
| `GET` | `/corpora/{corpus_id}/documents` | List documents and corpus metrics |
| `POST` | `/corpora/{corpus_id}/upload` | Upload and index PDF |
| `POST` | `/search` | Retrieve relevant chunks |
| `POST` | `/answer` | Generate grounded answer |
| `GET` | `/history` | Retrieve chat history |
| `POST` | `/comparisons` | Compare multiple documents |
| `GET` | `/comparisons` | List comparisons |
| `GET` | `/comparisons/{id}` | Get comparison details |
| `POST` | `/comparisons/{id}/ask` | Ask questions across compared documents |

## Folder Structure

```text
.
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI routes and dependencies
│   │   ├── core/             # Config and security
│   │   ├── crud/             # Data access functions
│   │   ├── db/               # Engine, sessions, migration startup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic request/response models
│   │   └── services/         # PDF, chunking, embedding, vector, LLM, comparison
│   ├── render.yaml
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Streamlit application
│   ├── styles.py             # Design system CSS and UI helpers
│   └── requirements.txt
└── docs/
```

## Screenshots

Add screenshots before submission:

- `screenshots/login.png`
- `screenshots/corpus-dashboard.png`
- `screenshots/corpus-detail.png`
- `screenshots/corpus-chat.png`
- `screenshots/compare-documents.png`
- `screenshots/chat-history.png`
- `screenshots/settings.png`

## Future Scope

- OCR support for scanned PDFs.
- Streaming LLM responses.
- Role-based team workspaces.
- Exportable chat and comparison reports.
- Dedicated evaluation dashboard for answer quality.
- Stronger semantic evaluation metrics.
- Object storage for uploaded files in production.
- Managed vector database deployment.

## Contributors

- Ayushman Rathi
- New Age Software Engineering Program by iHUB DivyaSampark

## License

Unable to determine from the repository. Add a `LICENSE` file before public release.

## Documentation Index

See [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) for the complete generated documentation package.
