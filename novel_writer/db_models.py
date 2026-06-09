"""SQLAlchemy 2.0 ORM 模型 — 全部数据表。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ═══ Core ═══

class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, default="AI")
    synopsis: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(Text, default="玄幻")
    status: Mapped[str] = mapped_column(Text, default="draft")
    mode: Mapped[str] = mapped_column(Text, default="creator")
    world_name: Mapped[str] = mapped_column(Text, default="")
    world_era: Mapped[str] = mapped_column(Text, default="")
    world_geo: Mapped[str] = mapped_column(Text, default="")
    power_system: Mapped[str] = mapped_column(Text, default="")
    world_rules: Mapped[str] = mapped_column(Text, default="[]")
    main_arc: Mapped[str] = mapped_column(Text, default="")
    current_arc: Mapped[str] = mapped_column(Text, default="开篇")
    arc_chapter_start: Mapped[int] = mapped_column(Integer, default=1)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    deleted_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="novel", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("novel_id", "number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    ending_hook: Mapped[str] = mapped_column(Text, default="")
    key_events: Mapped[str] = mapped_column(Text, default="[]")
    revelations: Mapped[str] = mapped_column(Text, default="[]")
    narrative_facts: Mapped[str] = mapped_column(Text, default="[]")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    model_used: Mapped[str] = mapped_column(Text, default="")
    prompt_version: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    generation_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    edit_ratio: Mapped[float] = mapped_column(Float, default=0)
    generated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    novel = relationship("Novel", back_populates="chapters")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("novel_id", "char_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    char_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, default="配角")
    personality: Mapped[str] = mapped_column(Text, default="")
    background: Mapped[str] = mapped_column(Text, default="")
    power_level: Mapped[str] = mapped_column(Text, default="")
    secrets: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(Text, default="alive")
    voice_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())

    novel = relationship("Novel", back_populates="characters")


# ═══ World ═══

class Faction(Base):
    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    leader: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CharacterRelation(Base):
    __tablename__ = "character_relations"
    __table_args__ = (UniqueConstraint("novel_id", "c1_name", "c2_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    c1_name: Mapped[str] = mapped_column(Text, nullable=False)
    c2_name: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)


# ═══ Generation ═══

class ChapterDraft(Base):
    __tablename__ = "chapter_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"))
    draft_label: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[str] = mapped_column(Text, default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    is_selected: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())


class ChapterTrace(Base):
    __tablename__ = "chapter_traces"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_num"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_num: Mapped[int] = mapped_column(Integer, nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    final_quality: Mapped[float] = mapped_column(Float, default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    genre: Mapped[str] = mapped_column(Text, default="玄幻")
    writer_voice: Mapped[str] = mapped_column(Text, default="")
    emotional_budget: Mapped[str] = mapped_column(Text, default="{}")
    rhythm_mode: Mapped[str] = mapped_column(Text, default="")
    gap_rule: Mapped[str] = mapped_column(Text, default="")
    central_question: Mapped[str] = mapped_column(Text, default="")
    soul_statement: Mapped[str] = mapped_column(Text, default="")
    target_platform: Mapped[str] = mapped_column(Text, default="fanqie")


# ═══ Cost ═══

class CostLog(Base):
    __tablename__ = "cost_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(Text, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    purpose: Mapped[str] = mapped_column(Text, default="generate")
    created_at: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())


# ═══ Config ═══

class ModelProvider(Base):
    __tablename__ = "model_providers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, default="")
    api_key: Mapped[str] = mapped_column(Text, default="")
    models: Mapped[str] = mapped_column(Text, default="[]")
    is_enabled: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=10)


# ═══ Engine factory ═══

def create_db_engine(db_path: str = "data/novel_writer.db"):
    """Create SQLAlchemy engine with WAL mode."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    # Enable WAL on each connection
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute("PRAGMA journal_size_limit=52428800")
    return engine
