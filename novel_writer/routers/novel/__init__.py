"""小说路由包。"""

from fastapi import APIRouter

from ._legacy import router as legacy_router
from .agent_diagnostics import router as agent_diagnostics_router
from .agent_pipeline import router as agent_pipeline_router
from .analytics import router as analytics_router
from .backup import router as backup_router
from .chapters import router as chapters_router
from .constraints import router as constraints_router
from .core import router as core_router
from .drafts import router as drafts_router
from .exports import router as exports_router
from .foreshadowing import router as foreshadowing_router
from .generation import router as generation_router
from .imports import router as imports_router
from .orchestration import router as orchestration_router
from .publish import router as publish_router
from .quality import router as quality_router
from .revision import router as revision_router
from .story_world import router as story_world_router

router = APIRouter()
router.include_router(agent_diagnostics_router)
router.include_router(agent_pipeline_router)
router.include_router(analytics_router)
router.include_router(backup_router)
router.include_router(chapters_router)
router.include_router(constraints_router)
router.include_router(core_router)
router.include_router(drafts_router)
router.include_router(exports_router)
router.include_router(foreshadowing_router)
router.include_router(generation_router)
router.include_router(imports_router)
router.include_router(orchestration_router)
router.include_router(publish_router)
router.include_router(quality_router)
router.include_router(revision_router)
router.include_router(story_world_router)
router.include_router(legacy_router)

__all__ = ["router"]
