from fastapi import FastAPI
from app.api.routes import router as api_router

print("USING FULL API VERSION")
app = FastAPI(title="Domain Knowledge Copilot API")

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "healthy"}