"""
Модуль для суммирования истории диалога с использованием LLM.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Попытка импорта LLM клиента (может не существовать)
try:
    from services.llm_client import get_llm_response
    HAS_LLM_CLIENT = True
except ImportError:
    HAS_LLM_CLIENT = False
    logger.warning("LLM client not found, using simple summarization")

from services.conversation_state import get_recent_messages


def summarize_conversation_history(
    chat_id: str,
    messages: List[Dict[str, str]],
    max_messages_to_summarize: int = 50,
    session: Optional[Any] = None
) -> str:
    """
    Создает краткое резюме истории диалога с помощью LLM.
    
    Args:
        chat_id: ID чата
        messages: Список сообщений (последние N сообщений)
        max_messages_to_summarize: Максимальное количество сообщений для суммирования
        session: Сессия БД (опционально)
    
    Returns:
        Краткое резюме диалога
    """
    if not messages or len(messages) < 5:
        # Если сообщений мало, суммирование не нужно
        return None
    
    # Берем последние N сообщений для суммирования
    messages_to_summarize = messages[-max_messages_to_summarize:]
    
    # Формируем промпт для суммирования
    messages_text = "\n".join([
        f"{'Пользователь' if msg.get('role') == 'user' else 'Ассистент'}: {msg.get('content', '')[:200]}"
        for msg in messages_to_summarize
    ])
    
    summary_prompt = f"""Создай краткое резюме диалога между пользователем и ассистентом Кометтик (помощник по насосному оборудованию).

История диалога:
{messages_text}

ВАЖНО - строгие правила:
- Пиши ТОЛЬКО факты из диалога выше
- НЕ выдумывай значения параметров (расход, напор, температура и т.д.)
- НЕ добавляй новые детали, которых нет в диалоге
- Если не уверен в факте - не включай его в резюме
- Если параметр не был упомянут - не пиши о нём

Резюме должно:
- Быть кратким (2-3 предложения)
- Указывать основную тему/задачу пользователя (только то, что реально было сказано)
- Упоминать ключевые параметры ТОЛЬКО если они были явно указаны в диалоге
- Не включать детали, которые не важны для продолжения диалога

Резюме:"""
    
    # Если LLM клиент доступен, используем его
    if HAS_LLM_CLIENT:
        try:
            summary = get_llm_response(
                prompt=summary_prompt,
                max_tokens=150,
                temperature=0.3,  # Низкая температура для более детерминированного резюме
            )
            
            if summary and len(summary.strip()) > 10:
                logger.info(f"Generated summary for chat {chat_id}: {summary[:100]}...")
                return summary.strip()
            else:
                logger.warning(f"Empty or too short summary for chat {chat_id}")
                return _generate_simple_summary(messages_to_summarize)
        except Exception as e:
            logger.error(f"Error generating summary for chat {chat_id}: {e}")
            # Fallback: простое резюме
            return _generate_simple_summary(messages_to_summarize)
    else:
        # Используем простое суммирование
        return _generate_simple_summary(messages_to_summarize)


def _generate_simple_summary(messages: List[Dict[str, str]]) -> str:
    """
    Генерирует простое резюме без LLM (fallback).
    """
    user_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'user']
    if not user_messages:
        return "Диалог начат."
    
    # Берем первые несколько сообщений пользователя
    first_messages = " ".join(user_messages[:3])
    if len(first_messages) > 150:
        first_messages = first_messages[:150] + "..."
    
    return f"Пользователь: {first_messages}"


def should_summarize(chat_id: str, message_count: int, session: Optional[Any] = None) -> bool:
    """
    Определяет, нужно ли суммировать историю.
    
    Args:
        chat_id: ID чата
        message_count: Количество сообщений в диалоге
        session: Сессия БД (опционально)
    
    Returns:
        True, если нужно суммировать
    """
    # Суммируем, если больше 30 сообщений
    return message_count > 30
