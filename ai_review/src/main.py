"""FastAPI 应用入口."""

from __future__ import annotations

from fastapi import FastAPI

from src import __version__
from src.api import health, review


def create_app() -> FastAPI:
    app = FastAPI(
        title="ai-review",
        description="政府项目文档智能审核系统 - 骨架版本",
        version=__version__,
    )
    app.include_router(health.router)
    app.include_router(review.router)
    return app


app = create_app()
