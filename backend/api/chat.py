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
from services.intents import detect_intent, Intent, extract_qh_from_text
from services.selector import select_by_working_point, find_analog_by_model
from services.file_extractors import process_file
from services.data_loader import load_kometta_data
from services.text_normalize import normalize_user_text
import os

router = APIRouter()


class Attachment(BaseModel):
    filename: str
    content_type: str
    base64: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    attachments: List[Attachment] = []


def generate_komettik_response(intent: str, data: Dict[str, Any], message: str, attachments: List[Attachment], session_id: str = "default") -> str:
    """
    Генерирует ответ Кометтика на основе интента.
    
    Args:
        intent: тип интента
        data: дополнительные данные
        message: сообщение пользователя
        attachments: вложения
        session_id: ID сессии для сохранения контекста
    """
    try:
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
            q = data.get("q")
            h = data.get("h")
            
            if not q or not h:
                response_parts.append(
                    "Для подбора насоса мне нужны параметры рабочей точки:\n"
                    "• Расход (Q) в м³/ч\n"
                    "• Напор (H) в метрах\n\n"
                    "Укажите их, например: Q=10, H=20 или расход 10 м³/ч, напор 20 м"
                )
            else:
                # Вариантивные фразы для начала ответа
                intro_phrases = [
                    f"Подбираю насосы для рабочей точки: Q = {q} м³/ч, H = {h} м...\n",
                    f"Ищу подходящие насосы по параметрам: Q = {q} м³/ч, H = {h} м...\n",
                    f"Анализирую рабочую точку Q = {q} м³/ч, H = {h} м и подбираю варианты...\n",
                    f"Подбираю оптимальные насосы для Q = {q} м³/ч и H = {h} м...\n"
                ]
                response_parts.append(random.choice(intro_phrases))
                
                pumps = select_by_working_point(q, h, top_n=3)
                
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
                        # Формируем название: brand + model (если model не пустая)
                        brand = pump.get('brand', 'Кометта')
                        model = pump.get('model', '')
                        articul = pump.get('articul', 'не указан')
                        
                        # Очищаем model от пустых значений и "Артикул ..."
                        if not model or model.strip() == "" or model.lower() in ["nan", "none", "не указана"] or model.startswith("Артикул "):
                            pump_name = brand
                        else:
                            # Убираем лишние пробелы из model
                            model_clean = model.strip()
                            pump_name = f"{brand} {model_clean}"
                        
                        response_parts.append(f"\n{i}. {pump_name}")
                        response_parts.append(f"   Артикул: {articul}")
                        if pump.get('power', 0) > 0:
                            response_parts.append(f"   Мощность: {pump['power']} кВт")
                        response_parts.append(f"   Рабочая точка: Q = {pump['q_work']:.2f} м³/ч, H = {pump['h_work']:.2f} м")
                        # ИСПРАВЛЕНО: Показываем относительное отклонение в процентах
                        if pump.get('relative_error_percent') is not None:
                            response_parts.append(f"   Отклонение: {pump['error']:.2f} м ({pump['relative_error_percent']:.1f}%)")
                        else:
                            response_parts.append(f"   Отклонение: {pump['error']:.2f} м")
                        # Ссылка на лист данных в формате Markdown
                        if pump.get('datasheet_url'):
                            response_parts.append(f"   📄 [Лист данных]({pump['datasheet_url']})")
                        else:
                            response_parts.append(f"   📄 Лист данных: не доступен")
                    
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
                            "• Сравнить несколько насосов на одном графике"
                        ],
                        [
                            "• Дополнить информацию о параметрах жидкости",
                            "• Показать график характеристики насоса",
                            "• Сравнить характеристики нескольких насосов"
                        ],
                        [
                            "• Указать параметры перекачиваемой жидкости",
                            "• Построить кривую насоса",
                            "• Сравнить насосы визуально на графике"
                        ],
                        [
                            "• Уточнить свойства жидкости",
                            "• Визуализировать кривую насоса",
                            "• Сопоставить несколько вариантов на графике"
                        ]
                    ]
                    response_parts.extend(random.choice(suggestions_variants))
        
        elif intent == Intent.ANALOG_BY_MODEL:
            # Проверяем, это запрос по бренду?
            if data.get("action") == "by_brand":
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
                model = data.get("model")
                
                if not model:
                    no_model_phrases = [
                        "Укажите модель насоса конкурента, например: CNP CDMF 1-3",
                        "Пожалуйста, укажите модель насоса конкурента (например: CNP CDMF 1-3)",
                        "Для поиска аналога нужна модель насоса конкурента, например: CNP CDMF 1-3"
                    ]
                    response_parts.append(random.choice(no_model_phrases))
                else:
                    search_phrases = [
                        f"Ищу аналог для модели {model}...\n",
                        f"Ищу подходящий аналог Кометта для {model}...\n",
                        f"Анализирую модель {model} и подбираю аналоги...\n"
                    ]
                    response_parts.append(random.choice(search_phrases))
                    
                    competitor_data, analogs = find_analog_by_model(model, top_n=3)
                    
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
                            brand = analog.get('brand', 'Кометта')
                            analog_model = analog.get('model', '')
                            articul = analog.get('articul', 'не указан')
                            
                            # Очищаем model от пустых значений и "Артикул ..."
                            if not analog_model or analog_model.strip() == "" or analog_model.lower() in ["nan", "none", "не указана"] or analog_model.startswith("Артикул "):
                                analog_name = brand
                            else:
                                # Убираем лишние пробелы из model
                                analog_model_clean = analog_model.strip()
                                analog_name = f"{brand} {analog_model_clean}"
                            
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
        
        elif intent == Intent.FILE_UPLOAD:
            if not attachments:
                response_parts.append("Прикрепите файл (PDF или изображение), и я попробую извлечь данные.")
            else:
                response_parts.append("Обрабатываю файл...\n")
                
                extracted_data = None
                for attachment in attachments:
                    result = process_file(
                        attachment.filename,
                        attachment.content_type,
                        attachment.base64
                    )
                    
                    if result.get("success"):
                        extracted_data = result
                        break
                
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
            # Запрос по типу насоса (циркуляционный, погружной, моноблочный и т.д.)
            pump_type_info = data.get("pump_type_info", {})
            
            if pump_type_info:
                # Используем функцию генерации ответа из модуля pump_types
                from services.pump_types import generate_type_response, PumpTypeAvailability
                
                type_response = generate_type_response(pump_type_info)
                response_parts.append(type_response)
                
                # Если тип есть у Кометта и есть Q/H в сообщении, сразу подбираем
                if pump_type_info.get("availability") == PumpTypeAvailability.AVAILABLE:
                    qh_data = extract_qh_from_text(message)
                    if qh_data:
                        q = qh_data.get("q")
                        h = qh_data.get("h")
                        if q and h:
                            response_parts.append(f"\n\n---\n\n**Подбор по рабочей точке Q = {q} м³/ч, H = {h} м:**\n")
                            
                            # Фильтруем по серии, если известна
                            series_list = pump_type_info.get("series", [])
                            pumps = select_by_working_point(q, h)
                            
                            if series_list:
                                # Фильтруем по серии
                                filtered_pumps = [p for p in pumps if any(s in p.get("model", "") or s in p.get("series", "") for s in series_list)]
                                if filtered_pumps:
                                    pumps = filtered_pumps
                            
                            if pumps:
                                for i, pump in enumerate(pumps[:3], 1):
                                    pump_name = pump.get("model", pump.get("articul", ""))
                                    brand = pump.get("brand", "Кометта")
                                    if pump_name and pump_name != pump.get("articul"):
                                        response_parts.append(f"\n**{i}. {brand} {pump_name}**")
                                    else:
                                        response_parts.append(f"\n**{i}. {brand}**")
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
        
        elif intent == Intent.MATERIALS_QUERY:
            # Запрос о материалах исполнения для жидкости (с "живым" диалоговым поведением)
            category = data.get("category", "unknown")
            has_abrasive = data.get("has_abrasive")
            temp_c = data.get("temp_c")
            liquid_description = data.get("description", "")
            
            # Используем диалоговый поток для генерации "живого" ответа
            from services.dialog_flow import generate_materials_response_with_dialog
            
            materials_response = generate_materials_response_with_dialog(
                session_id=session_id,
                liquid_text=liquid_description or message,
                category=category if category != "unknown" else None,
                has_abrasive=has_abrasive,
                temp_c=temp_c
            )
            response_parts.append(materials_response)
        
        elif intent == Intent.TECH_QA:
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
        
        # Добавляем уточняющие вопросы в конце (только если их ещё не добавили)
        # Уточняющие вопросы уже добавлены в блоках SELECTION_BY_POINT, ANALOG_BY_MODEL, DIAGNOSTICS, PUMP_TYPE, MATERIALS_QUERY, TECH_QA
        if intent not in [Intent.OFF_TOPIC, Intent.SELECTION_BY_POINT, Intent.ANALOG_BY_MODEL, Intent.DIAGNOSTICS, Intent.PUMP_TYPE, Intent.MATERIALS_QUERY, Intent.TECH_QA]:
            response_parts.append("\n\nЧто ещё могу помочь?")
            response_parts.append("• Подобрать другой насос")
            response_parts.append("• Найти аналог")
            response_parts.append("• Построить график кривой")
        
        return "\n".join(response_parts)
    except Exception as e:
        # Логируем ошибку
        import traceback
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:generate_komettik_response",
                    "message": "ERROR in generate_komettik_response",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "intent": intent,
                    "runId": "error",
                    "hypothesisId": "ERROR"
                }) + "\n")
        except:
            pass
        
        # Возвращаем информативное сообщение об ошибке
        return (
            "Извините, произошла ошибка при обработке вашего запроса. "
            "Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
        )


async def stream_response(text: str):
    """
    Потоковая передача ответа (SSE).
    """
    words = text.split(" ")
    
    for i, word in enumerate(words):
        if i > 0:
            yield f"data: {json.dumps({'type': 'token', 'content': ' '})}\n\n"
            await asyncio.sleep(0.05)  # Небольшая задержка между словами
        
        yield f"data: {json.dumps({'type': 'token', 'content': word})}\n\n"
        await asyncio.sleep(0.1)  # Задержка для эффекта печатания
    
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint для чата с Кометтиком.
    Возвращает потоковый ответ (SSE).
    """
    # #region agent log
    import json
    import os
    from datetime import datetime
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "chat.py:268",
                "message": "Chat endpoint called",
                "data": {
                    "session_id": request.session_id,
                    "message": request.message[:100],
                    "has_attachments": len(request.attachments) > 0
                },
                "sessionId": request.session_id,
                "runId": "analysis",
                "hypothesisId": "A"
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
        intent_result = detect_intent(normalized_message, has_attachments)
        
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:285",
                    "message": "Intent detected",
                    "data": {
                        "intent": intent_result["intent"],
                        "extracted_data": intent_result["data"]
                    },
                    "sessionId": request.session_id,
                    "runId": "analysis",
                    "hypothesisId": "A,B"
                }) + "\n")
        except: pass
        # #endregion
        
        # Генерируем ответ
        response_text = generate_komettik_response(
            intent_result["intent"],
            intent_result["data"],
            normalized_message,  # Используем нормализованное сообщение
            request.attachments,
            session_id=request.session_id  # Передаём session_id для сохранения контекста
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
        # Логируем ошибку для отладки
        import traceback
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:chat_endpoint",
                    "message": "ERROR in chat endpoint",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "sessionId": request.session_id if 'request' in locals() else "unknown",
                    "runId": "error",
                    "hypothesisId": "ERROR"
                }) + "\n")
        except:
            pass
        
        # Возвращаем информативное сообщение об ошибке
        error_message = f"Произошла ошибка при обработке запроса. Пожалуйста, попробуйте ещё раз или обратитесь к администратору."
        
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

