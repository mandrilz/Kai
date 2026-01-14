"""
Slot filler для извлечения информации о наличии примесей/твердых частиц.
"""
from typing import Optional, Dict, Any
from services.nlu.types import SlotUpdates


def fill_solids(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None
) -> Optional[SlotUpdates]:
    """
    Извлекает информацию о наличии примесей из сообщения.
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        
    Returns:
        SlotUpdates с заполненным solids, или None
    """
    if pending_slot != "solids" and state.get("solids") is not None:
        # Уже заполнено и не ожидается
        return None
    
    updates = SlotUpdates()
    
    # Проверяем наличие примесей
    if any(word in message for word in ["примеси", "песок", "твердые", "абразив", "solids", "abrasive"]):
        updates.solids = True
        return updates
    elif any(word in message for word in ["чистая", "без примесей", "чистая жидкость"]):
        updates.solids = False
        return updates
    
    return None
