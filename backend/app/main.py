# from fastapi import FastAPI

# from app.api.routes import router as api_router

# app = FastAPI(title="Domain Knowledge Copilot API")

# app.include_router(api_router)

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}