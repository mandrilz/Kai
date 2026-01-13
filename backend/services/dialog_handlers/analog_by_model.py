from typing import Any, Dict

from services.dialog_handlers.types import HandlerResult
from services.conversation_state import update_state
from services.selector import find_analog_by_model
from services.prompt_templates import (
    get_analog_confirmation,
    get_analog_no_model,
    get_analog_search_start,
    get_analog_not_found,
    get_analog_no_analogs,
    get_analog_found,
    get_analog_intro,
    get_analog_graph_offer,
    get_analog_graph_instruction,
    get_analog_wrong_model,
    get_analog_brand_not_found,
    get_analog_brand_no_analogs,
    get_analog_brand_no_model,
    get_analog_no_brand,
    get_error_message_generic,
)


def handle_analog_by_model(
    *,
    chat_id: str,
    message: str,
    data: Dict[str, Any],
    context: Dict[str, Any],
) -> HandlerResult:
    res = HandlerResult()
    try:
        # ВАЖНО: Сначала проверяем, есть ли в текущем сообщении новая модель
        # Это нужно, чтобы если пользователь написал новую модель, мы её распарсили,
        # даже если есть pending_confirmation от предыдущего запроса
        from services.intents import detect_model_name, extract_brand_and_model
        new_model_in_message = detect_model_name(message)

        # Проверяем, ожидается ли подтверждение модели
        pending_confirmation = (context.get("state") or {}).get("pending_analog_confirmation")

        # Если в сообщении есть новая модель И есть pending_confirmation - это новая модель, а не ответ на подтверждение
        if new_model_in_message and pending_confirmation:
            brand_model = extract_brand_and_model(message)
            confirmation_data = {
                "model": new_model_in_message,
                "brand": brand_model.get("brand"),
                "model_only": brand_model.get("model"),
            }
            update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
            res.immediate_response = get_analog_confirmation(new_model_in_message)
            return res

        # Проверяем, это ответ на подтверждение?
        if pending_confirmation:
            message_lower = message.lower().strip()
            positive_answers = ["да", "конечно", "верно", "правильно", "точно", "именно", "yes", "yep", "ага", "угу"]
            negative_answers = ["нет", "не", "неправильно", "неверно", "no", "nope", "не то"]

            is_positive = any(answer in message_lower for answer in positive_answers)
            is_negative = any(answer in message_lower for answer in negative_answers)

            if is_positive:
                model = pending_confirmation.get("model")
                brand = pending_confirmation.get("brand")
                model_only = pending_confirmation.get("model_only")

                # Очищаем ожидание подтверждения, но сохраняем контекст для продолжения диалога
                update_state(chat_id, {"pending_analog_confirmation": None}, keep_pending_if_not_set=True)
                res.response_parts.append(get_analog_search_start(model))

                # Если есть только модель без бренда, ищем по модели
                if not brand and model_only:
                    competitor_data, analogs = find_analog_by_model(model_only, top_n=3)
                else:
                    competitor_data, analogs = find_analog_by_model(model, top_n=3)

                if competitor_data is None:
                    res.response_parts.append(get_analog_not_found(model))
                    return res

                if not analogs:
                    res.response_parts.append(get_analog_no_analogs(model))
                    return res

                res.response_parts.append(get_analog_found(competitor_data['brand'], competitor_data['model']))
                res.response_parts.append(get_analog_intro())

                for i, analog in enumerate(analogs, 1):
                    brand_analog = analog.get("brand", "Кометта")
                    analog_model = analog.get("model", "")
                    articul = analog.get("articul", "не указан")

                    if (
                        not analog_model
                        or analog_model.strip() == ""
                        or analog_model.lower() in ["nan", "none", "не указана"]
                        or str(analog_model).startswith("Артикул ")
                    ):
                        analog_name = brand_analog
                    else:
                        analog_name = f"{brand_analog} {analog_model.strip()}"

                    res.response_parts.append(f"\n{i}. {analog_name}")
                    res.response_parts.append(f"   Артикул: {articul}")
                    if analog.get("power", 0) > 0:
                        res.response_parts.append(f"   Мощность: {analog['power']} кВт")
                    res.response_parts.append(f"   Отклонение кривой: {analog['rmse']:.2f} м")
                    datasheet_url = analog.get("datasheet_url")
                    if datasheet_url and isinstance(datasheet_url, str) and datasheet_url.strip():
                        # Проверяем, что URL начинается с http:// или https://
                        if datasheet_url.startswith(('http://', 'https://')):
                            res.response_parts.append(f"   📄 [Лист данных]({datasheet_url})")
                        elif datasheet_url.startswith('/'):
                            # Относительный URL - добавляем базовый домен
                            base_url = "https://kometta.ru"
                            res.response_parts.append(f"   📄 [Лист данных]({base_url}{datasheet_url})")
                    else:
                        res.response_parts.append(f"   📄 Лист данных: не доступен")

                res.response_parts.append(get_analog_graph_offer())
                res.response_parts.append(get_analog_graph_instruction())
                return res

            if is_negative:
                update_state(chat_id, {"pending_analog_confirmation": None})
                res.response_parts.append(get_analog_wrong_model())
                return res

            # Непонятный ответ - проверяем, может быть это новая модель?
            from services.intents import detect_model_name, extract_brand_and_model
            new_model = detect_model_name(message)
            if new_model:
                brand_model = extract_brand_and_model(message)
                confirmation_data = {
                    "model": new_model,
                    "brand": brand_model.get("brand"),
                    "model_only": brand_model.get("model"),
                }
                update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
                res.immediate_response = get_analog_confirmation(new_model)
                return res

            res.immediate_response = get_analog_confirmation(pending_confirmation.get('model', 'неизвестная модель'))
            return res

        # Проверяем, это запрос по бренду?
        if data.get("action") == "by_brand":
            brand = data.get("brand", "")
            if brand:
                from services.data_loader import load_competitors_data

                df_comp = load_competitors_data()
                brand_matches = df_comp[df_comp["brand"].astype(str).str.upper() == brand.upper()]
                if brand_matches.empty:
                    res.response_parts.append(get_analog_brand_not_found(brand))
                    return res

                first_row = brand_matches.iloc[0]
                model = f"{first_row.get('brand', '')} {first_row.get('model', '')}".strip()
                if model:
                    competitor_data, analogs = find_analog_by_model(model, top_n=3)
                    if competitor_data and analogs:
                        res.response_parts.append(f"Нашёл модели бренда {brand} в базе конкурентов.")
                        res.response_parts.append(f"\nАналоги Кометта:\n")
                        for i, analog in enumerate(analogs, 1):
                            brand_analog = analog.get("brand", "Кометта")
                            analog_model = analog.get("model", "")
                            if (
                                not analog_model
                                or analog_model.strip() == ""
                                or analog_model.lower() in ["nan", "none", "не указана"]
                                or str(analog_model).startswith("Артикул ")
                            ):
                                analog_name = brand_analog
                            else:
                                analog_name = f"{brand_analog} {analog_model.strip()}"
                            res.response_parts.append(f"{i}. {analog_name}")
                            res.response_parts.append(f"   Артикул: {analog.get('articul', 'не указан')}")
                            if analog.get("power", 0) > 0:
                                res.response_parts.append(f"   Мощность: {analog['power']} кВт")
                            res.response_parts.append(f"   Отклонение: {analog['rmse']:.2f} м")
                    else:
                        res.response_parts.append(get_analog_brand_no_analogs(brand))
                else:
                    res.response_parts.append(get_analog_brand_no_model(brand))
            else:
                res.response_parts.append(get_analog_no_brand())
            return res

        # Новый запрос на поиск аналога - показываем подтверждение
        model = data.get("model")
        brand = data.get("brand")
        model_only = data.get("model_only")

        if not model:
            res.response_parts.append(get_analog_no_model())
            return res

        confirmation_data = {"model": model, "brand": brand, "model_only": model_only}
        update_state(chat_id, {"pending_analog_confirmation": confirmation_data})
        res.immediate_response = get_analog_confirmation(model)
        return res

    except Exception as e:
        from services.error_handler import log_error

        log_error(e, "dialog_handlers.analog_by_model:handle_analog_by_model", context={"data": data}, session_id=chat_id)
        res.response_parts.append(get_error_message_generic())
        return res

