"""
Утилиты для логирования с correlationId и tokenCount.
"""
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)


def generate_correlation_id() -> str:
    """
    Генерирует уникальный correlation ID для отслеживания запроса.
    """
    return str(uuid.uuid4())


def log_request(
    correlation_id: str,
    endpoint: str,
    method: str,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Логирует входящий запрос с correlation ID.
    
    Args:
        correlation_id: Уникальный ID для отслеживания запроса
        endpoint: Эндпоинт API
        method: HTTP метод
        user_id: ID пользователя (опционально)
        chat_id: ID чата (опционально)
        **kwargs: Дополнительные поля для логирования
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": correlation_id,
        "type": "request",
        "endpoint": endpoint,
        "method": method,
        "user_id": user_id,
        "chat_id": chat_id,
        **kwargs
    }
    
    logger.info(f"[{correlation_id}] Request: {method} {endpoint}", extra={"data": log_data})


def log_response(
    correlation_id: str,
    status_code: int,
    response_time_ms: Optional[float] = None,
    token_count: Optional[int] = None,
    context_token_estimate: Optional[int] = None,
    summary_used: Optional[bool] = None,
    recent_messages_count: Optional[int] = None,
    **kwargs
) -> None:
    """
    Логирует ответ с correlation ID и метриками.
    
    Args:
        correlation_id: Уникальный ID запроса
        status_code: HTTP статус код
        response_time_ms: Время ответа в миллисекундах (опционально)
        token_count: Количество токенов в ответе (опционально)
        context_token_estimate: Оценка токенов контекста (опционально)
        summary_used: Использовался ли summary (опционально)
        recent_messages_count: Количество недавних сообщений (опционально)
        **kwargs: Дополнительные поля для логирования
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": correlation_id,
        "type": "response",
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "token_count": token_count,
        "context_token_estimate": context_token_estimate,
        "summary_used": summary_used,
        "recent_messages_count": recent_messages_count,
        **kwargs
    }
    
    # Удаляем PII из логов (полный текст пользователя)
    if "user_message" in log_data:
        del log_data["user_message"]
    
    logger.info(
        f"[{correlation_id}] Response: {status_code} "
        f"(tokens: {token_count or 'N/A'}, context_tokens: {context_token_estimate or 'N/A'}, "
        f"summary: {summary_used or False}, time: {response_time_ms or 'N/A'}ms)",
        extra={"data": log_data}
    )


def log_llm_call(
    correlation_id: str,
    prompt: str,
    response: str,
    token_count: Optional[int] = None,
    model: Optional[str] = None,
    **kwargs
) -> None:
    """
    Логирует вызов LLM с метриками.
    
    Args:
        correlation_id: Уникальный ID запроса
        prompt: Промпт, отправленный в LLM
        response: Ответ от LLM
        token_count: Количество токенов (опционально)
        model: Модель LLM (опционально)
        **kwargs: Дополнительные поля для логирования
    """
    # Ограничиваем длину промпта и ответа для логов
    prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
    response_preview = response[:200] + "..." if len(response) > 200 else response
    
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": correlation_id,
        "type": "llm_call",
        "model": model,
        "token_count": token_count,
        "prompt_length": len(prompt),
        "response_length": len(response),
        "prompt_preview": prompt_preview,
        "response_preview": response_preview,
        **kwargs
    }
    
    logger.info(
        f"[{correlation_id}] LLM call: model={model or 'N/A'}, "
        f"tokens={token_count or 'N/A'}, prompt_len={len(prompt)}, response_len={len(response)}",
        extra={"data": log_data}
    )


def estimate_token_count(text: str) -> int:
    """
    Оценивает количество токенов в тексте (приблизительно).
    
    Args:
        text: Текст для оценки
    
    Returns:
        Приблизительное количество токенов
    """
    # Простая оценка: ~4 символа на токен для русского/английского текста
    # Для более точной оценки нужно использовать tiktoken или аналогичную библиотеку
    return len(text) // 4


def write_debug_log(level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
    """
    Записывает лог в debug файл.
    
    Args:
        level: Уровень лога (info, warning, error)
        message: Сообщение
        data: Дополнительные данные
    """
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data or {}
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to write debug log: {e}")
