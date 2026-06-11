from fastapi import FastAPI
from app.api.routes import router as api_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Domain Knowledge Copilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://corpusiq.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "healthy"}