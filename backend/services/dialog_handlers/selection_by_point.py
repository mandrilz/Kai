from typing import Any, Dict
import json
import os
import random
from datetime import datetime

from services.dialog_handlers.types import HandlerResult
from services.conversation_state import update_state, set_last_question
from services.intents import Intent
from services.selector import select_by_working_point


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
                res.response_parts.append(
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
                res.response_parts.append(question)
            elif not h:
                next_slot = "head_m"
                update_state(chat_id, {}, pending_slot=next_slot)
                question = "Какой напор требуется? (в метрах, барах или других единицах)"
                set_last_question(chat_id, question)
                res.response_parts.append(question)
            return res

        q_display = round(q, 2)
        h_display = round(h, 2)
        intro_phrases = [
            f"Подбираю насосы для рабочей точки: Q = {q_display} м³/ч, H = {h_display} м...\n",
            f"Ищу подходящие насосы по параметрам: Q = {q_display} м³/ч, H = {h_display} м...\n",
            f"Анализирую рабочую точку Q = {q_display} м³/ч, H = {h_display} м и подбираю варианты...\n",
            f"Подбираю оптимальные насосы для Q = {q_display} м³/ч и H = {h_display} м...\n",
        ]
        res.response_parts.append(random.choice(intro_phrases))

        # Обновляем слоты если они были извлечены
        update_state(chat_id, {"flow_m3h": q, "head_m": h}, keep_pending_if_not_set=True)

        from services.parsing_validator import validate_qh
        is_valid, q_error, h_error = validate_qh(q, h, "m3/h", "m")
        if not is_valid:
            error_msg = []
            if q_error:
                error_msg.append(q_error)
            if h_error:
                error_msg.append(h_error)
            res.response_parts.append(
                f"Извините, параметры рабочей точки некорректны:\n"
                f"{' '.join(error_msg)}\n\n"
                f"Пожалуйста, укажите корректные значения Q и H."
            )
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

        # Если тип насоса определен, берём больше кандидатов, а затем фильтруем
        top_n = 50 if series_filter else 5
        pumps = select_by_working_point(q, h, h_st=h_st, top_n=top_n)

        if series_filter:
            filtered = []
            for p in pumps:
                model = str(p.get("model", "") or "")
                series = str(p.get("series", "") or "")
                if any(s in model or s in series for s in series_filter):
                    filtered.append(p)
            if filtered:
                pumps = filtered

        pumps = pumps[:5]
        if not pumps:
            res.response_parts.append(
                "К сожалению, не нашёл подходящих насосов Кометта для этой рабочей точки. "
                "Проверьте значения Q и H или уточните дополнительные параметры системы."
            )
            return res

        res.response_parts.append("\nПодходящие насосы Кометта:")
        for i, pump in enumerate(pumps, 1):
            brand = pump.get("brand", "Кометта")
            model = pump.get("model", "")
            series = pump.get("series", "не указана")
            articul = pump.get("articul", "не указан")
            power = pump.get("power", 0.0)

            name_parts = []
            if brand:
                name_parts.append(str(brand).strip())
            if model and str(model).lower() not in ["nan", "none", ""]:
                name_parts.append(str(model).strip())
            pump_name = " ".join(name_parts) or "Кометта"

            res.response_parts.append(f"\n{i}. {pump_name}")
            if series and series != "не указана":
                res.response_parts.append(f"   Серия: {series}")
            res.response_parts.append(f"   Артикул: {articul}")
            if power and float(power) > 0:
                res.response_parts.append(f"   Мощность: {power} кВт")

            if pump.get("datasheet_url"):
                res.response_parts.append(f"   📄 [Лист данных]({pump['datasheet_url']})")

        # Предлагаем уточнить параметры жидкости
        res.response_parts.append("\n\nДля более точного подбора укажите параметры жидкости:")
        res.response_parts.append("• Тип жидкости (вода, масло, химия и т.д.)")
        res.response_parts.append("• Температура")
        res.response_parts.append("• Вязкость (если известна)")
        res.response_parts.append("• Содержание примесей")

        follow_up_questions = [
            "\n\nЧто ещё могу помочь?",
            "\n\nЧем ещё могу быть полезен?",
            "\n\nЧто хотите уточнить?",
            "\n\nЕсть ещё вопросы?",
        ]
        res.response_parts.append(random.choice(follow_up_questions))

        suggestions_variants = [
            [
                "• Уточнить параметры жидкости (температура, вязкость, примеси)",
                "• Построить график кривой для выбранного насоса",
                "• Сравнить несколько насосов на одном графике",
                "• Выгрузить лист данных для насоса",
            ],
            [
                "• Дополнить информацию о параметрах жидкости",
                "• Показать график характеристики насоса",
                "• Выгрузить лист данных для насоса",
                "• Сравнить характеристики нескольких насосов",
            ],
            [
                "• Указать параметры перекачиваемой жидкости",
                "• Построить кривую насоса",
                "• Сравнить насосы визуально на графике",
                "• Выгрузить лист данных для насоса",
            ],
            [
                "• Уточнить свойства жидкости",
                "• Визуализировать кривую насоса",
                "• Выгрузить лист данных для насоса",
                "• Сопоставить несколько вариантов на графике",
            ],
        ]
        res.response_parts.extend(random.choice(suggestions_variants))
        return res
    except Exception as e:
        from services.error_handler import log_error

        log_error(
            e,
            "chat.py:generate_komettik_response:SELECTION_BY_POINT",
            context={"data": data},
            session_id=chat_id,
        )
        res.response_parts.append(
            "Извините, произошла ошибка при подборе насоса. "
            "Пожалуйста, проверьте параметры Q и H и попробуйте ещё раз."
        )
        return res

