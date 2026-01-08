"""
Загрузка и кэширование данных из XLSX файлов.
"""
import pandas as pd
import os
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
    """
    cache_key = "kometta"
    
    if cache_key in _cache:
        return _cache[cache_key]
    
    if file_path is None:
        data_dir = get_data_dir()
        file_path = os.path.join(data_dir, "K.ai_database_kometta.xlsx")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}. Проверьте переменную окружения DATA_DIR или путь к файлу.")
    
    df = pd.read_excel(file_path)
    df = normalize_dataframe(df)
    
    # Добавляем нормализованное название модели для поиска
    if "model" in df.columns:
        df["model_normalized"] = df["model"].apply(clean_model_name)
    
    _cache[cache_key] = df
    return df


def load_competitors_data(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Загружает данные по конкурентам (CNP и др.).
    
    Args:
        file_path: путь к файлу (опционально, по умолчанию берётся из DATA_DIR)
        
    Returns:
        DataFrame с данными
    """
    cache_key = "competitors"
    
    if cache_key in _cache:
        return _cache[cache_key]
    
    if file_path is None:
        data_dir = get_data_dir()
        file_path = os.path.join(data_dir, "K.ai_database_competitors_cnp.xlsx")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}. Проверьте переменную окружения DATA_DIR или путь к файлу.")
    
    df = pd.read_excel(file_path)
    df = normalize_dataframe(df)
    
    # Добавляем нормализованное название модели для поиска
    if "model" in df.columns:
        df["model_normalized"] = df["model"].apply(clean_model_name)
    
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

