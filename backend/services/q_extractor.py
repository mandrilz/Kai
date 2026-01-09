"""
Модуль для извлечения и нормализации расхода (Q) из текста.
Поддерживает различные единицы измерения и варианты записи.
"""
import re
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation


# Коэффициенты пересчета в м³/ч
CONVERSION_FACTORS = {
    'm3/h': 1.0,
    'l/s': 3.6,  # 1 л/с = 0.001 м³/с = 3.6 м³/ч
    'l/min': 0.06,  # 1 л/мин = 0.001 м³ / 60 мин = 0.06 м³/ч
    'l/h': 0.001,
    'm3/day': 1.0 / 24.0,  # 1 м³/сут = 1/24 м³/ч
    'gpm': 0.227124,  # US gallons per minute
}

# Ключевые слова для расхода (повышают уверенность)
Q_KEYWORDS = [
    'расход', 'подача', 'производительность', 'дебит',
    'flow', 'capacity', 'q', 'q=', 'q:'
]

# Ключевые слова, которые НЕ относятся к расходу (снижают уверенность)
NOT_Q_KEYWORDS = [
    'квт', 'kw', 'bar', 'атм', 'мм', 'mm', 'dn', 'rpm', 'об/мин',
    'мощность', 'давление', 'диаметр', 'обороты'
]


def normalize_text(text: str) -> str:
    """
    Нормализует текст для парсинга:
    - lowercase
    - заменяет м³, m³, m^3 → m3
    - заменяет кириллицу в единицах на латиницу
    - исправляет опечатки (мз → м3)
    - приводит разделитель числа (12,5 → 12.5)
    - удаляет лишние пробелы
    """
    text = text.lower()
    
    # Заменяем степени: м³, m³, m^3 → m3
    text = re.sub(r'м[³3]|m[³3]|m\^3', 'm3', text)
    
    # Исправляем опечатки: мз → м3 (кириллическая "з" вместо "3")
    text = re.sub(r'мз', 'м3', text)
    text = re.sub(r'mз', 'm3', text)
    
    # Заменяем кириллицу в единицах на латиницу (аккуратно, только в единицах)
    # м → m, ч → h, с → s, мин → min, сут → day
    text = re.sub(r'м3/ч|м3/час', 'm3/h', text)
    text = re.sub(r'м3/с|м3/сек|м3/секунду', 'm3/s', text)
    text = re.sub(r'м3/мин|м3/м|м3/минуту', 'm3/min', text)
    text = re.sub(r'м3/сут|м3/день', 'm3/day', text)
    text = re.sub(r'л/с|л/сек|л/секунду', 'l/s', text)
    text = re.sub(r'л/мин|л/м|л/минуту', 'l/min', text)
    text = re.sub(r'л/ч|л/час', 'l/h', text)
    
    # Заменяем синонимы кубометров
    text = re.sub(r'куб/ч|кубов/ч|куб/час|кубов/час|кубометров в час|куб\.м/ч|куб\. м/ч', 'm3/h', text)
    text = re.sub(r'куб/сут|кубометров в сутки', 'm3/day', text)
    
    # ИСПРАВЛЕНО: Убираем пробелы внутри чисел (например, "144. 306" → "144.306")
    # Паттерн: цифра, точка/запятая, пробел, цифры
    text = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', text)
    
    # Приводим разделитель числа: запятая → точка
    # Но только если это не разделитель тысяч
    text = re.sub(r'(\d+),(\d{1,2})(?=\s|$|[^\d])', r'\1.\2', text)
    
    # Удаляем лишние пробелы в единицах: м 3 / ч → м3/ч
    text = re.sub(r'м\s*3\s*/\s*ч', 'm3/h', text)
    text = re.sub(r'm\s*3\s*/\s*h', 'm3/h', text)
    
    # Удаляем лишние пробелы вокруг знаков
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_number(text: str, context: str = "") -> Optional[Tuple[float, Dict[str, Any]]]:
    """
    Извлекает число из текста с учетом различных форматов.
    
    Returns:
        (число, метаданные) или None
    """
    # ИСПРАВЛЕНО: Проверяем диапазон только если НЕТ точки/запятой внутри чисел
    # Это предотвращает интерпретацию "144.306" как диапазона "144-306"
    # Диапазон: 20-30, 20…30, но НЕ 144.306 (это одно число с десятичной частью)
    # Сначала проверяем, есть ли десятичная точка/запятая в тексте
    has_decimal = '.' in text or ',' in text
    
    if not has_decimal:
        # Только если нет десятичных чисел - проверяем диапазон
        range_pattern = r'(\d+)\s*[-…]{1,3}\s*(\d+)'  # Только целые числа для диапазона
        range_match = re.search(range_pattern, text)
        if range_match:
            try:
                num1_str = range_match.group(1).replace(',', '.')
                num2_str = range_match.group(2).replace(',', '.')
                num1 = float(num1_str)
                num2 = float(num2_str)
                avg = (num1 + num2) / 2
                return avg, {
                    "type": "range",
                    "min": min(num1, num2),
                    "max": max(num1, num2),
                    "raw": range_match.group(0)
                }
            except (ValueError, InvalidOperation):
                pass
    
    # Проверяем "примерно": ~50, около 50, примерно 50
    approx_pattern = r'(?:~|около|примерно|приблизительно)\s*(\d+(?:[.,]\d+)?)'
    approx_match = re.search(approx_pattern, text)
    if approx_match:
        try:
            num_str = approx_match.group(1).replace(',', '.')
            num = float(num_str)
            return num, {"type": "approx", "raw": approx_match.group(0), "confidence_modifier": -0.1}
        except (ValueError, InvalidOperation):
            pass
    
    # Обычное число: 50, 12.5, 12,5
    number_pattern = r'(\d+(?:[.,]\d+)?)'
    number_match = re.search(number_pattern, text)
    if number_match:
        try:
            num_str = number_match.group(1).replace(',', '.')
            num = float(num_str)
            return num, {"type": "single", "raw": number_match.group(0)}
        except (ValueError, InvalidOperation):
            pass
    
    return None


def detect_q_unit(text: str, number_pos: int) -> Optional[Tuple[str, float]]:
    """
    Определяет единицу измерения расхода в тексте около позиции числа.
    
    Returns:
        (единица, коэффициент_пересчета) или None
    """
    # Ищем единицы в радиусе 30 символов от числа
    start = max(0, number_pos - 15)
    end = min(len(text), number_pos + 30)
    context = text[start:end]
    
    # Паттерны единиц (в порядке приоритета)
    unit_patterns = [
        # m3/h и синонимы
        (r'm3/h|m3/hr|m3/час|m3h|m3\s*h', 'm3/h', CONVERSION_FACTORS['m3/h']),
        # l/s
        (r'l/s|l/сек|l/секунду|л/с|л/сек|л/секунду', 'l/s', CONVERSION_FACTORS['l/s']),
        # l/min
        (r'l/min|l/мин|l/м|л/мин|л/м|л/минуту', 'l/min', CONVERSION_FACTORS['l/min']),
        # l/h
        (r'l/h|l/ч|l/час|л/ч|л/час', 'l/h', CONVERSION_FACTORS['l/h']),
        # m3/day
        (r'm3/day|m3/сут|m3/день|м3/сут|м3/день', 'm3/day', CONVERSION_FACTORS['m3/day']),
        # gpm
        (r'gpm|gal/min|гал/мин', 'gpm', CONVERSION_FACTORS['gpm']),
    ]
    
    for pattern, unit, factor in unit_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return unit, factor
    
    return None


def calculate_confidence(text: str, number_pos: int, unit: Optional[str]) -> float:
    """
    Вычисляет уверенность в том, что найденное число - это расход.
    
    Returns:
        confidence от 0.0 до 1.0
    """
    confidence = 0.5  # Базовая уверенность
    
    # Ищем ключевые слова в радиусе 50 символов
    start = max(0, number_pos - 25)
    end = min(len(text), number_pos + 50)
    context = text[start:end]
    
    # Повышаем уверенность при наличии ключевых слов расхода
    for keyword in Q_KEYWORDS:
        if keyword in context.lower():
            confidence += 0.2
            break
    
    # Снижаем уверенность при наличии ключевых слов НЕ расхода
    for keyword in NOT_Q_KEYWORDS:
        if keyword in context.lower():
            confidence -= 0.3
            break
    
    # Повышаем уверенность, если есть явная единица
    if unit:
        confidence += 0.3
    
    # Ограничиваем диапазон
    return max(0.0, min(1.0, confidence))


def extract_q_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Извлекает расход (Q) из текста и приводит к м³/ч.
    
    Returns:
        {
            "q_m3h": float,
            "q_raw": str,
            "q_unit": str,
            "confidence": float,
            "range": Optional[Dict[str, float]]
        } или None
    """
    # Нормализуем текст
    normalized = normalize_text(text)
    
    # Ищем все возможные числа с единицами
    candidates = []
    
    # Паттерн: число + единица (более гибкий)
    # ИСПРАВЛЕНО: Не ищем диапазоны в числах с точкой/запятой (например, "144.306" не должен быть диапазоном)
    # Ищем числа, за которыми могут идти единицы
    # Паттерн для диапазона: только если есть явный разделитель диапазона (-, …, ..) И НЕТ точки/запятой внутри
    pattern = r'(\d+(?:[.,]\d+)?)\s*(?:[-…]{1,3}\s*(\d+(?:[.,]\d+)?))?\s*(?:м3|m3|l|л|куб|gpm|gal|м\s*3|m\s*3)[^\s]*'
    
    for match in re.finditer(pattern, normalized):
        number_pos = match.start()
        number_text = match.group(0)
        
        # Проверяем, что после числа действительно есть единица расхода
        # (не просто случайное число)
        if not detect_q_unit(normalized, number_pos):
            # Если единица не найдена, но есть ключевые слова - продолжаем
            if not any(kw in normalized[max(0, number_pos-30):number_pos+30] for kw in Q_KEYWORDS):
                continue
        
        # Извлекаем число
        number_result = extract_number(number_text)
        if not number_result:
            continue
        
        number, number_meta = number_result
        
        # Определяем единицу
        unit_result = detect_q_unit(normalized, number_pos)
        if not unit_result:
            # Если единица не найдена, но есть ключевые слова - предполагаем m3/h
            if any(kw in normalized[max(0, number_pos-30):number_pos+30] for kw in Q_KEYWORDS):
                unit_result = ('m3/h', CONVERSION_FACTORS['m3/h'])
            else:
                continue
        
        unit, factor = unit_result
        
        # Вычисляем уверенность
        confidence = calculate_confidence(normalized, number_pos, unit)
        
        # Пересчитываем в м³/ч
        q_m3h = number * factor
        
        # Валидация: допустимый диапазон
        if q_m3h < 0.01 or q_m3h > 5000:
            # Слишком большое/маленькое значение - снижаем уверенность
            confidence *= 0.5
        
        candidates.append({
            "q_m3h": q_m3h,
            "q_raw": match.group(0),
            "q_unit": unit,
            "confidence": confidence,
            "range": number_meta.get("range") if number_meta.get("type") == "range" else None,
            "number_meta": number_meta,
            "position": number_pos
        })
    
    if not candidates:
        return None
    
    # Если несколько кандидатов - выбираем лучший
    if len(candidates) == 1:
        best = candidates[0]
    else:
        # Приоритет: выше уверенность, ближе к ключевым словам
        best = max(candidates, key=lambda c: (
            c["confidence"],
            -c["position"] if any(kw in normalized[max(0, c["position"]-30):c["position"]+30] for kw in Q_KEYWORDS) else 0
        ))
    
    # Формируем результат
    result = {
        "q_m3h": best["q_m3h"],
        "q_raw": best["q_raw"],
        "q_unit": best["q_unit"],
        "confidence": best["confidence"],
    }
    
    if best.get("range"):
        result["range"] = best["range"]
    
    return result

