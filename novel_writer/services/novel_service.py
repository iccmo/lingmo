"""NovelService — 小说业务逻辑，基于 SQLAlchemy + Pydantic。"""

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db_models import Novel, Chapter, Character, Faction, create_db_engine
from ..schemas import NovelCreate, NovelUpdate, NovelSummary, NovelDetail, ChapterResponse


class NovelService:
    """小说 CRUD 服务。注入 SQLAlchemy session."""

    def __init__(self, session: Session):
        self.session = session

    def list_novels(self, include_deleted: bool = False) -> list[NovelSummary]:
        stmt = select(Novel)
        if not include_deleted:
            stmt = stmt.where(Novel.deleted_at.is_(None))
        stmt = stmt.order_by(Novel.updated_at.desc())
        novels = self.session.execute(stmt).scalars().all()
        return [self._to_summary(n) for n in novels]

    def get_novel(self, novel_id: str) -> Optional[NovelDetail]:
        novel = self.session.get(Novel, novel_id)
        if not novel or novel.deleted_at:
            return None
        return self._to_detail(novel)

    def create_novel(self, data: NovelCreate) -> NovelDetail:
        novel = Novel(
            id=data.id,
            title=data.title,
            author=data.author,
            synopsis=data.synopsis,
            genre=data.genre,
            world_name=data.world_name,
            world_era=data.era,
            world_geo=data.geography,
            power_system=data.power_system,
        )
        self.session.add(novel)
        self.session.commit()
        return self._to_detail(novel)

    def update_novel(self, novel_id: str, data: NovelUpdate) -> Optional[NovelDetail]:
        novel = self.session.get(Novel, novel_id)
        if not novel or novel.deleted_at:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(novel, field, value)
        self.session.commit()
        self.session.refresh(novel)
        return self._to_detail(novel)

    def delete_novel(self, novel_id: str) -> bool:
        novel = self.session.get(Novel, novel_id)
        if not novel:
            return False
        from datetime import datetime
        novel.deleted_at = datetime.now().isoformat()
        self.session.commit()
        return True

    # ── Chapters ──

    def get_chapter(self, novel_id: str, chapter_num: int) -> Optional[ChapterResponse]:
        from ..schemas import ChapterResponse
        stmt = select(Chapter).where(
            Chapter.novel_id == novel_id,
            Chapter.number == chapter_num,
        )
        ch = self.session.execute(stmt).scalar_one_or_none()
        if not ch:
            return None
        return ChapterResponse(
            number=ch.number,
            title=ch.title,
            word_count=ch.word_count,
            summary=ch.summary or "",
            content=ch.content or "",
            ending_hook=ch.ending_hook or "",
            quality_score=ch.quality_score or 0,
            model_used=ch.model_used or "",
            generated_at=ch.generated_at,
        )

    def save_chapter(self, novel_id: str, chapter_num: int, content: str) -> Optional[ChapterResponse]:
        from ..schemas import ChapterResponse
        stmt = select(Chapter).where(
            Chapter.novel_id == novel_id,
            Chapter.number == chapter_num,
        )
        ch = self.session.execute(stmt).scalar_one_or_none()
        if not ch:
            return None
        ch.content = content
        ch.word_count = len(content.replace(" ", "").replace("\n", ""))
        self.session.commit()
        self.session.refresh(ch)
        return ChapterResponse(
            number=ch.number, title=ch.title, word_count=ch.word_count,
            summary=ch.summary or "", content=ch.content or "",
            ending_hook=ch.ending_hook or "", quality_score=ch.quality_score or 0,
            model_used=ch.model_used or "", generated_at=ch.generated_at,
        )

    def delete_chapter(self, novel_id: str, chapter_num: int):
        stmt = select(Chapter).where(
            Chapter.novel_id == novel_id,
            Chapter.number == chapter_num,
        )
        ch = self.session.execute(stmt).scalar_one_or_none()
        if ch:
            self.session.delete(ch)
            self.session.commit()
        return True

    def get_stats(self) -> dict:
        total_novels = self.session.execute(
            select(func.count()).select_from(Novel).where(Novel.deleted_at.is_(None))
        ).scalar() or 0
        total_chapters = self.session.execute(
            select(func.count()).select_from(Chapter).join(Novel).where(
                Novel.deleted_at.is_(None),
                Chapter.word_count > 0,
            )
        ).scalar() or 0
        total_words = self.session.execute(
            select(func.sum(Chapter.word_count)).select_from(Chapter).join(Novel).where(Novel.deleted_at.is_(None))
        ).scalar() or 0
        from datetime import datetime
        return {
            "novels_count": total_novels,
            "total_chapters": total_chapters,
            "total_words": total_words or 0,
            "server_time": datetime.now().isoformat(),
        }

    # ── Private ──

    def _to_summary(self, novel: Novel) -> NovelSummary:
        generated_chapters = sorted(
            (chapter for chapter in novel.chapters if chapter.word_count > 0),
            key=lambda chapter: chapter.number,
        )
        latest = generated_chapters[-1] if generated_chapters else None
        return NovelSummary(
            id=novel.id,
            title=novel.title,
            author=novel.author,
            genre=novel.genre,
            status=novel.status,
            mode=novel.mode,
            total_chapters=len(generated_chapters),
            total_words=sum(ch.word_count for ch in novel.chapters),
            created_at=novel.created_at,
            updated_at=novel.updated_at,
            latest_chapter={
                "number": latest.number,
                "title": latest.title,
                "generated_at": latest.generated_at,
            } if latest else None,
        )

    def _to_detail(self, novel: Novel) -> NovelDetail:
        generated_chapters = sorted(
            (chapter for chapter in novel.chapters if chapter.word_count > 0),
            key=lambda chapter: chapter.number,
        )
        latest = generated_chapters[-1] if generated_chapters else None
        return NovelDetail(
            id=novel.id,
            title=novel.title,
            author=novel.author,
            genre=novel.genre,
            status=novel.status,
            mode=novel.mode,
            synopsis=novel.synopsis,
            world_name=novel.world_name,
            world_era=novel.world_era,
            world_geo=novel.world_geo,
            power_system=novel.power_system,
            main_arc=novel.main_arc,
            current_arc=novel.current_arc,
            arc_chapter_start=novel.arc_chapter_start,
            total_chapters=len(generated_chapters),
            total_words=sum(ch.word_count for ch in novel.chapters),
            created_at=novel.created_at,
            updated_at=novel.updated_at,
            latest_chapter={
                "number": latest.number,
                "title": latest.title,
                "generated_at": latest.generated_at,
            } if latest else None,
            chapters=[self._chapter_to_dict(ch) for ch in novel.chapters],
            characters=[self._character_to_dict(c) for c in novel.characters],
            factions=[],
            character_relations=[],
        )

    @staticmethod
    def _chapter_to_dict(ch: Chapter) -> dict:
        return {
            "number": ch.number, "title": ch.title, "word_count": ch.word_count,
            "summary": ch.summary, "ending_hook": ch.ending_hook,
            "quality_score": ch.quality_score, "model_used": ch.model_used,
            "generated_at": ch.generated_at,
        }

    @staticmethod
    def _character_to_dict(c: Character) -> dict:
        return {
            "id": c.id, "char_key": c.char_key, "name": c.name,
            "role": c.role, "personality": c.personality,
            "background": c.background, "power_level": c.power_level,
            "status": c.status, "voice_data": c.voice_data,
        }


# ── Session factory ──

from sqlalchemy.orm import sessionmaker

_engine = create_db_engine()
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_session():
    """FastAPI Depends: yields a SQLAlchemy session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
