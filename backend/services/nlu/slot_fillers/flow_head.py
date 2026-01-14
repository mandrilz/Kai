"""
Slot filler для извлечения расхода (Q) и напора (H).
Поддерживает извлечение как пары Q/H, так и отдельных параметров.
"""
from typing import Optional, Dict, Any
from services.intents import extract_qh_from_text
from services.q_extractor import extract_q_from_text
from services.h_extractor import extract_h_from_text
from services.nlu.types import SlotUpdates


def fill_flow_head(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None
) -> Optional[SlotUpdates]:
    """
    Извлекает расход (Q) и/или напор (H) из сообщения.
    
    PR2: Поддерживает извлечение по одному параметру:
    - Если найден только Q → обновляет flow_m3h
    - Если найден только H → обновляет head_m
    - Если найдены оба → обновляет оба
    
    Args:
        message: Нормализованное сообщение пользователя
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        
    Returns:
        SlotUpdates с заполненными flow_m3h и/или head_m, или None
    """
    updates = SlotUpdates()
    found_any = False
    
    # Приоритет 1: Пытаемся извлечь пару Q/H одновременно
    qh_data = extract_qh_from_text(message)
    if qh_data and qh_data.get("q") and qh_data.get("h"):
        updates.flow_m3h = qh_data["q"]
        updates.head_m = qh_data["h"]
        found_any = True
    else:
        # Приоритет 2: Извлекаем Q и H по отдельности
        # Это важно для кейса "Q=10" потом "H=40" в разных сообщениях
        
        # Извлекаем Q (если не заполнен в state)
        if not state.get("flow_m3h"):
            q_result = extract_q_from_text(message)
            if q_result and q_result.get("confidence", 0) > 0.5:
                updates.flow_m3h = q_result["q_m3h"]
                found_any = True
        
        # Извлекаем H (если не заполнен в state)
        if not state.get("head_m"):
            h_result = extract_h_from_text(message)
            if h_result and h_result.get("confidence", 0) > 0.5:
                updates.head_m = h_result["h_m"]
                found_any = True
    
    # Если pending_slot указывает на flow_m3h или head_m, приоритет выше
    if pending_slot == "flow_m3h" and not updates.flow_m3h:
        q_result = extract_q_from_text(message)
        if q_result and q_result.get("confidence", 0) > 0.3:
            updates.flow_m3h = q_result["q_m3h"]
            found_any = True
    
    if pending_slot == "head_m" and not updates.head_m:
        h_result = extract_h_from_text(message)
        if h_result and h_result.get("confidence", 0) > 0.3:
            updates.head_m = h_result["h_m"]
            found_any = True
    
    return updates if found_any else None


def should_trigger_selection(state: Dict[str, Any], updates: SlotUpdates) -> bool:
    """
    Проверяет, достаточно ли данных для запуска подбора насоса.
    
    Args:
        state: Текущее состояние диалога
        updates: Обновления слотов
        
    Returns:
        True если есть и Q и H (в state или updates)
    """
    flow = updates.flow_m3h if updates.flow_m3h is not None else state.get("flow_m3h")
    head = updates.head_m if updates.head_m is not None else state.get("head_m")
    
    return flow is not None and head is not None
