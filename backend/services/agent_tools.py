from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from backend.models.agent import TaskDraft, UserMemory, UserTaskPattern
from backend.models.agent_tools import (
    ConfirmedTaskDraftResult,
    MemoryProposalInput,
    MemoryProposalResponse,
    MissingFieldCheckResult,
    MissingFieldQuestion,
    RealismCheckIssue,
    RealismCheckResult,
    TaskDraftInput,
    TaskDraftPatch,
    TaskDraftPreparedData,
    TaskDraftResponse,
    TaskDraftValidationResult,
    TaskPreviewResult,
    UserMemoryResponse,
    UserTaskPatternResponse,
)
from backend.models.personalization import UserPreferenceProfile
from backend.models.user_planning import UserTaskCreate
from backend.repositories.agent_tools import AgentToolRepository
from backend.repositories.user_planning import UserPlanningRepository
from backend.services.personalization import UserPreferenceService


class AgentToolService:
    def __init__(self) -> None:
        self.repository = AgentToolRepository()
        self.user_planning_repository = UserPlanningRepository()
        self.preference_service = UserPreferenceService()

    async def get_active_draft(
        self,
        user_id: str,
        *,
        conversation_id: str | None = None,
    ) -> TaskDraftResponse | None:
        draft = await self.repository.get_active_draft(
            user_id,
            conversation_id=conversation_id,
        )
        return self._to_task_draft_response(draft) if draft else None

    async def create_task_draft(
        self,
        user_id: str,
        payload: TaskDraftInput,
    ) -> TaskDraftResponse:
        draft_data = self._extract_task_fields(payload)
        draft = await self.repository.create_task_draft(
            user_id=user_id,
            raw_text=payload.raw_text,
            draft_data=draft_data,
            conversation_id=payload.conversation_id,
            source_message_id=payload.source_message_id,
            model_name=payload.model_name,
            confidence_score=payload.confidence_score,
            status=payload.draft_status or "draft",
        )
        return self._to_task_draft_response(draft)

    async def update_task_draft(
        self,
        user_id: str,
        draft_id: str,
        payload: TaskDraftPatch,
    ) -> TaskDraftResponse:
        current_draft = await self.repository.get_draft(user_id, draft_id)
        if current_draft is None:
            raise ValueError("Task draft not found.")

        merged_draft_data = {
            **(current_draft.draft_data or {}),
            **self._extract_task_fields(payload),
        }
        draft = await self.repository.update_task_draft(
            user_id,
            draft_id,
            draft_data=merged_draft_data,
            raw_text=payload.raw_text,
            conversation_id=payload.conversation_id,
            source_message_id=payload.source_message_id,
            model_name=payload.model_name,
            confidence_score=payload.confidence_score,
            status=payload.draft_status,
        )
        if draft is None:
            raise ValueError("Task draft not found.")
        return self._to_task_draft_response(draft)

    async def get_user_task_patterns(
        self,
        user_id: str,
        *,
        include_profile_patterns: bool = True,
        active_only: bool = True,
    ) -> list[UserTaskPatternResponse]:
        stored_patterns = await self.repository.list_user_task_patterns(
            user_id,
            active_only=active_only,
        )
        results = [self._to_pattern_response(pattern) for pattern in stored_patterns]
        if include_profile_patterns:
            profile = await self.preference_service.get_profile(user_id)
            results.extend(self._build_profile_patterns(user_id, profile))
        return results

    async def get_user_memories(
        self,
        user_id: str,
        keywords: list[str],
        *,
        limit: int = 10,
    ) -> list[UserMemoryResponse]:
        memories = await self.repository.search_user_memories(
            user_id,
            keywords,
            limit=limit,
        )
        return [self._to_memory_response(memory) for memory in memories]

    async def get_pending_memory_candidates(
        self,
        user_id: str,
        *,
        conversation_id: str | None = None,
        limit: int = 5,
    ) -> list[str]:
        candidates = await self.repository.list_pending_memory_candidates(
            user_id,
            conversation_id=conversation_id,
            limit=limit,
        )
        return [candidate.id for candidate in candidates]

    async def propose_memory_update(
        self,
        user_id: str,
        payload: MemoryProposalInput,
    ) -> MemoryProposalResponse:
        if payload.candidate_id is not None:
            return await self._resolve_memory_candidate(user_id, payload)

        existing_memory = await self.repository.find_memory_by_content(user_id, payload.content)
        if existing_memory is not None:
            return MemoryProposalResponse(
                candidate_id=existing_memory.id,
                status="accepted",
                message="This memory already exists.",
                user_confirmation_required=False,
                saved_memory_id=existing_memory.id,
            )

        candidate = await self.repository.create_memory_candidate(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            source_message_id=payload.source_message_id,
            candidate_type=payload.candidate_type,
            content=payload.content,
            candidate_data=payload.candidate_data,
            confidence_score=payload.confidence_score,
            status="pending",
            rejection_reason=None,
        )
        if payload.confirm is None:
            return MemoryProposalResponse(
                candidate_id=candidate.id,
                status="pending",
                message="Memory candidate created and awaiting user confirmation.",
                user_confirmation_required=True,
                confirmation_question=f"Сохранить в память пользователя: '{payload.content}'?",
            )

        resolved_payload = payload.model_copy(update={"candidate_id": candidate.id})
        return await self._resolve_memory_candidate(user_id, resolved_payload)

    async def validate_task_draft(
        self,
        user_id: str,
        draft_id: str,
    ) -> TaskDraftValidationResult:
        draft = await self._require_draft(user_id, draft_id)
        missing_fields = self._compute_missing_fields(draft.draft_data or {})
        if missing_fields:
            updated_draft = await self.repository.update_task_draft(
                user_id,
                draft_id,
                status="needs_clarification",
            )
            if updated_draft is None:
                raise ValueError("Task draft not found.")
            return TaskDraftValidationResult(
                draft=self._to_task_draft_response(updated_draft),
                is_valid=False,
                missing_fields=missing_fields,
                errors=[],
                normalized_task=None,
            )

        try:
            normalized_task = UserTaskCreate.model_validate(draft.draft_data or {})
        except ValidationError as exc:
            errors = [error["msg"] for error in exc.errors(include_url=False)]
            updated_draft = await self.repository.update_task_draft(
                user_id,
                draft_id,
                status="needs_clarification",
            )
            if updated_draft is None:
                raise ValueError("Task draft not found.")
            return TaskDraftValidationResult(
                draft=self._to_task_draft_response(updated_draft),
                is_valid=False,
                missing_fields=[],
                errors=errors,
                normalized_task=None,
            )

        normalized_payload = normalized_task.model_dump(mode="json")
        updated_draft = await self.repository.update_task_draft(
            user_id,
            draft_id,
            draft_data=normalized_payload,
            status="validated",
        )
        if updated_draft is None:
            raise ValueError("Task draft not found.")
        return TaskDraftValidationResult(
            draft=self._to_task_draft_response(updated_draft),
            is_valid=True,
            missing_fields=[],
            errors=[],
            normalized_task=normalized_payload,
        )

    async def check_missing_fields(
        self,
        user_id: str,
        draft_id: str,
    ) -> MissingFieldCheckResult:
        draft = await self._require_draft(user_id, draft_id)
        missing_fields = self._compute_missing_fields(draft.draft_data or {})
        questions = [self._build_question(field_name) for field_name in missing_fields]
        return MissingFieldCheckResult(
            draft=self._to_task_draft_response(draft),
            missing_fields=missing_fields,
            questions=questions,
            ready_for_validation=not missing_fields,
        )

    async def check_realism(
        self,
        user_id: str,
        draft_id: str,
    ) -> RealismCheckResult:
        draft = await self._require_draft(user_id, draft_id)
        profile = await self.preference_service.get_profile(user_id)
        issues = self._compute_realism_issues(draft.draft_data or {}, profile)
        return RealismCheckResult(
            draft=self._to_task_draft_response(draft),
            is_realistic=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    async def prepare_task_preview(
        self,
        user_id: str,
        draft_id: str,
    ) -> TaskPreviewResult:
        validation = await self.validate_task_draft(user_id, draft_id)
        realism = await self.check_realism(user_id, draft_id)
        if not validation.is_valid or validation.normalized_task is None:
            return TaskPreviewResult(
                draft=validation.draft,
                title=(validation.draft.draft_data or {}).get("title") or "Task draft",
                summary="Task draft is missing required fields and is not ready for confirmation.",
                task_payload=validation.draft.draft_data,
                missing_fields=validation.missing_fields,
                warnings=validation.errors,
                ready_for_confirmation=False,
            )

        prepared = self._prepare_preview_data(validation.normalized_task)
        warnings = [issue.message for issue in realism.issues if issue.severity != "info"]
        updated_draft = await self.repository.update_task_draft(
            user_id,
            draft_id,
            status="preview_ready",
        )
        if updated_draft is None:
            raise ValueError("Task draft not found.")
        return TaskPreviewResult(
            draft=self._to_task_draft_response(updated_draft),
            title=prepared.payload.title,
            summary="\n".join(prepared.preview_lines),
            task_payload=prepared.payload.model_dump(mode="json"),
            missing_fields=[],
            warnings=warnings,
            ready_for_confirmation=not any(
                issue.severity == "error" for issue in realism.issues
            ),
        )

    async def confirm_task_draft(
        self,
        user_id: str,
        draft_id: str,
    ) -> ConfirmedTaskDraftResult:
        draft = await self._require_draft(user_id, draft_id)
        existing_task_id = (
            ((draft.draft_data or {}).get("llm_metadata") or {})
            .get("agent", {})
            .get("confirmed_task_id")
        )
        if draft.status == "confirmed" and existing_task_id:
            existing_task = await self.user_planning_repository.get_task(user_id, existing_task_id)
            if existing_task is None:
                raise ValueError("Draft is confirmed but linked task was not found.")
            return ConfirmedTaskDraftResult(
                draft=self._to_task_draft_response(draft),
                task=existing_task,
            )

        validation = await self.validate_task_draft(user_id, draft_id)
        if not validation.is_valid or validation.normalized_task is None:
            problems = validation.errors or validation.missing_fields
            raise ValueError(
                "Task draft is not ready for confirmation: " + ", ".join(problems)
            )

        task_payload = UserTaskCreate.model_validate(validation.normalized_task)
        enriched_payload = task_payload.model_copy(
            update={
                "llm_metadata": self._with_agent_metadata(
                    task_payload.model_dump(mode="python").get("llm_metadata"),
                    draft,
                )
            }
        )
        created_task = await self.user_planning_repository.create_task(user_id, enriched_payload)
        draft_data = enriched_payload.model_dump(mode="json")
        draft_data.setdefault("llm_metadata", {})
        draft_data["llm_metadata"].setdefault("agent", {})
        draft_data["llm_metadata"]["agent"]["confirmed_task_id"] = created_task.id
        updated_draft = await self.repository.update_task_draft(
            user_id,
            draft_id,
            draft_data=draft_data,
            status="confirmed",
        )
        if updated_draft is None:
            raise ValueError("Task draft not found.")
        return ConfirmedTaskDraftResult(
            draft=self._to_task_draft_response(updated_draft),
            task=created_task,
        )

    async def cancel_task_draft(
        self,
        user_id: str,
        draft_id: str,
    ) -> TaskDraftResponse:
        draft = await self.repository.update_task_draft(
            user_id,
            draft_id,
            status="cancelled",
        )
        if draft is None:
            raise ValueError("Task draft not found.")
        return self._to_task_draft_response(draft)

    async def _resolve_memory_candidate(
        self,
        user_id: str,
        payload: MemoryProposalInput,
    ) -> MemoryProposalResponse:
        if payload.candidate_id is None:
            raise ValueError("candidate_id is required to resolve a memory proposal.")
        if payload.confirm is None:
            raise ValueError("confirm must be provided to resolve a memory proposal.")

        candidate, memory = await self.repository.resolve_memory_candidate(
            user_id=user_id,
            candidate_id=payload.candidate_id,
            accepted=payload.confirm,
            memory_type=payload.memory_type,
            summary=payload.summary,
            importance_score=payload.importance_score,
        )
        if candidate is None:
            raise ValueError("Memory candidate not found.")

        if payload.confirm:
            return MemoryProposalResponse(
                candidate_id=candidate.id,
                status="accepted",
                message="Memory saved successfully.",
                user_confirmation_required=False,
                saved_memory_id=memory.id if memory else None,
            )

        return MemoryProposalResponse(
            candidate_id=candidate.id,
            status="rejected",
            message="Memory candidate was rejected.",
            user_confirmation_required=False,
        )

    async def _require_draft(self, user_id: str, draft_id: str) -> TaskDraft:
        draft = await self.repository.get_draft(user_id, draft_id)
        if draft is None:
            raise ValueError("Task draft not found.")
        return draft

    def _extract_task_fields(self, payload: TaskDraftInput | TaskDraftPatch) -> dict:
        data = payload.model_dump(
            exclude={
                "raw_text",
                "conversation_id",
                "source_message_id",
                "model_name",
                "confidence_score",
                "draft_status",
            },
            exclude_unset=True,
            mode="json",
        )
        return data

    def _compute_missing_fields(self, draft_data: dict[str, Any]) -> list[str]:
        missing_fields: list[str] = []
        if not str(draft_data.get("title") or "").strip():
            missing_fields.append("title")
        if draft_data.get("duration_minutes") in (None, ""):
            missing_fields.append("duration_minutes")
        if draft_data.get("is_fixed") and not draft_data.get("fixed_start"):
            missing_fields.append("fixed_start")
        if draft_data.get("allow_splitting") and not draft_data.get("min_split_part_minutes"):
            missing_fields.append("min_split_part_minutes")
        return missing_fields

    def _build_question(self, field_name: str) -> MissingFieldQuestion:
        prompts = {
            "title": "Как назвать эту задачу?",
            "duration_minutes": "Сколько минут реально займет эта задача?",
            "fixed_start": "На какое точное время нужно поставить задачу?",
            "min_split_part_minutes": "На какие минимальные части можно делить эту задачу?",
        }
        return MissingFieldQuestion(
            field=field_name,
            question=prompts.get(field_name, f"Уточните поле {field_name}."),
        )

    def _compute_realism_issues(
        self,
        draft_data: dict[str, Any],
        profile: UserPreferenceProfile,
    ) -> list[RealismCheckIssue]:
        issues: list[RealismCheckIssue] = []
        now = datetime.now(timezone.utc)
        duration = draft_data.get("duration_minutes")
        deadline = self._parse_datetime(draft_data.get("deadline"))
        earliest_start = self._parse_datetime(draft_data.get("earliest_start"))
        latest_end = self._parse_datetime(draft_data.get("latest_end"))
        fixed_start = self._parse_datetime(draft_data.get("fixed_start"))
        allow_splitting = bool(draft_data.get("allow_splitting"))
        min_split_part_minutes = draft_data.get("min_split_part_minutes")

        if isinstance(duration, int):
            if duration > 16 * 60:
                issues.append(
                    RealismCheckIssue(
                        severity="error",
                        field="duration_minutes",
                        message="Duration is longer than 16 hours and looks unrealistic for one task.",
                    )
                )
            if profile.load.max_daily_planned_minutes and duration > profile.load.max_daily_planned_minutes:
                issues.append(
                    RealismCheckIssue(
                        severity="warning",
                        field="duration_minutes",
                        message="Duration exceeds the user's preferred maximum planned minutes for one day.",
                    )
                )
            if duration > profile.load.preferred_focus_block_minutes and not allow_splitting:
                issues.append(
                    RealismCheckIssue(
                        severity="warning",
                        field="allow_splitting",
                        message="Task is longer than the user's preferred focus block and may need splitting.",
                    )
                )

        if deadline and deadline < now:
            issues.append(
                RealismCheckIssue(
                    severity="error",
                    field="deadline",
                    message="Deadline is already in the past.",
                )
            )
        if fixed_start and fixed_start < now:
            issues.append(
                RealismCheckIssue(
                    severity="warning",
                    field="fixed_start",
                    message="Fixed start is in the past.",
                )
            )
        if earliest_start and latest_end and latest_end <= earliest_start:
            issues.append(
                RealismCheckIssue(
                    severity="error",
                    field="latest_end",
                    message="latest_end must be later than earliest_start.",
                )
            )
        if deadline and earliest_start and earliest_start > deadline:
            issues.append(
                RealismCheckIssue(
                    severity="error",
                    field="deadline",
                    message="earliest_start is after the deadline.",
                )
            )
        if deadline and latest_end and latest_end > deadline:
            issues.append(
                RealismCheckIssue(
                    severity="warning",
                    field="latest_end",
                    message="latest_end exceeds the deadline.",
                )
            )
        if allow_splitting and isinstance(duration, int) and isinstance(min_split_part_minutes, int):
            if min_split_part_minutes >= duration:
                issues.append(
                    RealismCheckIssue(
                        severity="error",
                        field="min_split_part_minutes",
                        message="Minimum split part must be shorter than total duration.",
                    )
                )
        if fixed_start and not draft_data.get("is_fixed"):
            issues.append(
                RealismCheckIssue(
                    severity="info",
                    field="is_fixed",
                    message="fixed_start is set, but the task is not marked as fixed.",
                )
            )
        return issues

    def _prepare_preview_data(self, normalized_task: dict[str, Any]) -> TaskDraftPreparedData:
        payload = UserTaskCreate.model_validate(normalized_task)
        preview_lines = [
            f"Название: {payload.title}",
            f"Длительность: {payload.duration_minutes} мин.",
            f"Приоритет: {payload.priority}/5",
            f"Статус: {payload.status}",
        ]
        if payload.category:
            preview_lines.append(f"Категория: {payload.category}")
        if payload.energy_required:
            preview_lines.append(f"Требуемая энергия: {payload.energy_required}")
        if payload.deadline:
            preview_lines.append(f"Дедлайн: {payload.deadline.isoformat()}")
        if payload.is_fixed and payload.fixed_start:
            preview_lines.append(f"Фиксированное время: {payload.fixed_start.isoformat()}")
        elif payload.earliest_start or payload.latest_end:
            preview_lines.append(
                "Окно выполнения: "
                f"{payload.earliest_start.isoformat() if payload.earliest_start else 'any time'}"
                " -> "
                f"{payload.latest_end.isoformat() if payload.latest_end else 'no hard end'}"
            )
        if payload.allow_splitting:
            preview_lines.append(
                f"Разбиение разрешено, минимальная часть: {payload.min_split_part_minutes} мин."
            )
        if payload.description:
            preview_lines.append(f"Описание: {payload.description}")
        return TaskDraftPreparedData(
            payload=payload,
            preview_lines=preview_lines,
            preferred_windows=payload.preferred_windows,
        )

    def _build_profile_patterns(
        self,
        user_id: str,
        profile: UserPreferenceProfile,
    ) -> list[UserTaskPatternResponse]:
        patterns: list[UserTaskPatternResponse] = [
            UserTaskPatternResponse(
                id=f"profile:{user_id}:productivity",
                user_id=user_id,
                pattern_type="productivity_profile",
                name="Productivity profile",
                description="Derived from the stored user profile.",
                pattern_data=profile.productivity.model_dump(mode="json"),
                confidence_score=1.0,
                source="profile",
                is_active=True,
            ),
            UserTaskPatternResponse(
                id=f"profile:{user_id}:load",
                user_id=user_id,
                pattern_type="load_profile",
                name="Load profile",
                description="Derived from the stored user profile.",
                pattern_data=profile.load.model_dump(mode="json"),
                confidence_score=1.0,
                source="profile",
                is_active=True,
            ),
            UserTaskPatternResponse(
                id=f"profile:{user_id}:behavior",
                user_id=user_id,
                pattern_type="behavior_profile",
                name="Behavior profile",
                description="Derived from the stored user profile.",
                pattern_data=profile.behavior.model_dump(mode="json"),
                confidence_score=1.0,
                source="profile",
                is_active=True,
            ),
        ]
        for category, category_profile in profile.category_time_preferences.items():
            patterns.append(
                UserTaskPatternResponse(
                    id=f"profile:{user_id}:category:{category}",
                    user_id=user_id,
                    pattern_type="category_time_preference",
                    name=f"Category preference: {category}",
                    description="Derived from the stored user profile.",
                    pattern_data=category_profile.model_dump(mode="json"),
                    confidence_score=1.0,
                    source="profile",
                    is_active=True,
                )
            )
        for category, multiplier in profile.duration_multipliers.items():
            patterns.append(
                UserTaskPatternResponse(
                    id=f"profile:{user_id}:duration:{category}",
                    user_id=user_id,
                    pattern_type="duration_multiplier",
                    name=f"Duration multiplier: {category}",
                    description="Derived from the stored user profile.",
                    pattern_data={"category": category, "multiplier": multiplier},
                    confidence_score=1.0,
                    source="profile",
                    is_active=True,
                )
            )
        return patterns

    def _with_agent_metadata(self, llm_metadata: dict | None, draft: TaskDraft) -> dict:
        merged = dict(llm_metadata or {})
        agent_block = dict(merged.get("agent") or {})
        agent_block.update(
            {
                "task_draft_id": draft.id,
                "conversation_id": draft.conversation_id,
                "source_message_id": draft.source_message_id,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        merged["agent"] = agent_block
        return merged

    def _to_task_draft_response(self, draft: TaskDraft) -> TaskDraftResponse:
        return TaskDraftResponse(
            id=draft.id,
            user_id=draft.user_id,
            conversation_id=draft.conversation_id,
            source_message_id=draft.source_message_id,
            status=draft.status,
            raw_text=draft.raw_text,
            draft_data=draft.draft_data or {},
            model_name=draft.model_name,
            confidence_score=draft.confidence_score,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    def _to_pattern_response(self, pattern: UserTaskPattern) -> UserTaskPatternResponse:
        return UserTaskPatternResponse(
            id=pattern.id,
            user_id=pattern.user_id,
            pattern_type=pattern.pattern_type,
            name=pattern.name,
            description=pattern.description,
            pattern_data=pattern.pattern_data,
            confidence_score=pattern.confidence_score,
            source=pattern.source,
            is_active=pattern.is_active,
            last_observed_at=pattern.last_observed_at,
            created_at=pattern.created_at,
            updated_at=pattern.updated_at,
        )

    def _to_memory_response(self, memory: UserMemory) -> UserMemoryResponse:
        return UserMemoryResponse(
            id=memory.id,
            user_id=memory.user_id,
            memory_type=memory.memory_type,
            content=memory.content,
            summary=memory.summary,
            memory_data=memory.memory_data,
            confidence_score=memory.confidence_score,
            importance_score=memory.importance_score,
            source=memory.source,
            last_accessed_at=memory.last_accessed_at,
            superseded_at=memory.superseded_at,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
