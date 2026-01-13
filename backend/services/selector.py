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
    extract_curve_points,  # Старая функция (для обратной совместимости)
    extract_points,  # Новая нормализованная функция
    choose_fit_points_4,  # Новая функция выбора 4 точек
    select_4_points,  # Старая функция (для обратной совместимости)
    calculate_network_coeffs,
    network_curve_func,
    find_operating_point
)


def select_by_working_point(q: float, h: float, h_st: float = 0.0, top_n: int = 3) -> List[Dict[str, Any]]:
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
    # Убеждаемся, что h_st не None (по умолчанию 0.0)
    if h_st is None:
        h_st = 0.0
    
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
        # ИСПРАВЛЕНО: Используем нормализованную функцию extract_points() для работы с форматами Kometta и Competitors
        # Определяем схему данных (Kometta или Competitors)
        schema = "kometta"  # По умолчанию Kometta
        # Проверяем наличие колонок для определения схемы
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
                    "location": "selector.py:select_by_working_point",
                    "message": "Schema detection",
                    "data": {
                        "articul": str(row.get("articul", "")),
                        "has_graphic_q_1": "graphic_q_1" in row,
                        "has_graphic_h_1": "graphic_h_1" in row,
                        "schema_detected": schema
                    },
                    "sessionId": "selection",
                    "runId": "schema_detection",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        
        if "graphic_q_1" in row and "graphic_h_1" not in row:
            # Если есть graphic_q_1, но нет graphic_h_1 - это формат Competitors
            schema = "competitors"
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:select_by_working_point",
                        "message": "Schema changed to competitors",
                        "data": {"articul": str(row.get("articul", "")), "schema": schema},
                        "sessionId": "selection",
                        "runId": "schema_detection",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
        
        # Извлекаем все валидные точки (RAW_POINTS)
        raw_points = extract_points(row, schema=schema)
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selector.py:select_by_working_point",
                    "message": "RAW_POINTS extracted",
                    "data": {
                        "articul": str(row.get("articul", "")),
                        "schema": schema,
                        "raw_points_count": len(raw_points),
                        "raw_points_sample": [(round(p[0], 2), round(p[1], 2)) for p in raw_points[:5]] if raw_points else []
                    },
                    "sessionId": "selection",
                    "runId": "extraction",
                    "hypothesisId": "B"
                }) + "\n")
        except: pass
        # #endregion
        
        # Логируем количество RAW_POINTS
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        
        if len(raw_points) < 4:
            # Логируем причину пропуска: недостаточно точек
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:select_by_working_point",
                        "message": "Skipping pump: not enough valid points",
                        "data": {
                            "articul": str(row.get("articul", "")),
                            "raw_points_count": len(raw_points),
                            "schema": schema
                        },
                        "sessionId": "selection",
                        "runId": "selection",
                        "hypothesisId": "SKIP"
                    }) + "\n")
            except: pass
            continue
        
        # Выбираем 4 опорные точки для аппроксимации (FIT_POINTS)
        fit_points = choose_fit_points_4(raw_points)
        if fit_points is None or len(fit_points) != 4:
            # Логируем причину пропуска: не удалось выбрать 4 точки
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:select_by_working_point",
                        "message": "Skipping pump: failed to choose 4 fit points",
                        "data": {
                            "articul": str(row.get("articul", "")),
                            "raw_points_count": len(raw_points),
                            "fit_points_count": len(fit_points) if fit_points else 0
                        },
                        "sessionId": "selection",
                        "runId": "selection",
                        "hypothesisId": "SKIP"
                    }) + "\n")
            except: pass
            continue
        
        # Извлекаем Q и H из FIT_POINTS
        q_points = [p[0] for p in fit_points]
        h_points = [p[1] for p in fit_points]
        
        # Вычисляем q_max_raw для авто-поиска брекета
        q_max_raw = max([p[0] for p in raw_points]) if raw_points else max(q_points)
        
        # Аппроксимируем кривую (строго 4 точки, как в app.py)
        try:
            coeffs = approximate_curve(q_points, h_points)
            if coeffs is None:
                # Логируем причину пропуска
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
                            "message": "Skipping pump: solve failed",
                            "data": {"articul": str(row.get("articul", ""))},
                            "sessionId": "selection",
                            "runId": "selection",
                            "hypothesisId": "SKIP"
                        }) + "\n")
                except: pass
                continue
            a, b, c, d = coeffs
        except Exception as e:
            # Логируем ошибку
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
                        "message": "Skipping pump: exception in approximation",
                        "data": {"articul": str(row.get("articul", "")), "error": str(e)},
                        "sessionId": "selection",
                        "runId": "selection",
                        "hypothesisId": "SKIP"
                    }) + "\n")
            except: pass
            continue
        
        # Строим сетевую кривую (как в app.py)
        s = calculate_network_coeffs(h_st, q, h)
        def net_func(q_val):
            return network_curve_func(q_val, h_st, s)
        
        # Функция насоса
        def pump_func(q_val):
            return calculate_h(q_val, a, b, c, d)
        
        # Определяем рабочую точку как пересечение (как в app.py)
        # ИСПРАВЛЕНО: Используем q_max_raw для авто-поиска брекета
        q_max_input = max(q_points) if q_points else 10000
        q_op, h_op = find_operating_point(
            pump_func, 
            net_func, 
            q_guess_range=(0.1, q_max_input),
            q_max_raw=q_max_raw,
            auto_bracket=True
        )
        
        if q_op is None:
            # Логируем причину пропуска: нет пересечения в диапазоне
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:select_by_working_point",
                        "message": "Skipping pump: no intersection in range",
                        "data": {
                            "articul": str(row.get("articul", "")),
                            "q_max_raw": q_max_raw,
                            "q_guess_range": [0.1, q_max_input]
                        },
                        "sessionId": "selection",
                        "runId": "selection",
                        "hypothesisId": "SKIP"
                    }) + "\n")
            except: pass
            continue
        
        # ИСПРАВЛЕНО: Валидация рабочей точки - пропускаем насосы с неправильными значениями
        # Проблема: некоторые насосы имеют рабочую точку q_op: 0.47, h_op: 0.0, что неправильно
        # ВАЖНО: Проверяем ДО логирования "Operating point found"
        # Используем небольшой эпсилон для учета погрешности вычислений с плавающей точкой
        if h_op <= 1e-6 or q_op <= 0.1:
            # Логируем причину пропуска: неправильная рабочая точка
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "selector.py:select_by_working_point",
                        "message": "Skipping pump: invalid operating point",
                        "data": {
                            "articul": str(row.get("articul", "")),
                            "q_op": round(q_op, 2),
                            "h_op": round(h_op, 2),
                            "reason": "h_op <= 0 or q_op <= 0.1"
                        },
                        "sessionId": "selection",
                        "runId": "selection",
                        "hypothesisId": "SKIP"
                    }) + "\n")
            except: pass
            continue
        
        # Логируем успешное нахождение рабочей точки (только для валидных точек)
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selector.py:select_by_working_point",
                    "message": "Operating point found",
                    "data": {
                        "articul": str(row.get("articul", "")),
                        "raw_points_count": len(raw_points),
                        "fit_points": [(round(p[0], 2), round(p[1], 2)) for p in fit_points],
                        "q_max_raw": q_max_raw,
                        "q_op": round(q_op, 2),
                        "h_op": round(h_op, 2)
                    },
                    "sessionId": "selection",
                    "runId": "selection",
                    "hypothesisId": "SUCCESS"
                }) + "\n")
        except: pass
        
        # Метрика ошибки для ранжирования (как в app.py)
        error = abs(q_op - q) / max(q, 1e-6) + abs(h_op - h) / max(h, 1e-6)
        
        # Собираем данные насоса (проверяем на NaN)
        def safe_str(value, default=""):
            if pd.isna(value) or value is None:
                return default
            val_str = str(value).strip()
            if val_str.lower() in ["nan", "none", ""]:
                return default
            return val_str
        
        # Используем артикул как fallback для model/series
        articul = safe_str(row.get("articul", ""), "")
        model_raw = safe_str(row.get("model", ""), "")
        series = safe_str(row.get("series", ""), "")
        
        # #region agent log - DEBUG model extraction
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "selector.py:select_by_working_point",
                    "message": "Model extraction from row",
                    "data": {
                        "articul": articul,
                        "model_raw": model_raw,
                        "model_raw_type": type(model_raw).__name__,
                        "model_in_row": str(row.get("model", "NOT_FOUND")),
                        "model_in_row_type": type(row.get("model", None)).__name__,
                        "has_model_column": "model" in row.index,
                        "all_columns": list(row.index)[:15]  # Первые 15 колонок для отладки
                    },
                    "sessionId": "selection",
                    "runId": "model_extraction",
                    "hypothesisId": "DEBUG"
                }) + "\n")
        except: pass
        # #endregion
        
        # Очищаем model от "nan" и пустых значений
        # НЕ заменяем на "Артикул ..." здесь - это будет fallback в chat.py
        model = model_raw if model_raw and model_raw.lower() not in ["nan", "none", ""] else ""
        
        # Получаем URL для листа данных (только для Кометта)
        url = safe_str(row.get("url", ""), "")
        datasheet_url = ""
        if url:
            datasheet_url = url if url.endswith("?pdf=1") else f"{url}?pdf=1"
        
        # Вычисляем относительную ошибку в процентах для отображения
        relative_error_percent = (abs(h_op - h) / max(h, 1)) * 100
        
        pump_data = {
            "articul": articul if articul else "не указан",
            "model": model,
            "series": series if series else "не указана",
            "brand": safe_str(row.get("brand", ""), "Кометта"),
            "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
            "q_work": q_op,
            "h_work": h_op,
            "error": error,  # Комбинированная ошибка для ранжирования
            "relative_error_percent": relative_error_percent,  # Относительная ошибка в %
            "coefficients": {"a": a, "b": b, "c": c, "d": d},
            "q_points_used": q_points,  # 4 FIT_POINTS, использованные для аппроксимации
            "h_points_used": h_points,
            "raw_points_count": len(raw_points),  # Количество всех валидных точек
            "fit_points": [(round(p[0], 2), round(p[1], 2)) for p in fit_points],  # 4 опорные точки
            "q_min": min(q_points) if q_points else 0.0,
            "q_max": max(q_points) if q_points else 0.0,
            "url": url,
            "datasheet_url": datasheet_url
        }
        
        results.append(pump_data)
    
    # Сортируем по ошибке (комбинированная ошибка, как в app.py)
    results.sort(key=lambda x: x["error"])
    
    # Возвращаем топ-N
    return results[:top_n]


def self_check():
    """
    Самопроверка логики подбора насосов на тестовых данных из app.py.
    """
    # Тестовые данные из app.py: Q:[0,50,100,150], H:[100,95,80,50], H_st=20, Q_p=100, H_p=60
    test_q_points = [0, 50, 100, 150]
    test_h_points = [100, 95, 80, 50]
    test_h_st = 20.0
    test_q_p = 100.0
    test_h_p = 60.0
    
    # Аппроксимируем кривую
    coeffs = approximate_curve(test_q_points, test_h_points)
    if coeffs is None:
        return {"status": "FAIL", "message": "approximate_curve returned None"}
    
    a, b, c, d = coeffs
    
    # Строим сетевую кривую
    s = calculate_network_coeffs(test_h_st, test_q_p, test_h_p)
    def net_func(q_val):
        return network_curve_func(q_val, test_h_st, s)
    
    # Функция насоса
    def pump_func(q_val):
        return calculate_h(q_val, a, b, c, d)
    
    # Находим рабочую точку
    q_max_input = max(test_q_points)
    q_op, h_op = find_operating_point(pump_func, net_func, q_guess_range=(0.1, q_max_input))
    
    if q_op is None:
        return {"status": "FAIL", "message": "find_operating_point returned None"}
    
    return {
        "status": "OK",
        "q_op": q_op,
        "h_op": h_op,
        "coefficients": {"a": a, "b": b, "c": c, "d": d},
        "network_s": s
    }


def find_competitor_model(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Ищет модель конкурента в базе.
    
    Поддерживает поиск:
    - По полному названию: "CNP CDM 1-3"
    - По модели без бренда: "CDM 1-3"
    - По частичному совпадению
    
    Args:
        model_name: название модели (может быть с брендом или без)
        
    Returns:
        словарь с данными модели или None
    """
    df = load_competitors_data()
    model_upper = model_name.upper().strip()
    
    # Сначала пробуем точное совпадение по полному названию (бренд + модель)
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
    
    # Если не нашли, пробуем поиск по модели без бренда
    # Извлекаем только модель (убираем бренд, если он есть)
    model_only = model_upper
    known_brands = ["CNP", "GRUNDFOS", "WILO", "PEDROLLO", "EBARA", "KSB", "FLYGT"]
    for brand in known_brands:
        if model_upper.startswith(brand):
            model_only = model_upper[len(brand):].strip()
            break
    
    # Ищем по модели без бренда (точное совпадение)
    if "model" in df.columns:
        import pandas as pd
        df_model_str = df["model"].astype(str).replace("nan", "").replace("None", "")
        # Точное совпадение модели (без учета бренда)
        matches = df[df_model_str.str.upper().str.strip() == model_only]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "model": str(row.get("model", "")),
                "brand": str(row.get("brand", "")),
                "series": str(row.get("series", "")),
                "row": row
            }
    
    # Ищем частичное совпадение по полному названию
    if "model" in df.columns:
        import pandas as pd
        df_model_str = df["model"].astype(str).replace("nan", "").replace("None", "")
        matches = df[df_model_str.str.upper().str.contains(model_upper, na=False, regex=False)]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "model": str(row.get("model", "")),
                "brand": str(row.get("brand", "")),
                "series": str(row.get("series", "")),
                "row": row
            }
    
    # Ищем частичное совпадение по модели без бренда
    if "model" in df.columns and model_only != model_upper:
        import pandas as pd
        df_model_str = df["model"].astype(str).replace("nan", "").replace("None", "")
        matches = df[df_model_str.str.upper().str.contains(model_only, na=False, regex=False)]
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
    
    # Аппроксимация строго по app.py: берем РОВНО 4 опорные точки (если их >=4)
    coeffs = None
    raw_points = []
    try:
        for qv, hv in zip(q_points or [], h_points or []):
            if qv is None or hv is None:
                continue
            try:
                qf = float(qv)
                hf = float(hv)
            except Exception:
                continue
            if np.isnan(qf) or np.isnan(hf):
                continue
            raw_points.append((qf, hf))
    except Exception:
        raw_points = []

    raw_points.sort(key=lambda p: p[0])

    if len(raw_points) >= 4:
        fit_points = choose_fit_points_4(raw_points)
        if fit_points and len(fit_points) == 4:
            q_fit = [p[0] for p in fit_points]
            h_fit = [p[1] for p in fit_points]
            coeffs = approximate_curve(q_fit, h_fit)
    
    # Устанавливаем коэффициенты
    if coeffs is not None:
        a, b, c, d = coeffs
    else:
        a, b, c, d = None, None, None, None
    
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
    
    # Формируем результат
    result = {
        "articul": articul if articul else "не указан",
        "model": model,
        "series": series if series else "не указана",
        "brand": safe_str(row.get("brand", ""), "Кометта"),
        "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
        "q_points": q_points,
        "h_points": h_points,
        "url": url,
        "datasheet_url": datasheet_url,
    }
    
    # Добавляем коэффициенты только если они есть
    if coeffs is not None:
        result["coefficients"] = {"a": a, "b": b, "c": c, "d": d}
    
    return result


def get_pump_curve_data_by_model(model: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные кривой насоса по названию модели (например, "К144 65-80/04А/055Т2").
    
    Args:
        model: название модели насоса
        
    Returns:
        словарь с данными кривой или None
    """
    df = load_kometta_data()
    
    # Нормализуем модель для поиска (приводим к верхнему регистру, заменяем K на К)
    model_normalized = str(model).strip().upper().replace("K", "К")
    
    # Пробуем точное совпадение
    df["model_normalized"] = df["model"].astype(str).str.strip().str.upper().str.replace("K", "К")
    matches = df[df["model_normalized"] == model_normalized]
    
    if matches.empty:
        # Пробуем частичное совпадение (модель содержит искомую строку или наоборот)
        # Проверяем, содержит ли нормализованная модель искомую строку
        matches = df[df["model_normalized"].str.contains(model_normalized, na=False, regex=False)]
        
        # Если все еще пусто, пробуем обратное - ищем модели, которые начинаются с искомой строки
        if matches.empty:
            matches = df[df["model_normalized"].str.startswith(model_normalized, na=False)]
    
    if matches.empty:
        return None
    
    # Берем первое совпадение
    row = matches.iloc[0]
    q_points, h_points = extract_curve_points(row)
    
    # Возвращаем данные даже если точек < 3
    coeffs = None
    raw_points = []
    try:
        for qv, hv in zip(q_points or [], h_points or []):
            if qv is None or hv is None:
                continue
            try:
                qf = float(qv)
                hf = float(hv)
            except Exception:
                continue
            if np.isnan(qf) or np.isnan(hf):
                continue
            raw_points.append((qf, hf))
    except Exception:
        raw_points = []

    raw_points.sort(key=lambda p: p[0])

    if len(raw_points) >= 4:
        fit_points = choose_fit_points_4(raw_points)
        if fit_points and len(fit_points) == 4:
            q_fit = [p[0] for p in fit_points]
            h_fit = [p[1] for p in fit_points]
            coeffs = approximate_curve(q_fit, h_fit)
    
    if coeffs is not None:
        a, b, c, d = coeffs
    else:
        a, b, c, d = None, None, None, None
    
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
    
    # Формируем результат
    result = {
        "articul": articul if articul else "не указан",
        "model": model,
        "series": series if series else "не указана",
        "brand": safe_str(row.get("brand", ""), "Кометта"),
        "power": float(row.get("power", 0)) if pd.notna(row.get("power")) else 0.0,
        "q_points": q_points,
        "h_points": h_points,
        "url": url,
        "datasheet_url": datasheet_url,
    }
    
    # Добавляем коэффициенты только если они есть
    if coeffs is not None:
        result["coefficients"] = {"a": a, "b": b, "c": c, "d": d}
    
    return result

