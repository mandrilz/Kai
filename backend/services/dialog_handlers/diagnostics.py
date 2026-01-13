"""
Обработчик интента DIAGNOSTICS - диагностика проблем с насосами.
"""
from typing import Dict, Any
from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import (
    get_diagnostics_intro,
    get_diagnostics_noise,
    get_diagnostics_cavitation,
    get_diagnostics_vibration,
    get_diagnostics_generic,
    get_diagnostics_suggestions,
)


def handle_diagnostics(
    *,
    message: str,
    data: Dict[str, Any],
) -> HandlerResult:
    """
    Обрабатывает запрос на диагностику проблем с насосом.
    
    Args:
        message: Текст сообщения пользователя
        data: Извлеченные данные из сообщения (intent detection)
    
    Returns:
        HandlerResult с частями ответа
    """
    result = HandlerResult()
    
    # Добавляем вводное сообщение
    result.response_parts.append(get_diagnostics_intro())
    
    # Определяем тип проблемы
    message_lower = message.lower()
    
    if "шум" in message_lower or "шумит" in message_lower:
        result.response_parts.append(get_diagnostics_noise())
    elif "кавитац" in message_lower:
        result.response_parts.append(get_diagnostics_cavitation())
    elif "вибрац" in message_lower or "вибрирует" in message_lower:
        result.response_parts.append(get_diagnostics_vibration())
    else:
        result.response_parts.append(get_diagnostics_generic())
    
    # Добавляем предложения
    suggestions = get_diagnostics_suggestions()
    result.response_parts.append("\n\nЧто ещё могу помочь?")
    result.response_parts.extend(suggestions)
    
    return result
