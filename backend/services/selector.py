"""
Подбор насосов по рабочей точке и поиск аналогов.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from services.data_loader import load_kometta_data, load_competitors_data
from services.curve_math import (
    approximate_curve,
    calculate_h,
    calculate_rmse,
    extract_curve_points
)


def select_by_working_point(q: float, h: float, top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Подбирает насосы Кометта по рабочей точке.
    
    ВАЖНО: 
    - Параметр q должен быть в м³/ч! Все единицы расхода должны быть пересчитаны в м³/ч ДО вызова этой функции.
    - Параметр h должен быть в метрах! Все единицы напора (бар, кПа, МПа и т.д.) должны быть пересчитаны в метры ДО вызова этой функции.
    База данных насосов использует м³/ч для расхода и метры для напора.
    
    Args:
        q: расход в м³/ч (обязательно!)
        h: напор в метрах (обязательно!)
        top_n: количество лучших вариантов
        
    Returns:
        список словарей с данными насосов, отсортированный по ошибке
    """
    # Валидация: проверяем, что q в разумных пределах для м³/ч
    if q < 0.01 or q > 5000:
        # Логируем предупреждение, но продолжаем работу
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selector.py:select_by_working_point",
                    "message": "WARNING: Q value out of expected range for m3/h",
                    "data": {"q": q, "h": h, "expected_range": "0.01-5000 m3/h"},
                    "sessionId": "validation",
                    "runId": "validation",
                    "hypothesisId": "WARNING"
                }) + "\n")
        except: pass
    
    # Валидация: проверяем, что h в разумных пределах для метров
    if h < 0.5 or h > 500:
        # Логируем предупреждение, но продолжаем работу
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selector.py:select_by_working_point",
                    "message": "WARNING: H value out of expected range for meters",
                    "data": {"q": q, "h": h, "expected_range": "0.5-500 m"},
                    "sessionId": "validation",
                    "runId": "validation",
                    "hypothesisId": "WARNING"
                }) + "\n")
        except: pass
    df = load_kometta_data()
    results = []
    
    for idx, row in df.iterrows():
        # Извлекаем точки кривой
        q_points, h_points = extract_curve_points(row)
        
        if len(q_points) < 3:
            continue  # Слишком мало точек
        
        # Аппроксимируем кривую
        try:
            coeffs = approximate_curve(q_points, h_points)
            if coeffs is None:
                continue
            a, b, c, d = coeffs
            
            # Находим точку на кривой насоса, ближайшую к рабочей точке (Q, H)
            # Вариант 1: Найти Q на кривой, где H = желаемый H
            from services.curve_math import get_q_for_h
            q_min_curve = min(q_points) if q_points else 0
            q_max_curve = max(q_points) if q_points else 10000
            q_at_h = get_q_for_h(h, a, b, c, d, q_min_curve, q_max_curve)
            
            # Вариант 2: Найти H на кривой при заданном Q
            h_at_q = calculate_h(q, a, b, c, d)
            
            # Выбираем лучший вариант (минимальная ошибка)
            # Ошибка = взвешенное расстояние до рабочей точки
            # Используем веса: w_q = 1, w_h = 10 (напор важнее расхода)
            if q_at_h > 0:
                # Нашли Q на кривой для нужного H
                error_q = abs(q_at_h - q) / max(q, 1)  # Относительная ошибка по Q
                error_h = 0  # H точно совпадает
                error = error_q * 1 + error_h * 10
                q_work = q_at_h
                h_work = h
            else:
                # Не нашли Q для нужного H, используем H при заданном Q
                error_q = 0  # Q точно совпадает
                error_h = abs(h_at_q - h) / max(h, 1)  # Относительная ошибка по H
                error = error_q * 1 + error_h * 10
                q_work = q
                h_work = h_at_q
            
            # ИСПРАВЛЕНО: Более строгий порог фильтрации
            # error - это взвешенная относительная ошибка (error_q * 1 + error_h * 10)
            # error_h = 0.1 означает 10% относительного отклонения по напору
            # Порог 1.0 означает максимум 10% отклонения по напору (error_h <= 0.1)
            if h_work < 0 or error > 1.0:  # Ошибка не более 1.0 (10% относительного отклонения по напору)
                continue
            
            # Собираем данные насоса (проверяем на NaN)
            def safe_str(value, default=""):
                if pd.isna(value) or value is None:
                    return default
                val_str = str(value).strip()
                if val_str.lower() in ["nan", "none", ""]:
                    return default
                return val_str
            
            # #region agent log
            import json
            import os
            from datetime import datetime
            log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
            raw_articul = row.get("articul", "")
            raw_model = row.get("model", "")
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:53",
                        "message": "Processing pump data",
                        "data": {
                            "raw_articul": str(raw_articul),
                            "raw_model": str(raw_model),
                            "is_na_articul": pd.isna(raw_articul),
                            "is_na_model": pd.isna(raw_model)
                        },
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "C"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Используем артикул как fallback для model/series
            articul = safe_str(row.get("articul", ""), "")
            model_raw = safe_str(row.get("model", ""), "")
            series = safe_str(row.get("series", ""), "")
            
            # Очищаем model от "nan" и пустых значений
            # НЕ заменяем на "Артикул ..." здесь - это будет fallback в chat.py
            model = model_raw if model_raw and model_raw.lower() not in ["nan", "none", ""] else ""
            
            # Получаем URL для листа данных (только для Кометта)
            url = safe_str(row.get("url", ""), "")
            datasheet_url = ""
            if url:
                datasheet_url = url if url.endswith("?pdf=1") else f"{url}?pdf=1"
            
            # Вычисляем относительную ошибку в процентах для отображения
            relative_error_percent = (abs(h_work - h) / max(h, 1)) * 100
            
            pump_data = {
                "articul": articul if articul else "не указан",
                "model": model,
                "series": series if series else "не указана",
                "brand": safe_str(row.get("brand", ""), "Кометта"),
                "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
                "q_work": q_work,
                "h_work": h_work,
                "error": abs(h_work - h),  # Абсолютная ошибка по напору для отображения
                "relative_error_percent": relative_error_percent,  # Относительная ошибка в %
                "coefficients": {"a": a, "b": b, "c": c, "d": d},
                "url": url,
                "datasheet_url": datasheet_url
            }
            
            # #region agent log
            import json
            import os
            from datetime import datetime
            log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:75",
                        "message": "Pump data after processing",
                        "data": {
                            "articul": pump_data["articul"],
                            "model": pump_data["model"],
                            "series": pump_data["series"]
                        },
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "C"
                    }) + "\n")
            except: pass
            # #endregion
            
            results.append(pump_data)
        except Exception as e:
            # Пропускаем насосы с ошибками
            continue
    
    # Сортируем по ошибке (абсолютная ошибка по напору)
    results.sort(key=lambda x: x["error"])
    
    # Возвращаем топ-N
    return results[:top_n]


def find_competitor_model(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Ищет модель конкурента в базе.
    
    Args:
        model_name: название модели
        
    Returns:
        словарь с данными модели или None
    """
    df = load_competitors_data()
    model_upper = model_name.upper().strip()
    
    # Ищем точное совпадение в нормализованном поле
    if "model_normalized" in df.columns:
        matches = df[df["model_normalized"] == model_upper]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "model": str(row.get("model", "")),
                "brand": str(row.get("brand", "")),
                "series": str(row.get("series", "")),
                "row": row
            }
    
    # Ищем частичное совпадение
    if "model" in df.columns:
        matches = df[df["model"].str.upper().str.contains(model_upper, na=False, regex=False)]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "model": str(row.get("model", "")),
                "brand": str(row.get("brand", "")),
                "series": str(row.get("series", "")),
                "row": row
            }
    
    return None


def find_analog_by_model(competitor_model: str, top_n: int = 3) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Находит аналог насоса Кометта для модели конкурента.
    
    Args:
        competitor_model: название модели конкурента
        top_n: количество лучших аналогов
        
    Returns:
        (данные конкурента, список аналогов Кометта)
    """
    # Ищем модель конкурента
    competitor_data = find_competitor_model(competitor_model)
    
    if competitor_data is None:
        return None, []
    
    competitor_row = competitor_data["row"]
    
    # Извлекаем кривую конкурента
    q_comp, h_comp = extract_curve_points(competitor_row)
    
    if len(q_comp) < 3:
        return competitor_data, []
    
    # Аппроксимируем кривую конкурента
    coeffs_comp = approximate_curve(q_comp, h_comp)
    if coeffs_comp is None:
        return competitor_data, []
    a_comp, b_comp, c_comp, d_comp = coeffs_comp
    
    # Ищем аналоги в базе Кометта
    df_kometta = load_kometta_data()
    analogs = []
    
    for idx, row in df_kometta.iterrows():
        q_kometta, h_kometta = extract_curve_points(row)
        
        if len(q_kometta) < 3:
            continue
        
        # Аппроксимируем кривую Кометта
        try:
            coeffs_kometta = approximate_curve(q_kometta, h_kometta)
            if coeffs_kometta is None:
                continue
            a_kometta, b_kometta, c_kometta, d_kometta = coeffs_kometta
            
            # Вычисляем RMSE между кривыми
            # Используем общий диапазон Q
            q_min = max(min(q_comp), min(q_kometta))
            q_max = min(max(q_comp), max(q_kometta))
            
            if q_min >= q_max:
                continue
            
            # Генерируем точки для сравнения
            q_test = np.linspace(q_min, q_max, 20)
            h_comp_test = [calculate_h(q, a_comp, b_comp, c_comp, d_comp) for q in q_test]
            h_kometta_test = [calculate_h(q, a_kometta, b_kometta, c_kometta, d_kometta) for q in q_test]
            
            # Вычисляем RMSE
            errors = [(h_c - h_k) ** 2 for h_c, h_k in zip(h_comp_test, h_kometta_test)]
            rmse = np.sqrt(np.mean(errors))
            
            # Фильтруем слишком большие отклонения
            if rmse > 50:  # Максимальное отклонение 50 м
                continue
            
            # Используем артикул как fallback для model/series
            def safe_str(value, default=""):
                if pd.isna(value) or value is None:
                    return default
                val_str = str(value).strip()
                if val_str.lower() in ["nan", "none", ""]:
                    return default
                return val_str
            
            articul = safe_str(row.get("articul", ""), "")
            model_raw = safe_str(row.get("model", ""), "")
            series = safe_str(row.get("series", ""), "")
            
            # Очищаем model от "nan" и пустых значений
            # НЕ заменяем на "Артикул ..." здесь - это будет fallback в chat.py
            model = model_raw if model_raw and model_raw.lower() not in ["nan", "none", ""] else ""
            
            # Получаем URL для листа данных
            url = safe_str(row.get("url", ""), "")
            datasheet_url = ""
            if url:
                datasheet_url = url if url.endswith("?pdf=1") else f"{url}?pdf=1"
            
            analog_data = {
                "articul": articul if articul else "не указан",
                "model": model,
                "series": series if series else "не указана",
                "brand": safe_str(row.get("brand", ""), "Кометта"),
                "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
                "rmse": rmse,
                "url": url,
                "datasheet_url": datasheet_url,
                "coefficients": {
                    "a": a_kometta,
                    "b": b_kometta,
                    "c": c_kometta,
                    "d": d_kometta
                }
            }
            
            analogs.append(analog_data)
        except Exception:
            continue
    
    # Сортируем по RMSE
    analogs.sort(key=lambda x: x["rmse"])
    
    return competitor_data, analogs[:top_n]


def get_pump_curve_data(articul: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные кривой насоса по артикулу.
    
    Args:
        articul: артикул насоса (строка или число)
        
    Returns:
        словарь с данными кривой или None
    """
    df = load_kometta_data()
    
    # Приводим артикул к строке для сравнения
    articul_str = str(articul).strip()
    # Также пробуем как число (на случай если в базе число)
    try:
        articul_num = int(articul_str)
    except:
        articul_num = None
    
    # Ищем по строке или числу
    if articul_num is not None:
        matches = df[(df["articul"].astype(str) == articul_str) | (df["articul"] == articul_num)]
    else:
        matches = df[df["articul"].astype(str) == articul_str]
    
    if matches.empty:
        return None
    
    row = matches.iloc[0]
    q_points, h_points = extract_curve_points(row)
    
    if len(q_points) < 3:
        return None
    
    coeffs = approximate_curve(q_points, h_points)
    if coeffs is None:
        return None
    a, b, c, d = coeffs
    
    # Используем артикул как fallback для model/series
    def safe_str(value, default=""):
        if pd.isna(value) or value is None:
            return default
        val_str = str(value).strip()
        if val_str.lower() in ["nan", "none", ""]:
            return default
        return val_str
    
    articul = safe_str(row.get("articul", ""), "")
    model = safe_str(row.get("model", ""), "")
    series = safe_str(row.get("series", ""), "")
    
    # Если model пустая, используем артикул
    if not model or model == "не указана":
        model = f"Артикул {articul}" if articul else "не указана"
    
    # Получаем URL для листа данных
    url = safe_str(row.get("url", ""), "")
    datasheet_url = ""
    if url:
        datasheet_url = url if url.endswith("?pdf=1") else f"{url}?pdf=1"
    
    return {
        "articul": articul if articul else "не указан",
        "model": model,
        "series": series if series else "не указана",
        "brand": safe_str(row.get("brand", ""), "Кометта"),
        "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
        "q_points": q_points,
        "h_points": h_points,
        "url": url,
        "datasheet_url": datasheet_url,
        "coefficients": {"a": a, "b": b, "c": c, "d": d}
    }

