"""
Slot filler для извлечения температуры.
Использует унифицированный temperature_extractor.
"""
from typing import Optional, Dict, Any, Union
from services.temperature_extractor import extract_temperature
from services.conversation_state import set_temp_without_sign
from services.nlu.types import SlotUpdates


def fill_temperature(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None,
    chat_id: Optional[str] = None
) -> Optional[Union[SlotUpdates, Dict[str, Any]]]:
    """
    Извлекает температуру из сообщения.
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        chat_id: ID чата для сохранения температуры без знака
        
    Returns:
        SlotUpdates с заполненным temperature_c, или None
        Если температура найдена без знака, возвращает dict с needs_clarification=True
    """
    if pending_slot != "temperature_c" and state.get("temperature_c") is not None:
        # Температура уже заполнена и не ожидается
        return None
    
    temp_result = extract_temperature(message)
    
    if not temp_result:
        return None
    
    temp = temp_result["temperature_c"]
    has_sign = temp_result["has_sign"]
    
    if has_sign:
        # Температура со знаком - сохраняем сразу
        updates = SlotUpdates()
        updates.temperature_c = temp
        return updates
    else:
        # Температура без знака - нужно уточнить
        if pending_slot == "temperature_c":
            # Уже обработано в parse_short_answer
            return None
        
        # Сохраняем во временную переменную для последующего уточнения
        if chat_id:
            set_temp_without_sign(chat_id, temp)
        
        # Возвращаем специальный результат для уточнения
        return {
            "needs_clarification": True,
            "detected_value": temp,
            "note": "Temperature value detected but sign unclear"
        }
