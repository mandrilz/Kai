"""
Единый пайплайн для заполнения слотов из сообщения пользователя.
Объединяет все модульные slot fillers в единый процесс.
"""
from typing import Dict, Any, Optional
from services.nlu.types import SlotUpdates, SlotFillResult
from services.nlu.slot_fillers.flow_head import fill_flow_head
from services.nlu.slot_fillers.fluid import fill_fluid
from services.nlu.slot_fillers.temperature import fill_temperature
from services.nlu.slot_fillers.solids import fill_solids
from services.nlu.slot_fillers.h_st import fill_h_st
from services.nlu.slot_fillers.body_material import fill_body_material
from services.conversation_state import parse_short_answer, get_next_empty_slot
from services.dialog_phrases import get_phrase, TEMPERATURE_SIGN_QUESTIONS
from services.clarifying_questions import get_clarifying_question
import random


def fill_slots(
    message: str,
    state: Dict[str, Any],
    pending_slot: Optional[str] = None,
    chat_id: Optional[str] = None,
    already_normalized: bool = False
) -> SlotFillResult:
    """
    Единый пайплайн для заполнения слотов из сообщения пользователя.
    
    Порядок обработки:
    1. Если есть pending_slot - сначала пытаемся распарсить как ответ на вопрос
    2. Затем применяем все fillers по приоритету
    3. Определяем следующий слот для уточнения
    
    Args:
        message: Сообщение пользователя (будет нормализовано, если already_normalized=False)
        state: Текущее состояние диалога
        pending_slot: Ожидаемый слот (если есть)
        chat_id: ID чата (для работы с температурой без знака)
        already_normalized: Уже нормализовано ли сообщение (для избежания двойной нормализации)
        
    Returns:
        SlotFillResult с обновлениями и информацией о следующем шаге
    
    Note:
        PR4: Для избежания двойной нормализации рекомендуется передавать уже нормализованный текст
        с флагом already_normalized=True. Экстракторы внутри могут выполнять дополнительную
        нормализацию (например, temperature-specific), но базовая нормализация должна быть
        выполнена один раз на уровне DialogueManager.
    """
    # Нормализуем только если еще не нормализовано
    if not already_normalized:
        from services.nlu.preprocess import normalize_text
        message = normalize_text(message)
    # Итоговые обновления
    final_updates = SlotUpdates()
    confidence = 0.5
    needs_clarification = False
    next_question = None
    next_slot = None
    note = None
    
    # Приоритет 1: Если есть pending_slot - парсим как ответ
    if pending_slot:
        short_answer = parse_short_answer(message, pending_slot, chat_id=chat_id)
        if short_answer:
            # Проверяем, нужно ли пропустить слот
            if short_answer.get("skip_slot"):
                # Пропускаем этот слот и переходим к следующему
                merged_state = {**state, **final_updates.to_dict()}
                next_slot = get_next_empty_slot(merged_state, {})
                if next_slot:
                    next_question = get_clarifying_question(next_slot, merged_state)
                return SlotFillResult(
                    updates=SlotUpdates(),
                    confidence=short_answer.get("confidence", 0.5),
                    next_slot=next_slot,
                    needs_clarification=bool(next_slot),
                    next_question=next_question,
                    note=short_answer.get("note", "User indicated they want to skip this parameter")
                )
            
            # Проверяем, нужно ли уточнение (например, для категории MAYBE)
            if short_answer.get("needs_clarification"):
                merged_state = {**state, **final_updates.to_dict()}
                next_question = get_clarifying_question(pending_slot, merged_state)
                return SlotFillResult(
                    updates=SlotUpdates(),
                    confidence=short_answer.get("confidence", 0.5),
                    needs_clarification=True,
                    next_question=next_question,
                    next_slot=short_answer.get("next_slot", pending_slot),
                    note=short_answer.get("note", "User is unsure about this parameter")
                )
            
            # Обновляем слоты из short_answer
            short_updates = short_answer.get("updates", {})
            for key, value in short_updates.items():
                if hasattr(final_updates, key):
                    setattr(final_updates, key, value)
            
            confidence = max(confidence, short_answer.get("confidence", 0.7))
            next_slot = short_answer.get("next_slot")
    
    # Приоритет 2: Применяем все fillers по порядку
    # Порядок важен: сначала критичные параметры (Q/H), затем остальные
    
    # 2.1: Расход и напор (рабочая точка)
    flow_head_updates = fill_flow_head(message, state, pending_slot)
    if flow_head_updates:
        if flow_head_updates.flow_m3h is not None:
            final_updates.flow_m3h = flow_head_updates.flow_m3h
        if flow_head_updates.head_m is not None:
            final_updates.head_m = flow_head_updates.head_m
        confidence = max(confidence, 0.9)
    
    # 2.2: Материал корпуса
    body_material_updates = fill_body_material(message, state, pending_slot)
    if body_material_updates and body_material_updates.body_material_code:
        final_updates.body_material_code = body_material_updates.body_material_code
        confidence = max(confidence, 0.75)
    
    # 2.3: Температура
    temp_result = fill_temperature(message, state, pending_slot, chat_id)
    if temp_result:
        if isinstance(temp_result, SlotUpdates):
            final_updates.temperature_c = temp_result.temperature_c
            confidence = max(confidence, 0.85)
        elif isinstance(temp_result, dict) and temp_result.get("needs_clarification"):
            # Температура без знака - нужно уточнить
            fluid = state.get("fluid")
            temp = temp_result.get("detected_value")
            if fluid and temp is not None:
                plus_val = f"+{temp}".replace("+-", "-")
                variants = [
                    f"Я правильно понял: {fluid} {plus_val}°C?",
                    f"Уточню знак температуры: {fluid} {plus_val}°C — верно?",
                    f"Подтвердите, пожалуйста: {fluid} {plus_val}°C?",
                    f"Для правильного подбора важно понять знак: {fluid} {plus_val}°C — это плюс?",
                ]
                next_question = random.choice(variants) + " Если температура минусовая — напишите «минус» или укажите «-...°C»."
            else:
                next_question = get_phrase(TEMPERATURE_SIGN_QUESTIONS)
                if temp is not None:
                    next_question = f"Вы указали {temp}°C. {next_question}"
            
            return SlotFillResult(
                updates=SlotUpdates(),
                confidence=0.6,
                needs_clarification=True,
                next_question=next_question,
                next_slot="temperature_c",
                note="Temperature value detected but sign unclear"
            )
    
    # 2.4: Жидкость
    fluid_updates = fill_fluid(message, state, pending_slot)
    if fluid_updates:
        final_updates.fluid = fluid_updates.fluid
        if fluid_updates.concentration is not None:
            final_updates.concentration = fluid_updates.concentration
        confidence = max(confidence, 0.8)
    
    # 2.5: Примеси
    solids_updates = fill_solids(message, state, pending_slot)
    if solids_updates and solids_updates.solids is not None:
        final_updates.solids = solids_updates.solids
        confidence = max(confidence, 0.75)
    
    # 2.6: Статический напор
    h_st_updates = fill_h_st(message, state, pending_slot)
    if h_st_updates and h_st_updates.h_st is not None:
        final_updates.h_st = h_st_updates.h_st
        confidence = max(confidence, 0.8)
    
    # Определяем следующий слот для уточнения
    if not final_updates.has_updates() and pending_slot:
        # Пользователь не ответил на вопрос - повторяем тот же слот
        next_slot = pending_slot
        next_question = get_clarifying_question(pending_slot, state)
        needs_clarification = True
        note = "User did not provide expected slot value"
    elif final_updates.has_updates():
        # Успешно распарсили - определяем следующий незаполненный слот
        if next_slot is None:
            merged_state = {**state, **final_updates.to_dict()}
            next_slot = get_next_empty_slot(merged_state, {})
        
        if next_slot:
            merged_state = {**state, **final_updates.to_dict()}
            next_question = get_clarifying_question(next_slot, merged_state)
            needs_clarification = True
        else:
            # Все слоты заполнены - можно делать подбор
            needs_clarification = False
    else:
        # Не распарсили ничего - сохраняем pending_slot если он был
        if pending_slot:
            next_slot = pending_slot
            next_question = get_clarifying_question(pending_slot, state)
            note = "Could not extract slot value from message"
    
    return SlotFillResult(
        updates=final_updates,
        confidence=confidence,
        needs_clarification=needs_clarification,
        next_question=next_question,
        next_slot=next_slot,
        note=note
    )
