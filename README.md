# Domain Knowledge Copilot

Domain Knowledge Copilot is a multi-user retrieval-augmented generation (RAG)
application for chatting with private collections of PDF documents. Users can
create corpora, upload PDFs, run semantic searches, and receive grounded
answers with page-level source citations.

The application consists of a FastAPI backend and a Streamlit frontend. It uses
SQLAlchemy for application data, ChromaDB for vector retrieval, and Groq for
answer generation.

## Features

- Email/password registration and JWT-based authentication
- User-owned, isolated document corpora
- PDF upload and page-by-page text extraction
- Overlapping text chunking with stored embedding metadata
- Persistent, per-corpus ChromaDB vector collections
- Semantic search over uploaded documents
- Groq-powered answers constrained to retrieved sources
- Page, filename, and chunk citations for generated answers
- Per-user and per-corpus chat history
- SQLite for local development and PostgreSQL support for deployment

## How it works

```mermaid
flowchart LR
    U["User"] --> F["Streamlit UI"]
    F --> A["FastAPI API"]
    A --> DB["SQLite or PostgreSQL"]
    A --> P["PDF extraction and chunking"]
    P --> E["Embedding service"]
    E --> C["ChromaDB"]
    A --> C
    C --> A
    A --> G["Groq LLM"]
    G --> A
    A --> F
```

When a PDF is uploaded, the backend extracts text with `pypdf`, splits each
page into overlapping chunks, creates embeddings, and writes the vectors to a
Chroma collection dedicated to that corpus. At question time, the same
embedding backend encodes the query, Chroma returns the nearest chunks, and
the backend sends those chunks plus recent conversation history to Groq. The
answer and its retrieved sources are then saved to chat history.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit, Requests |
| API | FastAPI, Uvicorn, Pydantic |
| Authentication | Signed JWT-style bearer tokens, PBKDF2 password hashing |
| Relational data | SQLAlchemy, Alembic, SQLite/PostgreSQL |
| PDF processing | pypdf |
| Embeddings | Built-in hash embeddings or Sentence Transformers |
| Vector store | ChromaDB |
| Answer generation | Groq (`llama-3.3-70b-versatile`) |

## Repository structure

```text
.
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI routes and dependencies
│   │   ├── core/             # Configuration and security
│   │   ├── crud/             # Database operations
│   │   ├── db/               # Engine, sessions, and migration startup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Request and response models
│   │   └── services/         # PDF, chunking, embeddings, retrieval, and LLM
│   ├── render.yaml           # Render backend service definition
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Streamlit application
│   └── requirements.txt
└── docs/
```

## Prerequisites

- Python 3.10 or newer
- A [Groq API key](https://console.groq.com/keys) for generated answers
- PostgreSQL only if you do not want to use the default local SQLite database

The default hash embedding backend works without downloading a model. To use
Sentence Transformers, the selected model must be downloaded on first use
unless it is already cached.

## Local setup

Clone the repository and create a virtual environment:

```bash
git clone <repository-url>
cd Domain-Knowledge-Copilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt -r frontend/requirements.txt
```

Configure the backend environment:

```bash
export GROQ_API_KEY="your-groq-api-key"
export JWT_SECRET_KEY="replace-with-a-long-random-secret"
```

Optional configuration:

```bash
# Defaults to sqlite:///./domain_knowledge_copilot.db
export DATABASE_URL="postgresql+psycopg://user:password@localhost/copilot"

# "hash" is the default; use "sentence-transformers" for model embeddings
export EMBEDDING_BACKEND="sentence-transformers"
export EMBEDDING_MODEL="all-MiniLM-L6-v2"
```

Start the backend from the `backend` directory:

```bash
cd backend
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`, with interactive
documentation at `http://localhost:8000/docs`. On startup, the backend creates
a fresh schema or applies pending Alembic migrations automatically.

In a second terminal, activate the same environment and start the frontend:

```bash
cd frontend
export BACKEND_URL="http://localhost:8000"
streamlit run app.py
```

Streamlit normally opens the application at `http://localhost:8501`.

## Using the application

1. Register a new account or sign in.
2. Open **Corpus Settings** and create a corpus.
3. Select the corpus and upload one or more text-based PDF files from the
   dashboard.
4. Open **Corpus Chat** and ask questions about the uploaded material.
5. Expand the retrieved sources beneath an answer to inspect its citations.

> [!NOTE]
> PDF extraction is text-only. Scanned PDFs require OCR before upload.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | For answers | None | Authenticates requests to Groq |
| `JWT_SECRET_KEY` | Production | Development-only value | Signs authentication tokens |
| `DATABASE_URL` | No | `sqlite:///./domain_knowledge_copilot.db` | SQLAlchemy database URL |
| `EMBEDDING_BACKEND` | No | `hash` | `hash` or `sentence-transformers` |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Sentence Transformer model name |
| `BACKEND_URL` | No | `http://localhost:8000` | Backend URL used by Streamlit |

The backend also creates two local persistence directories relative to its
working directory:

- `uploads/` stores uploaded PDF files.
- `chroma/` stores persistent ChromaDB collections.

Both directories, local database files, virtual environments, and environment
files are excluded by `.gitignore`.

## API overview

All routes except the root, health checks, registration, and login require an
`Authorization: Bearer <token>` header.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/auth/register` | Create a user and return an access token |
| `POST` | `/auth/login` | Authenticate and return an access token |
| `PATCH` | `/auth/profile` | Update the current user's display name |
| `GET` | `/corpora` | List the current user's corpora |
| `POST` | `/corpora` | Create a corpus |
| `DELETE` | `/corpora/{corpus_id}` | Delete a corpus and its vector collection |
| `GET` | `/corpora/{corpus_id}/documents` | List indexed documents and corpus statistics |
| `POST` | `/corpora/{corpus_id}/upload` | Upload and index a PDF |
| `POST` | `/search` | Return semantically similar chunks |
| `POST` | `/answer` | Generate a grounded answer with sources |
| `GET` | `/history` | Return the current user's chat history |

Example authenticated search:

```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"corpus_id": 1, "question": "What are the key findings?", "limit": 5}'
```

## Data model

- A `User` owns many `Corpus` records.
- A `Corpus` contains documents and chat messages.
- A `Document` stores upload metadata, extracted pages, and text chunks.
- Each `DocumentChunk` has one persisted embedding record.
- Each assistant `ChatMessage` stores the citations used for its answer.

Deleting a corpus cascades through its relational records and also removes its
Chroma collection.

## Database migrations

Migrations run automatically when the FastAPI application starts. They can
also be run manually:

```bash
cd backend
python -m alembic upgrade head
```

Set `DATABASE_URL` before running the command when targeting PostgreSQL.

## Deployment notes

`backend/render.yaml` contains a Render web service definition that installs
the CPU build of PyTorch, installs backend dependencies, applies migrations,
and starts Uvicorn.

For a production deployment:

- Set `DATABASE_URL`, `GROQ_API_KEY`, and a strong `JWT_SECRET_KEY`.
- Attach persistent storage for `uploads/` and `chroma/`; otherwise uploaded
  files and vector indexes may be lost when an instance is replaced.
- Set `BACKEND_URL` in the frontend to the public API URL.
- Add the deployed frontend origin to the backend CORS allowlist in
  `backend/app/main.py`.
- Keep `EMBEDDING_BACKEND` consistent after documents have been indexed.
  Query vectors must have the same dimensions as stored vectors.

## Current limitations

- Only PDF uploads are supported.
- Scanned documents are not OCR-processed.
- Corpus editing and visibility controls in the Streamlit settings page are
  placeholders.
- File uploads and ChromaDB are stored on the local filesystem.
- There is currently no automated test suite.
