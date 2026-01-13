from typing import Any, Dict, List, Optional

from sqlmodel import Session

from services.dialog_fsm.state import FSMState
from services.dialog_fsm.followups import ensure_followups
from services.conversation_state import (
    get_context_for_model,
    update_state,
    set_last_question,
    get_state_meta,
    update_state_meta,
)
from services.slot_extractor import extract_slot_updates


def process_message(
    *,
    chat_id: str,
    message: str,
    attachments: List[Any],
    intent_result: Dict[str, Any],
    session: Optional[Session] = None,
    generate_response_fn=None,
) -> str:
    """
    FSM-оркестратор: INTENT → SLOT_FILLING → RESPONSE → FOLLOW_UP.
    Генерацию ответа делегирует существующему `generate_komettik_response`
    (передаётся через generate_response_fn).
    """
    if generate_response_fn is None:
        raise ValueError("generate_response_fn is required")

    # Загружаем контекст/слоты
    context = get_context_for_model(chat_id, session=session)
    state_slots = context.get("state", {}) if isinstance(context, dict) else {}
    pending_slot = context.get("pending_slot")

    meta = get_state_meta(chat_id, session=session)
    current_state = meta.get("current_state") or FSMState.INTENT_DETECTION.value

    intent = (intent_result or {}).get("intent") or "OFF_TOPIC"
    data = (intent_result or {}).get("data") if isinstance((intent_result or {}).get("data"), dict) else {}

    # 1) INTENT_DETECTION → сохраняем intent/data
    if current_state == FSMState.INTENT_DETECTION.value:
        update_state_meta(
            chat_id,
            {
                "current_state": FSMState.SLOT_FILLING.value,
                "intent": intent,
                "data": data,
            },
            session=session,
        )
        current_state = FSMState.SLOT_FILLING.value

    # 2) SLOT_FILLING
    if current_state == FSMState.SLOT_FILLING.value:
        # Перезагружаем контекст (на всякий случай)
        context = get_context_for_model(chat_id, session=session)
        pending_slot = context.get("pending_slot")

        slot_result = extract_slot_updates(message, context, pending_slot, chat_id=chat_id)
        updates = slot_result.get("updates", {}) or {}
        next_slot = slot_result.get("next_slot")
        next_question = slot_result.get("next_question")

        # Сохраняем слоты/ожидаемый слот
        if updates:
            update_state(chat_id, updates, pending_slot=next_slot, keep_pending_if_not_set=False, session=session)
            # обновляем локально для followups
            try:
                state_slots.update(updates)
            except Exception:
                pass
        elif next_slot is not None:
            update_state(chat_id, {}, pending_slot=next_slot, keep_pending_if_not_set=False, session=session)

        if next_question:
            set_last_question(chat_id, next_question, session=session)
            update_state_meta(chat_id, {"current_state": FSMState.SLOT_FILLING.value}, session=session)
            # Возвращаем вопрос без генерации ответа
            return next_question

        # Все слоты ок — переходим к генерации ответа
        update_state_meta(chat_id, {"current_state": FSMState.RESPONSE_GENERATION.value}, session=session)
        current_state = FSMState.RESPONSE_GENERATION.value

    # 3) RESPONSE_GENERATION
    if current_state == FSMState.RESPONSE_GENERATION.value:
        # берем intent/data из meta (если были установлены на прошлом шаге)
        meta = get_state_meta(chat_id, session=session)
        intent = meta.get("intent") or intent
        data = meta.get("data") if isinstance(meta.get("data"), dict) else data

        response_text = generate_response_fn(
            intent,
            data,
            message,
            attachments,
            chat_id=chat_id,
            skip_slot_extraction=True,
        )

        update_state_meta(chat_id, {"current_state": FSMState.FOLLOW_UP.value}, session=session)
        current_state = FSMState.FOLLOW_UP.value

    # 4) FOLLOW_UP
    if current_state == FSMState.FOLLOW_UP.value:
        # актуальные слоты для followups
        context = get_context_for_model(chat_id, session=session)
        state_slots = context.get("state", {}) if isinstance(context, dict) else {}

        meta = get_state_meta(chat_id, session=session)
        intent = meta.get("intent") or intent

        final_text = ensure_followups(response_text, intent, state_slots)

        # Сбрасываем FSM в начало цикла
        update_state_meta(chat_id, {"current_state": FSMState.INTENT_DETECTION.value}, session=session)
        return final_text

    # Fallback
    update_state_meta(chat_id, {"current_state": FSMState.INTENT_DETECTION.value}, session=session)
    return ensure_followups("Я Кометтик — инженер‑помощник Кометта.", intent, state_slots)

