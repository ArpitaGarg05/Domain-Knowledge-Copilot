# from fastapi import FastAPI

# from app.api.routes import router as api_router

# app = FastAPI(title="Domain Knowledge Copilot API")

# app.include_router(api_router)

print("Starting import of routes")

from app.api.routes import router as api_router

print("Routes imported successfully")

from fastapi import FastAPI

app = FastAPI(title="Domain Knowledge Copilot API")

print("FastAPI app created")

app.include_router(api_router)

print("Router included")