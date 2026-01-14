"""
Slot filler для извлечения типа жидкости.
"""
from typing import Optional, Dict, Any
from services.nlu.types import SlotUpdates


def fill_fluid(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None
) -> Optional[SlotUpdates]:
    """
    Извлекает тип жидкости из сообщения.
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        
    Returns:
        SlotUpdates с заполненным fluid, или None
    """
    if pending_slot != "fluid" and state.get("fluid"):
        # Жидкость уже заполнена и не ожидается
        return None
    
    updates = SlotUpdates()
    
    fluid_keywords = {
        "вода": "вода",
        "water": "вода",
        "этиленгликоль": "этиленгликоль",
        "пропиленгликоль": "пропиленгликоль",
        "масло": "масло",
        "oil": "масло",
        "гликоль": "этиленгликоль",
        "антифриз": "этиленгликоль"
    }
    
    for keyword, fluid in fluid_keywords.items():
        if keyword in message:
            updates.fluid = fluid
            
            # Для воды сразу заполняем концентрацию нулем (если не заполнена)
            if fluid == "вода":
                concentration = state.get("concentration")
                if concentration is None:
                    updates.concentration = 0.0
            
            return updates
    
    return None
