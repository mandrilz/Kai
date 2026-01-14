"""
Правило для определения интента PUMP_TYPE.
"""
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult
from services.question_detection import is_question as detect_question


def check_pump_type(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос запросом по типу насоса.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с PUMP_TYPE или None
    """
    # Проверяем, является ли сообщение вопросом
    is_question, _ = detect_question(message)
    
    # Если это вопрос - приоритет у TECH_QA, а не у PUMP_TYPE
    if is_question:
        return None
    
    # Определяем тип насоса
    try:
        from services.pump_types import detect_pump_type
        pump_type_info = detect_pump_type(message)
    except Exception:
        return None
    
    if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
        # Конвертируем Enum в строку для сериализации
        pump_type_info_serializable = pump_type_info.copy()
        if "availability" in pump_type_info_serializable:
            from services.pump_types import PumpTypeAvailability
            availability = pump_type_info_serializable["availability"]
            if isinstance(availability, PumpTypeAvailability):
                pump_type_info_serializable["availability"] = availability.value
        
        return IntentResult(
            intent=Intent.PUMP_TYPE,
            data={"pump_type_info": pump_type_info_serializable},
            confidence=pump_type_info.get("confidence", 0.5)
        )
    
    return None
