"""
Обработчик интента MATERIALS_QUERY - запросы о материалах исполнения.
"""
from typing import Dict, Any
from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import get_materials_error


def handle_materials_query(
    *,
    chat_id: str,
    message: str,
    data: Dict[str, Any],
) -> HandlerResult:
    """
    Обрабатывает запросы о материалах исполнения для жидкости.
    
    Args:
        chat_id: ID чата
        message: Текст сообщения пользователя
        data: Извлеченные данные из сообщения (intent detection)
    
    Returns:
        HandlerResult с частями ответа
    """
    result = HandlerResult()
    
    try:
        category = data.get("category", "unknown")
        has_abrasive = data.get("has_abrasive")
        temp_c = data.get("temp_c")
        liquid_description = data.get("description", "")
        
        # Используем диалоговый поток для генерации "живого" ответа
        from services.dialog_flow import generate_materials_response_with_dialog
        
        materials_response = generate_materials_response_with_dialog(
            session_id=chat_id,
            liquid_text=liquid_description or message,
            category=category if category != "unknown" else None,
            has_abrasive=has_abrasive,
            temp_c=temp_c
        )
        result.response_parts.append(materials_response)
    except Exception as e:
        from services.error_handler import log_error
        log_error(e, "materials_query.py:handle_materials_query", 
                 context={"intent": "MATERIALS_QUERY", "data": data}, session_id=chat_id)
        result.response_parts.append(get_materials_error())
    
    return result
