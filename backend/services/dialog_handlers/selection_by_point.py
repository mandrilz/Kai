from typing import Any, Dict
import json
import os
import random
from datetime import datetime

from services.dialog_handlers.types import HandlerResult
from services.conversation_state import update_state, set_last_question
from services.intents import Intent
from services.selector import select_by_working_point
from services.prompt_templates import (
    get_selection_intro,
    get_selection_no_qh,
    get_selection_no_q,
    get_selection_no_h,
    get_selection_no_results,
    get_selection_found,
    get_selection_series_not_found,
    get_selection_fluid_params,
    get_selection_suggestions,
    get_validation_error,
    get_follow_up_questions,
)


DEBUG_LOG_PATH = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")


def handle_selection_by_point(
    *,
    chat_id: str,
    message: str,
    data: Dict[str, Any],
    context: Dict[str, Any],
    pending_slot: Any,
    slot_result: Dict[str, Any],
    updates: Dict[str, Any],
) -> HandlerResult:
    """
    Вынесенная ветка Intent.SELECTION_BY_POINT из chat.py без изменения поведения.
    """
    res = HandlerResult()
    try:
        # КРИТИЧНО: Если есть pending_slot для температуры - сначала уточняем температуру
        if pending_slot == "temperature_c" and slot_result.get("next_question"):
            res.immediate_response = slot_result["next_question"]
            return res

        # Используем данные из слотов или из парсинга
        q = data.get("q") or (context.get("state") or {}).get("flow_m3h")
        h = data.get("h") or (context.get("state") or {}).get("head_m")
        h_st = (context.get("state") or {}).get("h_st", 0.0)
        body_material_code = data.get("body_material_code") or (context.get("state") or {}).get("body_material_code")
        temperature_c = (context.get("state") or {}).get("temperature_c")
        fluid = (context.get("state") or {}).get("fluid")

        # #region agent log
        try:
            os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selection_by_point.py:handle_selection_by_point",
                    "message": "SELECTION_BY_POINT: initial values",
                    "data": {
                        "q_from_data": data.get("q"),
                        "h_from_data": data.get("h"),
                        "q_from_state": (context.get("state") or {}).get("flow_m3h"),
                        "h_from_state": (context.get("state") or {}).get("head_m"),
                        "h_st_from_state": (context.get("state") or {}).get("h_st"),
                        "updates": updates
                    },
                    "sessionId": chat_id,
                    "runId": "selection_init",
                    "hypothesisId": "STAGE7"
                }) + "\n")
        except Exception:
            pass
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

        if h_st is None:
            h_st = 0.0

        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selection_by_point.py:handle_selection_by_point",
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
        except Exception:
            pass
        # #endregion

        # Проверяем, достаточно ли данных для подбора
        if not q or not h:
            if not q and not h:
                res.response_parts.append(get_selection_no_qh())
            elif not q:
                next_slot = "flow_m3h"
                update_state(chat_id, {}, pending_slot=next_slot)
                question = get_selection_no_q()
                set_last_question(chat_id, question)
                res.response_parts.append(question)
            elif not h:
                next_slot = "head_m"
                update_state(chat_id, {}, pending_slot=next_slot)
                question = get_selection_no_h()
                set_last_question(chat_id, question)
                res.response_parts.append(question)
            return res

        res.response_parts.append(get_selection_intro(q, h))

        # Обновляем слоты если они были извлечены
        update_state(chat_id, {"flow_m3h": q, "head_m": h}, keep_pending_if_not_set=True)

        from services.parsing_validator import validate_qh
        is_valid, q_error, h_error = validate_qh(q, h, "m3/h", "m")
        if not is_valid:
            res.response_parts.append(get_validation_error(q_error, h_error))
            return res

        # Параметры валидны - выполняем подбор
        pump_type_info = {}
        try:
            pump_type_info_raw = data.get("pump_type_info") or (context.get("state") or {}).get("pump_type_info")
            if not isinstance(pump_type_info_raw, dict):
                pump_type_info = {}
            else:
                pump_type_info = pump_type_info_raw.copy()

            if data.get("pump_type_info") and isinstance(data.get("pump_type_info"), dict):
                pump_type_to_save = data["pump_type_info"].copy()
                try:
                    update_state(chat_id, {"pump_type_info": pump_type_to_save}, keep_pending_if_not_set=True)
                    (context.get("state") or {})["pump_type_info"] = pump_type_to_save
                except Exception:
                    pass
        except Exception:
            pump_type_info = {}

        series_filter = None
        if isinstance(pump_type_info, dict):
            series_raw = pump_type_info.get("series")
            if isinstance(series_raw, list):
                series_filter = series_raw
            elif isinstance(series_raw, str):
                series_filter = [series_raw]

        # ВАЖНО: Если тип насоса определен, берём больше кандидатов для фильтрации
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

            # Если нашли по типу — показываем ТОЛЬКО их
            if filtered:
                pumps = filtered
            else:
                # Если тип указан, но насосов не найдено - сообщаем об этом
                type_name = pump_type_info.get("type_name", "указанного типа") if isinstance(pump_type_info, dict) else "указанного типа"
                res.response_parts.append(get_selection_series_not_found(type_name, series_norm, q, h))
                pumps = []  # Устанавливаем пустой список, чтобы показать сообщение об отсутствии
            
            # Предпочтение складской программы для К144: модели с "/04А/" (или "/04A/")
            # Особенно важно для воды при положительных температурах (+20°C и выше)
            if any(sn == "К144" for sn in series_norm) and pumps:
                import re
                
                # Проверяем условия для складской программы:
                # 1. Вода (fluid == "вода")
                # 2. Температура положительная (+20°C и выше) или не указана
                should_prefer_stock = (
                    fluid == "вода" and 
                    (temperature_c is None or temperature_c >= 0)
                )
                
                def _is_stock_pref(p: Dict[str, Any]) -> int:
                    m = str(p.get("model", "") or "")
                    # Ищем /04А/ или /04A/ - это складская программа для К144
                    has_stock = bool(re.search(r"/0*4[АA]/", m, re.IGNORECASE))
                    if should_prefer_stock:
                        # Для воды +20°C (или без указания температуры) предпочитаем складскую программу
                        return 0 if has_stock else 1
                    else:
                        # В остальных случаях сортируем по точности подбора
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

        # Ограничиваем до 5 насосов для отображения
        pumps = pumps[:5]
        
        if not pumps:
            res.response_parts.append(get_selection_no_results())
            return res

        res.response_parts.append(get_selection_found(len(pumps)))
        
        # Сохраняем информацию о первом (лучшем) насосе в состоянии для контекста
        if pumps and len(pumps) > 0:
            first_pump = pumps[0]
            last_selected_pump = {
                "articul": first_pump.get('articul', ''),
                "model": first_pump.get('model', ''),
                "brand": first_pump.get('brand', 'Кометта'),
                "power": first_pump.get('power', 0),
                "q_work": first_pump.get('q_work', 0),
                "h_work": first_pump.get('h_work', 0)
            }
            update_state(chat_id, {"last_selected_pump": last_selected_pump}, keep_pending_if_not_set=True)
            context["state"]["last_selected_pump"] = last_selected_pump
        
        for i, pump in enumerate(pumps, 1):
            # Формируем название: brand + model
            brand = pump.get('brand', 'Кометта')
            model = pump.get('model', '')
            articul = pump.get('articul', 'не указан')
            
            # Формируем имя: Brand + Model
            pump_name_parts = []
            if brand:
                pump_name_parts.append(str(brand).strip())
            if model and str(model).lower() not in ["nan", "none", ""]:
                pump_name_parts.append(str(model).strip())
            
            pump_name = " ".join(pump_name_parts)
            if not pump_name:
                pump_name = "Насос"
            
            res.response_parts.append(f"\n{i}. {pump_name}")
            if pump.get("series") and pump.get("series") != "не указана":
                res.response_parts.append(f"   Серия: {pump['series']}")
            res.response_parts.append(f"   Артикул: {articul}")
            if pump.get('power', 0) > 0:
                res.response_parts.append(f"   Мощность: {pump['power']} кВт")
            res.response_parts.append(f"   Рабочая точка: Q = {pump['q_work']:.2f} м³/ч, H = {pump['h_work']:.2f} м")
            # Показываем отклонение по H отдельно
            h_error = abs(pump['h_work'] - h)  # Отклонение по H от запрошенного значения
            h_error_percent = (h_error / max(h, 1e-6)) * 100  # Относительное отклонение по H в %
            res.response_parts.append(f"   Отклонение: {h_error:.2f} м ({h_error_percent:.1f}%)")
            # Ссылка на лист данных только если есть URL
            if pump.get('datasheet_url'):
                res.response_parts.append(f"   📄 [Лист данных]({pump['datasheet_url']})")

        # Предлагаем уточнить параметры жидкости
        res.response_parts.extend(get_selection_fluid_params())
        res.response_parts.append(random.choice(get_follow_up_questions()))
        res.response_parts.extend(get_selection_suggestions())
        return res
    except Exception as e:
        from services.error_handler import log_error

        log_error(
            e,
            "dialog_handlers.selection_by_point:handle_selection_by_point",
            context={"data": data},
            session_id=chat_id,
        )
        from services.prompt_templates import get_error_message_generic
        res.response_parts.append(get_error_message_generic())
        return res

