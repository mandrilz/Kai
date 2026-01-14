"""
Правило для определения интента SELECTION_BY_POINT.
"""
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult
from services.intents import extract_qh_from_text


def check_selection_by_point(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос подбором насоса по рабочей точке (Q/H).
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с SELECTION_BY_POINT или None
    """
    # Получаем расширенный контекст для поиска
    recent_messages = context.get("recent_messages", [])
    context_text = ""
    if recent_messages:
        user_messages = [msg.get("content", "") for msg in recent_messages[-5:] if msg.get("role") == "user"]
        if user_messages:
            context_text = " ".join(user_messages)
    
    full_context = f"{context_text} {message}".strip() if context_text else message
    search_text = full_context.lower()
    
    # 1. Извлекаем Q и H из сообщения
    qh_data = extract_qh_from_text(message)
    if qh_data:
        # Добавляем информацию о типе насоса, если есть
        try:
            from services.pump_types import detect_pump_type
            pump_type_info = detect_pump_type(message)
        except Exception:
            pump_type_info = None
        
        data = dict(qh_data)
        if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
            # Конвертируем Enum в строку для сериализации
            pump_type_info_serializable = pump_type_info.copy()
            if "availability" in pump_type_info_serializable:
                from services.pump_types import PumpTypeAvailability
                availability = pump_type_info_serializable["availability"]
                if isinstance(availability, PumpTypeAvailability):
                    pump_type_info_serializable["availability"] = availability.value
            data["pump_type_info"] = pump_type_info_serializable
        
        return IntentResult(
            intent=Intent.SELECTION_BY_POINT,
            data=data,
            confidence=0.9
        )
    
    # 2. Ключевые слова для подбора
    selection_keywords = [
        "подбери", "подобрать", "подбор", "нужен насос",
        "рабочая точка", "точка работы", "q=", "h=", "подача", "расход"
    ]
    if any(keyword in search_text for keyword in selection_keywords):
        # Пробуем извлечь Q и H ещё раз
        qh_data = extract_qh_from_text(message)
        try:
            from services.pump_types import detect_pump_type
            pump_type_info = detect_pump_type(message)
        except Exception:
            pump_type_info = None
        
        data = dict(qh_data or {})
        if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
            pump_type_info_serializable = pump_type_info.copy()
            if "availability" in pump_type_info_serializable:
                from services.pump_types import PumpTypeAvailability
                availability = pump_type_info_serializable["availability"]
                if isinstance(availability, PumpTypeAvailability):
                    pump_type_info_serializable["availability"] = availability.value
            data["pump_type_info"] = pump_type_info_serializable
        
        return IntentResult(
            intent=Intent.SELECTION_BY_POINT,
            data=data,
            confidence=0.8
        )
    
    return None
