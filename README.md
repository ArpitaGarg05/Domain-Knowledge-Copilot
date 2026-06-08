# Domain Knowledge Co-Pilot

Domain Knowledge Co-Pilot is a RAG-powered application that enables users to upload and organize documents into custom corpora, then ask questions in natural language. Using semantic search, vector embeddings, and LLMs, it delivers accurate, context-aware answers with source citations from the uploaded documents.

## Structure

```text
frontend/
backend/
docs/
```

## Development

Backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
streamlit run app.py
```
