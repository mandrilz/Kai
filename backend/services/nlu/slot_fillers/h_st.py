"""
Slot filler для извлечения статического напора (h_st).
"""
import re
from typing import Optional, Dict, Any
from services.nlu.types import SlotUpdates


def fill_h_st(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None
) -> Optional[SlotUpdates]:
    """
    Извлекает статический напор из сообщения.
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        
    Returns:
        SlotUpdates с заполненным h_st, или None
    """
    if pending_slot != "h_st" and state.get("h_st") is not None:
        # Уже заполнено и не ожидается
        return None
    
    updates = SlotUpdates()
    
    # Проверяем ответы "нет", "отсутствует", "0" для статического напора
    if any(word in message for word in ["нет", "отсутствует", "ноль", "нуль", "нет статического", "статического нет"]):
        updates.h_st = 0.0
        return updates
    
    # Ищем числовое значение статического напора
    h_st_patterns = [
        r'статический\s+напор[:\s]+(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
        r'h[_\s]*ст[:\s]*=?\s*(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
        r'статический[:\s]+(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
        r'(\d+(?:[.,]\d+)?)\s*м\s*(?:статический|статического)?'
    ]
    
    for pattern in h_st_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                h_st = float(match.group(1).replace(',', '.'))
                if 0 <= h_st <= 500:
                    updates.h_st = h_st
                    return updates
            except ValueError:
                pass
    
    return None
