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
    updates = {}
    confidence = 0.0
    needs_clarification = False
    next_question = None
    next_slot = None
    note = None
    
    state = context.get("state", {})
    message_lower = message.lower().strip()
    
    # Получаем контекст из истории для улучшения понимания
    recent_messages = context.get("recent_messages", [])
    dialog_summary = context.get("dialog_summary", "")
    
    # Формируем расширенный контекст для анализа
    # Объединяем последние сообщения пользователя для понимания контекста
    context_text = ""
    if recent_messages:
        user_messages = [msg.get("content", "") for msg in recent_messages[-5:] if msg.get("role") == "user"]
        if user_messages:
            context_text = " ".join(user_messages)
    
    # Объединяем текущее сообщение с контекстом для анализа
    full_context = f"{context_text} {message}".strip() if context_text else message
    full_context_lower = full_context.lower()
    
    # Совместимость: session_id (старое имя) → chat_id
    if chat_id is None:
        chat_id = session_id
    if chat_id is None:
        chat_id = context.get("chat_id") or context.get("session_id")
    
    # Приоритет 1: Если есть pending_slot - парсим как ответ (даже если текст длинный)
    # parse_short_answer теперь более гибкий и может парсить даже длинные тексты
    if pending_slot:
        short_answer = parse_short_answer(message, pending_slot, chat_id=chat_id)
        if short_answer:
            # Проверяем, нужно ли пропустить слот (пользователь сказал "не знаю", "неважно" и т.д.)
            if short_answer.get("skip_slot"):
                # Пропускаем этот слот и переходим к следующему
                # Объединяем текущее состояние с обновлениями для определения следующего слота
                merged_state = {**state, **updates}
                # Исключаем текущий pending_slot из проверки, чтобы перейти к следующему
                next_slot = get_next_empty_slot(merged_state, {})
                # Если следующий слот найден, задаем вопрос (get_slot_question определена ниже в этом же файле)
                if next_slot:
                    # Используем функцию напрямую, она определена в этом же файле
                    next_question = get_slot_question(next_slot, merged_state)
                else:
                    next_question = None
                return {
                    "updates": {},  # Не обновляем слот
                    "confidence": 0.5,
                    "needs_clarification": bool(next_slot),  # Задаем вопрос только если есть следующий слот
                    "next_question": next_question,
                    "next_slot": next_slot,  # Переходим к следующему слоту
                    "note": "User indicated they don't know or don't care about this parameter"
                }
            
            # Проверяем, нужно ли уточнение знака температуры
            if short_answer.get("needs_sign_clarification"):
                # Температура найдена, но без знака - нужно уточнить
                detected_value = short_answer.get("detected_value")
                next_question = get_phrase(TEMPERATURE_SIGN_QUESTIONS)
                if detected_value is not None:
                    # Если известна жидкость — задаём вопрос контекстно ("Вода +20°C, верно?")
                    fluid = (state or {}).get("fluid") or context.get("state", {}).get("fluid")
                    if fluid:
                        # По умолчанию предполагаем "+", но просим поправить если минус
                        plus_val = f"+{detected_value}".replace("+-", "-")
                        variants = [
                            f"Я правильно понял: {fluid} {plus_val}°C?",
                            f"Уточню знак температуры: {fluid} {plus_val}°C — верно?",
                            f"Подтвердите, пожалуйста: {fluid} {plus_val}°C?",
                            f"Для правильного подбора важно понять знак: {fluid} {plus_val}°C — это плюс?",
                        ]
                        next_question = random.choice(variants) + " Если температура минусовая — напишите «минус» или укажите «-...°C»."
                    else:
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
    # Используем расширенный контекст для поиска Q и H (может быть в предыдущих сообщениях)
    qh_data = extract_qh_from_text(full_context) if full_context else extract_qh_from_text(message)
    if qh_data and qh_data.get("q") and qh_data.get("h"):
        updates["flow_m3h"] = qh_data["q"]
        updates["head_m"] = qh_data["h"]
        confidence = max(confidence, 0.9)
    
    # Приоритет 3: Парсинг отдельных параметров из текста

    # Материал корпуса (304/316/чугун) — влияет на фильтрацию подбора
    if "body_material_code" not in updates:
        body_code = detect_body_material_code_from_text(message)
        if body_code:
            updates["body_material_code"] = body_code
            confidence = max(confidence, 0.75)
    
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
                    # Приоритет 4: Диапазон температур (например, "18-30 градусов")
                    temp_range_match = re.search(r'(\d+(?:[.,]\d+)?)\s*[-…]\s*(\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп)', message_lower, re.IGNORECASE)
                    if temp_range_match:
                        try:
                            temp1_str = temp_range_match.group(1).replace(',', '.')
                            temp2_str = temp_range_match.group(2).replace(',', '.')
                            temp1 = float(temp1_str)
                            temp2 = float(temp2_str)
                            # Берем среднее значение диапазона
                            temp_avg = (temp1 + temp2) / 2.0
                            if -50 <= temp_avg <= 200:
                                # Для диапазона обычно это положительная температура (вода, пищевые жидкости)
                                # Но если диапазон отрицательный, берем среднее
                                if temp1 < 0 and temp2 < 0:
                                    updates["temperature_c"] = temp_avg
                                else:
                                    # Положительный диапазон - берем среднее как положительное
                                    updates["temperature_c"] = abs(temp_avg)
                                confidence = max(confidence, 0.85)
                        except (ValueError, IndexError):
                            pass
                    
                    # Приоритет 5: Паттерны без знака (может быть положительное или отрицательное)
                    # Если находим число без знака - нужно уточнить
                    if "temperature_c" not in updates:
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
                                        # Если уже знаем жидкость — задаём вопрос контекстно
                                        fluid = (state or {}).get("fluid") or context.get("state", {}).get("fluid")
                                        if fluid:
                                            plus_val = f"+{temp}".replace("+-", "-")
                                            variants = [
                                                f"Я правильно понял: {fluid} {plus_val}°C?",
                                                f"Уточню знак температуры: {fluid} {plus_val}°C — верно?",
                                                f"Подтвердите, пожалуйста: {fluid} {plus_val}°C?",
                                                f"Для правильного подбора важно понять знак: {fluid} {plus_val}°C — это плюс?",
                                            ]
                                            next_question = random.choice(variants) + " Если температура минусовая — напишите «минус» или укажите «-...°C»."
                                        return {
                                            "updates": {},
                                            "confidence": 0.6,
                                            "needs_clarification": True,
                                            "next_question": next_question if fluid else f"Вы указали {temp}°C. {next_question}",
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
        # Паттерны для извлечения жидкости из контекста
        # "Перекачиваемая жидкость — вода", "жидкость: вода", "жидкость вода"
        fluid_patterns = [
            r'перекачиваемая\s+жидкость[:\s—\-]+\s*(\w+)',
            r'жидкость[:\s—\-]+\s*(\w+)',
            r'жидкость\s+—\s*(\w+)',
            r'жидкость\s+(\w+)',
        ]
        for pattern in fluid_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                fluid_text = match.group(1).strip()
                for keyword, fluid in fluid_keywords.items():
                    if keyword in fluid_text or fluid_text == keyword:
                        updates["fluid"] = fluid
                        confidence = max(confidence, 0.9)
                        # Для воды сразу заполняем концентрацию нулем
                        if fluid == "вода" and state.get("concentration") is None:
                            updates["concentration"] = 0.0
                        break
                if "fluid" in updates:
                    break
        
        # Если не нашли через паттерны, ищем по ключевым словам
        if "fluid" not in updates:
            for keyword, fluid in fluid_keywords.items():
                if keyword in message_lower:
                    updates["fluid"] = fluid
                    confidence = max(confidence, 0.8)
                    # Для воды сразу заполняем концентрацию нулем
                    if fluid == "вода" and state.get("concentration") is None:
                        updates["concentration"] = 0.0
                    break
    
    # Примеси/твердые частицы
    if "solids" not in updates:
        if any(word in message_lower for word in ["примеси", "песок", "твердые", "абразив", "solids", "abrasive"]):
            updates["solids"] = True
            confidence = max(confidence, 0.75)
        elif any(word in message_lower for word in ["чистая", "без примесей", "чистая жидкость"]):
            updates["solids"] = False
            confidence = max(confidence, 0.75)
    
    # Тип установки (вертикальный/горизонтальный)
    if "installation" not in updates:
        if any(word in message_lower for word in ["вертикальный", "вертикальная", "vertical", "вертикально"]):
            updates["installation"] = "вертикальный"
            confidence = max(confidence, 0.85)
        elif any(word in message_lower for word in ["горизонтальный", "горизонтальная", "horizontal", "горизонтально"]):
            updates["installation"] = "горизонтальный"
            confidence = max(confidence, 0.85)
    
    # Проверяем, не является ли это "многоступенчатый" без уточнения вертикальный/горизонтальный
    # Если пользователь написал просто "многоступенчатый", нужно уточнить тип установки
    # ВАЖНО: проверяем ДО вызова detect_pump_type, так как он может не найти "многоступенчатый" без уточнения
    has_vertical_keyword = any(word in message_lower for word in ["вертикальный", "вертикальная", "vertical", "вертикально"])
    has_horizontal_keyword = any(word in message_lower for word in ["горизонтальный", "горизонтальная", "horizontal", "горизонтально"])
    has_multistage_keyword = any(word in message_lower for word in ["многоступенчатый", "многоступенчатая", "многоступенчатые", "multistage"])
    
    # Если есть "многоступенчатый", но нет указания на вертикальный/горизонтальный
    if has_multistage_keyword and not has_vertical_keyword and not has_horizontal_keyword:
        # Не устанавливаем series_filter, а задаем вопрос
        if "installation" not in updates and "series_filter" not in updates:
            next_slot = "installation"
            next_question = "Какой тип многоступенчатого насоса вас интересует: вертикальный или горизонтальный?"
            needs_clarification = True
            return {
                "updates": {},
                "confidence": 0.7,
                "needs_clarification": True,
                "next_question": next_question,
                "next_slot": next_slot,
                "note": "Multistage pump type needs clarification (vertical/horizontal)"
            }
    
    # Определение серии насоса по типу (моноблочный, вертикальный, горизонтальный и т.д.)
    # Используем detect_pump_type для универсального определения типа насоса
    if "series_filter" not in updates:
        try:
            from services.pump_types import detect_pump_type
            pump_type_info = detect_pump_type(message)
            if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
                pump_type_key = pump_type_info.get("type_key", "")
                series = pump_type_info.get("series")
                
                # Если тип определен четко (есть series), устанавливаем его
                if series and isinstance(series, list) and len(series) > 0:
                    updates["series_filter"] = series
                    confidence = max(confidence, 0.9)
                    # Также устанавливаем installation, если тип насоса подразумевает это
                    if "vertical" in pump_type_key and "installation" not in updates:
                        updates["installation"] = "вертикальный"
                    elif "horizontal" in pump_type_key and "installation" not in updates:
                        updates["installation"] = "горизонтальный"
        except Exception:
            # Если detect_pump_type не сработал, используем простую логику для вертикального
            if updates.get("installation") == "вертикальный":
                # К377 - это многоступенчатый вертикальный насос
                updates["series_filter"] = ["К377"]
                confidence = max(confidence, 0.9)
    
    # Статический напор
    if "h_st" not in updates:
        # Проверяем ответы "нет", "отсутствует", "0" для статического напора
        if any(word in message_lower for word in ["нет", "отсутствует", "ноль", "нуль", "нет статического", "статического нет"]):
            updates["h_st"] = 0.0
            confidence = max(confidence, 0.8)
        else:
            h_st_patterns = [
                r'статический\s+напор[:\s]+(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
                r'h[_\s]*ст[:\s]*=?\s*(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
                r'статический[:\s]+(\d+(?:[.,]\d+)?)\s*(?:м|meters?|m)?',
                r'(\d+(?:[.,]\d+)?)\s*м\s*(?:статический|статического)?'
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
    """
    Получает уточняющий вопрос для слота.
    Использует унифицированный модуль clarifying_questions.
    """
    from services.clarifying_questions import get_clarifying_question
    return get_clarifying_question(slot, state)


def get_next_empty_slot(state: Dict[str, Any], updates: Dict[str, Any] = None) -> Optional[str]:
    """
    Определяет следующий незаполненный слот для уточнения.
    Использует приоритеты, чтобы не задавать вопросы "пачкой".
    """
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
    """Определяет, достаточно ли данных для подбора насоса."""
    # Минимум: расход и напор
    return (
        state.get("flow_m3h") is not None and
        state.get("head_m") is not None
    )
