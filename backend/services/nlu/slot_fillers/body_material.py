"""
Slot filler для извлечения материала корпуса насоса.
"""
from typing import Optional, Dict, Any
from services.body_material import detect_body_material_code_from_text
from services.nlu.types import SlotUpdates


def fill_body_material(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None
) -> Optional[SlotUpdates]:
    """
    Извлекает код материала корпуса из сообщения.
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        
    Returns:
        SlotUpdates с заполненным body_material_code, или None
    """
    if pending_slot != "body_material_code" and state.get("body_material_code"):
        # Уже заполнено и не ожидается
        return None
    
    body_code = detect_body_material_code_from_text(message)
    
    if body_code:
        updates = SlotUpdates()
        updates.body_material_code = body_code
        return updates
    
    return None
