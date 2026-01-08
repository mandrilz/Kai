"""
Нормализация данных из XLSX файлов.
Обработка десятичных запятых, NaN, приведение типов.
"""
import pandas as pd
import numpy as np
from typing import Union


def normalize_float(value: Union[str, float, int, None]) -> float:
    """
    Нормализует значение к float.
    Обрабатывает десятичные запятые (заменяет на точку).
    
    Args:
        value: значение для нормализации
        
    Returns:
        float или np.nan
    """
    if pd.isna(value) or value is None:
        return np.nan
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Заменяем запятую на точку
        value = value.replace(",", ".")
        # Убираем пробелы
        value = value.strip()
        
        if value == "" or value == "-":
            return np.nan
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return np.nan
    
    return np.nan


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Нормализует весь DataFrame:
    - приводит числовые колонки к float
    - обрабатывает десятичные запятые
    - очищает от мусора
    
    Args:
        df: исходный DataFrame
        
    Returns:
        нормализованный DataFrame
    """
    df_normalized = df.copy()
    
    # Нормализуем числовые колонки (graphic_*)
    for col in df_normalized.columns:
        if col.startswith("graphic_"):
            df_normalized[col] = df_normalized[col].apply(normalize_float)
        elif df_normalized[col].dtype == "object":
            # Пробуем преобразовать строковые числовые колонки
            try:
                df_normalized[col] = df_normalized[col].apply(normalize_float)
            except:
                pass
    
    return df_normalized


def clean_model_name(model: Union[str, float, None]) -> str:
    """
    Очищает название модели от лишних символов.
    
    Args:
        model: название модели
        
    Returns:
        очищенное название
    """
    if pd.isna(model) or model is None:
        return ""
    
    model_str = str(model).strip().upper()
    # Убираем лишние пробелы
    model_str = " ".join(model_str.split())
    
    return model_str

