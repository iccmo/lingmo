"""Pydantic v2 请求/响应 Schema — FastAPI 自动生成 OpenAPI 文档。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ═══ Novel ═══

class NovelCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(..., min_length=1)
    author: str = "AI"
    synopsis: str = ""
    genre: str = "玄幻"
    total_chapters: int = Field(default=0, ge=0, le=2000)
    world_name: str = ""
    era: str = ""
    geography: str = ""
    power_system: str = ""


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    world_name: Optional[str] = None
    world_era: Optional[str] = None
    world_geo: Optional[str] = None
    power_system: Optional[str] = None
    main_arc: Optional[str] = None
    current_arc: Optional[str] = None


class NovelSummary(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    status: str
    mode: str
    total_chapters: int
    total_words: int
    created_at: str
    updated_at: str
    latest_chapter: Optional[dict] = None

    model_config = {"from_attributes": True}


class NovelDetail(NovelSummary):
    synopsis: str = ""
    world_name: str = ""
    world_era: str = ""
    world_geo: str = ""
    power_system: str = ""
    main_arc: str = ""
    current_arc: str = ""
    arc_chapter_start: int = 1
    chapters: list[dict] = []
    characters: list[dict] = []
    factions: list[dict] = []
    character_relations: list[dict] = []


# ═══ Chapter ═══

class ChapterCreate(BaseModel):
    number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    content: str = ""


class ChapterUpdate(BaseModel):
    content: str
    title: Optional[str] = None


class ChapterResponse(BaseModel):
    number: int
    title: str
    word_count: int = 0
    summary: str = ""
    content: str = ""
    ending_hook: str = ""
    quality_score: float = 0
    model_used: str = ""
    generated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ═══ Generation ═══

class GenerateRequest(BaseModel):
    quality_threshold: float = Field(default=0.78, ge=0.5, le=1.0)
    direction: str = ""
    compression: str = "L1"
    soul_injection: str = ""


class GenerateBatchRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    quality_threshold: float = Field(default=0.8, ge=0.5, le=1.0)


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    count: int = 0
    next_chapter: int = 0


class QueueStatus(BaseModel):
    job_id: Optional[str] = None
    status: str = "idle"
    progress: dict = Field(default_factory=lambda: {"current": 0, "total": 0})
    last_error: Optional[str] = None

    model_config = {"extra": "allow"}


class GenStatus(BaseModel):
    status: str
    message: str = ""
    progress: int = 0
    overall: Optional[float] = None
    stream_content: Optional[str] = None
    grade: Optional[str] = None
    quality_detail: Optional[dict] = None


# ═══ Export ═══

class ExportRequest(BaseModel):
    format: str = Field(default="txt", pattern="^(txt|json|epub|pdf|mobi)$")


# ═══ Characters & World ═══

class CharacterCreate(BaseModel):
    char_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role: str = "配角"
    personality: str = ""
    background: str = ""
    power_level: str = ""


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    power_level: Optional[str] = None
    status: Optional[str] = None


class FactionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    leader: str = ""
    sort_order: int = 0


class FactionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    leader: Optional[str] = None
    sort_order: Optional[int] = None


# ═══ System ═══

class SystemStatus(BaseModel):
    novels_count: int = 0
    total_chapters: int = 0
    total_words: int = 0
    server_time: str = ""


class ProviderUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[list[str]] = None
    is_enabled: Optional[int] = None
    priority: Optional[int] = None


class ProviderTestResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


class MessageResponse(BaseModel):
    ok: bool = True
    message: str = ""
