"""
Единая система обработки ошибок для AI-бота Кометтик.
"""
from typing import Optional, Dict, Any
from enum import Enum
import traceback
import json
import os
from datetime import datetime


class BotErrorType(Enum):
    """Типы ошибок бота."""
    VALIDATION_ERROR = "validation_error"  # Ошибка валидации входных данных
    DATA_LOAD_ERROR = "data_load_error"  # Ошибка загрузки данных
    PARSING_ERROR = "parsing_error"  # Ошибка парсинга параметров
    CALCULATION_ERROR = "calculation_error"  # Ошибка расчётов
    INTENT_ERROR = "intent_error"  # Ошибка определения намерения
    INTEGRATION_ERROR = "integration_error"  # Ошибка интеграции модулей
    UNKNOWN_ERROR = "unknown_error"  # Неизвестная ошибка


class BotError(Exception):
    """Базовый класс для ошибок бота."""
    
    def __init__(
        self,
        error_type: BotErrorType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует ошибку в словарь для логирования."""
        result = {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details
        }
        if self.original_error:
            result["original_error"] = str(self.original_error)
            result["original_error_type"] = type(self.original_error).__name__
        return result


def log_error(
    error: Exception,
    location: str,
    context: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> None:
    """
    Логирует ошибку в debug.log.
    
    Args:
        error: исключение для логирования
        location: место возникновения ошибки (файл:строка)
        context: дополнительный контекст
        session_id: ID сессии (если есть)
    """
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "location": location,
            "message": "ERROR",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "sessionId": session_id or "system",
            "runId": "error",
            "hypothesisId": "ERROR"
        }
        
        if context:
            error_data["context"] = context
        
        if isinstance(error, BotError):
            error_data["bot_error"] = error.to_dict()
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_data) + "\n")
    except Exception as log_error:
        # Если не удалось залогировать, выводим в консоль
        print(f"Failed to log error: {log_error}")
        print(f"Original error: {error}")


def handle_error(
    error: Exception,
    location: str,
    context: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    user_message: Optional[str] = None
) -> str:
    """
    Обрабатывает ошибку и возвращает понятное сообщение пользователю.
    
    Args:
        error: исключение для обработки
        location: место возникновения ошибки
        context: дополнительный контекст
        session_id: ID сессии
        user_message: сообщение пользователя (для контекста)
        
    Returns:
        Понятное сообщение об ошибке для пользователя
    """
    # Логируем ошибку
    log_error(error, location, context, session_id)
    
    # Определяем тип ошибки и возвращаем соответствующее сообщение
    if isinstance(error, BotError):
        error_type = error.error_type
    elif isinstance(error, FileNotFoundError):
        error_type = BotErrorType.DATA_LOAD_ERROR
    elif isinstance(error, ValueError):
        error_type = BotErrorType.VALIDATION_ERROR
    elif isinstance(error, (KeyError, AttributeError)):
        error_type = BotErrorType.INTEGRATION_ERROR
    else:
        error_type = BotErrorType.UNKNOWN_ERROR
    
    # Формируем сообщение в зависимости от типа ошибки
    if error_type == BotErrorType.VALIDATION_ERROR:
        return (
            "Извините, не удалось обработать ваш запрос. "
            "Пожалуйста, проверьте формат данных и попробуйте ещё раз."
        )
    elif error_type == BotErrorType.DATA_LOAD_ERROR:
        return (
            "Извините, произошла ошибка при загрузке данных. "
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
    elif error_type == BotErrorType.PARSING_ERROR:
        return (
            "Извините, не удалось распознать параметры в вашем сообщении. "
            "Пожалуйста, укажите параметры в формате: Q: [расход] м³/ч, H: [напор] м"
        )
    elif error_type == BotErrorType.CALCULATION_ERROR:
        return (
            "Извините, произошла ошибка при расчётах. "
            "Пожалуйста, проверьте параметры и попробуйте ещё раз."
        )
    elif error_type == BotErrorType.INTENT_ERROR:
        return (
            "Извините, не удалось определить, что вы хотите. "
            "Пожалуйста, переформулируйте запрос."
        )
    elif error_type == BotErrorType.INTEGRATION_ERROR:
        return (
            "Извините, произошла внутренняя ошибка. "
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
    else:
        return (
            "Извините, произошла неожиданная ошибка. "
            "Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
        )


def error_handler(location: str):
    """
    Декоратор для обработки ошибок в функциях.
    
    Args:
        location: место вызова (обычно "файл:функция")
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Извлекаем session_id из аргументов, если есть
                session_id = None
                if args and isinstance(args[0], dict) and "session_id" in args[0]:
                    session_id = args[0]["session_id"]
                elif "session_id" in kwargs:
                    session_id = kwargs["session_id"]
                
                error_message = handle_error(e, location, session_id=session_id)
                return error_message
        
        return wrapper
    return decorator
