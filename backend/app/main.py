"""FastAPI entry point:  uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logger import get_logger
from app.services.runs import RunService

log = get_logger("main")


def create_app(run_service: RunService | None = None) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runs = run_service or RunService(settings=settings)
        s = app.state.runs.settings
        log.info("PromptForge ready: %d models, mock=%s, strategy=%s",
                 len(app.state.runs.llm.catalog.models), s.mock_enabled, s.ROUTING_STRATEGY)
        yield

    app = FastAPI(
        title="PromptForge AI",
        version="1.0.0",
        description="Autonomous multi-agent code generation with telemetry-driven LLM routing "
                    "and a self-repairing test pipeline.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/")
    async def root():
        return {"name": "PromptForge AI", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
