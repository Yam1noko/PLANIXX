from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from backend.db.database import AsyncSessionLocal
from backend.models.agent import Conversation, ConversationMessage


class ConversationRepository:
    async def get_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Conversation | None:
        async with AsyncSessionLocal() as session:
            statement = select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.id == conversation_id,
            )
            return await session.scalar(statement)

    async def create_conversation(
        self,
        *,
        user_id: str,
        title: str | None,
        model_name: str | None,
        system_prompt: str | None = None,
        summary: str | None = None,
        context_data: dict | None = None,
    ) -> Conversation:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                conversation = Conversation(
                    id=str(uuid4()),
                    user_id=user_id,
                    title=title,
                    status="active",
                    model_name=model_name,
                    system_prompt=system_prompt,
                    summary=summary,
                    context_data=context_data,
                    last_message_at=datetime.now(timezone.utc),
                )
                session.add(conversation)
                await session.flush()
                await session.refresh(conversation)
                return conversation

    async def add_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        message_metadata: dict | None = None,
    ) -> ConversationMessage:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                conversation = await session.get(Conversation, conversation_id)
                if conversation is None or conversation.user_id != user_id:
                    raise ValueError("Conversation not found.")

                message = ConversationMessage(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role=role,
                    message_type=message_type,
                    content=content,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    message_metadata=message_metadata,
                )
                session.add(message)
                conversation.last_message_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(message)
                return message

    async def list_recent_messages(
        self,
        user_id: str,
        conversation_id: str,
        *,
        limit: int = 12,
    ) -> list[ConversationMessage]:
        async with AsyncSessionLocal() as session:
            statement = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.user_id == user_id,
                    ConversationMessage.conversation_id == conversation_id,
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(limit)
            )
            messages = list((await session.scalars(statement)).all())
            messages.reverse()
            return messages

    async def update_conversation_context(
        self,
        *,
        user_id: str,
        conversation_id: str,
        title: str | None = None,
        summary: str | None = None,
        context_data: dict | None = None,
        status: str | None = None,
    ) -> Conversation | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(Conversation).where(
                    Conversation.user_id == user_id,
                    Conversation.id == conversation_id,
                )
                conversation = await session.scalar(statement)
                if conversation is None:
                    return None
                if title is not None:
                    conversation.title = title
                if summary is not None:
                    conversation.summary = summary
                if context_data is not None:
                    conversation.context_data = context_data
                if status is not None:
                    conversation.status = status
                await session.flush()
                await session.refresh(conversation)
                return conversation
