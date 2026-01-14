"""
Модуль предобработки текста для NLU.
Нормализует текст перед применением правил и парсеров.
"""
import re
# ИСПРАВЛЕНО: В Python 3.9+ str не нужно импортировать из typing
# str - встроенный тип, можно использовать напрямую в аннотациях типов


def normalize_lookalikes(text: str) -> str:
    """
    Нормализует похожие символы (кириллица/латиница, разные варианты).
    
    Примеры:
    - К/k → k (для моделей)
    - м/m → m (для единиц)
    - °С/°C → °C
    - м³/м3 → m3
    """
    text = text.strip()
    
    # Нормализуем степени: м³, m³, m^3 → m3
    text = re.sub(r'м[³3]|m[³3]|m\^3', 'm3', text, flags=re.IGNORECASE)
    
    # Нормализуем градусы: °С, °C, градус → °C
    text = re.sub(r'°[СC]|градус[ов]?', '°C', text, flags=re.IGNORECASE)
    
    # Нормализуем единицы измерения (только в контексте единиц, не в словах)
    # м → m (только если это единица, не часть слова)
    text = re.sub(r'\bм\b', 'm', text, flags=re.IGNORECASE)
    
    # К → k (для моделей: K377, К377, к377 → k377)
    # ИСПРАВЛЕНО: Обрабатываем как "К 377" (с пробелом), так и "К377" (без пробела)
    # Но аккуратно: "Кометта" не трогаем (это слово, не модель)
    # Паттерн 1: К перед цифрой без пробела (К377, к377)
    text = re.sub(r'([Кк])(?=\d)', r'k', text)
    # Паттерн 2: К как отдельное слово перед цифрой (К 377)
    text = re.sub(r'\b[Кк]\b(?=\s+\d)', 'k', text)
    
    return text


def normalize_numbers(text: str) -> str:
    """
    Нормализует числа: запятая → точка, убирает пробелы в числах.
    
    Примеры:
    - "10,5" → "10.5"
    - "144. 306" → "144.306"
    - "1 000" → "1000" (но только если это не разделитель тысяч в больших числах)
    """
    # Убираем пробелы внутри чисел: "144. 306" → "144.306"
    text = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', text)
    
    # Запятая → точка (только для десятичных дробей, не для разделителей тысяч)
    # ИСПРАВЛЕНО: Поддерживаем до 4 знаков после запятой (10,5555 → 10.5555)
    # Паттерн: цифры, запятая, 1-4 цифры, затем пробел/конец/не цифра
    text = re.sub(r'(\d+),(\d{1,4})(?=\s|$|[^\d])', r'\1.\2', text)
    
    return text


def normalize_units(text: str) -> str:
    """
    Нормализует единицы измерения: приводит к единому формату.
    
    Примеры:
    - "м3/ч", "м³/час", "кубов" → "m3/h"
    - "м напор", "метров" → "m"
    - "л/с", "л/сек" → "l/s"
    - "бар", "bar" → "bar"
    """
    text_lower = text.lower()
    
    # Нормализуем единицы расхода
    # м³/ч, м3/ч, м³/час, м3/час → m3/h
    text_lower = re.sub(r'м\s*3\s*/\s*ч|м\s*3\s*/\s*час|м[³3]/ч|м[³3]/час', 'm3/h', text_lower)
    text_lower = re.sub(r'м\s*3\s*/\s*с|м\s*3\s*/\s*сек|м[³3]/с|м[³3]/сек', 'm3/s', text_lower)
    text_lower = re.sub(r'м\s*3\s*/\s*мин|м\s*3\s*/\s*м|м[³3]/мин', 'm3/min', text_lower)
    text_lower = re.sub(r'м\s*3\s*/\s*сут|м\s*3\s*/\s*день|м[³3]/сут', 'm3/day', text_lower)
    
    # л/с, л/сек → l/s
    text_lower = re.sub(r'л\s*/\s*с|л\s*/\s*сек|л\s*/\s*секунду', 'l/s', text_lower)
    text_lower = re.sub(r'л\s*/\s*мин|л\s*/\s*м|л\s*/\s*минуту', 'l/min', text_lower)
    text_lower = re.sub(r'л\s*/\s*ч|л\s*/\s*час', 'l/h', text_lower)
    
    # Синонимы кубометров
    text_lower = re.sub(
        r'куб/ч|кубов/ч|куб/час|кубов/час|кубометров в час|куб\.м/ч|куб\. м/ч',
        'm3/h',
        text_lower
    )
    
    # Нормализуем единицы напора
    # м.в.ст, мвст, м вод.ст → mh2o
    text_lower = re.sub(
        r'м\.?в\.?ст|мвст|м\s*вод\.?\s*ст|м\s*водяного\s*столба|mh2o|mh₂o',
        'mh2o',
        text_lower
    )
    
    # Нормализуем давление
    text_lower = re.sub(r'\bбар\b|\bbar\b', 'bar', text_lower)
    text_lower = re.sub(r'\bкпа\b|\bkpa\b', 'kpa', text_lower)
    text_lower = re.sub(r'\bмпа\b|\bmpa\b', 'mpa', text_lower)
    text_lower = re.sub(r'\bатм\b|\batm\b', 'atm', text_lower)
    text_lower = re.sub(r'кгс/см[2²]|kgf/cm[2²]', 'kgf_cm2', text_lower)
    
    return text_lower


def normalize_text(text: str) -> str:
    """
    Полная нормализация текста: применяет все нормализации по порядку.
    
    Порядок:
    1. normalize_lookalikes (похожие символы)
    2. normalize_numbers (числа)
    3. normalize_units (единицы)
    4. lowercase и удаление лишних пробелов
    
    Args:
        text: Исходный текст
        
    Returns:
        Нормализованный текст
    """
    if not text or not text.strip():
        return text.strip() if text else ""
    
    # Шаг 1: Нормализуем похожие символы
    normalized = normalize_lookalikes(text)
    
    # Шаг 2: Нормализуем числа
    normalized = normalize_numbers(normalized)
    
    # Шаг 3: Нормализуем единицы (применяем к lowercase версии)
    normalized_lower = normalized.lower()
    normalized_lower = normalize_units(normalized_lower)
    
    # Шаг 4: Удаляем лишние пробелы
    normalized_lower = re.sub(r'\s+', ' ', normalized_lower)
    
    return normalized_lower.strip()
