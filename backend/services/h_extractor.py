"""
Модуль для извлечения и нормализации напора (H) из текста.
Поддерживает различные единицы измерения и варианты записи.
Все единицы автоматически пересчитываются в метры (м).
"""
import re
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation


# Коэффициенты пересчета в метры (м вод. ст.)
CONVERSION_FACTORS = {
    'm': 1.0,  # метры
    'mm': 1.0 / 1000.0,  # миллиметры → метры
    'cm': 1.0 / 100.0,  # сантиметры → метры
    'bar': 10.197,  # бар → метры вод. ст.
    'kpa': 0.10197,  # кПа → метры вод. ст.
    'mpa': 101.97,  # МПа → метры вод. ст.
    'atm': 10.33,  # атмосферы → метры вод. ст.
    'kgf_cm2': 10.0,  # kgf/cm2 → метры вод. ст.
    'mh2o': 1.0,  # метры водяного столба = метры
}

# Ключевые слова для напора (повышают уверенность)
H_KEYWORDS = [
    'напор', 'h', 'h=', 'h:', 'высота', 'подъем', 'подъём', 'перепад',
    'высота подъема', 'высота подъёма', 'перепад высот',
    'total head', 'tdh', 'head',
    'давление на выходе', 'требуемое давление', 'на точке',
    'геодезический напор', 'потери', 'с учётом потерь'
]

# Ключевые слова, которые НЕ относятся к напору (снижают уверенность)
NOT_H_KEYWORDS = [
    'dn', 'диаметр', 'мм', 'mm', 'квт', 'kw', 'мощность',
    'об/мин', 'rpm', 'температура', '°c', '°с',
    'размер', 'размерность'
]


def normalize_h_text(text: str) -> str:
    """
    Нормализует текст для парсинга напора:
    - lowercase
    - заменяет H₂O, H2O → h2o
    - нормализует единицы напора
    - приводит разделитель числа
    - удаляет лишние пробелы
    """
    text = text.lower()
    
    # Заменяем H₂O, H2O → h2o
    text = re.sub(r'h[₂2]o', 'h2o', text)
    
    # Нормализуем единицы напора
    # м.в.ст, мвст, м вод.ст → mh2o
    text = re.sub(r'м\.?в\.?ст|мвст|м\s*вод\.?\s*ст|м\s*водяного\s*столба|mh2o|mh₂o', 'mh2o', text)
    
    # ИСПРАВЛЕНО: Нормализуем метры, но сохраняем контекстные слова
    # Убираем пробелы между числом и единицей, если есть контекстное слово "напор"
    # "65 м напор" → "65m напор" для лучшего распознавания
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s+м\s+(напор|высота|подъем|подъём)', r'\1m \2', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s+m\s+(напор|высота|подъем|подъём)', r'\1m \2', text)
    
    # Нормализуем метры (общий случай)
    text = re.sub(r'\bм\b|\bметр[ов]?\b|\bm\b(?!\w)', 'm', text)
    
    # Нормализуем давление
    text = re.sub(r'\bбар\b|\bbar\b', 'bar', text)
    text = re.sub(r'\bкпа\b|\bkpa\b', 'kpa', text)
    text = re.sub(r'\bмпа\b|\bmpa\b', 'mpa', text)
    text = re.sub(r'\bатм\b|\batm\b', 'atm', text)
    text = re.sub(r'кгс/см[2²]|kgf/cm[2²]', 'kgf_cm2', text)
    
    # Нормализуем мм, см
    text = re.sub(r'\bмм\b|\bmm\b', 'mm', text)
    text = re.sub(r'\bсм\b|\bcm\b', 'cm', text)
    
    # ИСПРАВЛЕНО: Удаляем пробелы внутри чисел (например, "45. 87" → "45.87")
    # Это должно быть ДО приведения разделителя и удаления лишних пробелов
    text = re.sub(r'(\d+)\s*([.,])\s*(\d+)', r'\1\2\3', text)
    
    # Приводим разделитель числа: запятая → точка
    text = re.sub(r'(\d+),(\d{1,2})(?=\s|$|[^\d])', r'\1.\2', text)
    
    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_h_number(text: str) -> Optional[Tuple[float, Dict[str, Any]]]:
    """
    Извлекает число из текста с учетом различных форматов.
    
    Returns:
        (число, метаданные) или None
    """
    # ИСПРАВЛЕНО: Проверяем диапазон только если НЕТ точки/запятой внутри чисел
    # Это предотвращает интерпретацию "45.87" (или "45. 87" после нормализации) как диапазона "45-87"
    # Диапазон: 20-30, 20…30, но НЕ 45.87 (это одно число с десятичной частью)
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
    
    # Проверяем "примерно": ~40, около 40, примерно 40
    approx_pattern = r'(?:~|около|примерно|приблизительно)\s*(\d+(?:[.,]\d+)?)'
    approx_match = re.search(approx_pattern, text)
    if approx_match:
        try:
            num_str = approx_match.group(1).replace(',', '.')
            num = float(num_str)
            return num, {"type": "approx", "raw": approx_match.group(0), "confidence_modifier": -0.1}
        except (ValueError, InvalidOperation):
            pass
    
    # Обычное число: 40, 12.5, 12,5
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


def detect_h_unit(text: str, number_pos: int) -> Optional[Tuple[str, float]]:
    """
    Определяет единицу измерения напора в тексте около позиции числа.
    
    Returns:
        (единица, коэффициент_пересчета) или None
    """
    # Ищем единицы в радиусе 30 символов от числа
    start = max(0, number_pos - 15)
    end = min(len(text), number_pos + 30)
    context = text[start:end]
    
    # Паттерны единиц (в порядке приоритета)
    unit_patterns = [
        # Метры и производные
        (r'\bm\b(?!\w)|\bметр[ов]?\b|\bmh2o\b', 'm', CONVERSION_FACTORS['m']),
        (r'\bmm\b|\bмм\b', 'mm', CONVERSION_FACTORS['mm']),
        (r'\bcm\b|\bсм\b', 'cm', CONVERSION_FACTORS['cm']),
        # Давление
        (r'\bbar\b|\bбар\b', 'bar', CONVERSION_FACTORS['bar']),
        (r'\bkpa\b|\bкпа\b', 'kpa', CONVERSION_FACTORS['kpa']),
        (r'\bmpa\b|\bмпа\b', 'mpa', CONVERSION_FACTORS['mpa']),
        (r'\batm\b|\bатм\b', 'atm', CONVERSION_FACTORS['atm']),
        (r'kgf_cm2|кгс/см', 'kgf_cm2', CONVERSION_FACTORS['kgf_cm2']),
    ]
    
    for pattern, unit, factor in unit_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return unit, factor
    
    return None


def calculate_h_confidence(text: str, number_pos: int, unit: Optional[str]) -> float:
    """
    Вычисляет уверенность в том, что найденное число - это напор.
    
    Returns:
        confidence от 0.0 до 1.0
    """
    confidence = 0.5  # Базовая уверенность
    
    # Ищем ключевые слова в радиусе 50 символов
    start = max(0, number_pos - 25)
    end = min(len(text), number_pos + 50)
    context = text[start:end]
    
    # Повышаем уверенность при наличии ключевых слов напора
    for keyword in H_KEYWORDS:
        if keyword in context.lower():
            confidence += 0.2
            break
    
    # Снижаем уверенность при наличии ключевых слов НЕ напора
    for keyword in NOT_H_KEYWORDS:
        if keyword in context.lower():
            confidence -= 0.3
            break
    
    # Повышаем уверенность, если есть явная единица
    if unit:
        confidence += 0.3
    
    # Ограничиваем диапазон
    return max(0.0, min(1.0, confidence))


def extract_h_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Извлекает напор (H) из текста и приводит к метрам (м).
    
    ВАЖНО: Все единицы автоматически пересчитываются в метры!
    База данных насосов использует метры.
    
    Returns:
        {
            "h_m": float,  # значение в метрах
            "h_raw": str,  # исходная строка
            "h_unit": str,  # исходная единица
            "confidence": float,  # уверенность
            "range": Optional[Dict[str, float]]  # диапазон (если был)
        } или None
    """
    # Нормализуем текст
    normalized = normalize_h_text(text)
    
    # Ищем все возможные числа с единицами или ключевыми словами
    candidates = []
    
    # Паттерн 1: H=40, H: 40, h 40
    h_explicit_pattern = r'h\s*[=:]\s*(\d+(?:[.,]\d+)?)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм)?'
    for match in re.finditer(h_explicit_pattern, normalized, re.IGNORECASE):
        number_pos = match.start()
        number_text = match.group(0)
        
        number_result = extract_h_number(number_text)
        if not number_result:
            continue
        
        number, number_meta = number_result
        unit_result = detect_h_unit(normalized, number_pos)
        
        if not unit_result:
            # Если единица не найдена, но есть H= - предполагаем метры
            unit_result = ('m', CONVERSION_FACTORS['m'])
        
        unit, factor = unit_result
        confidence = calculate_h_confidence(normalized, number_pos, unit)
        h_m = number * factor
        
        # Валидация
        if h_m < 0.5 or h_m > 500:
            confidence *= 0.5
        
        candidates.append({
            "h_m": h_m,
            "h_raw": match.group(0),
            "h_unit": unit,
            "confidence": confidence + 0.2,  # Бонус за явный H=
            "range": number_meta.get("range") if number_meta.get("type") == "range" else None,
            "position": number_pos
        })
    
    # Паттерн 2: напор/высота/перепад + число + единица
    h_keyword_patterns = [
        r'(?:напор[а]?|высота\s+подъ[её]ма?|перепад\s+высот)\s+(\d+(?:[.,]\d+)?)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм|mm|мм|cm|см)?',
        r'(\d+(?:[.,]\d+)?)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм|mm|мм|cm|см)\s*(?:напор|высота|подъем)',
    ]
    
    for pattern in h_keyword_patterns:
        for match in re.finditer(pattern, normalized, re.IGNORECASE):
            number_pos = match.start()
            number_text = match.group(0)
            
            number_result = extract_h_number(number_text)
            if not number_result:
                continue
            
            number, number_meta = number_result
            unit_result = detect_h_unit(normalized, number_pos)
            
            if not unit_result:
                # Если единица не найдена, предполагаем метры
                unit_result = ('m', CONVERSION_FACTORS['m'])
            
            unit, factor = unit_result
            confidence = calculate_h_confidence(normalized, number_pos, unit)
            h_m = number * factor
            
            # Валидация
            if h_m < 0.5 or h_m > 500:
                confidence *= 0.5
            
            candidates.append({
                "h_m": h_m,
                "h_raw": match.group(0),
                "h_unit": unit,
                "confidence": confidence + 0.1,  # Бонус за ключевые слова
                "range": number_meta.get("range") if number_meta.get("type") == "range" else None,
                "position": number_pos
            })
    
    # Паттерн 3: давление + число + единица (бар/кПа/МПа)
    pressure_pattern = r'(?:давление|pressure)\s+(\d+(?:[.,]\d+)?)\s*(?:bar|бар|kpa|кпа|mpa|мпа|atm|атм)'
    for match in re.finditer(pressure_pattern, normalized, re.IGNORECASE):
        number_pos = match.start()
        number_text = match.group(0)
        
        number_result = extract_h_number(number_text)
        if not number_result:
            continue
        
        number, number_meta = number_result
        unit_result = detect_h_unit(normalized, number_pos)
        
        if not unit_result:
            continue  # Без единицы давления не можем пересчитать
        
        unit, factor = unit_result
        confidence = calculate_h_confidence(normalized, number_pos, unit)
        h_m = number * factor
        
        # Валидация
        if h_m < 0.5 or h_m > 500:
            confidence *= 0.5
        
        candidates.append({
            "h_m": h_m,
            "h_raw": match.group(0),
            "h_unit": unit,
            "confidence": confidence,  # Давление - меньше уверенность, чем явный напор
            "range": number_meta.get("range") if number_meta.get("type") == "range" else None,
            "position": number_pos
        })
    
    # Паттерн 4: просто число + единица напора (без ключевых слов)
    # Только если единица явная (м, bar, кПа и т.д.)
    simple_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм|mm|мм|cm|см|mh2o)\b'
    for match in re.finditer(simple_pattern, normalized, re.IGNORECASE):
        number_pos = match.start()
        number_text = match.group(0)
        
        # Пропускаем, если это уже обработано выше
        if any(c["position"] == number_pos for c in candidates):
            continue
        
        number_result = extract_h_number(number_text)
        if not number_result:
            continue
        
        number, number_meta = number_result
        unit_result = detect_h_unit(normalized, number_pos)
        
        if not unit_result:
            continue  # Без единицы не можем определить
        
        unit, factor = unit_result
        confidence = calculate_h_confidence(normalized, number_pos, unit)
        h_m = number * factor
        
        # Валидация
        if h_m < 0.5 or h_m > 500:
            confidence *= 0.5
        
        # Снижаем уверенность для простых паттернов без ключевых слов
        confidence *= 0.7
        
        candidates.append({
            "h_m": h_m,
            "h_raw": match.group(0),
            "h_unit": unit,
            "confidence": confidence,
            "range": number_meta.get("range") if number_meta.get("type") == "range" else None,
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
            -c["position"] if any(kw in normalized[max(0, c["position"]-30):c["position"]+30] for kw in H_KEYWORDS) else 0
        ))
    
    # Формируем результат
    result = {
        "h_m": best["h_m"],
        "h_raw": best["h_raw"],
        "h_unit": best["h_unit"],
        "confidence": best["confidence"],
    }
    
    if best.get("range"):
        result["range"] = best["range"]
    
    return result

