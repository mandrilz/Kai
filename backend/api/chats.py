"""
API endpoints для управления чатами.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from models import Chat, Message, ConversationState, User, get_session, select
from sqlmodel import Session
from middleware.auth import require_auth
from api.chat import generate_komettik_response, stream_response
from services.intents import detect_intent
from services.text_normalize import normalize_user_text
from services.conversation_state import (
    get_conversation, add_message, update_state, set_last_question,
    get_context_for_model, clear_conversation
)
from services.slot_extractor import extract_slot_updates, get_next_empty_slot
from fastapi import Request
from api.types import Attachment
import json
import os

from services.dialog_fsm.orchestrator import process_message as fsm_process_message

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatCreateRequest(BaseModel):
    title: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    attachments: Optional[str]
    created_at: datetime


class ChatDetailResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]


class ChatMessageRequest(BaseModel):
    message: str
    attachments: List[Dict[str, Any]] = []


def get_db_session():
    """Dependency для получения сессии БД."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def verify_chat_ownership(chat_id: UUID, user_id: str, session: Session) -> Chat:
    """Проверяет, что чат принадлежит пользователю."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")
    
    # Нормализуем user_id (убираем пробелы)
    user_id = user_id.strip() if user_id else ""
    
    # Преобразуем user_id в UUID для корректного сравнения
    try:
        user_uuid = UUID(user_id)
        chat_user_uuid = chat.user_id if isinstance(chat.user_id, UUID) else UUID(str(chat.user_id))
        if chat_user_uuid != user_uuid:
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Chat ownership verification failed: "
                f"chat_id={chat_id}, "
                f"chat.user_id={chat.user_id} (type={type(chat.user_id)}, str={str(chat.user_id)}), "
                f"user_id={user_id} (type={type(user_id)}), "
                f"user_uuid={user_uuid}, "
                f"chat_user_uuid={chat_user_uuid}"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещен")
    except ValueError as e:
        # Если user_id не является валидным UUID, сравниваем как строки
        chat_user_str = str(chat.user_id) if chat.user_id else ""
        if chat_user_str != user_id:
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Chat ownership verification failed (string comparison): "
                f"chat_id={chat_id}, "
                f"chat.user_id={chat_user_str}, "
                f"user_id={user_id}, "
                f"error={str(e)}"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещен")
    
    if chat.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат удален")
    return chat


@router.get("", response_model=List[ChatResponse])
async def list_chats(
    request: Request,
    session: Session = Depends(get_db_session),
):
    """Возвращает список чатов текущего пользователя."""
    user_id = await require_auth(request)
    
    chats = session.exec(
        select(Chat)
        .where(Chat.user_id == UUID(user_id))
        .where(Chat.deleted_at == None)
        .order_by(Chat.updated_at.desc())
    ).all()
    
    return [
        ChatResponse(
            id=str(chat.id),
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )
        for chat in chats
    ]


def get_welcome_message(is_first_chat: bool) -> str:
    """Возвращает приветственное сообщение для нового чата."""
    if is_first_chat:
        return (
            "Рад знакомству! Меня зовут Кометтик, и я буду вашим помощником.\n"
            "K.ai — первый искусственный интеллект в мире насосного оборудования.\n\n"
            "Я помогу подобрать насос Кометта под вашу задачу, предоставлю листы данных и графики рабочих характеристик.\n"
            "Также могу подобрать аналог насоса другого производителя.\n\n"
            "Давайте подберём насос Кометта или опишите вашу задачу."
        )
    else:
        import random
        greetings = [
            "Кометтик на связи. Готов подобрать насос Кометта или сравнить с другим производителем.",
            "Начнём работу. Опишите задачу или параметры насоса.",
            "Готов к новой задаче. Можем подобрать насос Кометта или сравнить с вашим оборудованием.",
            "Чем могу помочь? Можем начать с подбора насоса.",
            "Готов начать. Подберём насос Кометта или найдём аналог.",
            "Кометтик на связи. Опишите задачу или параметры.",
        ]
        return random.choice(greetings)


@router.post("", response_model=ChatResponse)
async def create_chat(
    request: Request,
    chat_data: ChatCreateRequest = Body(default=ChatCreateRequest()),
    session: Session = Depends(get_db_session),
):
    """Создает новый чат."""
    user_id = await require_auth(request)
    
    # Проверяем, есть ли у пользователя другие чаты (не удаленные)
    existing_chats = session.exec(
        select(Chat)
        .where(Chat.user_id == UUID(user_id))
        .where(Chat.deleted_at == None)
    ).all()
    
    is_first_chat = len(existing_chats) == 0
    
    chat = Chat(
        user_id=UUID(user_id),
        title=chat_data.title or "Новый чат",
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Создаем пустое состояние диалога
    conv_state = ConversationState(chat_id=chat.id)
    session.add(conv_state)
    session.commit()
    
    # Добавляем приветственное сообщение от бота
    welcome_message = get_welcome_message(is_first_chat)
    add_message(str(chat.id), "assistant", welcome_message, session)
    
    return ChatResponse(
        id=str(chat.id),
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: UUID,
    request: Request,
    session: Session = Depends(get_db_session),
):
    """Возвращает детали чата с сообщениями."""
    user_id = await require_auth(request)
    chat = verify_chat_ownership(chat_id, user_id, session)
    
    # Загружаем сообщения
    messages = session.exec(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    ).all()
    
    return ChatDetailResponse(
        id=str(chat.id),
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[
            MessageResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                attachments=msg.attachments,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
    )


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: UUID,
    request: Request,
    title: Optional[str] = None,
    session: Session = Depends(get_db_session),
):
    """Обновляет чат (например, название)."""
    user_id = await require_auth(request)
    chat = verify_chat_ownership(chat_id, user_id, session)
    
    if title is not None:
        chat.title = title
        chat.updated_at = datetime.utcnow()
        session.add(chat)
        session.commit()
        session.refresh(chat)
    
    return ChatResponse(
        id=str(chat.id),
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: UUID,
    request: Request,
    session: Session = Depends(get_db_session),
):
    """Удаляет чат (soft delete)."""
    user_id = await require_auth(request)
    chat = verify_chat_ownership(chat_id, user_id, session)
    
    chat.deleted_at = datetime.utcnow()
    session.add(chat)
    session.commit()
    
    return {"message": "Чат удален"}


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: UUID,
    request: Request,
    message_data: ChatMessageRequest,
    session: Session = Depends(get_db_session),
):
    """
    Отправляет сообщение в чат и возвращает потоковый ответ (SSE).
    Аналог старого /api/chat, но работает с chat_id и требует аутентификации.
    """
    try:
        user_id = await require_auth(request)
        chat = verify_chat_ownership(chat_id, user_id, session)
        
        # Нормализуем сообщение
        enable_fuzzy = os.getenv("TYPO_FUZZY", "1") == "1"
        normalized_message, corrections = normalize_user_text(
            message_data.message,
            enable_fuzzy=enable_fuzzy
        )
        
        # Сохраняем сообщение пользователя в БД
        # Важно: коммитим сразу, чтобы сообщение точно сохранилось даже при ошибке
        from services.conversation_state import add_message
        # Создаем сообщение напрямую, чтобы контролировать коммит
        from models import Message
        from uuid import UUID
        user_message = Message(
            chat_id=chat_id,
            role="user",
            content=normalized_message,
            attachments=None,
        )
        session.add(user_message)
        chat.updated_at = datetime.utcnow()
        session.add(chat)
        session.commit()  # Коммитим сообщение пользователя сразу
        
        # Определяем интент с учетом контекста истории
        has_attachments = len(message_data.attachments) > 0
        try:
            # Загружаем контекст для передачи в detect_intent
            from services.conversation_state import get_context_for_model
            context_for_intent = get_context_for_model(str(chat_id))
            intent_result = detect_intent(normalized_message, has_attachments, context=context_for_intent)
            
            # Убеждаемся, что intent_result имеет правильную структуру
            if not isinstance(intent_result, dict):
                intent_result = {"intent": "OFF_TOPIC", "data": {}}
            if "intent" not in intent_result:
                intent_result["intent"] = "OFF_TOPIC"
            if "data" not in intent_result or not isinstance(intent_result["data"], dict):
                intent_result["data"] = {}
        except Exception as e:
            # Если ошибка при определении интента, логируем и используем OFF_TOPIC
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error detecting intent: {str(e)}\n{traceback.format_exc()}")
            intent_result = {"intent": "OFF_TOPIC", "data": {}}
        
        # Преобразуем attachments в формат Attachment
        attachments = []
        try:
            for att in message_data.attachments:
                try:
                    attachments.append(Attachment(
                        filename=att.get("filename", "") if isinstance(att, dict) else "",
                        content_type=att.get("content_type", "") if isinstance(att, dict) else "",
                        base64=att.get("base64", "") if isinstance(att, dict) else ""
                    ))
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error processing attachment: {str(e)}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing attachments: {str(e)}")
        
        # FSM: INTENT -> SLOT_FILLING -> RESPONSE -> FOLLOW_UP
        try:
            response_text = fsm_process_message(
                chat_id=str(chat_id),
                message=normalized_message,
                attachments=attachments,
                intent_result=intent_result,
                session=session,
                generate_response_fn=generate_komettik_response,
            )
        except Exception:
            raise
        
        # Сохраняем ответ бота в БД ДО начала стриминга
        # Это гарантирует, что сообщение будет в БД когда фронтенд загрузит историю
        from services.conversation_state import add_message
        add_message(str(chat_id), "assistant", response_text, session=session)
        
        # Обновляем updated_at чата
        chat.updated_at = datetime.utcnow()
        session.add(chat)
        session.commit()
        
        # Возвращаем потоковый ответ
        return StreamingResponse(
            stream_response(response_text),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    except Exception as e:
        # Обработка ошибок
        import traceback
        import logging
        
        logger = logging.getLogger(__name__)
        error_trace = traceback.format_exc()
        logger.error(f"Error in send_message: {str(e)}\n{error_trace}")
        
        # Используем единую систему обработки ошибок
        from services.error_handler import handle_error, log_error
        
        error_message = handle_error(
            e,
            "chats.py:send_message",
            context={
                "chat_id": str(chat_id),
                "message_length": len(message_data.message) if 'message_data' in locals() else 0
            },
            session_id=str(chat_id),
            user_message=message_data.message if 'message_data' in locals() else None
        )
        
        # Для критических ошибок возвращаем простой ответ вместо 500
        async def error_stream():
            import json as json_module
            yield f"data: {json_module.dumps({'type': 'token', 'content': error_message})}\n\n"
            yield f"data: {json_module.dumps({'type': 'done'})}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
