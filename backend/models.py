"""
Модели данных для аутентификации и чатов.
Использует SQLModel для работы с SQLite (MVP) с возможностью миграции на PostgreSQL.
"""
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session, select
from sqlalchemy import Column, String
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
import json


class User(SQLModel, table=True):
    """Пользователь системы."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    chats: List["Chat"] = Relationship(back_populates="user")
    magic_link_tokens: List["MagicLinkToken"] = Relationship(back_populates="user")


class Chat(SQLModel, table=True):
    """Чат пользователя."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    title: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None)  # Soft delete
    
    # Relationships
    user: User = Relationship(back_populates="chats")
    messages: List["Message"] = Relationship(back_populates="chat")
    conversation_state: Optional["ConversationState"] = Relationship(back_populates="chat")


class Message(SQLModel, table=True):
    """Сообщение в чате."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chat_id: UUID = Field(foreign_key="chat.id", index=True)
    role: str = Field()  # "user" | "assistant"
    content: str
    attachments: Optional[str] = Field(default=None, sa_column=Column(String))  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    chat: Chat = Relationship(back_populates="messages")


class ConversationState(SQLModel, table=True):
    """Состояние диалога (слоты) для чата."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chat_id: UUID = Field(foreign_key="chat.id", unique=True, index=True)
    state: str = Field(default="{}")  # JSON string with slots
    pending_slot: Optional[str] = Field(default=None)
    last_question: Optional[str] = Field(default=None)
    dialog_summary: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    chat: Chat = Relationship(back_populates="conversation_state")


class MagicLinkToken(SQLModel, table=True):
    """Одноразовый токен для magic-link аутентификации."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    token: str = Field(unique=True, index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    email: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    used_at: Optional[datetime] = Field(default=None)
    expires_at: datetime
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="magic_link_tokens")


# Database engine (SQLite для MVP)
DATABASE_URL = "sqlite:///./kometta_ai.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    """Создает все таблицы в БД."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Возвращает сессию БД."""
    return Session(engine)
