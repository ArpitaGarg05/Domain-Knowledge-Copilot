from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.init_db import run_migrations
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===== Application startup: version=%s =====", settings.app_version)

    logger.info("Calling run_migrations()")
    run_migrations()

    logger.info("run_migrations() finished")

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title="Domain Knowledge Copilot API",
    lifespan=lifespan,
)
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


@app.get("/")
def root():
    return {
        "name": "Domain Knowledge Copilot API",
        "status": "ok",
        "health": "/health",
        "version": settings.app_version,
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": settings.app_version}
