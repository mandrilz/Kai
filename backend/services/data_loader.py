"""
Загрузка и кэширование данных из XLSX файлов.
"""
import pandas as pd
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from services.normalize import normalize_dataframe, clean_model_name

# Глобальный кэш
_cache: Dict[str, pd.DataFrame] = {}


def get_data_dir() -> str:
    """
    Получает путь к папке data из переменной окружения.
    По умолчанию: ../data (на уровень выше backend)
    """
    # Получаем путь из переменной окружения
    data_dir = os.getenv("DATA_DIR")
    
    if data_dir is None:
        # По умолчанию: на уровень выше backend (где services/)
        # __file__ = backend/services/data_loader.py
        # dirname(__file__) = backend/services/
        # dirname(dirname(__file__)) = backend/
        # join(.., "..", "data") = ../data (относительно backend/)
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        project_dir = os.path.dirname(backend_dir)
        data_dir = os.path.join(project_dir, "data")
    
    # Нормализуем путь (убираем относительные части, преобразует в абсолютный)
    data_dir = os.path.abspath(data_dir)
    return data_dir


def load_kometta_data(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Загружает данные по насосам Кометта.
    
    Args:
        file_path: путь к файлу (опционально, по умолчанию берётся из DATA_DIR)
        
    Returns:
        DataFrame с данными
        
    Raises:
        FileNotFoundError: если файл не найден
        ValueError: если файл пустой или не содержит обязательных колонок
    """
    cache_key = "kometta"
    
    if cache_key in _cache:
        return _cache[cache_key]
    
    if file_path is None:
        data_dir = get_data_dir()
        file_path = os.path.join(data_dir, "K.ai_database_kometta.xlsx")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}. Проверьте переменную окружения DATA_DIR или путь к файлу.")
    
    try:
        # Читаем Excel с явным указанием типов для текстовых колонок
        # Это предотвращает автоматическое преобразование model/brand в числа
        dtype_dict = {}
        # Сначала читаем без dtype, чтобы узнать названия колонок
        df_temp = pd.read_excel(file_path, nrows=1)
        # Для всех текстовых колонок указываем str
        for col in df_temp.columns:
            if col.lower() in ["brand", "model", "series", "articul", "url", "datasheet_url"]:
                dtype_dict[col] = str
        
        # Читаем полный файл с указанием типов
        df = pd.read_excel(file_path, dtype=dtype_dict)
    except Exception as e:
        raise ValueError(f"Ошибка при чтении файла {file_path}: {str(e)}")
    
    if df.empty:
        raise ValueError(f"Файл {file_path} пустой или не содержит данных.")
    
    # #region agent log - DEBUG columns before normalization
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_kometta_data",
                "message": "Columns before normalization",
                "data": {
                    "all_columns": df.columns.tolist(),
                    "has_brand": "brand" in df.columns,
                    "has_model": "model" in df.columns,
                    "has_articul": "articul" in df.columns,
                    "first_row_brand": str(df.iloc[0].get("brand", "NOT_FOUND")) if "brand" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model": str(df.iloc[0].get("model", "NOT_FOUND")) if "model" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_articul": str(df.iloc[0].get("articul", "NOT_FOUND")) if "articul" in df.columns else "COLUMN_NOT_FOUND"
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "DEBUG"
            }) + "\n")
    except: pass
    # #endregion
    
    # Валидация обязательных колонок для формата Kometta
    required_columns = ["articul"]  # Минимум артикул должен быть
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Файл {file_path} не содержит обязательных колонок: {', '.join(missing_columns)}")
    
    df = normalize_dataframe(df)
    
    # #region agent log - DEBUG columns after normalization
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_kometta_data",
                "message": "Columns after normalization",
                "data": {
                    "has_brand": "brand" in df.columns,
                    "has_model": "model" in df.columns,
                    "first_row_brand": str(df.iloc[0].get("brand", "NOT_FOUND")) if "brand" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model": str(df.iloc[0].get("model", "NOT_FOUND")) if "model" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model_type": type(df.iloc[0].get("model", None)).__name__ if "model" in df.columns else "COLUMN_NOT_FOUND"
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "DEBUG"
            }) + "\n")
    except: pass
    # #endregion
    
    # Добавляем нормализованное название модели для поиска
    if "model" in df.columns:
        df["model_normalized"] = df["model"].apply(clean_model_name)
    
    # Логируем успешную загрузку
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_kometta_data",
                "message": "Kometta data loaded successfully",
                "data": {
                    "rows_count": len(df),
                    "columns_count": len(df.columns),
                    "has_graphic_columns": any(col.startswith("graphic_") for col in df.columns)
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "STAGE1"
            }) + "\n")
    except:
        pass
    
    _cache[cache_key] = df
    return df


def load_competitors_data(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Загружает данные по конкурентам (CNP и др.).
    
    Args:
        file_path: путь к файлу (опционально, по умолчанию берётся из DATA_DIR)
        
    Returns:
        DataFrame с данными
        
    Raises:
        FileNotFoundError: если файл не найден
        ValueError: если файл пустой или не содержит обязательных колонок
    """
    cache_key = "competitors"
    
    if cache_key in _cache:
        return _cache[cache_key]
    
    if file_path is None:
        data_dir = get_data_dir()
        file_path = os.path.join(data_dir, "K.ai_database_competitors_cnp.xlsx")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}. Проверьте переменную окружения DATA_DIR или путь к файлу.")
    
    try:
        # Читаем Excel с явным указанием типов для текстовых колонок
        # Это предотвращает автоматическое преобразование model/brand в числа
        dtype_dict = {}
        # Сначала читаем без dtype, чтобы узнать названия колонок
        df_temp = pd.read_excel(file_path, nrows=1)
        # Для всех текстовых колонок указываем str
        for col in df_temp.columns:
            if col.lower() in ["brand", "model", "series", "articul", "url", "datasheet_url"]:
                dtype_dict[col] = str
        
        # Читаем полный файл с указанием типов
        df = pd.read_excel(file_path, dtype=dtype_dict)
    except Exception as e:
        raise ValueError(f"Ошибка при чтении файла {file_path}: {str(e)}")
    
    if df.empty:
        raise ValueError(f"Файл {file_path} пустой или не содержит данных.")
    
    # #region agent log - DEBUG columns before normalization
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_competitors_data",
                "message": "Columns before normalization",
                "data": {
                    "all_columns": df.columns.tolist(),
                    "has_brand": "brand" in df.columns,
                    "has_model": "model" in df.columns,
                    "first_row_brand": str(df.iloc[0].get("brand", "NOT_FOUND")) if "brand" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model": str(df.iloc[0].get("model", "NOT_FOUND")) if "model" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_articul": str(df.iloc[0].get("articul", "NOT_FOUND")) if "articul" in df.columns else "COLUMN_NOT_FOUND"
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "DEBUG"
            }) + "\n")
    except: pass
    # #endregion
    
    # Валидация обязательных колонок для формата Competitors
    required_columns = ["brand", "model"]  # Минимум бренд и модель должны быть
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Файл {file_path} не содержит обязательных колонок: {', '.join(missing_columns)}")
    
    df = normalize_dataframe(df)
    
    # #region agent log - DEBUG columns after normalization
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_competitors_data",
                "message": "Columns after normalization",
                "data": {
                    "has_brand": "brand" in df.columns,
                    "has_model": "model" in df.columns,
                    "first_row_brand": str(df.iloc[0].get("brand", "NOT_FOUND")) if "brand" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model": str(df.iloc[0].get("model", "NOT_FOUND")) if "model" in df.columns else "COLUMN_NOT_FOUND",
                    "first_row_model_type": type(df.iloc[0].get("model", None)).__name__ if "model" in df.columns else "COLUMN_NOT_FOUND"
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "DEBUG"
            }) + "\n")
    except: pass
    # #endregion
    
    # Добавляем нормализованное название модели для поиска
    if "model" in df.columns:
        df["model_normalized"] = df["model"].apply(clean_model_name)
    
    # Логируем успешную загрузку
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "data_loader.py:load_competitors_data",
                "message": "Competitors data loaded successfully",
                "data": {
                    "rows_count": len(df),
                    "columns_count": len(df.columns),
                    "has_graphic_columns": any(col.startswith("graphic_") for col in df.columns)
                },
                "sessionId": "system",
                "runId": "data_loading",
                "hypothesisId": "STAGE1"
            }) + "\n")
    except:
        pass
    
    _cache[cache_key] = df
    return df


def clear_cache():
    """Очищает кэш данных."""
    global _cache
    _cache = {}


def get_all_brands() -> List[str]:
    """Возвращает список всех брендов из базы Кометта."""
    df = load_kometta_data()
    if "brand" in df.columns:
        brands = df["brand"].dropna().unique().tolist()
        return [str(b) for b in brands]
    return []


def get_all_series() -> List[str]:
    """Возвращает список всех серий из базы Кометта."""
    df = load_kometta_data()
    if "series" in df.columns:
        series = df["series"].dropna().unique().tolist()
        return [str(s) for s in series]
    return []

