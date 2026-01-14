"""
Унифицированный модуль для извлечения температуры из текста.
Используется в parse_short_answer и slot_extractor для единообразной обработки.
"""
import re
from typing import Optional, Dict, Any, Tuple


def normalize_temperature_text(text: str) -> str:
    """
    Нормализует текст для парсинга температуры.
    
    ИСПРАВЛЕНО: Использует общий preprocess.normalize_text() для базовой нормализации,
    затем применяет специфичные для температуры преобразования.
    """
    # Используем общую нормализацию из preprocess
    from services.nlu.preprocess import normalize_text as preprocess_normalize
    text_normalized = preprocess_normalize(text)
    
    # Дополнительные нормализации специфичные для температуры
    # Убираем пробел между "+" и числом (поддерживаем дробные)
    text_normalized = re.sub(r'\+\s+(\d+(?:[.,]\d+)?)', r'+\1', text_normalized)
    text_normalized = re.sub(r'-\s+(\d+(?:[.,]\d+)?)', r'-\1', text_normalized)
    
    # "плюс 20" → "+20" (поддерживаем дробные)
    text_normalized = re.sub(r'плюс\s+(\d+(?:[.,]\d+)?)', r'+\1', text_normalized)
    
    return text_normalized


def extract_temperature(text: str) -> Optional[Dict[str, Any]]:
    """
    Унифицированная функция для извлечения температуры из текста.
    
    Returns:
        {
            "temperature_c": float,  # значение температуры
            "has_sign": bool,  # есть ли явный знак (+/-)
            "confidence": float,  # уверенность (0.0-1.0)
        } или None, если температура не найдена
    """
    if not text or not text.strip():
        return None
    
    # ИСПРАВЛЕНО: Проверяем "минус" и "плюс" ДО нормализации, т.к. нормализация преобразует их в "+/-"
    # Приоритет 1: "минус" как слово (до нормализации)
    minus_word_match = re.search(r'минус\s+(\d+(?:[.,]\d+)?)', text.lower())
    if minus_word_match:
        try:
            temp = -float(minus_word_match.group(1).replace(',', '.'))
            if -50 <= temp <= 200:
                return {
                    "temperature_c": temp,
                    "has_sign": True,
                    "confidence": 0.9
                }
        except (ValueError, IndexError):
            pass
    
    # Приоритет 2: "плюс" как слово (до нормализации)
    plus_word_match = re.search(r'плюс\s+(\d+(?:[.,]\d+)?)', text.lower())
    if plus_word_match:
        try:
            temp = float(plus_word_match.group(1).replace(',', '.'))
            if -50 <= temp <= 200:
                return {
                    "temperature_c": temp,
                    "has_sign": True,
                    "confidence": 0.85
                }
        except (ValueError, IndexError):
            pass
    
    # Нормализуем текст для дальнейшего парсинга
    text_normalized = normalize_temperature_text(text)
    
    # Приоритет 3: Явный знак (+/-) в числе
    patterns_with_sign = [
        r'([+-]\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|[сc]\b)',
        r'([+-]\d+(?:[.,]\d+)?)\s*(?:°|[сc]\b)',
    ]
    for pattern in patterns_with_sign:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            try:
                temp_str = match.group(1).replace(',', '.')
                temp = float(temp_str)
                if -50 <= temp <= 200:
                    return {
                        "temperature_c": temp,
                        "has_sign": True,
                        "confidence": 0.9
                    }
            except (ValueError, IndexError):
                pass
    
    # Приоритет 4: Число без знака (нужно уточнение)
    patterns_without_sign = [
        r'(\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|[сc]\b)',
        r'(?:темп|temp)[\s:]+(\d+(?:[.,]\d+)?)',
        r'(\d+(?:[.,]\d+)?)\s*(?:°|[сc]\b)',
    ]
    for pattern in patterns_without_sign:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            try:
                temp_str = match.group(1).replace(',', '.')
                temp = float(temp_str)
                if -50 <= temp <= 200:
                    return {
                        "temperature_c": temp,
                        "has_sign": False,
                        "confidence": 0.7
                    }
            except (ValueError, IndexError):
                pass
    
    return None
