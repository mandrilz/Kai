"""
API endpoint для чата с Кометтиком.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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

# Глобальная переменная для пути к логу (избегаем повторных вызовов os.getenv)
DEBUG_LOG_PATH = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")

router = APIRouter()


class Attachment(BaseModel):
    filename: str
    content_type: str
    base64: str


class ChatRequest(BaseModel):
    chat_id: str  # Изменено с session_id на chat_id
    message: str
    attachments: List[Attachment] = []
    
    # Валидация будет выполняться в chat_endpoint перед обработкой
    # Pydantic v2 валидация выполняется автоматически при создании модели


def generate_komettik_response(intent: str, data: Dict[str, Any], message: str, attachments: List[Attachment], chat_id: str = "default") -> str:
    """
    Генерирует ответ Кометтика на основе интента.
    
    Args:
        intent: тип интента
        data: дополнительные данные
        message: сообщение пользователя
        attachments: вложения
        chat_id: ID чата для сохранения контекста
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
        
        # Извлекаем обновления слотов из сообщения
        slot_result = extract_slot_updates(message, context, pending_slot, session_id=chat_id)
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
        
        # Добавляем сообщение пользователя в историю
        add_message(chat_id, "user", message)
        
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
            response_parts.append(
                "Привет! Я Кометтик — инженер-помощник Кометта. "
                "Я помогаю с подбором насосов и поиском аналогов. "
                "Задайте вопрос по насосам, и я помогу!"
            )
            response_parts.append("\n\nМогу помочь с:")
            response_parts.append("• Подбором насоса по рабочей точке (Q и H)")
            response_parts.append("• Поиском аналога насоса конкурента")
            response_parts.append("• Анализом шильдика или документации")
        
        elif intent == Intent.SELECTION_BY_POINT:
            # ВАЖНО: 
            # - q всегда в м³/ч (пересчитано из любой единицы в extract_qh_from_text)
            # - h всегда в метрах (пересчитано из любой единицы в extract_qh_from_text)
            # База данных насосов использует м³/ч для расхода и метры для напора
            
            # КРИТИЧНО: Если есть pending_slot для температуры - сначала уточняем температуру
            # Это важно для правильного подбора, особенно для определения материалов
            if pending_slot == "temperature_c" and slot_result.get("next_question"):
                response_parts.append(slot_result["next_question"])
                # Не выполняем подбор, пока не уточнена температура
                return "\n".join(response_parts)
            
            # Используем данные из слотов или из парсинга
            q = data.get("q") or context["state"].get("flow_m3h")
            h = data.get("h") or context["state"].get("head_m")
            h_st = context["state"].get("h_st", 0.0)
            body_material_code = data.get("body_material_code") or context["state"].get("body_material_code")
            temperature_c = context["state"].get("temperature_c")
            fluid = context["state"].get("fluid")
            
            # #region agent log
            try:
                os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "chat.py:generate_komettik_response",
                        "message": "SELECTION_BY_POINT: initial values",
                        "data": {
                            "q_from_data": data.get("q"),
                            "h_from_data": data.get("h"),
                            "q_from_state": context["state"].get("flow_m3h"),
                            "h_from_state": context["state"].get("head_m"),
                            "h_st_from_state": context["state"].get("h_st"),
                            "updates": updates
                        },
                        "sessionId": chat_id,
                        "runId": "selection_init",
                        "hypothesisId": "STAGE7"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Если обновили слоты - используем их
            if updates.get("flow_m3h"):
                q = updates["flow_m3h"]
            if updates.get("head_m"):
                h = updates["head_m"]
            if updates.get("h_st") is not None:
                h_st = updates["h_st"]
            if updates.get("body_material_code"):
                body_material_code = updates["body_material_code"]
            if updates.get("temperature_c") is not None:
                temperature_c = updates["temperature_c"]
            if updates.get("fluid"):
                fluid = updates["fluid"]
            
            # Убеждаемся, что h_st не None (по умолчанию 0.0)
            if h_st is None:
                h_st = 0.0
            
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "chat.py:generate_komettik_response",
                        "message": "SELECTION_BY_POINT: final values before selection",
                        "data": {
                            "q": q,
                            "h": h,
                            "h_st": h_st,
                            "q_type": type(q).__name__,
                            "h_type": type(h).__name__
                        },
                        "sessionId": chat_id,
                        "runId": "selection_init",
                        "hypothesisId": "STAGE7"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Проверяем, достаточно ли данных для подбора
            if not q or not h:
                # Недостаточно данных - уточняем
                if not q and not h:
                    response_parts.append(
                        "Для подбора насоса мне нужны параметры рабочей точки:\n"
                        "• Расход (Q) в м³/ч\n"
                        "• Напор (H) в метрах\n\n"
                        "Укажите их, например: Q=10, H=20 или расход 10 м³/ч, напор 20 м"
                    )
                elif not q:
                    next_slot = "flow_m3h"
                    update_state(chat_id, {}, pending_slot=next_slot)
                    question = "Какой расход нужен? (м³/ч, л/мин или другие единицы)"
                    set_last_question(chat_id, question)
                    response_parts.append(question)
                elif not h:
                    next_slot = "head_m"
                    update_state(chat_id, {}, pending_slot=next_slot)
                    question = "Какой напор требуется? (в метрах, барах или других единицах)"
                    set_last_question(chat_id, question)
                    response_parts.append(question)
            else:
                # Вариантивные фразы для начала ответа
                # ИСПРАВЛЕНО: Используем округленные значения для отображения (2 знака после запятой)
                q_display = round(q, 2)
                h_display = round(h, 2)
                intro_phrases = [
                    f"Подбираю насосы для рабочей точки: Q = {q_display} м³/ч, H = {h_display} м...\n",
                    f"Ищу подходящие насосы по параметрам: Q = {q_display} м³/ч, H = {h_display} м...\n",
                    f"Анализирую рабочую точку Q = {q_display} м³/ч, H = {h_display} м и подбираю варианты...\n",
                    f"Подбираю оптимальные насосы для Q = {q_display} м³/ч и H = {h_display} м...\n"
                ]
                response_parts.append(random.choice(intro_phrases))
                
                # Обновляем слоты если они были извлечены
                # ВАЖНО: Не сбрасываем pending_slot, если он был установлен для уточнения других параметров
                # pending_slot будет обновлен выше в блоке обработки slot_result
                if q and h:
                    # Используем keep_pending_if_not_set=True, чтобы не сбрасывать pending_slot
                    update_state(chat_id, {"flow_m3h": q, "head_m": h}, keep_pending_if_not_set=True)
                
                # ВАЛИДАЦИЯ: Проверяем Q и H перед вызовом select_by_working_point
                from services.parsing_validator import validate_qh
                is_valid, q_error, h_error = validate_qh(q, h, "m3/h", "m")
                
                if not is_valid:
                    # Параметры невалидны - сообщаем пользователю
                    error_msg = []
                    if q_error:
                        error_msg.append(q_error)
                    if h_error:
                        error_msg.append(h_error)
                    response_parts.append(
                        f"Извините, параметры рабочей точки некорректны:\n"
                        f"{' '.join(error_msg)}\n\n"
                        f"Пожалуйста, укажите корректные значения Q и H."
                    )
                else:
                    # Параметры валидны - выполняем подбор
                    try:
                        # Если пользователь указал тип насоса (например, "вертикальный многоступенчатый"),
                        # то берём больше кандидатов, чтобы потом отфильтровать по серии.
                        # ВАЖНО: проверяем pump_type_info сначала в data (из текущего запроса),
                        # затем в состоянии (из предыдущих сообщений, если был определен ранее)
                        try:
                            pump_type_info_raw = data.get("pump_type_info") or context.get("state", {}).get("pump_type_info")
                            
                            # Логируем для отладки
                            try:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"Processing pump_type_info: raw={pump_type_info_raw}, type={type(pump_type_info_raw)}")
                            except:
                                pass
                            
                            # Убеждаемся, что pump_type_info - это dict
                            if not isinstance(pump_type_info_raw, dict):
                                pump_type_info = {}
                            else:
                                pump_type_info = pump_type_info_raw.copy()
                            
                            # Если pump_type_info определен в текущем запросе, сохраняем его в состоянии
                            # Это важно для случаев, когда пользователь подтверждает температуру ("да") в следующем сообщении
                            # ВАЖНО: update_state теперь сам рекурсивно обрабатывает Enum и другие несериализуемые объекты
                            if data.get("pump_type_info") and isinstance(data.get("pump_type_info"), dict):
                                pump_type_to_save = data["pump_type_info"].copy()
                                try:
                                    update_state(chat_id, {"pump_type_info": pump_type_to_save}, keep_pending_if_not_set=True)
                                    context["state"]["pump_type_info"] = pump_type_to_save
                                except Exception as e:
                                    # Логируем ошибку, но продолжаем работу
                                    import logging
                                    import traceback
                                    logger = logging.getLogger(__name__)
                                    logger.error(f"Error saving pump_type_info: {str(e)}\n{traceback.format_exc()}")
                        except Exception as e:
                            # Логируем ошибку при обработке pump_type_info
                            import logging
                            import traceback
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error processing pump_type_info: {str(e)}\n{traceback.format_exc()}")
                            pump_type_info = {}
                        
                        # Безопасно извлекаем series из pump_type_info
                        series_filter = None
                        if isinstance(pump_type_info, dict):
                            series_raw = pump_type_info.get("series")
                            # Убеждаемся, что series - это список
                            if isinstance(series_raw, list):
                                series_filter = series_raw
                            elif isinstance(series_raw, str):
                                # Если series - строка, превращаем в список
                                series_filter = [series_raw]
                        
                        # ВАЖНО: Если тип насоса определен, сразу фильтруем только по этой серии
                        # Это значит, что для "вертикальный многоступенчатый" показываем только К377
                        # А для "моноблочный" - только К144
                        top_n = 200 if (series_filter or body_material_code) else 50
                        pumps = select_by_working_point(q, h, h_st=h_st, top_n=top_n)

                        # Фильтрация по серии Кометта (К377/К144/...) - КРИТИЧНО: делаем это ПЕРВЫМ делом
                        if series_filter:
                            def _norm(s: str) -> str:
                                return (s or "").upper().replace("K", "К")

                            series_norm = [_norm(s) for s in series_filter]

                            filtered = []
                            for p in pumps:
                                model_s = _norm(str(p.get("model", "")))
                                series_s = _norm(str(p.get("series", "")))
                                # Проверяем, содержит ли модель или серия одну из указанных серий
                                if any(sn in model_s or sn == series_s for sn in series_norm):
                                    filtered.append(p)

                            # Если нашли по типу — показываем ТОЛЬКО их (фильтруем сразу, как вы просили)
                            if filtered:
                                pumps = filtered
                            else:
                                # Если тип указан, но насосов не найдено - сообщаем об этом
                                type_name = pump_type_info.get("type_name", "указанного типа") if isinstance(pump_type_info, dict) else "указанного типа"
                                response_parts.append(
                                    f"\n⚠️ Для {type_name} (серия {', '.join(series_norm)}) "
                                    f"не найдено насосов для рабочей точки Q = {round(q, 2)} м³/ч, H = {round(h, 2)} м.\n"
                                )
                                pumps = []  # Устанавливаем пустой список, чтобы показать сообщение об отсутствии
                            
                            # Предпочтение складской программы для К144: модели с "/04А/" (или "/04A/")
                            # Особенно важно для воды при положительных температурах (+20°C и выше)
                            if any(sn == "К144" for sn in series_norm) and pumps:
                                import re
                                
                                # Проверяем условия для складской программы:
                                # 1. Вода (fluid == "вода")
                                # 2. Температура положительная (+20°C и выше) или не указана
                                # Для воды +20°C и выше (или без указания температуры) складская программа /04А/ подходит лучше всего
                                # Складская программа универсальна для воды при положительных температурах
                                should_prefer_stock = (
                                    fluid == "вода" and 
                                    (temperature_c is None or temperature_c >= 0)
                                )
                                
                                def _is_stock_pref(p: Dict[str, Any]) -> int:
                                    m = str(p.get("model", "") or "")
                                    # Ищем /04А/ или /04A/ - это складская программа для К144
                                    # A = graphite/sic/fpm уплотнения, подходят для воды при положительных температурах
                                    has_stock = bool(re.search(r"/0*4[АA]/", m, re.IGNORECASE))
                                    if should_prefer_stock:
                                        # Для воды +20°C (или без указания температуры) предпочитаем складскую программу
                                        # Возвращаем 0 для складской программы (она идет первой), 1 для остальных
                                        return 0 if has_stock else 1
                                    else:
                                        # В остальных случаях (не вода или отрицательная температура) сортируем по точности подбора
                                        # Но все равно складская программа немного в приоритете
                                        return 0 if has_stock else 1

                                # Сортируем: сначала складская программа (если подходит), затем по точности подбора
                                pumps.sort(key=lambda p: (_is_stock_pref(p), p.get("error", 1e9)))

                        # Фильтрация по материалу корпуса: /04*/ /16*/ /25*/
                        if body_material_code:
                            import re

                            code = str(body_material_code).strip()

                            def _has_body_code(p: Dict[str, Any]) -> bool:
                                m = str(p.get("model", "") or "")
                                return re.search(rf"/\s*{re.escape(code)}\s*[A-Za-zА-Яа-я]\s*/", m) is not None

                            filtered_by_body = [p for p in pumps if _has_body_code(p)]
                            if filtered_by_body:
                                pumps = filtered_by_body
                    except Exception as e:
                        # Обработка ошибок при подборе насосов
                        from services.error_handler import handle_error, log_error
                        log_error(e, "chat.py:generate_komettik_response:select_by_working_point", 
                                 context={"q": q, "h": h, "h_st": h_st}, session_id=chat_id)
                        response_parts.append(
                            "Извините, произошла ошибка при подборе насосов. "
                            "Пожалуйста, попробуйте ещё раз или обратитесь к администратору."
                        )
                        pumps = []  # Устанавливаем пустой список для корректной обработки ниже
                
                if not pumps:
                    # Вариантивные фразы для отсутствия результатов
                    no_results_phrases = [
                        "К сожалению, не нашёл подходящих насосов для этой рабочей точки. Попробуйте скорректировать параметры.",
                        "Для указанной рабочей точки не удалось найти подходящие насосы. Попробуйте изменить параметры Q или H.",
                        "Не нашёл насосов, соответствующих этой рабочей точке. Возможно, стоит скорректировать параметры.",
                        "Подходящих насосов для этой рабочей точки не найдено. Попробуйте указать другие значения Q и H."
                    ]
                    response_parts.append(random.choice(no_results_phrases))
                else:
                    # Вариантивные фразы для найденных результатов
                    found_phrases = [
                        f"Нашёл {len(pumps)} подходящих варианта:\n",
                        f"Подобрал {len(pumps)} насоса для вашей рабочей точки:\n",
                        f"Найдено {len(pumps)} подходящих варианта:\n",
                        f"Рекомендую {len(pumps)} насоса по вашим параметрам:\n"
                    ]
                    response_parts.append(random.choice(found_phrases))
                    
                    for i, pump in enumerate(pumps, 1):
                        # Формируем название: brand + model
                        brand = pump.get('brand', 'Кометта')
                        model = pump.get('model', '')
                        articul = pump.get('articul', 'не указан')
                        
                        # #region agent log - DEBUG pump data
                        try:
                            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "timestamp": datetime.now().isoformat(),
                                    "location": "chat.py:generate_komettik_response",
                                    "message": "Pump data in chat.py",
                                    "data": {
                                        "articul": articul,
                                        "brand": brand,
                                        "model": model,
                                        "model_type": type(model).__name__,
                                        "model_is_empty": not model or str(model).strip() == ""
                                    },
                                    "sessionId": chat_id,
                                    "runId": "display",
                                    "hypothesisId": "DEBUG"
                                }) + "\n")
                        except: pass
                        # #endregion
                        
                        # Формируем имя: Brand + Model
                        pump_name_parts = []
                        if brand:
                            pump_name_parts.append(str(brand).strip())
                        if model and str(model).lower() not in ["nan", "none", ""]:
                            pump_name_parts.append(str(model).strip())
                        
                        pump_name = " ".join(pump_name_parts)
                        if not pump_name:
                            pump_name = "Насос"
                        
                        response_parts.append(f"\n{i}. {pump_name}")
                        response_parts.append(f"   Артикул: {articul}")
                        if pump.get('power', 0) > 0:
                            response_parts.append(f"   Мощность: {pump['power']} кВт")
                        response_parts.append(f"   Рабочая точка: Q = {pump['q_work']:.2f} м³/ч, H = {pump['h_work']:.2f} м")
                        # ИСПРАВЛЕНО: Показываем отклонение по H отдельно (не комбинированное)
                        h_error = abs(pump['h_work'] - h)  # Отклонение по H от запрошенного значения
                        h_error_percent = (h_error / max(h, 1e-6)) * 100  # Относительное отклонение по H в %
                        response_parts.append(f"   Отклонение: {h_error:.2f} м ({h_error_percent:.1f}%)")
                        # ИСПРАВЛЕНО: Показываем ссылку на лист данных только если есть URL
                        if pump.get('datasheet_url'):
                            response_parts.append(f"   📄 [Лист данных]({pump['datasheet_url']})")
                    
                    # Перемещаем фразу про параметры жидкости ПОСЛЕ списка насосов
                    response_parts.append("\n\nДля более точного подбора укажите параметры жидкости:")
                    response_parts.append("• Тип жидкости (вода, масло, химия и т.д.)")
                    response_parts.append("• Температура")
                    response_parts.append("• Вязкость (если известна)")
                    response_parts.append("• Содержание примесей")
                    
                    # Вариантивные уточняющие вопросы
                    follow_up_questions = [
                        "\n\nЧто ещё могу помочь?",
                        "\n\nЧем ещё могу быть полезен?",
                        "\n\nЧто хотите уточнить?",
                        "\n\nЕсть ещё вопросы?"
                    ]
                    response_parts.append(random.choice(follow_up_questions))
                    
                    # Вариантивные предложения
                    suggestions_variants = [
                        [
                            "• Уточнить параметры жидкости (температура, вязкость, примеси)",
                            "• Построить график кривой для выбранного насоса",
                            "• Сравнить несколько насосов на одном графике",
                            "• Выгрузить лист данных для насоса"
                        ],
                        [
                            "• Дополнить информацию о параметрах жидкости",
                            "• Показать график характеристики насоса",
                            "• Выгрузить лист данных для насоса",
                            "• Сравнить характеристики нескольких насосов"
                        ],
                        [
                            "• Указать параметры перекачиваемой жидкости",
                            "• Построить кривую насоса",
                            "• Сравнить насосы визуально на графике",
                            "• Выгрузить лист данных для насоса"
                        ],
                        [
                            "• Уточнить свойства жидкости",
                            "• Визуализировать кривую насоса",
                            "• Выгрузить лист данных для насоса",
                            "• Сопоставить несколько вариантов на графике"
                        ]
                    ]
                    response_parts.extend(random.choice(suggestions_variants))
        
        elif intent == Intent.ANALOG_BY_MODEL:
            try:
                # ВАЖНО: Сначала проверяем, есть ли в текущем сообщении новая модель
                # Это нужно, чтобы если пользователь написал новую модель, мы её распарсили,
                # даже если есть pending_confirmation от предыдущего запроса
                from services.intents import detect_model_name, extract_brand_and_model
                new_model_in_message = detect_model_name(message)
                
                # Проверяем, ожидается ли подтверждение модели
                pending_confirmation = context["state"].get("pending_analog_confirmation")
                
                # Если в сообщении есть новая модель И есть pending_confirmation - это новая модель, а не ответ на подтверждение
                if new_model_in_message and pending_confirmation:
                    # Пользователь указал новую модель - очищаем старое подтверждение и парсим новую
                    brand_model = extract_brand_and_model(message)
                    confirmation_data = {
                        "model": new_model_in_message,
                        "brand": brand_model.get("brand"),
                        "model_only": brand_model.get("model")
                    }
                    update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
                    
                    confirmation_phrases = [
                        f"Я правильно понял, что вам нужен аналог насоса {new_model_in_message}?",
                        f"Правильно ли я понял, что вы ищете аналог для насоса {new_model_in_message}?",
                        f"Вы хотите найти аналог насоса {new_model_in_message}?",
                        f"Подтвердите, пожалуйста: вы ищете аналог насоса {new_model_in_message}?",
                        f"Мне нужно подтверждение: вы ищете аналог для насоса {new_model_in_message}?",
                        f"Правильно ли я понял модель: {new_model_in_message}?",
                        f"Вы имеете в виду насос {new_model_in_message}?",
                        f"Подтвердите модель насоса: {new_model_in_message}?",
                        f"Это правильная модель для поиска аналога: {new_model_in_message}?",
                        f"Вы ищете аналог насоса {new_model_in_message} — верно?"
                    ]
                    response_parts.append(random.choice(confirmation_phrases))
                    return "\n".join(response_parts)
                
                # Проверяем, это ответ на подтверждение?
                if pending_confirmation:
                    # Проверяем, это положительный ответ?
                    message_lower = message.lower().strip()
                    positive_answers = ["да", "конечно", "верно", "правильно", "точно", "именно", "yes", "yep", "ага", "угу"]
                    negative_answers = ["нет", "не", "неправильно", "неверно", "no", "nope", "не то"]
                    
                    is_positive = any(answer in message_lower for answer in positive_answers)
                    is_negative = any(answer in message_lower for answer in negative_answers)
                    
                    if is_positive:
                        # Подтверждено - выполняем поиск
                        model = pending_confirmation.get("model")
                        brand = pending_confirmation.get("brand")
                        model_only = pending_confirmation.get("model_only")
                        
                        # Очищаем ожидание подтверждения
                        update_state(chat_id, {"pending_analog_confirmation": None})
                        
                        # Выполняем поиск аналога
                        search_phrases = [
                            f"Ищу аналог для модели {model}...\n",
                            f"Ищу подходящий аналог Кометта для {model}...\n",
                            f"Анализирую модель {model} и подбираю аналоги...\n"
                        ]
                        response_parts.append(random.choice(search_phrases))
                        
                        # Если есть только модель без бренда, ищем по модели
                        if not brand and model_only:
                            competitor_data, analogs = find_analog_by_model(model_only, top_n=3)
                        else:
                            competitor_data, analogs = find_analog_by_model(model, top_n=3)
                        
                        # Обрабатываем результаты поиска
                        if competitor_data is None:
                            not_found_phrases = [
                                f"Не нашёл модель {model} в базе конкурентов. Попробуйте указать точное название модели или подберите насос по рабочей точке.",
                                f"Модель {model} отсутствует в базе конкурентов. Укажите точное название или используйте подбор по рабочей точке.",
                                f"В базе конкурентов нет модели {model}. Попробуйте указать точное название или подобрать насос по параметрам Q и H."
                            ]
                            response_parts.append(random.choice(not_found_phrases))
                        elif not analogs:
                            no_analogs_phrases = [
                                f"Нашёл модель {model}, но не нашёл подходящих аналогов Кометта. Попробуйте подобрать насос по рабочей точке.",
                                f"Модель {model} найдена, но подходящих аналогов Кометта нет. Рекомендую подобрать насос по параметрам Q и H.",
                                f"Для модели {model} не удалось найти аналоги Кометта. Попробуйте подобрать насос по рабочей точке."
                            ]
                            response_parts.append(random.choice(no_analogs_phrases))
                        else:
                            found_phrases = [
                                f"Нашёл модель конкурента: {competitor_data['brand']} {competitor_data['model']}",
                                f"Модель найдена: {competitor_data['brand']} {competitor_data['model']}",
                                f"Обнаружена модель: {competitor_data['brand']} {competitor_data['model']}"
                            ]
                            response_parts.append(random.choice(found_phrases))
                            
                            analog_intro_phrases = [
                                f"\nПодходящие аналоги Кометта:\n",
                                f"\nРекомендую следующие аналоги Кометта:\n",
                                f"\nНайдены следующие аналоги Кометта:\n"
                            ]
                            response_parts.append(random.choice(analog_intro_phrases))
                            
                            for i, analog in enumerate(analogs, 1):
                                # Формируем название: brand + model
                                brand_analog = analog.get('brand', 'Кометта')
                                analog_model = analog.get('model', '')
                                articul = analog.get('articul', 'не указан')
                                
                                # Очищаем model от пустых значений и "Артикул ..."
                                if not analog_model or analog_model.strip() == "" or analog_model.lower() in ["nan", "none", "не указана"] or analog_model.startswith("Артикул "):
                                    analog_name = brand_analog
                                else:
                                    # Убираем лишние пробелы из model
                                    analog_model_clean = analog_model.strip()
                                    analog_name = f"{brand_analog} {analog_model_clean}"
                                
                                response_parts.append(f"\n{i}. {analog_name}")
                                response_parts.append(f"   Артикул: {articul}")
                                if analog.get('power', 0) > 0:
                                    response_parts.append(f"   Мощность: {analog['power']} кВт")
                                response_parts.append(f"   Отклонение кривой: {analog['rmse']:.2f} м")
                                # Ссылка на лист данных в формате Markdown
                                if analog.get('datasheet_url'):
                                    response_parts.append(f"   📄 [Лист данных]({analog['datasheet_url']})")
                                else:
                                    response_parts.append(f"   📄 Лист данных: не доступен")
                            
                            graph_offer_phrases = [
                                "\n\nМогу построить две кривые на одном графике для сравнения — хотите?",
                                "\n\nХотите сравнить кривые визуально? Могу построить график с кривыми обоих насосов.",
                                "\n\nМогу визуализировать сравнение кривых на одном графике — интересно?"
                            ]
                            response_parts.append(random.choice(graph_offer_phrases))
                            
                            graph_instruction_phrases = [
                                "Просто напишите: 'Построй график сравнения' или укажите артикул насоса Кометта.",
                                "Напишите 'Построй график' или укажите артикул насоса Кометта для сравнения.",
                                "Укажите артикул насоса Кометта или напишите 'Построй график' для визуализации."
                            ]
                            response_parts.append(random.choice(graph_instruction_phrases))
                        
                        return "\n".join(response_parts)
                    elif is_negative:
                        # Отклонено - очищаем и просим уточнить
                        update_state(chat_id, {"pending_analog_confirmation": None})
                        response_parts.append("Понял. Пожалуйста, укажите правильную модель насоса конкурента, например: CNP CDM 1-3")
                    else:
                        # Непонятный ответ - проверяем, может быть это новая модель?
                        # Пробуем распарсить модель из текущего сообщения
                        from services.intents import detect_model_name, extract_brand_and_model
                        new_model = detect_model_name(message)
                        if new_model:
                            # Пользователь указал новую модель - очищаем старое подтверждение и парсим новую
                            brand_model = extract_brand_and_model(message)
                            confirmation_data = {
                                "model": new_model,
                                "brand": brand_model.get("brand"),
                                "model_only": brand_model.get("model")
                            }
                            update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
                            
                            confirmation_phrases = [
                                f"Я правильно понял, что вам нужен аналог насоса {new_model}?",
                                f"Правильно ли я понял, что вы ищете аналог для насоса {new_model}?",
                                f"Вы хотите найти аналог насоса {new_model}?",
                                f"Подтвердите, пожалуйста: вы ищете аналог насоса {new_model}?",
                                f"Мне нужно подтверждение: вы ищете аналог для насоса {new_model}?",
                                f"Правильно ли я понял модель: {new_model}?",
                                f"Вы имеете в виду насос {new_model}?",
                                f"Подтвердите модель насоса: {new_model}?",
                                f"Это правильная модель для поиска аналога: {new_model}?",
                                f"Вы ищете аналог насоса {new_model} — верно?"
                            ]
                            response_parts.append(random.choice(confirmation_phrases))
                            return "\n".join(response_parts)
                        else:
                            # Непонятный ответ и не новая модель - уточняем
                            confirmation_phrases = [
                                f"Я правильно понял, что вам нужен аналог насоса {pending_confirmation.get('model', 'неизвестная модель')}?",
                                f"Правильно ли я понял, что вы ищете аналог для насоса {pending_confirmation.get('model', 'неизвестная модель')}?",
                                f"Вы хотите найти аналог насоса {pending_confirmation.get('model', 'неизвестная модель')}?"
                            ]
                            response_parts.append(random.choice(confirmation_phrases))
                            return "\n".join(response_parts)
                
                # Проверяем, это запрос по бренду?
                elif data.get("action") == "by_brand":
                    brand = data.get("brand", "")
                    if brand:
                        from services.data_loader import load_competitors_data
                        df_comp = load_competitors_data()
                        # Ищем все модели этого бренда
                        brand_matches = df_comp[df_comp["brand"].astype(str).str.upper() == brand.upper()]
                        if brand_matches.empty:
                            response_parts.append(f"Не нашёл насосов бренда {brand} в базе конкурентов.")
                        else:
                            # Берём первую модель и ищем аналоги
                            first_row = brand_matches.iloc[0]
                            model = f"{first_row.get('brand', '')} {first_row.get('model', '')}".strip()
                            if model:
                                competitor_data, analogs = find_analog_by_model(model, top_n=3)
                                if competitor_data and analogs:
                                    response_parts.append(f"Нашёл модели бренда {brand} в базе конкурентов.")
                                    response_parts.append(f"\nАналоги Кометта:\n")
                                    for i, analog in enumerate(analogs, 1):
                                        brand_analog = analog.get('brand', 'Кометта')
                                        analog_model = analog.get('model', '')
                                        if not analog_model or analog_model.strip() == "" or analog_model.lower() in ["nan", "none", "не указана"] or analog_model.startswith("Артикул "):
                                            analog_name = brand_analog
                                        else:
                                            analog_name = f"{brand_analog} {analog_model.strip()}"
                                        response_parts.append(f"{i}. {analog_name}")
                                        response_parts.append(f"   Артикул: {analog.get('articul', 'не указан')}")
                                        if analog.get('power', 0) > 0:
                                            response_parts.append(f"   Мощность: {analog['power']} кВт")
                                        response_parts.append(f"   Отклонение: {analog['rmse']:.2f} м")
                                else:
                                    response_parts.append(f"Нашёл модели бренда {brand}, но не нашёл подходящих аналогов Кометта.")
                            else:
                                response_parts.append(f"Не удалось определить модель для бренда {brand}.")
                    else:
                        response_parts.append("Укажите бренд насоса конкурента.")
                else:
                    # Новый запрос на поиск аналога - показываем подтверждение
                    model = data.get("model")
                    brand = data.get("brand")
                    model_only = data.get("model_only")
                    
                    if not model:
                        no_model_phrases = [
                            "Укажите модель насоса конкурента, например: CNP CDMF 1-3",
                            "Пожалуйста, укажите модель насоса конкурента (например: CNP CDMF 1-3)",
                            "Для поиска аналога нужна модель насоса конкурента, например: CNP CDMF 1-3"
                        ]
                        response_parts.append(random.choice(no_model_phrases))
                    else:
                        # Сохраняем информацию о модели для подтверждения
                        confirmation_data = {
                            "model": model,
                            "brand": brand,
                            "model_only": model_only
                        }
                        update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
                        
                        # Показываем подтверждение
                        confirmation_phrases = [
                            f"Я правильно понял, что вам нужен аналог насоса {model}?",
                            f"Правильно ли я понял, что вы ищете аналог для насоса {model}?",
                            f"Вы хотите найти аналог насоса {model}?",
                            f"Подтвердите, пожалуйста: вы ищете аналог насоса {model}?",
                            f"Мне нужно подтверждение: вы ищете аналог для насоса {model}?",
                            f"Правильно ли я понял модель: {model}?",
                            f"Вы имеете в виду насос {model}?",
                            f"Подтвердите модель насоса: {model}?",
                            f"Это правильная модель для поиска аналога: {model}?",
                            f"Вы ищете аналог насоса {model} — верно?"
                        ]
                        response_parts.append(random.choice(confirmation_phrases))
                        return "\n".join(response_parts)
            except Exception as e:
                # Обработка ошибок при поиске аналогов
                from services.error_handler import handle_error, log_error
                log_error(e, "chat.py:generate_komettik_response:ANALOG_BY_MODEL", 
                         context={"intent": intent, "data": data}, session_id=chat_id)
                response_parts.append(
                    "Извините, произошла ошибка при поиске аналогов. "
                    "Пожалуйста, попробуйте ещё раз или обратитесь к администратору."
                )
        
        elif intent == Intent.FILE_UPLOAD:
            try:
                if not attachments:
                    response_parts.append("Прикрепите файл (PDF или изображение), и я попробую извлечь данные.")
                else:
                    response_parts.append("Обрабатываю файл...\n")
                    
                    extracted_data = None
                    for attachment in attachments:
                        try:
                            result = process_file(
                                attachment.filename,
                                attachment.content_type,
                                attachment.base64
                            )
                            
                            if result.get("success"):
                                extracted_data = result
                                break
                        except Exception as e:
                            # Логируем ошибку обработки файла, но продолжаем с другими файлами
                            from services.error_handler import log_error
                            log_error(e, "chat.py:generate_komettik_response:FILE_UPLOAD:process_file",
                                     context={"filename": attachment.filename, "content_type": attachment.content_type},
                                     session_id=chat_id)
                            continue
                    
                    if extracted_data and extracted_data.get("success"):
                        model = extracted_data.get("model")
                        brand = extracted_data.get("brand")
                        power = extracted_data.get("power")
                        
                        response_parts.append("Извлёк данные из файла:\n")
                        
                        if model:
                            response_parts.append(f"Модель: {model}")
                        if brand:
                            response_parts.append(f"Бренд: {brand}")
                        if power:
                            response_parts.append(f"Мощность: {power} кВт")
                        
                        if model:
                            response_parts.append(f"\nЯ правильно понял модель {model}?")
                            response_parts.append("Если да, могу найти аналог или подобрать насос по параметрам.")
                        else:
                            response_parts.append("\nНе удалось извлечь модель. Попробуйте указать её вручную.")
                    else:
                        response_parts.append(
                            "Не удалось обработать файл. "
                            "Попробуйте указать модель насоса в тексте сообщения."
                        )
            except Exception as e:
                # Обработка ошибок при обработке файлов
                from services.error_handler import handle_error, log_error
                log_error(e, "chat.py:generate_komettik_response:FILE_UPLOAD", 
                         context={"intent": intent, "attachments_count": len(attachments)}, session_id=chat_id)
                response_parts.append(
                    "Извините, произошла ошибка при обработке файла. "
                    "Пожалуйста, попробуйте ещё раз или укажите модель насоса в тексте сообщения."
                )
        
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
                # message уже нормализован (исправлены опечатки) в chat_endpoint
                query = data.get("query", message)
                
                from services.kb.search import search
                from services.kb.summarize import format_answer
                
                # Выполняем поиск по нормализованному запросу
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
            session_id=session_id,
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


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint для чата с Кометтиком.
    Возвращает потоковый ответ (SSE).
    """
    # #region agent log
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "chat.py:chat_endpoint",
                "message": "Chat endpoint called",
                "data": {
                    "chat_id": request.chat_id,
                    "message_length": len(request.message),
                    "message_preview": request.message[:MAX_MESSAGE_PREVIEW] if len(request.message) > MAX_MESSAGE_PREVIEW else request.message,
                    "has_attachments": len(request.attachments) > 0
                },
                "sessionId": request.chat_id,
                "runId": "analysis",
                "hypothesisId": "STAGE7"
            }) + "\n")
    except: pass
    # #endregion
    try:
        # Нормализуем сообщение: исправляем опечатки (НО сохраняем оригинал для логов)
        # ВАЖНО: normalize_user_text не трогает модели, артикулы, числа, бренды
        enable_fuzzy = os.getenv("TYPO_FUZZY", "1") == "1"
        normalized_message, corrections = normalize_user_text(
            request.message,
            enable_fuzzy=enable_fuzzy
        )
        
        # Определяем интент на нормализованном тексте
        has_attachments = len(request.attachments) > 0

        # ВАЖНО: если мы ждём подтверждение модели для аналога, то короткие ответы
        # ("да/нет/ага/верно/...") должны попадать в обработчик ANALOG_BY_MODEL,
        # даже если они не содержат модель.
        try:
            pending_confirmation = get_context_for_model(request.chat_id).get("state", {}).get("pending_analog_confirmation")
        except Exception:
            pending_confirmation = None

        msg_l = normalized_message.lower().strip()
        positive_answers = {"да", "конечно", "верно", "правильно", "точно", "именно", "yes", "yep", "ага", "угу"}
        negative_answers = {"нет", "не", "неправильно", "неверно", "no", "nope", "не то"}

        if pending_confirmation and (msg_l in positive_answers or msg_l in negative_answers):
            intent_result = {"intent": Intent.ANALOG_BY_MODEL, "data": {}}
        else:
            intent_result = detect_intent(normalized_message, has_attachments)
        
        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:chat_endpoint",
                    "message": "Intent detected",
                    "data": {
                        "intent": intent_result["intent"],
                        "extracted_data": intent_result["data"]
                    },
                    "sessionId": request.chat_id,
                    "runId": "analysis",
                    "hypothesisId": "STAGE7"
                }) + "\n")
        except: pass
        # #endregion
        
        # Генерируем ответ
        response_text = generate_komettik_response(
            intent_result["intent"],
            intent_result["data"],
            normalized_message,  # Используем нормализованное сообщение
            request.attachments,
            chat_id=request.chat_id  # Передаём chat_id для сохранения контекста
        )
        
        # Возвращаем потоковый ответ
        return StreamingResponse(
            stream_response(response_text),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    except Exception as e:
        # Используем единую систему обработки ошибок
        from services.error_handler import handle_error, log_error
        
        session_id = request.chat_id if 'request' in locals() else "unknown"
        error_message = handle_error(
            e,
            "chat.py:chat_endpoint",
            context={"message_length": len(request.message) if 'request' in locals() else 0},
            session_id=session_id,
            user_message=request.message if 'request' in locals() else None
        )
        
        # Для критических ошибок возвращаем простой ответ вместо 500
        async def error_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': error_message})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

