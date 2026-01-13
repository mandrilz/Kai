"""
Обработчик интента DOCUMENTATION - работа с документацией насосов.
"""
from typing import Dict, Any, Optional, List
import re
import numpy as np
from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import (
    get_documentation_by_model_prompt,
    get_documentation_not_found,
    get_documentation_pump_info,
    get_documentation_plot_suggestion,
    get_documentation_body_material_prompt,
    get_documentation_body_material_result,
    get_documentation_body_material_unknown,
    get_documentation_articul_prompt,
    get_documentation_compare_prompt,
    get_documentation_plot_prompt,
    get_documentation_generic,
)


def handle_documentation(
    *,
    message: str,
    data: Dict[str, Any],
) -> HandlerResult:
    """
    Обрабатывает запросы на документацию насосов.
    
    Args:
        message: Текст сообщения пользователя
        data: Извлеченные данные из сообщения (intent detection)
    
    Returns:
        HandlerResult с частями ответа
    """
    result = HandlerResult()
    action = data.get("action", "")
    
    # Поиск информации о насосе по модели
    if action == "by_model":
        model_text = data.get("model", "")
        if not model_text:
            result.response_parts.append(get_documentation_by_model_prompt())
            return result
        
        from services.selector import get_pump_curve_data_by_model
        pump_data = get_pump_curve_data_by_model(model_text)
        
        if pump_data:
            model = pump_data.get("model", model_text)
            articul = pump_data.get("articul", "не указан")
            series = pump_data.get("series", "не указана")
            power = pump_data.get("power", 0)
            datasheet_url = pump_data.get("datasheet_url", "")
            
            info_parts = get_documentation_pump_info(model, series, articul, power, datasheet_url)
            result.response_parts.extend(info_parts)
            
            # Проверяем наличие точек кривой
            q_points = pump_data.get("q_points", [])
            h_points = pump_data.get("h_points", [])
            if len(q_points) >= 3 and len(h_points) >= 3:
                result.response_parts.append(get_documentation_plot_suggestion())
        else:
            result.response_parts.append(get_documentation_not_found(model_text))
        
        return result
    
    # Материал корпуса насоса
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
                result.response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
                return result
        
        if not model_text:
            result.response_parts.append(get_documentation_body_material_prompt())
            return result
        
        code = extract_body_material_code_from_model(model_text)
        mat = describe_body_material(code)
        
        if code and mat:
            material_parts = get_documentation_body_material_result(model_text, mat, code)
            result.response_parts.extend(material_parts)
        else:
            unknown_parts = get_documentation_body_material_unknown(model_text)
            result.response_parts.extend(unknown_parts)
        
        return result
    
    # Аналоги по артикулу Кометта
    if action == "analog_by_articul":
        articul = data.get("articul", "")
        if articul:
            _handle_analog_by_articul(result, articul)
        else:
            result.response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
        return result
    
    # Запрос по артикулу
    if action == "by_articul":
        articul = data.get("articul", "")
        if articul:
            _handle_by_articul(result, articul)
        else:
            result.response_parts.append(get_documentation_articul_prompt())
        return result
    
    # Сравнение двух насосов
    if action == "compare":
        articul1 = data.get("articul1", "")
        articul2 = data.get("articul2", "")
        if articul1 and articul2:
            _handle_compare(result, articul1, articul2)
        else:
            result.response_parts.append(get_documentation_compare_prompt())
        return result
    
    # Построение графика
    if action == "plot":
        articul_match = re.search(r'\d{6,12}', message)
        if articul_match:
            articul = articul_match.group()
            _handle_plot(result, articul)
        else:
            result.response_parts.append(get_documentation_plot_prompt())
        return result
    
    # Общий запрос
    result.response_parts.append(get_documentation_generic())
    return result


def _handle_analog_by_articul(result: HandlerResult, articul: str):
    """Обработка поиска аналогов по артикулу Кометта."""
    from services.selector import get_pump_curve_data
    from services.curve_math import approximate_curve, calculate_h
    from services.data_loader import load_competitors_data
    
    pump_data = get_pump_curve_data(articul)
    if not pump_data:
        result.response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
        return
    
    q_points = pump_data.get('q_points', [])
    h_points = pump_data.get('h_points', [])
    
    if len(q_points) < 3:
        result.response_parts.append(f"Нашёл насос: {pump_data.get('model', f'Артикул {articul}')}")
        result.response_parts.append(f"Артикул: {articul}")
        result.response_parts.append("\nНедостаточно данных кривой для поиска аналогов.")
        return
    
    coeffs_kometta = approximate_curve(q_points, h_points)
    if coeffs_kometta is None:
        result.response_parts.append(f"Нашёл насос Кометта: {pump_data.get('model', f'Артикул {articul}')}")
        result.response_parts.append(f"Артикул: {articul}")
        result.response_parts.append("\nНедостаточно данных кривой для поиска аналогов.")
        return
    
    a_kometta, b_kometta, c_kometta, d_kometta = coeffs_kometta
    df_comp = load_competitors_data()
    analogs = []
    
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
            
            q_min = min(min(q_points), min(q_comp))
            q_max = max(max(q_points), max(q_comp))
            q_test = np.linspace(q_min, q_max, 20)
            h_comp_test = [calculate_h(q, a_comp, b_comp, c_comp, d_comp) for q in q_test]
            h_kometta_test = [calculate_h(q, a_kometta, b_kometta, c_kometta, d_kometta) for q in q_test]
            
            errors = [(h_c - h_k) ** 2 for h_c, h_k in zip(h_comp_test, h_kometta_test)]
            rmse = np.sqrt(np.mean(errors))
            
            if rmse > 50:
                continue
            
            import pandas as pd
            def safe_str(value, default=""):
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
    
    result.response_parts.append(f"Нашёл насос Кометта: {pump_data.get('model', f'Артикул {articul}')}")
    result.response_parts.append(f"Артикул: {articul}")
    
    if analogs:
        result.response_parts.append(f"\nАналоги среди конкурентов:\n")
        for i, analog in enumerate(analogs, 1):
            result.response_parts.append(f"{i}. {analog['brand']} {analog['model']} (отклонение: {analog['rmse']:.2f} м)")
    else:
        result.response_parts.append("\nНе нашёл подходящих аналогов среди конкурентов.")


def _handle_by_articul(result: HandlerResult, articul: str):
    """Обработка запроса по артикулу."""
    from services.selector import get_pump_curve_data
    
    pump_data = get_pump_curve_data(articul)
    if pump_data:
        model_name = pump_data.get('model', f"Артикул {articul}")
        result.response_parts.append(f"Нашёл насос: {model_name}")
        if pump_data.get('series'):
            result.response_parts.append(f"Серия: {pump_data['series']}")
        result.response_parts.append(f"Артикул: {articul}")
        if pump_data.get('power', 0) > 0:
            result.response_parts.append(f"Мощность: {pump_data['power']} кВт")
        datasheet_url = pump_data.get('datasheet_url')
        if datasheet_url and isinstance(datasheet_url, str) and datasheet_url.strip():
            # Проверяем, что URL начинается с http:// или https://
            if datasheet_url.startswith(('http://', 'https://')):
                result.response_parts.append(f"\n📄 [Лист данных]({datasheet_url})")
            elif datasheet_url.startswith('/'):
                # Относительный URL - добавляем базовый домен
                base_url = "https://kometta.ru"
                result.response_parts.append(f"\n📄 [Лист данных]({base_url}{datasheet_url})")
        result.response_parts.append("\nМогу построить график кривой этого насоса — хотите?")
    else:
        result.response_parts.append(f"Насос с артикулом {articul} не найден в базе.")


def _handle_compare(result: HandlerResult, articul1: str, articul2: str):
    """Обработка сравнения двух насосов."""
    from services.selector import get_pump_curve_data
    
    pump1 = get_pump_curve_data(articul1)
    pump2 = get_pump_curve_data(articul2)
    
    if pump1 and pump2:
        model1 = pump1.get('model', f"Артикул {articul1}")
        model2 = pump2.get('model', f"Артикул {articul2}")
        result.response_parts.append(f"Сравниваю насосы:\n")
        result.response_parts.append(f"1. {model1} (артикул: {articul1})")
        result.response_parts.append(f"2. {model2} (артикул: {articul2})")
        result.response_parts.append(f"\nГрафик сравнения можно построить через API:")
        result.response_parts.append(f"/api/plot/compare?kometta_articul={articul1}&competitor_articul={articul2}")
        result.response_parts.append("\n\nИли напишите 'Построй график сравнения' для визуализации.")
    elif pump1:
        result.response_parts.append(f"Нашёл первый насос: {pump1.get('model', f'Артикул {articul1}')}")
        result.response_parts.append(f"Второй насос с артикулом {articul2} не найден в базе Кометта.")
    elif pump2:
        result.response_parts.append(f"Нашёл второй насос: {pump2.get('model', f'Артикул {articul2}')}")
        result.response_parts.append(f"Первый насос с артикулом {articul1} не найден в базе Кометта.")
    else:
        result.response_parts.append(f"Оба насоса не найдены в базе Кометта.")
        result.response_parts.append(f"Проверьте правильность артикулов: {articul1} и {articul2}")


def _handle_plot(result: HandlerResult, articul: str):
    """Обработка запроса на построение графика."""
    from services.selector import get_pump_curve_data
    
    pump_data = get_pump_curve_data(articul)
    if pump_data:
        model_name = pump_data.get('model', f"Артикул {articul}")
        result.response_parts.append(f"Нашёл насос: {model_name}")
        result.response_parts.append(f"Артикул: {articul}")
        if pump_data.get('power', 0) > 0:
            result.response_parts.append(f"Мощность: {pump_data['power']} кВт")
        datasheet_url = pump_data.get('datasheet_url')
        if datasheet_url and isinstance(datasheet_url, str) and datasheet_url.strip():
            # Проверяем, что URL начинается с http:// или https://
            if datasheet_url.startswith(('http://', 'https://')):
                result.response_parts.append(f"\n📄 [Лист данных]({datasheet_url})")
            elif datasheet_url.startswith('/'):
                # Относительный URL - добавляем базовый домен
                base_url = "https://kometta.ru"
                result.response_parts.append(f"\n📄 [Лист данных]({base_url}{datasheet_url})")
        result.response_parts.append(f"\nГрафик кривой можно построить через API:")
        result.response_parts.append(f"/api/plot/compare?kometta_articul={articul}")
        result.response_parts.append("\nИли укажите артикул насоса конкурента для сравнения.")
    else:
        result.response_parts.append(f"Насос с артикулом {articul} не найден в базе Кометта.")
        result.response_parts.append("Проверьте правильность артикула.")
