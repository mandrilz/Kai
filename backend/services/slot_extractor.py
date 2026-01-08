"""
NLU/Extractor для парсинга сообщений пользователя и обновления слотов.
Реализует двухходовку: сначала структурирование, потом ответ.
"""
from typing import Dict, Any, Optional
import re
from services.q_extractor import extract_q_from_text
from services.h_extractor import extract_h_from_text
from services.intents import extract_qh_from_text
from services.conversation_state import parse_short_answer, SLOT_SCHEMA
from services.dialog_phrases import TEMPERATURE_SIGN_QUESTIONS, get_phrase
import random


def extract_slot_updates(
    message: str,
    context: Dict[str, Any],
    pending_slot: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Извлекает обновления слотов из сообщения пользователя.
    
    Args:
        message: сообщение пользователя
        context: контекст диалога (state, recent_messages и т.д.)
        pending_slot: ожидаемый слот
        session_id: ID сессии (для работы с сохраненными значениями температуры без знака)
        
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
    updates = {}
    confidence = 0.0
    needs_clarification = False
    next_question = None
    next_slot = None
    note = None
    
    state = context.get("state", {})
    message_lower = message.lower().strip()
    
    # Извлекаем session_id из context, если не передан явно
    if session_id is None:
        session_id = context.get("session_id")
    
    # Приоритет 1: Если есть pending_slot - парсим как ответ (даже если текст длинный)
    # parse_short_answer теперь более гибкий и может парсить даже длинные тексты
    if pending_slot:
        short_answer = parse_short_answer(message, pending_slot, session_id=session_id)
        if short_answer:
            # Проверяем, нужно ли уточнение знака температуры
            if short_answer.get("needs_sign_clarification"):
                # Температура найдена, но без знака - нужно уточнить
                detected_value = short_answer.get("detected_value")
                next_question = get_phrase(TEMPERATURE_SIGN_QUESTIONS)
                if detected_value:
                    next_question = f"Вы указали {detected_value}°C. {next_question}"
                return {
                    "updates": {},  # Не обновляем, нужно уточнить знак
                    "confidence": 0.6,
                    "needs_clarification": True,
                    "next_question": next_question,
                    "next_slot": "temperature_c",  # Оставляем тот же слот
                    "note": "Temperature value detected but sign unclear"
                }
            
            updates.update(short_answer.get("updates", {}))
            confidence = short_answer.get("confidence", 0.7)
            # Если успешно распарсили - определяем следующий слот
            if updates:
                # pending_slot будет обновлен в chat.py на основе next_slot
                next_slot = short_answer.get("next_slot")  # Может быть None - определим ниже
    
    # Приоритет 2: Парсинг Q и H (рабочая точка)
    qh_data = extract_qh_from_text(message)
    if qh_data and qh_data.get("q") and qh_data.get("h"):
        updates["flow_m3h"] = qh_data["q"]
        updates["head_m"] = qh_data["h"]
        confidence = max(confidence, 0.9)
    
    # Приоритет 3: Парсинг отдельных параметров из текста
    
    # Температура (поддержка минусовых и плюсовых значений)
    if "temperature_c" not in updates:
        # Приоритет 1: Проверяем "минус" как слово
        minus_word_match = re.search(r'минус\s+(\d+(?:[.,]\d+)?)', message_lower)
        if minus_word_match:
            try:
                temp = -float(minus_word_match.group(1).replace(',', '.'))
                if -50 <= temp <= 200:
                    updates["temperature_c"] = temp
                    confidence = max(confidence, 0.85)
            except (ValueError, IndexError):
                pass
        else:
            # Приоритет 2: Проверяем "плюс" как слово (приравнивается к положительному)
            plus_word_match = re.search(r'плюс\s+(\d+(?:[.,]\d+)?)', message_lower)
            if plus_word_match:
                try:
                    temp = float(plus_word_match.group(1).replace(',', '.'))
                    if -50 <= temp <= 200:
                        updates["temperature_c"] = temp
                        confidence = max(confidence, 0.85)
                except (ValueError, IndexError):
                    pass
            else:
                # Приоритет 3: Паттерны с явным знаком (+, -)
                temp_match_with_sign = re.search(r'([+-]\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп)', message_lower, re.IGNORECASE)
                if temp_match_with_sign:
                    try:
                        temp_str = temp_match_with_sign.group(1).replace(',', '.')
                        temp = float(temp_str)
                        if -50 <= temp <= 200:
                            updates["temperature_c"] = temp
                            confidence = max(confidence, 0.85)
                    except (ValueError, IndexError):
                        pass
                else:
                    # Приоритет 4: Паттерны без знака (может быть положительное или отрицательное)
                    # Если находим число без знака - нужно уточнить
                    temp_match_without_sign = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп)', message_lower, re.IGNORECASE)
                    if temp_match_without_sign:
                        try:
                            temp_str = temp_match_without_sign.group(1).replace(',', '.')
                            temp = float(temp_str)
                            if -50 <= temp <= 200:
                                # Если число без знака и pending_slot не temperature_c - нужно уточнить
                                if pending_slot == "temperature_c":
                                    # Уже обработано в parse_short_answer
                                    pass
                                else:
                                    # Найдена температура без знака в общем тексте - сохраняем и нужно уточнить
                                    from services.conversation_state import set_temp_without_sign
                                    if session_id:
                                        set_temp_without_sign(session_id, temp)
                                    next_question = get_phrase(TEMPERATURE_SIGN_QUESTIONS)
                                    return {
                                        "updates": {},
                                        "confidence": 0.6,
                                        "needs_clarification": True,
                                        "next_question": f"Вы указали {temp}°C. {next_question}",
                                        "next_slot": "temperature_c",
                                        "note": "Temperature value detected but sign unclear"
                                    }
                        except (ValueError, IndexError):
                            pass
    
    # Жидкость
    if "fluid" not in updates:
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
            if keyword in message_lower:
                updates["fluid"] = fluid
                confidence = max(confidence, 0.8)
                break
    
    # Примеси/твердые частицы
    if "solids" not in updates:
        if any(word in message_lower for word in ["примеси", "песок", "твердые", "абразив", "solids", "abrasive"]):
            updates["solids"] = True
            confidence = max(confidence, 0.75)
        elif any(word in message_lower for word in ["чистая", "без примесей", "чистая жидкость"]):
            updates["solids"] = False
            confidence = max(confidence, 0.75)
    
    # Статический напор
    if "h_st" not in updates:
        h_st_patterns = [
            r'статический\s+напор[:\s]+(\d+(?:[.,]\d+)?)',
            r'h[_\s]*ст[:\s]*=?\s*(\d+(?:[.,]\d+)?)',
            r'статический[:\s]+(\d+(?:[.,]\d+)?)'
        ]
        for pattern in h_st_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                try:
                    h_st = float(match.group(1).replace(',', '.'))
                    if 0 <= h_st <= 500:
                        updates["h_st"] = h_st
                        confidence = max(confidence, 0.8)
                        break
                except ValueError:
                    pass
    
    # Определяем следующий вопрос и слот
    if not updates and pending_slot:
        # Пользователь не ответил на вопрос - повторяем тот же слот
        next_slot = pending_slot  # КРИТИЧНО: сохраняем pending_slot
        next_question = get_slot_question(pending_slot, state)
        needs_clarification = True
        note = "User did not provide expected slot value"
    elif updates:
        # Успешно распарсили - определяем следующий незаполненный слот
        if next_slot is None:  # Если parse_short_answer не вернул next_slot
            next_slot = get_next_empty_slot(state, updates)
        if next_slot:
            next_question = get_slot_question(next_slot, {**state, **updates})
            needs_clarification = True
        else:
            # Все слоты заполнены - можно делать подбор
            needs_clarification = False
    else:
        # Не распарсили ничего - возможно, вопрос не по теме
        # КРИТИЧНО: сохраняем pending_slot если он был
        if pending_slot:
            next_slot = pending_slot  # Не теряем pending_slot!
            next_question = get_slot_question(pending_slot, state)
            note = "Could not extract slot value from message"
    
    return {
        "updates": updates,
        "confidence": confidence,
        "needs_clarification": needs_clarification,
        "next_question": next_question,
        "next_slot": next_slot,  # КРИТИЧНО: возвращаем next_slot
        "note": note
    }


def get_slot_question(slot: str, state: Dict[str, Any]) -> str:
    """Возвращает вопрос для заполнения слота."""
    questions = {
        "fluid": "Какая жидкость будет перекачиваться? (вода, этиленгликоль, масло и т.д.)",
        "temperature_c": "Какая температура жидкости? (в градусах Цельсия)",
        "flow_m3h": "Какой расход нужен? (м³/ч, л/мин или другие единицы)",
        "head_m": "Какой напор требуется? (в метрах, барах или других единицах)",
        "viscosity": "Какая вязкость жидкости? (если известна)",
        "concentration": "Какая концентрация? (для этиленгликоля и т.д.)",
        "solids": "Есть ли в жидкости твердые частицы или примеси?",
        "installation": "Какой тип установки? (вертикальный/горизонтальный)",
        "materials": "Какие материалы требуются? (A/E/X/H)",
        "h_st": "Какой статический напор сети? (в метрах)"
    }
    
    base_question = questions.get(slot, f"Уточните параметр: {slot}")
    
    # Добавляем контекст если есть
    if state.get("fluid") and slot == "temperature_c":
        return f"Какая температура {state['fluid']}? (в градусах Цельсия)"
    
    return base_question


def get_next_empty_slot(state: Dict[str, Any], updates: Dict[str, Any] = None) -> Optional[str]:
    """Определяет следующий незаполненный слот для уточнения."""
    merged_state = {**state, **(updates or {})}
    
    # Приоритет слотов для подбора насоса
    priority_slots = [
        "flow_m3h",  # Расход - самый важный
        "head_m",    # Напор - второй по важности
        "fluid",     # Жидкость
        "temperature_c",  # Температура
        "solids",    # Примеси
        "h_st",      # Статический напор
        "concentration",  # Концентрация
        "viscosity",  # Вязкость
        "installation",  # Установка
        "materials"  # Материалы
    ]
    
    for slot in priority_slots:
        if slot in SLOT_SCHEMA and merged_state.get(slot) is None:
            return slot
    
    return None


def should_trigger_selection(state: Dict[str, Any]) -> bool:
    """Определяет, достаточно ли данных для подбора насоса."""
    # Минимум: расход и напор
    return (
        state.get("flow_m3h") is not None and
        state.get("head_m") is not None
    )
