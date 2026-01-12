"""
Legacy-API модуль.

Роут `/api/chat` удалён (клиенты используют `/api/chats/*` + FSM),
но в этом модуле остаются общие функции генерации ответа и SSE-стрима,
которые используются в `api/chats.py`.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import random
import os
from datetime import datetime
from services.intents import detect_intent, Intent, extract_qh_from_text
from services.selector import select_by_working_point, find_analog_by_model
from services.file_extractors import process_file
from services.data_loader import load_kometta_data
from services.text_normalize import normalize_user_text
from services.conversation_state import (
    get_conversation, add_message, update_state, set_last_question,
    get_context_for_model, clear_conversation
)
from services.slot_extractor import (
    extract_slot_updates, get_next_empty_slot, should_trigger_selection
)
from api.types import Attachment
from services.dialog_handlers.off_topic import handle_off_topic
from services.dialog_handlers.selection_by_point import handle_selection_by_point
from services.dialog_handlers.analog_by_model import handle_analog_by_model
from services.dialog_handlers.file_upload import handle_file_upload

# Глобальная переменная для пути к логу (избегаем повторных вызовов os.getenv)
DEBUG_LOG_PATH = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")


def generate_komettik_response(
    intent: str,
    data: Dict[str, Any],
    message: str,
    attachments: List[Attachment],
    chat_id: str = "default",
    skip_slot_extraction: bool = False,
) -> str:
    """
    Генерирует ответ Кометтика на основе интента.
    
    Args:
        intent: тип интента
        data: дополнительные данные
        message: сообщение пользователя
        attachments: вложения
        chat_id: ID чата для сохранения контекста
        skip_slot_extraction: если True — не выполняет slot filling внутри (используется FSM-оркестратором)
    """
    try:
        # Шаг A: NLU/Extractor - извлекаем обновления слотов
        try:
            context = get_context_for_model(chat_id)
            # Убеждаемся, что context - это dict и содержит state
            if not isinstance(context, dict):
                context = {"state": {}, "pending_slot": None, "last_question": None, "dialog_summary": None, "recent_messages": [], "full_message_count": 0}
            if "state" not in context or not isinstance(context["state"], dict):
                context["state"] = {}
            pending_slot = context.get("pending_slot")
        except Exception as e:
            # Если ошибка при загрузке контекста, создаем пустой
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading context: {str(e)}\n{traceback.format_exc()}")
            context = {"state": {}, "pending_slot": None, "last_question": None, "dialog_summary": None, "recent_messages": [], "full_message_count": 0}
            pending_slot = None

        # Извлекаем обновления слотов из сообщения (если не отключено FSM-оркестратором)
        if not skip_slot_extraction:
            slot_result = extract_slot_updates(message, context, pending_slot, chat_id=chat_id)
            updates = slot_result.get("updates", {})
            confidence = slot_result.get("confidence", 0.0)
            next_slot = slot_result.get("next_slot")  # КРИТИЧНО: берем next_slot из extractor

            # КРИТИЧНО: Обновляем состояние с правильной логикой pending_slot
            # Если updates есть - обновляем слоты и устанавливаем next_slot
            # Если updates нет, но next_slot есть - сохраняем pending_slot (не сбрасываем!)
            if updates:
                # Обновляем слоты и устанавливаем next_slot (может быть None если все заполнено)
                update_state(chat_id, updates, pending_slot=next_slot, keep_pending_if_not_set=False)
                context["state"].update(updates)  # Обновляем локальный контекст
            elif next_slot is not None:
                # Не распарсили, но extractor вернул next_slot - сохраняем его
                # КРИТИЧНО: не передаем updates={}, только обновляем pending_slot
                update_state(chat_id, {}, pending_slot=next_slot, keep_pending_if_not_set=False)
            # Если и updates нет, и next_slot None - ничего не делаем (pending_slot сохраняется)

            # Устанавливаем последний вопрос если есть
            if slot_result.get("next_question"):
                set_last_question(chat_id, slot_result["next_question"])
        else:
            slot_result = {"updates": {}, "confidence": 0.0, "next_slot": None, "next_question": None}
            updates = {}
            confidence = 0.0
            next_slot = None
        
        # Сообщение пользователя уже сохранено в chats.py перед вызовом generate_komettik_response
        # Не сохраняем его повторно здесь, чтобы избежать дублирования
        # add_message(chat_id, "user", message)
        
        # КРИТИЧНО: Если пользователь подтвердил температуру (pending_slot был temperature_c и temperature_c обновлена),
        # и есть Q и H в состоянии - автоматически выполняем подбор, даже если intent другой
        if (pending_slot == "temperature_c" and 
            updates.get("temperature_c") is not None and 
            not slot_result.get("next_question") and  # Температура подтверждена, не нужно уточнять
            context["state"].get("flow_m3h") and 
            context["state"].get("head_m")):
            # Автоматически переключаемся на подбор по рабочей точке
            intent = Intent.SELECTION_BY_POINT
            data = {
                "q": context["state"].get("flow_m3h"),
                "h": context["state"].get("head_m"),
                "pump_type_info": context["state"].get("pump_type_info"),  # Сохраняем тип насоса, если был определен
            }
        
        response_parts = []
        
        if intent == Intent.OFF_TOPIC:
            result = handle_off_topic()
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.SELECTION_BY_POINT:
            result = handle_selection_by_point(
                chat_id=chat_id,
                message=message,
                data=data,
                context=context,
                pending_slot=pending_slot,
                slot_result=slot_result,
                updates=updates,
            )
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)

        elif intent == Intent.ANALOG_BY_MODEL:
            result = handle_analog_by_model(
                chat_id=chat_id,
                message=message,
                data=data,
                context=context,
            )
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)

        elif intent == Intent.FILE_UPLOAD:
            result = handle_file_upload(chat_id, attachments)
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.DIAGNOSTICS:
            response_parts.append(
                "Помогу разобраться с проблемой! Для диагностики мне нужна информация:\n"
                "• Модель насоса или артикул\n"
                "• Рабочая точка (Q и H)\n"
                "• Подробное описание проблемы\n\n"
            )
            
            # Определяем тип проблемы
            message_lower = message.lower()
            if "шум" in message_lower or "шумит" in message_lower:
                response_parts.append(
                    "**Возможные причины шума:**\n"
                    "• Кавитация (слишком высокий расход или низкое давление на входе)\n"
                    "• Износ подшипников\n"
                    "• Неправильная установка или вибрация\n"
                    "• Засорение рабочего колеса\n\n"
                    "Проверьте давление на входе и сравните с паспортными данными."
                )
            elif "кавитац" in message_lower:
                response_parts.append(
                    "**Кавитация** возникает при недостаточном давлении на входе насоса.\n"
                    "**Решения:**\n"
                    "• Увеличьте давление на входе (поднимите уровень жидкости или увеличьте диаметр всасывающего патрубка)\n"
                    "• Снизьте расход\n"
                    "• Проверьте, нет ли засорения на всасывающей линии\n\n"
                    "Укажите давление на входе и расход — подскажу точнее."
                )
            elif "вибрац" in message_lower or "вибрирует" in message_lower:
                response_parts.append(
                    "**Вибрация** может быть вызвана:\n"
                    "• Неправильной центровкой насоса и двигателя\n"
                    "• Износом подшипников\n"
                    "• Дисбалансом рабочего колеса\n"
                    "• Неправильной установкой на фундамент\n\n"
                    "Проверьте центровку и состояние подшипников."
                )
            else:
                response_parts.append(
                    "Опишите проблему подробнее:\n"
                    "• Когда началась проблема?\n"
                    "• При каких условиях возникает?\n"
                    "• Какие параметры работы насоса?"
                )
            
            response_parts.append("\n\nЧто ещё могу помочь?")
            response_parts.append("• Подобрать новый насос по параметрам")
            response_parts.append("• Найти аналог для замены")
        
        elif intent == Intent.DOCUMENTATION:
            # Проверяем тип запроса
            action = data.get("action", "")

            # НОВОЕ: Поиск информации о насосе по модели (например, "К144 65-80/04А/055Т2")
            if action == "by_model":
                from services.selector import get_pump_curve_data_by_model
                model_text = data.get("model", "")
                
                if not model_text:
                    response_parts.append("Укажите модель насоса Кометта (например, К144 65-80/04А/055Т2 или K377 32-50).")
                    return "\n".join(response_parts)
                
                pump_data = get_pump_curve_data_by_model(model_text)
                if pump_data:
                    model = pump_data.get("model", model_text)
                    articul = pump_data.get("articul", "не указан")
                    series = pump_data.get("series", "не указана")
                    power = pump_data.get("power", 0)
                    datasheet_url = pump_data.get("datasheet_url", "")
                    
                    response_parts.append(f"**{model}**")
                    response_parts.append(f"Серия: {series}")
                    if articul != "не указан":
                        response_parts.append(f"Артикул: {articul}")
                    if power > 0:
                        response_parts.append(f"Мощность: {power} кВт")
                    
                    # Добавляем ссылку на лист данных
                    if datasheet_url:
                        response_parts.append(f"\n[Скачать лист данных (PDF)]({datasheet_url})")
                    else:
                        response_parts.append("\nК сожалению, лист данных для этого насоса пока недоступен.")
                    
                    # Проверяем наличие точек кривой
                    q_points = pump_data.get("q_points", [])
                    h_points = pump_data.get("h_points", [])
                    if len(q_points) >= 3 and len(h_points) >= 3:
                        response_parts.append("\nДля построения графика кривой напишите: **построй график**")
                    
                    return "\n".join(response_parts)
                else:
                    response_parts.append(f"Насос с моделью **{model_text}** не найден в базе Кометта.")
                    response_parts.append("\nПроверьте написание модели или попробуйте указать артикул.")
                    return "\n".join(response_parts)
            
            # Материал корпуса насоса Кометта (по модели / по артикулу)
            if action in ["body_material_by_model", "body_material_by_articul"]:
                from services.body_material import extract_body_material_code_from_model, describe_body_material
                model_text = data.get("model", "")
                articul = data.get("articul", "")

                if action == "body_material_by_articul" and articul:
                    from services.selector import get_pump_curve_data
                    pump_data = get_pump_curve_data(articul)
                    if pump_data:
                        model_text = pump_data.get("model", model_text)
                    else:
                        response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
                        return "\n".join(response_parts)

                if not model_text:
                    response_parts.append("Укажите модель или артикул насоса Кометта, чтобы определить материал корпуса.")
                    return "\n".join(response_parts)

                code = extract_body_material_code_from_model(model_text)
                mat = describe_body_material(code)

                # Нормализуем К/К
                model_norm = model_text.strip().replace("K", "К")

                if code and mat:
                    response_parts.append(f"Насос: {model_norm}")
                    response_parts.append(f"Материал корпуса: **{mat}** (код исполнения: **{code}**)")
                else:
                    response_parts.append(f"Насос: {model_norm}")
                    response_parts.append("Не смог однозначно определить материал корпуса по коду исполнения в модели. Проверьте, что в модели есть сегмент вида `/04*/`, `/16*/` или `/25*/`.")

                return "\n".join(response_parts)
            
            # Проверяем, это запрос на аналоги по артикулу Кометта?
            if action == "analog_by_articul":
                articul = data.get("articul", "")
                if articul:
                    from services.selector import get_pump_curve_data
                    pump_data = get_pump_curve_data(articul)
                    if pump_data:
                        # Получаем кривую насоса Кометта
                        q_points = pump_data.get('q_points', [])
                        h_points = pump_data.get('h_points', [])
                        if len(q_points) >= 3:
                            # Ищем аналоги среди конкурентов
                            from services.curve_math import approximate_curve, calculate_h
                            from services.data_loader import load_competitors_data
                            import numpy as np
                            
                            df_comp = load_competitors_data()
                            analogs = []
                            
                            coeffs_kometta = approximate_curve(q_points, h_points)
                            if coeffs_kometta is None:
                                response_parts.append(f"Нашёл насос Кометта: {pump_data.get('model', f'Артикул {articul}')}")
                                response_parts.append(f"Артикул: {articul}")
                                response_parts.append("\nНедостаточно данных кривой для поиска аналогов.")
                            else:
                                a_kometta, b_kometta, c_kometta, d_kometta = coeffs_kometta
                                
                                for idx, row_comp in df_comp.iterrows():
                                    from services.selector import extract_curve_points
                                    q_comp, h_comp = extract_curve_points(row_comp)
                                    if len(q_comp) < 3:
                                        continue
                                    
                                    try:
                                        coeffs_comp = approximate_curve(q_comp, h_comp)
                                        if coeffs_comp is None:
                                            continue
                                        a_comp, b_comp, c_comp, d_comp = coeffs_comp
                                        
                                        # Сравниваем кривые
                                        q_min = min(min(q_points), min(q_comp))
                                        q_max = max(max(q_points), max(q_comp))
                                        q_test = np.linspace(q_min, q_max, 20)
                                        h_comp_test = [calculate_h(q, a_comp, b_comp, c_comp, d_comp) for q in q_test]
                                        h_kometta_test = [calculate_h(q, a_kometta, b_kometta, c_kometta, d_kometta) for q in q_test]
                                        
                                        errors = [(h_c - h_k) ** 2 for h_c, h_k in zip(h_comp_test, h_kometta_test)]
                                        rmse = np.sqrt(np.mean(errors))
                                        
                                        if rmse > 50:
                                            continue
                                        
                                        def safe_str(value, default=""):
                                            import pandas as pd
                                            if pd.isna(value) or value is None:
                                                return default
                                            val_str = str(value).strip()
                                            if val_str.lower() in ["nan", "none", ""]:
                                                return default
                                            return val_str
                                        
                                        analogs.append({
                                            "brand": safe_str(row_comp.get("brand", ""), ""),
                                            "model": safe_str(row_comp.get("model", ""), ""),
                                            "rmse": rmse
                                        })
                                    except:
                                        continue
                                
                                analogs.sort(key=lambda x: x["rmse"])
                                analogs = analogs[:3]
                                
                                if analogs:
                                    response_parts.append(f"Нашёл насос Кометта: {pump_data.get('model', f'Артикул {articul}')}")
                                    response_parts.append(f"Артикул: {articul}")
                                    response_parts.append(f"\nАналоги среди конкурентов:\n")
                                    for i, analog in enumerate(analogs, 1):
                                        response_parts.append(f"{i}. {analog['brand']} {analog['model']} (отклонение: {analog['rmse']:.2f} м)")
                                else:
                                    response_parts.append(f"Нашёл насос Кометта: {pump_data.get('model', f'Артикул {articul}')}")
                                    response_parts.append(f"Артикул: {articul}")
                                    response_parts.append("\nНе нашёл подходящих аналогов среди конкурентов.")
                        else:
                            response_parts.append(f"Нашёл насос: {pump_data.get('model', f'Артикул {articul}')}")
                            response_parts.append(f"Артикул: {articul}")
                            response_parts.append("\nНедостаточно данных кривой для поиска аналогов.")
                else:
                    response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
            # Проверяем, это запрос по артикулу?
            elif action == "by_articul":
                articul = data.get("articul", "")
                if articul:
                    from services.selector import get_pump_curve_data
                    pump_data = get_pump_curve_data(articul)
                    if pump_data:
                        model_name = pump_data.get('model', f"Артикул {articul}")
                        response_parts.append(f"Нашёл насос: {model_name}")
                        if pump_data.get('series'):
                            response_parts.append(f"Серия: {pump_data['series']}")
                        response_parts.append(f"Артикул: {articul}")
                        if pump_data.get('power', 0) > 0:
                            response_parts.append(f"Мощность: {pump_data['power']} кВт")
                        if pump_data.get('datasheet_url'):
                            response_parts.append(f"\n📄 Лист данных: {pump_data['datasheet_url']}")
                        response_parts.append("\nМогу построить график кривой этого насоса — хотите?")
                    else:
                        response_parts.append(f"Насос с артикулом {articul} не найден в базе.")
                else:
                    response_parts.append("Укажите артикул насоса.")
            # Проверяем, это запрос на сравнение двух насосов?
            elif action == "compare":
                articul1 = data.get("articul1", "")
                articul2 = data.get("articul2", "")
                if articul1 and articul2:
                    from services.selector import get_pump_curve_data
                    pump1 = get_pump_curve_data(articul1)
                    pump2 = get_pump_curve_data(articul2)
                    
                    if pump1 and pump2:
                        model1 = pump1.get('model', f"Артикул {articul1}")
                        model2 = pump2.get('model', f"Артикул {articul2}")
                        response_parts.append(f"Сравниваю насосы:\n")
                        response_parts.append(f"1. {model1} (артикул: {articul1})")
                        response_parts.append(f"2. {model2} (артикул: {articul2})")
                        response_parts.append(f"\nГрафик сравнения можно построить через API:")
                        response_parts.append(f"/api/plot/compare?kometta_articul={articul1}&competitor_articul={articul2}")
                        response_parts.append("\n\nИли напишите 'Построй график сравнения' для визуализации.")
                    elif pump1:
                        response_parts.append(f"Нашёл первый насос: {pump1.get('model', f'Артикул {articul1}')}")
                        response_parts.append(f"Второй насос с артикулом {articul2} не найден в базе Кометта.")
                    elif pump2:
                        response_parts.append(f"Нашёл второй насос: {pump2.get('model', f'Артикул {articul2}')}")
                        response_parts.append(f"Первый насос с артикулом {articul1} не найден в базе Кометта.")
                    else:
                        response_parts.append(f"Оба насоса не найдены в базе Кометта.")
                        response_parts.append(f"Проверьте правильность артикулов: {articul1} и {articul2}")
                else:
                    response_parts.append("Для сравнения укажите два артикула насосов.")
                    response_parts.append("Пример: 'Сравнить насосы 14101003 и 14101004'")
            # Проверяем, это запрос на график?
            elif action == "plot":
                # Пытаемся извлечь артикул из сообщения
                import re
                articul_match = re.search(r'\d{6,12}', message)
                if articul_match:
                    articul = articul_match.group()
                    from services.selector import get_pump_curve_data
                    
                    pump_data = get_pump_curve_data(articul)
                    if pump_data:
                        # Сообщаем пользователю о возможности построения графика
                        model_name = pump_data.get('model', f"Артикул {articul}")
                        response_parts.append(f"Нашёл насос: {model_name}")
                        response_parts.append(f"Артикул: {articul}")
                        if pump_data.get('power', 0) > 0:
                            response_parts.append(f"Мощность: {pump_data['power']} кВт")
                        if pump_data.get('datasheet_url'):
                            response_parts.append(f"\n📄 [Лист данных]({pump_data['datasheet_url']})")
                        response_parts.append(f"\nГрафик кривой можно построить через API:")
                        response_parts.append(f"/api/plot/compare?kometta_articul={articul}")
                        response_parts.append("\nИли укажите артикул насоса конкурента для сравнения.")
                    else:
                        response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
                        response_parts.append("Проверьте правильность артикула.")
                else:
                    response_parts.append(
                        "Для построения графика мне нужен артикул насоса Кометта.\n"
                        "Укажите артикул, и я построю кривую характеристики.\n\n"
                        "Примеры запросов:\n"
                        "• Покажи график насоса 11101013\n"
                        "• Построй кривую для артикула 13101167\n\n"
                        "Для сравнения с насосом конкурента укажите:\n"
                        "• Артикул насоса Кометта\n"
                        "• Модель насоса конкурента"
                    )
            else:
                response_parts.append(
                    "Я могу помочь с документацией по насосам Кометта. "
                    "Что именно вам нужно?\n"
                    "• Кривая характеристики насоса\n"
                    "• Паспорт насоса\n"
                    "• Лист данных\n\n"
                    "Укажите модель или артикул насоса."
                )
        
        elif intent == Intent.PUMP_TYPE:
            try:
                # Запрос по типу насоса (циркуляционный, погружной, моноблочный и т.д.)
                pump_type_info_raw = data.get("pump_type_info")
                
                # Убеждаемся, что pump_type_info - это dict
                if not isinstance(pump_type_info_raw, dict):
                    pump_type_info = {}
                else:
                    pump_type_info = pump_type_info_raw.copy()
                
                if pump_type_info:
                    # Используем функцию генерации ответа из модуля pump_types
                    from services.pump_types import generate_type_response, PumpTypeAvailability
                    
                    # ВАЖНО: pump_type_info может быть загружен из состояния, где availability - строка
                    # Нужно нормализовать для правильного сравнения
                    if isinstance(pump_type_info.get("availability"), str):
                        availability_str = pump_type_info.get("availability")
                        if availability_str == "available":
                            pump_type_info["availability"] = PumpTypeAvailability.AVAILABLE
                        elif availability_str == "not_available":
                            pump_type_info["availability"] = PumpTypeAvailability.NOT_AVAILABLE
                    
                    try:
                        type_response = generate_type_response(pump_type_info)
                        response_parts.append(type_response)
                    except Exception as e:
                        # Логируем ошибку, но продолжаем работу
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error generating type response: {str(e)}")
                        response_parts.append("Информация о типе насоса получена, но возникла ошибка при генерации ответа.")
                    
                    # Если тип есть у Кометта и есть Q/H в сообщении, сразу подбираем
                    # Сравниваем правильно (Enum или его значение)
                    availability = pump_type_info.get("availability")
                    is_available = (
                        availability == PumpTypeAvailability.AVAILABLE or
                        (isinstance(availability, str) and availability == "available")
                    )
                    
                    if is_available:
                        qh_data = extract_qh_from_text(message)
                        if qh_data:
                            q = qh_data.get("q")
                            h = qh_data.get("h")
                            if q and h:
                                response_parts.append(f"\n\n---\n\n**Подбор по рабочей точке Q = {q} м³/ч, H = {h} м:**\n")
                                
                                # Фильтруем по серии, если известна
                                # Безопасно извлекаем series
                                series_raw = pump_type_info.get("series")
                                if isinstance(series_raw, list):
                                    series_list = series_raw
                                elif isinstance(series_raw, str):
                                    series_list = [series_raw]
                                else:
                                    series_list = []
                                pumps = select_by_working_point(q, h, top_n=50)
                                
                                if series_list:
                                    # Фильтруем по серии
                                    filtered_pumps = [p for p in pumps if any(s in p.get("model", "") or s in p.get("series", "") for s in series_list)]
                                    if filtered_pumps:
                                        pumps = filtered_pumps
                                
                                if pumps:
                                    for i, pump in enumerate(pumps, 1):
                                        # Формируем название: brand + model
                                        brand = pump.get("brand", "Кометта")
                                        model = pump.get("model", "")
                                        
                                        # Формируем имя: Brand + Model
                                        pump_name_parts = []
                                        if brand:
                                            pump_name_parts.append(str(brand).strip())
                                        if model and str(model).lower() not in ["nan", "none", ""]:
                                            pump_name_parts.append(str(model).strip())
                                        
                                        pump_name = " ".join(pump_name_parts)
                                        if not pump_name:
                                            pump_name = "Насос"
                                        
                                        response_parts.append(f"\n**{i}. {pump_name}**")
                                        response_parts.append(f"\nАртикул: {pump.get('articul', 'не указан')}")
                                        response_parts.append(f"\nМощность: {pump.get('power', 'не указана')} кВт")
                                        response_parts.append(f"\nРабочая точка: Q = {pump.get('q_work', q):.1f} м³/ч, H = {pump.get('h_work', h):.1f} м")
                                        error = pump.get('error', 0)
                                        relative_error = pump.get('relative_error_percent', 0)
                                        response_parts.append(f"\nОтклонение: {error:.2f} м ({relative_error:.1f}%)")
                                        
                                        datasheet_url = pump.get('datasheet_url')
                                        if datasheet_url:
                                            response_parts.append(f"\n📄 [Лист данных]({datasheet_url})")
                                        else:
                                            response_parts.append(f"\n📄 Лист данных: не доступен")
                                else:
                                    response_parts.append("\nК сожалению, не нашёл подходящих насосов для указанной рабочей точки.")
                else:
                    response_parts.append(
                        "Не удалось определить тип насоса. "
                        "Уточните, какой тип вам нужен:\n"
                        "• Моноблочный центробежный (К144)\n"
                        "• Многоступенчатый горизонтальный (К233)\n"
                        "• Многоступенчатый вертикальный (К377)\n"
                        "• С открытым рабочим колесом (К610)\n"
                        "• Циркуляционный inline (К987)"
                    )
            except Exception as e:
                # Обработка ошибок при обработке типа насоса
                from services.error_handler import handle_error, log_error
                log_error(e, "chat.py:generate_komettik_response:PUMP_TYPE", 
                         context={"intent": intent, "data": data}, session_id=chat_id)
                response_parts.append(
                    "Извините, произошла ошибка при обработке запроса о типе насоса. "
                    "Пожалуйста, попробуйте ещё раз."
                )
        
        elif intent == Intent.MATERIALS_QUERY:
            try:
                # Запрос о материалах исполнения для жидкости (с "живым" диалоговым поведением)
                category = data.get("category", "unknown")
                has_abrasive = data.get("has_abrasive")
                temp_c = data.get("temp_c")
                liquid_description = data.get("description", "")
                
                # Используем диалоговый поток для генерации "живого" ответа
                from services.dialog_flow import generate_materials_response_with_dialog
                
                materials_response = generate_materials_response_with_dialog(
                    session_id=chat_id,
                    liquid_text=liquid_description or message,
                    category=category if category != "unknown" else None,
                    has_abrasive=has_abrasive,
                    temp_c=temp_c
                )
                response_parts.append(materials_response)
            except Exception as e:
                # Обработка ошибок при обработке запроса о материалах
                from services.error_handler import handle_error, log_error
                log_error(e, "chat.py:generate_komettik_response:MATERIALS_QUERY", 
                         context={"intent": intent, "data": data}, session_id=chat_id)
                response_parts.append(
                    "Извините, произошла ошибка при обработке запроса о материалах. "
                    "Пожалуйста, попробуйте ещё раз."
                )
        
        elif intent == Intent.TECH_QA:
            try:
                # Технический вопрос - ищем в базе знаний
                # message уже нормализован (исправлены опечатки) во внешнем endpoint'е (/api/chats/*)
                query = data.get("query", message)
                
                # Добавляем контекст из предыдущих сообщений для улучшения поиска
                context_text = ""
                if context.get("recent_messages"):
                    # Берем последние 3 сообщения пользователя для контекста
                    user_messages = [msg for msg in context["recent_messages"][-5:] if msg.get("role") == "user"]
                    if user_messages:
                        context_text = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
                        # Объединяем контекст с текущим запросом
                        enhanced_query = f"{context_text} {query}".strip()
                    else:
                        enhanced_query = query
                else:
                    enhanced_query = query
                
                from services.kb.search import search
                from services.kb.summarize import format_answer
                
                # Выполняем поиск по нормализованному запросу с контекстом
                hits = search(enhanced_query, limit=5)
                
                # Если не нашли результатов с контекстом, пробуем без контекста
                if not hits:
                    hits = search(query, limit=5)
                
                # Форматируем ответ с тезисами
                answer = format_answer(query, hits, max_bullets=7)
                response_parts.append(answer)
            except Exception as e:
                # Обработка ошибок при поиске в базе знаний
                from services.error_handler import handle_error, log_error
                log_error(e, "chat.py:generate_komettik_response:TECH_QA", 
                         context={"intent": intent, "query": query}, session_id=chat_id)
                response_parts.append(
                    "Извините, произошла ошибка при поиске в базе знаний. "
                    "Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
                )
        
        # Добавляем уточняющие вопросы в конце (только если их ещё не добавили)
        # Уточняющие вопросы уже добавлены в блоках SELECTION_BY_POINT, ANALOG_BY_MODEL, DIAGNOSTICS, PUMP_TYPE, MATERIALS_QUERY, TECH_QA
        if intent not in [Intent.OFF_TOPIC, Intent.SELECTION_BY_POINT, Intent.ANALOG_BY_MODEL, Intent.DIAGNOSTICS, Intent.PUMP_TYPE, Intent.MATERIALS_QUERY, Intent.TECH_QA]:
            response_parts.append("\n\nЧто ещё могу помочь?")
            response_parts.append("• Подобрать другой насос")
            response_parts.append("• Найти аналог")
            response_parts.append("• Построить график кривой")
        
        response_text = "\n".join(response_parts)
        
        # Сохраняем ответ в историю диалога
        add_message(chat_id, "assistant", response_text)
        
        return response_text
    except Exception as e:
        # Используем единую систему обработки ошибок
        from services.error_handler import handle_error
        
        error_message = handle_error(
            e,
            "chat.py:generate_komettik_response",
            context={"intent": intent},
            session_id=chat_id,
            user_message=message
        )
        
        return error_message


async def stream_response(text: str):
    """
    Потоковая передача ответа (SSE).
    Обрабатывает edge cases: пустой текст, очень длинный текст, спецсимволы.
    """
    if not text or not text.strip():
        # Пустой ответ - отправляем сразу
        yield f"data: {json.dumps({'type': 'token', 'content': text or ''})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return
    
    # Разбиваем на слова, но ограничиваем максимальное количество для производительности
    words = text.split(" ")
    max_words = 1000  # Защита от слишком длинных ответов
    
    if len(words) > max_words:
        # Для очень длинных ответов отправляем большими блоками
        chunk_size = 50
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            await asyncio.sleep(0.05)
    else:
        # Обычный режим - по одному слову
        for i, word in enumerate(words):
            if i > 0:
                yield f"data: {json.dumps({'type': 'token', 'content': ' '})}\n\n"
                await asyncio.sleep(0.05)  # Небольшая задержка между словами
            
            # Экранируем спецсимволы в JSON
            try:
                word_json = json.dumps({'type': 'token', 'content': word})
            except (UnicodeEncodeError, TypeError):
                # Если не удалось сериализовать, заменяем проблемные символы
                word_safe = word.encode('utf-8', errors='replace').decode('utf-8')
                word_json = json.dumps({'type': 'token', 'content': word_safe})
            
            yield f"data: {word_json}\n\n"
            await asyncio.sleep(0.1)  # Задержка для эффекта печатания
    
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
