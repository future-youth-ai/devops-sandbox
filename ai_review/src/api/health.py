"""健康检查路由."""

from __future__ import annotations

from fastapi import APIRouter

from src import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """liveness probe - 进程是否存活."""
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """readiness probe - 是否可以接受流量 (当前: 和 liveness 相同)."""
    return {"status": "ready", "version": __version__}
