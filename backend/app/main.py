import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.database import SessionLocal
from app.jobs.runner import JobRunner
from app.logging_setup import configure_logging
from app.models import ProviderCatalog
from app.providers.base import ProviderError
from app.providers.registry import build_registry
from app.routes import assets, jobs, presets, projects, providers, workflow, concepts, exports, gallery
from app.schemas import HealthResponse

configure_logging()


def load_saved_catalogues(registry) -> None:
    """Restore model lists fetched from provider APIs, so a restart keeps what was saved."""
    log = logging.getLogger("app.providers")
    with SessionLocal() as db:
        for row in db.query(ProviderCatalog):
            try:
                registry.get(row.provider).apply_catalogue(row.items or [])
            except ProviderError as exc:
                log.warning("skipped saved catalogue for %s: %s", row.provider, exc.code)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(follow_redirects=False) as client:
        app.state.http = client
        app.state.registry = build_registry(client)
        load_saved_catalogues(app.state.registry)
        app.state.runner = None
        if config.JOBS_AUTOSTART:
            runner = JobRunner(
                SessionLocal,
                app.state.registry,
                assets.storage,
                concurrency=config.JOB_CONCURRENCY,
                backoff_base=config.JOB_BACKOFF_BASE_SECONDS,
                poll_interval=config.JOB_POLL_INTERVAL_SECONDS,
                poll_timeout=config.JOB_POLL_TIMEOUT_SECONDS,
                tick=config.JOB_TICK_SECONDS,
            )
            await runner.start()
            app.state.runner = runner
        try:
            yield
        finally:
            if app.state.runner is not None:
                await app.state.runner.stop()


app = FastAPI(
    title="Character Studio API",
    description="Transform photos into stylized 3D characters",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(assets.router)
app.include_router(providers.router)
app.include_router(presets.router)
app.include_router(jobs.router)
app.include_router(workflow.router)
app.include_router(concepts.router)
app.include_router(exports.router)
app.include_router(gallery.router)


@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "message": "Character Studio API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", 8000)))
