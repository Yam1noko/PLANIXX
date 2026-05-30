from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text, cast, or_, select

from backend.db.database import AsyncSessionLocal
from backend.models.agent import MemoryCandidate, TaskDraft, UserMemory, UserTaskPattern


ACTIVE_DRAFT_STATUSES = (
    "draft",
    "needs_clarification",
    "validated",
    "preview_ready",
)


class AgentToolRepository:
    async def get_active_draft(
        self,
        user_id: str,
        *,
        conversation_id: str | None = None,
    ) -> TaskDraft | None:
        async with AsyncSessionLocal() as session:
            statement = select(TaskDraft).where(
                TaskDraft.user_id == user_id,
                TaskDraft.status.in_(ACTIVE_DRAFT_STATUSES),
            )
            if conversation_id is not None:
                statement = statement.where(TaskDraft.conversation_id == conversation_id)
            statement = statement.order_by(TaskDraft.updated_at.desc(), TaskDraft.created_at.desc())
            return await session.scalar(statement)

    async def get_draft(self, user_id: str, draft_id: str) -> TaskDraft | None:
        async with AsyncSessionLocal() as session:
            statement = select(TaskDraft).where(
                TaskDraft.user_id == user_id,
                TaskDraft.id == draft_id,
            )
            return await session.scalar(statement)

    async def create_task_draft(
        self,
        *,
        user_id: str,
        raw_text: str,
        draft_data: dict,
        conversation_id: str | None,
        source_message_id: str | None,
        model_name: str | None,
        confidence_score: float | None,
        status: str,
    ) -> TaskDraft:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._supersede_active_drafts(session, user_id)
                draft = TaskDraft(
                    id=str(uuid4()),
                    user_id=user_id,
                    conversation_id=conversation_id,
                    source_message_id=source_message_id,
                    status=status,
                    raw_text=raw_text,
                    draft_data=draft_data,
                    model_name=model_name,
                    confidence_score=confidence_score,
                )
                session.add(draft)
                await session.flush()
                await session.refresh(draft)
                return draft

    async def update_task_draft(
        self,
        user_id: str,
        draft_id: str,
        *,
        draft_data: dict | None = None,
        raw_text: str | None = None,
        conversation_id: str | None = None,
        source_message_id: str | None = None,
        model_name: str | None = None,
        confidence_score: float | None = None,
        status: str | None = None,
    ) -> TaskDraft | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(TaskDraft).where(
                    TaskDraft.user_id == user_id,
                    TaskDraft.id == draft_id,
                )
                draft = await session.scalar(statement)
                if draft is None:
                    return None

                if draft_data is not None:
                    draft.draft_data = draft_data
                if raw_text is not None:
                    draft.raw_text = raw_text
                if model_name is not None:
                    draft.model_name = model_name
                if confidence_score is not None:
                    draft.confidence_score = confidence_score
                if status is not None:
                    draft.status = status
                if source_message_id is not None:
                    draft.source_message_id = source_message_id
                if conversation_id is not None:
                    draft.conversation_id = conversation_id

                await session.flush()
                await session.refresh(draft)
                return draft

    async def list_user_task_patterns(
        self,
        user_id: str,
        *,
        active_only: bool = True,
    ) -> list[UserTaskPattern]:
        async with AsyncSessionLocal() as session:
            statement = select(UserTaskPattern).where(UserTaskPattern.user_id == user_id)
            if active_only:
                statement = statement.where(UserTaskPattern.is_active.is_(True))
            statement = statement.order_by(
                UserTaskPattern.is_active.desc(),
                UserTaskPattern.updated_at.desc(),
                UserTaskPattern.created_at.desc(),
            )
            return list((await session.scalars(statement)).all())

    async def search_user_memories(
        self,
        user_id: str,
        keywords: list[str],
        *,
        limit: int = 10,
    ) -> list[UserMemory]:
        async with AsyncSessionLocal() as session:
            statement = select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.superseded_at.is_(None),
            )
            cleaned_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
            if cleaned_keywords:
                keyword_filters = []
                for keyword in cleaned_keywords:
                    token = f"%{keyword}%"
                    keyword_filters.append(
                        or_(
                            UserMemory.content.ilike(token),
                            UserMemory.summary.ilike(token),
                            cast(UserMemory.memory_data, Text).ilike(token),
                        )
                    )
                statement = statement.where(or_(*keyword_filters))

            statement = statement.order_by(
                UserMemory.importance_score.desc().nullslast(),
                UserMemory.confidence_score.desc().nullslast(),
                UserMemory.updated_at.desc(),
            ).limit(limit)
            memories = list((await session.scalars(statement)).all())
            now = datetime.now(timezone.utc)
            for memory in memories:
                memory.last_accessed_at = now
            await session.commit()
            return memories

    async def get_memory_candidate(
        self,
        user_id: str,
        candidate_id: str,
    ) -> MemoryCandidate | None:
        async with AsyncSessionLocal() as session:
            statement = select(MemoryCandidate).where(
                MemoryCandidate.user_id == user_id,
                MemoryCandidate.id == candidate_id,
            )
            return await session.scalar(statement)

    async def list_pending_memory_candidates(
        self,
        user_id: str,
        *,
        conversation_id: str | None = None,
        limit: int = 5,
    ) -> list[MemoryCandidate]:
        async with AsyncSessionLocal() as session:
            statement = select(MemoryCandidate).where(
                MemoryCandidate.user_id == user_id,
                MemoryCandidate.status == "pending",
            )
            if conversation_id is not None:
                statement = statement.where(
                    MemoryCandidate.conversation_id == conversation_id
                )
            statement = statement.order_by(
                MemoryCandidate.updated_at.desc(),
                MemoryCandidate.created_at.desc(),
            ).limit(limit)
            return list((await session.scalars(statement)).all())

    async def find_memory_by_content(
        self,
        user_id: str,
        content: str,
    ) -> UserMemory | None:
        async with AsyncSessionLocal() as session:
            statement = select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.content == content,
                UserMemory.superseded_at.is_(None),
            )
            return await session.scalar(statement)

    async def create_memory_candidate(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        source_message_id: str | None,
        candidate_type: str,
        content: str,
        candidate_data: dict | None,
        confidence_score: float | None,
        status: str = "pending",
        rejection_reason: str | None = None,
        accepted_memory_id: str | None = None,
    ) -> MemoryCandidate:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                candidate = MemoryCandidate(
                    id=str(uuid4()),
                    user_id=user_id,
                    conversation_id=conversation_id,
                    source_message_id=source_message_id,
                    accepted_memory_id=accepted_memory_id,
                    candidate_type=candidate_type,
                    content=content,
                    candidate_data=candidate_data,
                    confidence_score=confidence_score,
                    status=status,
                    rejection_reason=rejection_reason,
                )
                session.add(candidate)
                await session.flush()
                await session.refresh(candidate)
                return candidate

    async def resolve_memory_candidate(
        self,
        *,
        user_id: str,
        candidate_id: str,
        accepted: bool,
        memory_type: str | None = None,
        summary: str | None = None,
        importance_score: float | None = None,
    ) -> tuple[MemoryCandidate | None, UserMemory | None]:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(MemoryCandidate).where(
                    MemoryCandidate.user_id == user_id,
                    MemoryCandidate.id == candidate_id,
                )
                candidate = await session.scalar(statement)
                if candidate is None:
                    return None, None

                if accepted:
                    memory = UserMemory(
                        id=str(uuid4()),
                        user_id=user_id,
                        memory_type=memory_type or candidate.candidate_type,
                        content=candidate.content,
                        summary=summary,
                        memory_data=candidate.candidate_data,
                        confidence_score=candidate.confidence_score,
                        importance_score=importance_score,
                        source="agent",
                    )
                    session.add(memory)
                    await session.flush()
                    candidate.status = "accepted"
                    candidate.accepted_memory_id = memory.id
                    candidate.rejection_reason = None
                    await session.flush()
                    await session.refresh(candidate)
                    await session.refresh(memory)
                    return candidate, memory

                candidate.status = "rejected"
                candidate.rejection_reason = "Rejected by user confirmation flow."
                await session.flush()
                await session.refresh(candidate)
                return candidate, None

    async def get_memory_by_id(self, user_id: str, memory_id: str) -> UserMemory | None:
        async with AsyncSessionLocal() as session:
            statement = select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.id == memory_id,
            )
            return await session.scalar(statement)

    async def _supersede_active_drafts(self, session, user_id: str) -> None:
        statement = select(TaskDraft).where(
            TaskDraft.user_id == user_id,
            TaskDraft.status.in_(ACTIVE_DRAFT_STATUSES),
        )
        active_drafts = list((await session.scalars(statement)).all())
        for draft in active_drafts:
            draft.status = "superseded"
