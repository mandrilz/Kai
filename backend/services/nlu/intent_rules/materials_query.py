"""
Правило для определения интента MATERIALS_QUERY.
"""
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult


def check_materials_query(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос запросом о материалах исполнения.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с MATERIALS_QUERY или None
    """
    message_lower = message.lower()
    
    # Ключевые слова для запроса материалов
    materials_keywords = [
        "материал", "исполнение", "жидкость", "среда", "для воды", "для масла",
        "для масла", "для топлива", "для гликоля", "для раствора", "для антифриза",
        "какое исполнение", "какой материал", "подходит материал", "материал a",
        "материал e", "материал x", "материал h", "исполнение a", "исполнение e",
        "исполнение x", "исполнение h", "epdm", "fpm", "силикон", "graphite",
        "sic", "уплотнение", "эластомер"
    ]
    
    if any(keyword in message_lower for keyword in materials_keywords):
        # Извлекаем информацию о жидкости
        from services.materials import extract_liquid_info
        liquid_info = extract_liquid_info(message)
        
        return IntentResult(
            intent=Intent.MATERIALS_QUERY,
            data=liquid_info,
            confidence=0.85
        )
    
    return None
