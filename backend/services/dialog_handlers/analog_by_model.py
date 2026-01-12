from typing import Any, Dict
import random

from services.dialog_handlers.types import HandlerResult
from services.conversation_state import update_state
from services.selector import find_analog_by_model


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
                f"Вы ищете аналог насоса {new_model_in_message} — верно?",
            ]
            res.immediate_response = random.choice(confirmation_phrases)
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

                # Очищаем ожидание подтверждения
                update_state(chat_id, {"pending_analog_confirmation": None})

                search_phrases = [
                    f"Ищу аналог для модели {model}...\n",
                    f"Ищу подходящий аналог Кометта для {model}...\n",
                    f"Анализирую модель {model} и подбираю аналоги...\n",
                ]
                res.response_parts.append(random.choice(search_phrases))

                # Если есть только модель без бренда, ищем по модели
                if not brand and model_only:
                    competitor_data, analogs = find_analog_by_model(model_only, top_n=3)
                else:
                    competitor_data, analogs = find_analog_by_model(model, top_n=3)

                if competitor_data is None:
                    not_found_phrases = [
                        f"Не нашёл модель {model} в базе конкурентов. Попробуйте указать точное название модели или подберите насос по рабочей точке.",
                        f"Модель {model} отсутствует в базе конкурентов. Укажите точное название или используйте подбор по рабочей точке.",
                        f"В базе конкурентов нет модели {model}. Попробуйте указать точное название или подобрать насос по параметрам Q и H.",
                    ]
                    res.response_parts.append(random.choice(not_found_phrases))
                    return res

                if not analogs:
                    no_analogs_phrases = [
                        f"Нашёл модель {model}, но не нашёл подходящих аналогов Кометта. Попробуйте подобрать насос по рабочей точке.",
                        f"Модель {model} найдена, но подходящих аналогов Кометта нет. Рекомендую подобрать насос по параметрам Q и H.",
                        f"Для модели {model} не удалось найти аналоги Кометта. Попробуйте подобрать насос по рабочей точке.",
                    ]
                    res.response_parts.append(random.choice(no_analogs_phrases))
                    return res

                found_phrases = [
                    f"Нашёл модель конкурента: {competitor_data['brand']} {competitor_data['model']}",
                    f"Модель найдена: {competitor_data['brand']} {competitor_data['model']}",
                    f"Обнаружена модель: {competitor_data['brand']} {competitor_data['model']}",
                ]
                res.response_parts.append(random.choice(found_phrases))

                analog_intro_phrases = [
                    f"\nПодходящие аналоги Кометта:\n",
                    f"\nРекомендую следующие аналоги Кометта:\n",
                    f"\nНайдены следующие аналоги Кометта:\n",
                ]
                res.response_parts.append(random.choice(analog_intro_phrases))

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
                    if analog.get("datasheet_url"):
                        res.response_parts.append(f"   📄 [Лист данных]({analog['datasheet_url']})")
                    else:
                        res.response_parts.append(f"   📄 Лист данных: не доступен")

                graph_offer_phrases = [
                    "\n\nМогу построить две кривые на одном графике для сравнения — хотите?",
                    "\n\nХотите сравнить кривые визуально? Могу построить график с кривыми обоих насосов.",
                    "\n\nМогу визуализировать сравнение кривых на одном графике — интересно?",
                ]
                res.response_parts.append(random.choice(graph_offer_phrases))

                graph_instruction_phrases = [
                    "Просто напишите: 'Построй график сравнения' или укажите артикул насоса Кометта.",
                    "Напишите 'Построй график' или укажите артикул насоса Кометта для сравнения.",
                    "Укажите артикул насоса Кометта или напишите 'Построй график' для визуализации.",
                ]
                res.response_parts.append(random.choice(graph_instruction_phrases))
                return res

            if is_negative:
                update_state(chat_id, {"pending_analog_confirmation": None})
                res.response_parts.append(
                    "Понял. Пожалуйста, укажите правильную модель насоса конкурента, например: CNP CDM 1-3"
                )
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
                    f"Вы ищете аналог насоса {new_model} — верно?",
                ]
                res.immediate_response = random.choice(confirmation_phrases)
                return res

            confirmation_phrases = [
                f"Я правильно понял, что вам нужен аналог насоса {pending_confirmation.get('model', 'неизвестная модель')}?",
                f"Правильно ли я понял, что вы ищете аналог для насоса {pending_confirmation.get('model', 'неизвестная модель')}?",
                f"Вы хотите найти аналог насоса {pending_confirmation.get('model', 'неизвестная модель')}?",
            ]
            res.immediate_response = random.choice(confirmation_phrases)
            return res

        # Проверяем, это запрос по бренду?
        if data.get("action") == "by_brand":
            brand = data.get("brand", "")
            if brand:
                from services.data_loader import load_competitors_data

                df_comp = load_competitors_data()
                brand_matches = df_comp[df_comp["brand"].astype(str).str.upper() == brand.upper()]
                if brand_matches.empty:
                    res.response_parts.append(f"Не нашёл насосов бренда {brand} в базе конкурентов.")
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
                        res.response_parts.append(f"Нашёл модели бренда {brand}, но не нашёл подходящих аналогов Кометта.")
                else:
                    res.response_parts.append(f"Не удалось определить модель для бренда {brand}.")
            else:
                res.response_parts.append("Укажите бренд насоса конкурента.")
            return res

        # Новый запрос на поиск аналога - показываем подтверждение
        model = data.get("model")
        brand = data.get("brand")
        model_only = data.get("model_only")

        if not model:
            no_model_phrases = [
                "Укажите модель насоса конкурента, например: CNP CDMF 1-3",
                "Пожалуйста, укажите модель насоса конкурента (например: CNP CDMF 1-3)",
                "Для поиска аналога нужна модель насоса конкурента, например: CNP CDMF 1-3",
            ]
            res.response_parts.append(random.choice(no_model_phrases))
            return res

        confirmation_data = {"model": model, "brand": brand, "model_only": model_only}
        update_state(chat_id, {"pending_analog_confirmation": confirmation_data})

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
            f"Вы ищете аналог насоса {model} — верно?",
        ]
        res.immediate_response = random.choice(confirmation_phrases)
        return res

    except Exception as e:
        from services.error_handler import log_error

        log_error(e, "chat.py:generate_komettik_response:ANALOG_BY_MODEL", context={"data": data}, session_id=chat_id)
        res.response_parts.append(
            "Извините, произошла ошибка при поиске аналогов. "
            "Пожалуйста, попробуйте ещё раз или обратитесь к администратору."
        )
        return res

