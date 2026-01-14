"""
NLU/Extractor для парсинга сообщений пользователя и обновления слотов.
Реализует двухходовку: сначала структурирование, потом ответ.
"""
from typing import Dict, Any, Optional
import re
import warnings
from services.q_extractor import extract_q_from_text
from services.h_extractor import extract_h_from_text
from services.intents import extract_qh_from_text
from services.conversation_state import parse_short_answer, SLOT_SCHEMA
from services.dialog_phrases import TEMPERATURE_SIGN_QUESTIONS, get_phrase
import random
from services.body_material import detect_body_material_code_from_text


def extract_slot_updates(
    message: str,
    context: Dict[str, Any],
    pending_slot: Optional[str] = None,
    chat_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Извлекает обновления слотов из сообщения пользователя.
    
    PR2: Использует единый пайплайн slot_filler.fill_slots().
    Этот метод теперь является тонким фасадом над новым модульным пайплайном.
    
    Args:
        message: сообщение пользователя
        context: контекст диалога (state, recent_messages и т.д.)
        pending_slot: ожидаемый слот
        chat_id: ID чата (для работы с сохраненными значениями температуры без знака)
        session_id: устаревший алиас chat_id (для обратной совместимости)
        
    Returns:
        {
            "updates": Dict[str, Any],  # Обновления слотов
            "confidence": float,  # Уверенность (0-1)
            "needs_clarification": bool,  # Нужно ли уточнение
            "next_question": str | None,  # Следующий вопрос
            "next_slot": str | None,  # Следующий слот для уточнения
            "note": str | None  # Примечание (например, "unrelated question")
        }
    """
    # PR2: Используем единый пайплайн slot_filler
    from services.nlu.slot_filler import fill_slots
    from services.nlu.preprocess import normalize_text
    
    # Нормализуем сообщение
    message_normalized = normalize_text(message)
    
    # Получаем состояние из контекста
    state = context.get("state", {})
    
    # Совместимость: session_id (старое имя) → chat_id
    if chat_id is None:
        chat_id = session_id
    if chat_id is None:
        chat_id = context.get("chat_id") or context.get("session_id")
    
    # Вызываем единый пайплайн
    # ИСПРАВЛЕНО: Передаем already_normalized=True, т.к. уже нормализовали выше
    result = fill_slots(message_normalized, state, pending_slot, chat_id, already_normalized=True)
    
    # Преобразуем SlotFillResult в старый формат для обратной совместимости
    return {
        "updates": result.updates.to_dict(),
        "confidence": result.confidence,
        "needs_clarification": result.needs_clarification,
        "next_question": result.next_question,
        "next_slot": result.next_slot,
        "note": result.note
    }


def get_slot_question(slot: str, state: Dict[str, Any]) -> str:
    """
    Получает уточняющий вопрос для слота.
    Использует унифицированный модуль clarifying_questions.
    """
    from services.clarifying_questions import get_clarifying_question
    return get_clarifying_question(slot, state)


# ===== LEGACY FUNCTIONS (DO NOT USE IN NEW PIPELINE) =====
# PR4: Эти функции устарели и не используются новым пайплайном (services.nlu.slot_filler).
# Они оставлены для обратной совместимости со старым кодом (api/chat.py, api/chats.py).
# В новом коде используйте:
# - conversation_state.get_next_empty_slot() вместо get_next_empty_slot()
# - slot_fillers.flow_head.should_trigger_selection() вместо should_trigger_selection()

def get_next_empty_slot(state: Dict[str, Any], updates: Dict[str, Any] = None) -> Optional[str]:
    """
    LEGACY: Определяет следующий незаполненный слот для уточнения.
    
    ⚠️ DEPRECATED: Эта функция устарела и не используется новым пайплайном.
    Используйте conversation_state.get_next_empty_slot() вместо неё.
    
    Оставлена для обратной совместимости со старым кодом.
    """
    warnings.warn(
        "get_next_empty_slot is deprecated, use conversation_state.get_next_empty_slot",
        DeprecationWarning,
        stacklevel=2
    )
    merged_state = {**state, **(updates or {})}
    
    # Приоритет слотов для подбора насоса (по важности)
    # Уровень 1: Критичные для подбора (рабочая точка)
    priority_level_1 = [
        "flow_m3h",  # Расход - самый важный
        "head_m",    # Напор - второй по важности
    ]
    
    # Уровень 2: Важные для точности подбора
    priority_level_2 = [
        "fluid",     # Жидкость
        "temperature_c",  # Температура
    ]
    
    # Уровень 3: Дополнительные параметры (если нужны)
    priority_level_3 = [
        "solids",    # Примеси
        "h_st",      # Статический напор
        "viscosity",  # Вязкость
    ]
    
    # Уровень 4: Монтаж и материалы (если нужны)
    priority_level_4 = [
        "installation",  # Установка
        "materials"  # Материалы
    ]
    
    # Проверяем по приоритетам - задаем только ОДИН вопрос за раз
    for slot in priority_level_1:
        if slot in SLOT_SCHEMA and merged_state.get(slot) is None:
            return slot
    
    # Если рабочая точка есть, переходим к уровню 2
    if merged_state.get("flow_m3h") and merged_state.get("head_m"):
        for slot in priority_level_2:
            if slot in SLOT_SCHEMA and merged_state.get(slot) is None:
                return slot
        
        # Если есть рабочая точка и жидкость, переходим к уровню 3
        if merged_state.get("fluid"):
            for slot in priority_level_3:
                if slot in SLOT_SCHEMA and merged_state.get(slot) is None:
                    return slot
            
            # Если жидкость требует концентрации (например, этиленгликоль), запрашиваем concentration
            fluid = merged_state.get("fluid")
            if fluid and fluid.lower() in {"этиленгликоль", "пропиленгликоль", "антифриз", "гликоль"} and merged_state.get("concentration") is None:
                return "concentration"
            
            # Уровень 4 - только если все остальное заполнено
            for slot in priority_level_4:
                if slot in SLOT_SCHEMA and merged_state.get(slot) is None:
                    return slot
    
    return None


def should_trigger_selection(state: Dict[str, Any]) -> bool:
    """
    LEGACY: Определяет, достаточно ли данных для подбора насоса.
    
    ⚠️ DEPRECATED: Эта функция устарела и не используется новым пайплайном.
    Используйте slot_fillers.flow_head.should_trigger_selection() вместо неё.
    
    Оставлена для обратной совместимости со старым кодом.
    """
    warnings.warn(
        "should_trigger_selection is deprecated, use slot_fillers.flow_head.should_trigger_selection",
        DeprecationWarning,
        stacklevel=2
    )
    # Минимум: расход и напор
    return (
        state.get("flow_m3h") is not None and
        state.get("head_m") is not None
    )
