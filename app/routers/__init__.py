# File: /workspace/routers/__init__.py

from fastapi import APIRouter

router = APIRouter()

from app.routers.projects import router as projects_router
from app.routers.legacy import router as legacy_router

router.include_router(projects_router, prefix="/api/projects", tags=["projects"])
router.include_router(legacy_router, prefix="/legacy", tags=["legacy"])
