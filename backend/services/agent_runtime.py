import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.core.config import settings
from backend.models.agent_runtime import AgentTurnResponse
from backend.models.agent_tools import (
    MemoryProposalInput,
    TaskDraftInput,
    TaskDraftPatch,
)
from backend.models.user_planning import UserTaskResponse
from backend.repositories.conversations import ConversationRepository
from backend.services.agent_tools import AgentToolService
from backend.services.ollama import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)


TERMINAL_ONLY_SYSTEM_PROMPT = """
Отвечай только на русском языке.
Не используй китайский, английский или смешанный язык, если пользователь явно не попросил об этом.
""".strip()

RUSSIAN_REWRITE_SYSTEM_PROMPT = """
Перепиши текст полностью на русском языке.
Запрещено использовать китайские иероглифы, английские слова, латиницу и смешанный язык.
Сохрани смысл ответа, но выдай итог только на русском языке.
""".strip()

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_RE = re.compile(r"[A-Za-z]")


ANALYSIS_SYSTEM_PROMPT = """
You are a task-intake planner agent.
Extract structured task data from the user's latest message and current draft context.
Reply with a single JSON object only.

Rules:
- Focus on helping create one actionable task draft.
- If the user is adding details to an existing task draft, return only fields that should be updated.
- Infer values conservatively.
- duration_minutes must be an integer number of minutes if known.
- priority must be 1..5 if known.
- status for normal new tasks should usually be "active".
- If the user reveals a stable preference or habit about themselves, include it in memory_candidates.
- memory_keywords should contain short keywords useful for searching user memories.
- conversation_title should be short and human-readable if this is the start of a conversation.

Expected JSON shape:
{
  "intent": "create_task|update_task|confirm|cancel|clarify|other",
  "conversation_title": "optional short title",
  "task_patch": {
    "title": "...",
    "description": "...",
    "duration_minutes": 60,
    "priority": 3,
    "category": "work",
    "energy_required": "low|medium|high",
    "status": "active",
    "deadline": "ISO datetime or null",
    "earliest_start": "ISO datetime or null",
    "latest_end": "ISO datetime or null",
    "fixed_start": "ISO datetime or null",
    "is_mandatory": false,
    "is_fixed": false,
    "allow_splitting": false,
    "min_split_part_minutes": 30
  },
  "memory_keywords": ["keyword1", "keyword2"],
  "memory_candidates": [
    {
      "content": "User prefers deep work in the morning.",
      "candidate_type": "preference",
      "memory_type": "preference",
      "summary": "Morning deep work preference",
      "confidence_score": 0.82,
      "importance_score": 0.74
    }
  ]
}
""".strip()


PREVIEW_SYSTEM_PROMPT = """
You are a productivity assistant.
Write a concise natural-language response in Russian for the user.
If the task draft is incomplete, ask only for the missing details.
If the task draft is ready, present the task preview naturally and ask for confirmation.
If the task was confirmed, say it has been added.
If there are realism warnings, mention them briefly.
Do not output JSON.
""".strip()


CONFIRMATION_WORDS = {
    "да",
    "ага",
    "ок",
    "окей",
    "подтверждаю",
    "подтвердить",
    "подтверди",
    "верно",
    "согласен",
    "согласна",
    "сохраняй",
    "сохрани",
    "добавляй",
    "добавь",
}

CANCELLATION_WORDS = {
    "нет",
    "не надо",
    "отмена",
    "отменить",
    "не подтверждаю",
    "не сохраняй",
    "не добавляй",
}


@dataclass
class AgentAnalysis:
    intent: str
    conversation_title: str | None
    task_patch: dict[str, Any]
    memory_keywords: list[str]
    memory_candidates: list[dict[str, Any]]


class AgentRuntimeService:
    def __init__(self) -> None:
        self.ollama_service = OllamaService()
        self.tool_service = AgentToolService()
        self.conversation_repository = ConversationRepository()

    async def handle_user_message(
        self,
        user_id: str,
        text: str,
        *,
        conversation_id: str | None = None,
    ) -> AgentTurnResponse:
        user_text = text.strip()
        if not user_text:
            raise ValueError("User message must not be empty.")

        return await self._run_terminal_only_ollama(user_text)

        conversation = await self._ensure_conversation(
            user_id,
            conversation_id=conversation_id,
            initial_text=user_text,
        )
        user_message = await self.conversation_repository.add_message(
            conversation_id=conversation.id,
            user_id=user_id,
            role="user",
            content=user_text,
        )

        active_draft = await self.tool_service.get_active_draft(
            user_id,
            conversation_id=conversation.id,
        )
        pending_memory_candidate_ids = await self.tool_service.get_pending_memory_candidates(
            user_id,
            conversation_id=conversation.id,
            limit=5,
        )

        preview_candidate = await self._handle_confirmation_flow(
            user_id,
            user_text,
            conversation.id,
            active_draft,
            pending_memory_candidate_ids,
        )
        if preview_candidate is not None:
            return await self._finalize_turn(
                user_id=user_id,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                reply=preview_candidate.reply,
                draft=preview_candidate.draft,
                task_preview=preview_candidate.task_preview,
                confirmed_task=preview_candidate.confirmed_task,
                memory_proposals=preview_candidate.memory_proposals,
                requires_user_input=preview_candidate.requires_user_input,
                requires_confirmation=preview_candidate.requires_confirmation,
            )

        recent_messages = await self.conversation_repository.list_recent_messages(
            user_id,
            conversation.id,
            limit=8,
        )
        analysis = await self._analyze_message(
            user_text,
            active_draft.draft_data if active_draft else None,
            recent_messages=[
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in recent_messages
            ],
        )
        if analysis.conversation_title:
            await self.conversation_repository.update_conversation_context(
                user_id=user_id,
                conversation_id=conversation.id,
                title=analysis.conversation_title,
            )

        memories = await self.tool_service.get_user_memories(
            user_id,
            analysis.memory_keywords,
            limit=8,
        )
        patterns = await self.tool_service.get_user_task_patterns(user_id)

        draft = await self._upsert_draft_from_analysis(
            user_id=user_id,
            conversation_id=conversation.id,
            source_message_id=user_message.id,
            user_text=user_text,
            active_draft_id=active_draft.id if active_draft else None,
            analysis=analysis,
        )

        memory_proposals = []
        for candidate in analysis.memory_candidates:
            try:
                proposal = await self.tool_service.propose_memory_update(
                    user_id,
                    MemoryProposalInput(
                        content=str(candidate.get("content") or "").strip(),
                        candidate_type=str(candidate.get("candidate_type") or "preference"),
                        memory_type=str(candidate.get("memory_type") or "preference"),
                        summary=self._as_optional_string(candidate.get("summary")),
                        conversation_id=conversation.id,
                        source_message_id=user_message.id,
                        candidate_data={
                            "source": "agent_runtime",
                            "detected_from_text": user_text,
                        },
                        confidence_score=self._as_optional_float(candidate.get("confidence_score")),
                        importance_score=self._as_optional_float(candidate.get("importance_score")),
                        confirm=None,
                    ),
                )
            except ValueError:
                continue
            memory_proposals.append(proposal)

        missing = await self.tool_service.check_missing_fields(user_id, draft.id)
        if not missing.ready_for_validation:
            reply = await self._compose_missing_fields_reply(
                user_text=user_text,
                draft_data=draft.draft_data,
                missing_questions=missing.questions,
                memory_proposals=memory_proposals,
                memories=[memory.model_dump(mode="json") for memory in memories],
                patterns=[pattern.model_dump(mode="json") for pattern in patterns[:8]],
            )
            latest_draft = await self.tool_service.get_active_draft(
                user_id,
                conversation_id=conversation.id,
            )
            return await self._finalize_turn(
                user_id=user_id,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                reply=reply,
                draft=latest_draft,
                task_preview=None,
                confirmed_task=None,
                memory_proposals=memory_proposals,
                requires_user_input=True,
                requires_confirmation=False,
            )

        preview = await self.tool_service.prepare_task_preview(user_id, draft.id)
        reply = await self._compose_preview_reply(
            user_text=user_text,
            preview=preview.model_dump(mode="json"),
            memory_proposals=memory_proposals,
            memories=[memory.model_dump(mode="json") for memory in memories],
            patterns=[pattern.model_dump(mode="json") for pattern in patterns[:8]],
        )
        refreshed_draft = await self.tool_service.get_active_draft(
            user_id,
            conversation_id=conversation.id,
        )
        return await self._finalize_turn(
            user_id=user_id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            reply=reply,
            draft=refreshed_draft,
            task_preview=preview,
            confirmed_task=None,
            memory_proposals=memory_proposals,
            requires_user_input=False,
            requires_confirmation=preview.ready_for_confirmation,
        )

    async def _run_terminal_only_ollama(self, user_text: str) -> AgentTurnResponse:
        reply = await asyncio.to_thread(
            self.ollama_service.chat_text,
            user_text,
            system=TERMINAL_ONLY_SYSTEM_PROMPT,
            temperature=0.1,
        )
        reply = await self._ensure_russian_only_reply(reply)

        print("\n=== OLLAMA RESPONSE START ===")
        print(reply)
        print("=== OLLAMA RESPONSE END ===\n")

        return AgentTurnResponse(
            conversation_id="",
            user_message_id="",
            assistant_message_id="",
            reply=reply,
            draft=None,
            task_preview=None,
            confirmed_task=None,
            memory_proposals=[],
            requires_user_input=False,
            requires_confirmation=False,
        )

    async def _ensure_russian_only_reply(self, reply: str) -> str:
        if not self._contains_foreign_script(reply):
            return reply

        rewrite_prompt = (
            "Перепиши следующий текст полностью на русском языке. "
            "Переведи все иностранные фрагменты на русский язык. "
            "Нельзя копировать иероглифы, латиницу или иностранные слова. "
            "Верни только исправленный русский текст.\n\n"
            f"{reply}"
        )
        rewritten = await asyncio.to_thread(
            self.ollama_service.chat_text,
            rewrite_prompt,
            system=RUSSIAN_REWRITE_SYSTEM_PROMPT,
            temperature=0.1,
        )
        if self._contains_foreign_script(rewritten):
            logger.warning("Ollama returned mixed-language output after rewrite | body=%s", rewritten)
            return (
                "Модель вернула смешанный ответ с иностранными символами. "
                "Ответ отклонён. Повторите запрос или переформулируйте его короче."
            )
        return rewritten

    def _contains_foreign_script(self, text: str) -> bool:
        return bool(CJK_RE.search(text) or LATIN_RE.search(text))

    async def _ensure_conversation(
        self,
        user_id: str,
        *,
        conversation_id: str | None,
        initial_text: str,
    ):
        if conversation_id:
            conversation = await self.conversation_repository.get_conversation(
                user_id,
                conversation_id,
            )
            if conversation is None:
                raise ValueError("Conversation not found.")
            return conversation

        title = self._truncate_title(initial_text)
        return await self.conversation_repository.create_conversation(
            user_id=user_id,
            title=title,
            model_name=settings.ollama_model,
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
        )

    async def _handle_confirmation_flow(
        self,
        user_id: str,
        user_text: str,
        conversation_id: str,
        active_draft,
        pending_memory_candidate_ids: list[str],
    ):
        if active_draft is None:
            if pending_memory_candidate_ids:
                return await self._handle_memory_confirmation_flow(
                    user_id,
                    user_text,
                    pending_memory_candidate_ids,
                )
            return None

        normalized = user_text.strip().lower()
        if active_draft.status == "preview_ready" and self._contains_phrase(
            normalized,
            CONFIRMATION_WORDS,
        ):
            confirmed = await self.tool_service.confirm_task_draft(user_id, active_draft.id)
            reply = await self._compose_confirmation_reply(confirmed.task)
            return _RuntimeTurnDraft(
                reply=reply,
                draft=confirmed.draft,
                task_preview=None,
                confirmed_task=confirmed.task,
                memory_proposals=[],
                requires_user_input=False,
                requires_confirmation=False,
            )

        if active_draft.status == "preview_ready" and self._contains_phrase(
            normalized,
            CANCELLATION_WORDS,
        ):
            cancelled = await self.tool_service.cancel_task_draft(user_id, active_draft.id)
            reply = "Черновик задачи отменен. Если хотите, опишите задачу заново."
            return _RuntimeTurnDraft(
                reply=reply,
                draft=cancelled,
                task_preview=None,
                confirmed_task=None,
                memory_proposals=[],
                requires_user_input=False,
                requires_confirmation=False,
            )

        if pending_memory_candidate_ids:
            return await self._handle_memory_confirmation_flow(
                user_id,
                user_text,
                pending_memory_candidate_ids,
            )

        return None

    async def _handle_memory_confirmation_flow(
        self,
        user_id: str,
        user_text: str,
        pending_memory_candidate_ids: list[str],
    ):
        if not pending_memory_candidate_ids:
            return None
        normalized = user_text.strip().lower()
        latest_candidate_id = pending_memory_candidate_ids[0]
        if self._contains_phrase(normalized, CONFIRMATION_WORDS):
            proposal = await self.tool_service.propose_memory_update(
                user_id,
                MemoryProposalInput(
                    candidate_id=latest_candidate_id,
                    content="placeholder",
                    confirm=True,
                ),
            )
            reply = "Сохранил это в память о ваших предпочтениях."
            return _RuntimeTurnDraft(
                reply=reply,
                draft=None,
                task_preview=None,
                confirmed_task=None,
                memory_proposals=[proposal],
                requires_user_input=False,
                requires_confirmation=False,
            )
        if self._contains_phrase(normalized, CANCELLATION_WORDS):
            proposal = await self.tool_service.propose_memory_update(
                user_id,
                MemoryProposalInput(
                    candidate_id=latest_candidate_id,
                    content="placeholder",
                    confirm=False,
                ),
            )
            reply = "Не сохраняю это в память пользователя."
            return _RuntimeTurnDraft(
                reply=reply,
                draft=None,
                task_preview=None,
                confirmed_task=None,
                memory_proposals=[proposal],
                requires_user_input=False,
                requires_confirmation=False,
            )
        return None

    async def _analyze_message(
        self,
        user_text: str,
        current_draft: dict[str, Any] | None,
        recent_messages: list[dict[str, str]],
    ) -> AgentAnalysis:
        prompt = self._build_analysis_prompt(user_text, current_draft, recent_messages)
        try:
            result = await asyncio.to_thread(
                self.ollama_service.generate_json,
                prompt,
                system=ANALYSIS_SYSTEM_PROMPT,
                temperature=0.1,
            )
        except OllamaServiceError as exc:
            logger.exception("Agent analysis failed | error=%s", exc)
            return AgentAnalysis(
                intent="create_task",
                conversation_title=None,
                task_patch={"description": user_text},
                memory_keywords=self._naive_keywords(user_text),
                memory_candidates=[],
            )

        return AgentAnalysis(
            intent=str(result.get("intent") or "create_task"),
            conversation_title=self._as_optional_string(result.get("conversation_title")),
            task_patch=result.get("task_patch") if isinstance(result.get("task_patch"), dict) else {},
            memory_keywords=self._coerce_string_list(result.get("memory_keywords")),
            memory_candidates=result.get("memory_candidates")
            if isinstance(result.get("memory_candidates"), list)
            else [],
        )

    async def _upsert_draft_from_analysis(
        self,
        *,
        user_id: str,
        conversation_id: str,
        source_message_id: str,
        user_text: str,
        active_draft_id: str | None,
        analysis: AgentAnalysis,
    ):
        payload = self._build_draft_payload(
            user_text=user_text,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            analysis=analysis,
        )
        if active_draft_id:
            return await self.tool_service.update_task_draft(
                user_id,
                active_draft_id,
                TaskDraftPatch.model_validate(payload),
            )
        return await self.tool_service.create_task_draft(
            user_id,
            TaskDraftInput.model_validate(payload),
        )

    async def _compose_missing_fields_reply(
        self,
        *,
        user_text: str,
        draft_data: dict[str, Any],
        missing_questions: list[Any],
        memory_proposals: list[Any],
        memories: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
    ) -> str:
        prompt = (
            "User request:\n"
            f"{user_text}\n\n"
            "Current draft data:\n"
            f"{json.dumps(draft_data, ensure_ascii=False, indent=2)}\n\n"
            "Missing field questions:\n"
            f"{json.dumps([item.model_dump(mode='json') for item in missing_questions], ensure_ascii=False, indent=2)}\n\n"
            "Relevant memories:\n"
            f"{json.dumps(memories, ensure_ascii=False, indent=2)}\n\n"
            "Relevant patterns:\n"
            f"{json.dumps(patterns, ensure_ascii=False, indent=2)}\n\n"
            "Memory proposals:\n"
            f"{json.dumps([proposal.model_dump(mode='json') for proposal in memory_proposals], ensure_ascii=False, indent=2)}\n\n"
            "Write a short Russian answer asking only for the missing details."
        )
        return await self._generate_natural_reply(prompt)

    async def _compose_preview_reply(
        self,
        *,
        user_text: str,
        preview: dict[str, Any],
        memory_proposals: list[Any],
        memories: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
    ) -> str:
        prompt = (
            "User request:\n"
            f"{user_text}\n\n"
            "Prepared task preview:\n"
            f"{json.dumps(preview, ensure_ascii=False, indent=2)}\n\n"
            "Relevant memories:\n"
            f"{json.dumps(memories, ensure_ascii=False, indent=2)}\n\n"
            "Relevant patterns:\n"
            f"{json.dumps(patterns, ensure_ascii=False, indent=2)}\n\n"
            "Memory proposals:\n"
            f"{json.dumps([proposal.model_dump(mode='json') for proposal in memory_proposals], ensure_ascii=False, indent=2)}\n\n"
            "Write a short Russian confirmation-ready summary of the task and ask the user to confirm or correct it."
        )
        return await self._generate_natural_reply(prompt)

    async def _compose_confirmation_reply(self, task: UserTaskResponse) -> str:
        prompt = (
            "A task has been confirmed and saved.\n"
            f"Task payload:\n{json.dumps(task.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
            "Write a short Russian message confirming the task was added."
        )
        return await self._generate_natural_reply(prompt)

    async def _generate_natural_reply(self, prompt: str) -> str:
        try:
            return await asyncio.to_thread(
                self.ollama_service.generate_text,
                prompt,
                system=PREVIEW_SYSTEM_PROMPT,
                temperature=0.2,
            )
        except OllamaServiceError:
            logger.exception("Natural reply generation failed")
            return "Не удалось сгенерировать ответ через модель. Попробуйте уточнить задачу еще раз."

    async def _finalize_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message_id: str,
        reply: str,
        draft,
        task_preview,
        confirmed_task,
        memory_proposals,
        requires_user_input: bool,
        requires_confirmation: bool,
    ) -> AgentTurnResponse:
        assistant_message = await self.conversation_repository.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=reply,
            message_metadata={
                "draft_id": draft.id if draft else None,
                "requires_user_input": requires_user_input,
                "requires_confirmation": requires_confirmation,
                "confirmed_task_id": confirmed_task.id if confirmed_task else None,
            },
        )
        return AgentTurnResponse(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            reply=reply,
            draft=draft,
            task_preview=task_preview,
            confirmed_task=confirmed_task,
            memory_proposals=memory_proposals,
            requires_user_input=requires_user_input,
            requires_confirmation=requires_confirmation,
        )

    def _build_analysis_prompt(
        self,
        user_text: str,
        current_draft: dict[str, Any] | None,
        recent_messages: list[dict[str, str]],
    ) -> str:
        return (
            "Recent conversation messages:\n"
            f"{json.dumps(recent_messages, ensure_ascii=False, indent=2)}\n\n"
            "Current draft context:\n"
            f"{json.dumps(current_draft or {}, ensure_ascii=False, indent=2)}\n\n"
            "Latest user message:\n"
            f"{user_text}\n\n"
            "Return the JSON object now."
        )

    def _build_draft_payload(
        self,
        *,
        user_text: str,
        conversation_id: str,
        source_message_id: str,
        analysis: AgentAnalysis,
    ) -> dict[str, Any]:
        task_patch = dict(analysis.task_patch or {})
        if not task_patch.get("description"):
            task_patch["description"] = user_text
        if not task_patch.get("status"):
            task_patch["status"] = "active"
        payload = {
            **task_patch,
            "raw_text": user_text,
            "conversation_id": conversation_id,
            "source_message_id": source_message_id,
            "model_name": settings.ollama_model,
            "confidence_score": 0.7,
        }
        return payload

    def _truncate_title(self, text: str) -> str:
        compact = " ".join(text.strip().split())
        return compact[:80] if len(compact) > 80 else compact

    def _naive_keywords(self, text: str) -> list[str]:
        keywords: list[str] = []
        for token in text.lower().replace(",", " ").replace(".", " ").split():
            token = token.strip()
            if len(token) >= 4 and token not in keywords:
                keywords.append(token)
            if len(keywords) >= 6:
                break
        return keywords

    def _coerce_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
        return result

    def _as_optional_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    def _as_optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0 or parsed > 1:
            return None
        return parsed

    def _contains_phrase(self, text: str, phrases: set[str]) -> bool:
        compact = " ".join(text.split())
        return any(phrase in compact for phrase in phrases)


@dataclass
class _RuntimeTurnDraft:
    reply: str
    draft: Any
    task_preview: Any
    confirmed_task: UserTaskResponse | None
    memory_proposals: list[Any]
    requires_user_input: bool
    requires_confirmation: bool
