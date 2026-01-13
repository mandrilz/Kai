"""
Модуль диалогового потока для "живого" поведения Кометтика.
Управляет задаванием вопросов, памятью контекста и генерацией ответов.
"""
from typing import Dict, Any, Optional, Tuple, List
from services.session_state import get_session_state, update_session_state, calculate_confidence
from services.materials import classify_liquid, decide_materials, get_stock_series_by_materials, generate_materials_response
from services.dialog_phrases import (
    get_phrase, combine_phrases,
    INTRO_PHRASES, CONFIRM_PHRASES, LIQUID_QUESTIONS,
    TEMPERATURE_QUESTIONS, ABRASIVE_QUESTIONS, REASONING_PHRASES,
    EXPLAIN_PHRASES, MATERIALS_RESULT_PHRASES, STOCK_PHRASES,
    FOLLOWUP_PHRASES, HUMAN_TOUCH_PHRASES, MISSING_DATA_PHRASES
)


def next_question(state: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Определяет следующий вопрос на основе текущего состояния.
    
    Returns:
        (question_text, question_type) или None если все вопросы заданы
    """
    # Приоритет 1: Категория жидкости (самое важное)
    if state.get("liquid_category") in [None, "unknown"]:
        return (get_phrase(LIQUID_QUESTIONS), "liquid")
    
    # Приоритет 2: Температура
    if state.get("temp_c") is None:
        return (get_phrase(TEMPERATURE_QUESTIONS), "temperature")
    
    # Приоритет 3: Примеси/абразив
    if state.get("has_abrasive") is None:
        return (get_phrase(ABRASIVE_QUESTIONS), "abrasive")
    
    # Все вопросы заданы
    return None


def generate_reasoning_trace(state: Dict[str, Any], category: str, has_abrasive: Optional[bool]) -> str:
    """
    Генерирует короткое "инженерное рассуждение" (2-3 пункта).
    
    Returns:
        Текст рассуждения
    """
    reasoning_parts = []
    
    # Определяем категорию если ещё не определена
    if category and category != "unknown":
        reasoning_parts.append(f"Среда классифицирована как: {category}")
    
    if state.get("temp_c") is not None:
        temp = state.get("temp_c")
        reasoning_parts.append(f"температура: {temp}°C")
    
    if has_abrasive is not None:
        reasoning_parts.append(f"абразив: {'есть' if has_abrasive else 'нет'}")
    
    if reasoning_parts:
        reasoning_text = " → ".join(reasoning_parts)
        
        # Определяем материалы для объяснения
        materials_result = decide_materials(category, has_abrasive, state.get("temp_c"))
        allowed = materials_result.get("allowed_materials", [])
        
        if allowed:
            reasoning_text += f" → подходят материалы: {', '.join(allowed)}"
        
        return reasoning_text
    
    return ""


def generate_materials_response_with_dialog(
    session_id: str,
    liquid_text: str,
    category: Optional[str] = None,
    has_abrasive: Optional[bool] = None,
    temp_c: Optional[float] = None
) -> str:
    """
    Генерирует ответ о материалах с "живым" диалоговым поведением.
    
    Args:
        session_id: ID сессии
        liquid_text: текст пользователя о жидкости
        category: категория (если уже определена)
        has_abrasive: есть ли абразив
        temp_c: температура
        
    Returns:
        Ответ бота
    """
    # Получаем состояние сессии
    state = get_session_state(session_id)
    
    # Обновляем состояние на основе нового сообщения
    if liquid_text:
        # Классифицируем жидкость если категория не известна
        if not category:
            category, _ = classify_liquid(liquid_text)
        
        state["liquid_text"] = liquid_text
        state["liquid_category"] = category
    
    if temp_c is not None:
        state["temp_c"] = temp_c
    
    if has_abrasive is not None:
        state["has_abrasive"] = has_abrasive
    
    # Вычисляем уверенность
    confidence = calculate_confidence(state)
    state["confidence"] = confidence
    
    # Сохраняем состояние
    update_session_state(session_id, state)
    
    # Генерируем ответ
    response_parts = []
    
    # 1. Вступительная фраза (если это первое сообщение о материалах)
    if not state.get("materials_discussed"):
        response_parts.append(get_phrase(INTRO_PHRASES))
    
    # 2. Проверяем, нужно ли задать вопрос
    next_q = next_question(state)
    
    if next_q:
        question_text, question_type = next_q
        
        # Если категория уже определена, но не все параметры - задаём уточняющий вопрос
        if category and category != "unknown":
            # Добавляем подтверждение предположения
            from services.materials import load_materials_rules
            rules = load_materials_rules()
            categories = rules.get("liquid_categories", {})
            cat_data = categories.get(category, {})
            cat_title = cat_data.get("title", category)
            
            # Формируем предположение
            assumption_parts = []
            if temp_c:
                assumption_parts.append(f"температура {temp_c}°C")
            if has_abrasive is not None:
                assumption_parts.append(f"абразив {'есть' if has_abrasive else 'нет'}")
            
            assumption = f"Среда: {cat_title}"
            if assumption_parts:
                assumption += ", " + ", ".join(assumption_parts)
            
            # Подтверждаем предположение
            response_parts.append(f"{get_phrase(CONFIRM_PHRASES)} {assumption}.")
            response_parts.append(f"\n{question_text}")
            
            # Добавляем короткое объяснение почему это важно
            response_parts.append(f"\n\n{get_phrase(EXPLAIN_PHRASES)}")
        else:
            # Просто задаём вопрос
            response_parts.append(question_text)
        
        # Обновляем последний вопрос
        update_session_state(session_id, {"last_question": question_type})
        
        return "\n".join(response_parts)
    
    # 3. Все данные есть - выдаём результат
    category = state.get("liquid_category", "unknown")
    temp_c = state.get("temp_c")
    has_abrasive = state.get("has_abrasive")
    
    # Инженерное рассуждение (короткое)
    reasoning = generate_reasoning_trace(state, category, has_abrasive)
    if reasoning:
        response_parts.append(f"**{get_phrase(REASONING_PHRASES)}**")
        response_parts.append(f"{reasoning}\n")
    
    # Определяем материалы
    materials_result = decide_materials(category, has_abrasive, temp_c)
    allowed = materials_result.get("allowed_materials", [])
    not_allowed = materials_result.get("not_allowed_materials", [])
    preferred = materials_result.get("preferred_materials", [])
    
    # Определяем складские серии
    stock_result = get_stock_series_by_materials(allowed)
    stock_series = stock_result.get("stock_series", [])
    non_stock_series = stock_result.get("non_stock_series", [])
    
    # Выводим результат по материалам
    if allowed:
        response_parts.append(f"\n{get_phrase(MATERIALS_RESULT_PHRASES)}")
        
        materials_list = []
        for mat in allowed:
            mat_info = materials_result.get("materials_info", {}).get(mat, {})
            seal = mat_info.get("seal", "")
            elastomer = mat_info.get("elastomer", "")
            is_preferred = mat in preferred
            
            mat_desc = f"**{mat}** (уплотнение: {seal}, эластомер: {elastomer})"
            if is_preferred:
                mat_desc += " ⭐ (предпочтительно)"
            materials_list.append(mat_desc)
        
        response_parts.append("\n".join(materials_list))
    else:
        response_parts.append(f"\n{get_phrase(MISSING_DATA_PHRASES)}")
    
    if not_allowed:
        response_parts.append(f"\n**Не подходят:** {', '.join(not_allowed)}")
    
    # Выводим информацию о складских сериях
    response_parts.append("")
    if stock_series:
        response_parts.append(f"{get_phrase(STOCK_PHRASES)} **{', '.join(stock_series)}**")
    
    if non_stock_series:
        response_parts.append(
            f"\n**Серии не со склада:** {', '.join(non_stock_series)}. "
            "Могу уточнить возможность спец-комплектации/под заказ."
        )
    
    # Короткое объяснение "почему"
    response_parts.append("")
    response_parts.append(f"**Почему:** {get_phrase(EXPLAIN_PHRASES)}")
    
    # Переход к следующему шагу
    response_parts.append("")
    response_parts.append(get_phrase(FOLLOWUP_PHRASES))
    
    # Отмечаем, что материалы обсудили
    update_session_state(session_id, {"materials_discussed": True})
    
    return "\n".join(response_parts)

