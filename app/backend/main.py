from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.backend.config import settings
from app.backend.routers import (
    art_reviews,
    assets,
    brand_integrations,
    cloud_runtime,
    concept_generator,
    concepts,
    dashboard,
    dinkly_agent,
    examples,
    failures,
    generation_engine,
    health,
    knowledge,
    memory,
    prompt_templates,
    prompts,
    slack,
    social_intelligence,
    social_learning,
    sprite_animations,
    sprite_compositions,
    sprite_exports,
    sprites,
    story_library,
)
from app.backend.routers import (
    settings as settings_router,
)
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.social_intelligence_scheduler import SocialIntelligenceScheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    if settings.app_mode == "cloud":
        # Cloud scheduling is event-driven. A platform scheduler calls the
        # authenticated enqueue endpoints; no laptop-style polling loop runs.
        yield
        return
    social_scheduler = SocialIntelligenceScheduler(social_intelligence.service)

    async def social_schedule_loop() -> None:
        while True:
            with suppress(Exception):
                await asyncio.to_thread(social_scheduler.run_due)
            await asyncio.sleep(60)

    application.state.social_intelligence_scheduler_task = asyncio.create_task(social_schedule_loop())
    try:
        yield
    finally:
        application.state.social_intelligence_scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await application.state.social_intelligence_scheduler_task


app = FastAPI(
    title="DINKLY Generation Engine API",
    description="Character-locked DINKLY concept-to-approval production API.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        list(settings.allowed_origins)
        if settings.app_mode == "cloud"
        else sorted({*settings.allowed_origins, "http://127.0.0.1:3000", "http://localhost:3000"})
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router,
    cloud_runtime.router,
    assets.router,
    memory.router,
    dashboard.router,
    dinkly_agent.router,
    slack.router,
    concepts.router,
    concept_generator.router,
    concept_generator.compatibility_router,
    prompts.router,
    prompt_templates.router,
    art_reviews.router,
    social_learning.router,
    social_intelligence.router,
    story_library.router,
    examples.router,
    failures.router,
    generation_engine.router,
    brand_integrations.router,
    knowledge.router,
    settings_router.router,
    sprites.router,
    sprite_animations.router,
    sprite_exports.router,
    sprite_compositions.router,
):
    app.include_router(router)

app.mount("/sprite-assets", StaticFiles(directory=settings.sprites_dir), name="sprite-assets")
app.mount(
    "/generation-assets",
    StaticFiles(directory=settings.generation_engine_dir),
    name="generation-assets",
)


@app.exception_handler(RepositoryError)
async def repository_error(_: Request, exc: RepositoryError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/search", tags=["search"])
def search(q: str = "") -> list[dict]:
    route_map = {
        "concept": "/concepts",
        "social post": "/social-learning",
        "learning": "/social-learning",
        "prompt": "/prompt-builder",
        "sprite animation": "/sprite-studio",
        "knowledge": "/knowledge",
        "example": "/examples",
    }
    return [
        {
            "type": item["kind"],
            "title": str(item.get("title", "Untitled")),
            "excerpt": str(item.get("source", "")),
            "href": route_map.get(item["kind"], "/"),
        }
        for item in RepositoryService().search(q)
    ]
