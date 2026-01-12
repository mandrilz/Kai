"""
Валидация результатов парсинга Q и H.
Проверяет разумность значений и обрабатывает edge cases.
"""
from typing import Optional, Dict, Any, Tuple


# Разумные диапазоны для насосов (в стандартных единицах: м³/ч и метры)
MIN_Q_M3H = 0.01  # Минимальный расход: 0.01 м³/ч (10 л/ч)
MAX_Q_M3H = 100000.0  # Максимальный расход: 100000 м³/ч (очень большой насос)

MIN_H_M = 0.1  # Минимальный напор: 0.1 м
MAX_H_M = 10000.0  # Максимальный напор: 10000 м (очень высокий напор)


def validate_q(q_value: float, unit: str = "m3/h") -> Tuple[bool, Optional[str]]:
    """
    Валидирует значение расхода Q.
    
    Args:
        q_value: значение расхода
        unit: единица измерения (по умолчанию м³/ч)
        
    Returns:
        (is_valid, error_message)
        - is_valid: True если значение валидно
        - error_message: сообщение об ошибке (если невалидно)
    """
    # Проверка на NaN и Infinity
    if not isinstance(q_value, (int, float)):
        return False, f"Q должно быть числом, получено: {type(q_value).__name__}"
    
    import math
    if math.isnan(q_value) or math.isinf(q_value):
        return False, f"Q не может быть NaN или Infinity: {q_value}"
    
    # Проверка на отрицательные значения
    if q_value < 0:
        return False, f"Q не может быть отрицательным: {q_value} {unit}"
    
    # Проверка на ноль
    if q_value == 0:
        return False, f"Q не может быть нулём: {q_value} {unit}"
    
    # Проверка на разумный диапазон
    if q_value < MIN_Q_M3H:
        return False, f"Q слишком маленькое: {q_value} {unit} (минимум: {MIN_Q_M3H} м³/ч)"
    
    if q_value > MAX_Q_M3H:
        return False, f"Q слишком большое: {q_value} {unit} (максимум: {MAX_Q_M3H} м³/ч)"
    
    return True, None


def validate_h(h_value: float, unit: str = "m") -> Tuple[bool, Optional[str]]:
    """
    Валидирует значение напора H.
    
    Args:
        h_value: значение напора
        unit: единица измерения (по умолчанию метры)
        
    Returns:
        (is_valid, error_message)
        - is_valid: True если значение валидно
        - error_message: сообщение об ошибке (если невалидно)
    """
    # Проверка на NaN и Infinity
    if not isinstance(h_value, (int, float)):
        return False, f"H должно быть числом, получено: {type(h_value).__name__}"
    
    import math
    if math.isnan(h_value) or math.isinf(h_value):
        return False, f"H не может быть NaN или Infinity: {h_value}"
    
    # Проверка на отрицательные значения (для насосов напор обычно положительный)
    # Но допускаем небольшие отрицательные значения (могут быть ошибки измерения)
    if h_value < -10:
        return False, f"H слишком отрицательное: {h_value} {unit} (минимум: -10 м)"
    
    # Проверка на ноль (для насосов напор должен быть > 0)
    if h_value == 0:
        return False, f"H не может быть нулём: {h_value} {unit}"
    
    # Проверка на разумный диапазон
    if h_value < MIN_H_M:
        return False, f"H слишком маленькое: {h_value} {unit} (минимум: {MIN_H_M} м)"
    
    if h_value > MAX_H_M:
        return False, f"H слишком большое: {h_value} {unit} (максимум: {MAX_H_M} м)"
    
    return True, None


def validate_qh(q_value: float, h_value: float, q_unit: str = "m3/h", h_unit: str = "m") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Валидирует пару Q и H вместе.
    
    Args:
        q_value: значение расхода
        h_value: значение напора
        q_unit: единица измерения расхода
        h_unit: единица измерения напора
        
    Returns:
        (is_valid, q_error, h_error)
        - is_valid: True если оба значения валидны
        - q_error: сообщение об ошибке для Q (если есть)
        - h_error: сообщение об ошибке для H (если есть)
    """
    q_valid, q_error = validate_q(q_value, q_unit)
    h_valid, h_error = validate_h(h_value, h_unit)
    
    is_valid = q_valid and h_valid
    
    return is_valid, q_error, h_error


def validate_parsing_result(parsing_result: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Валидирует результат парсинга из extract_qh_from_text.
    
    Args:
        parsing_result: результат парсинга {"q": float, "h": float}
        
    Returns:
        (is_valid, error_message, validated_result)
        - is_valid: True если результат валиден
        - error_message: сообщение об ошибке (если есть)
        - validated_result: валидированный результат (может быть None если невалидно)
    """
    if not parsing_result:
        return False, "Результат парсинга пуст", None
    
    q_value = parsing_result.get("q")
    h_value = parsing_result.get("h")
    
    if q_value is None:
        return False, "Q не найдено в результате парсинга", None
    
    if h_value is None:
        return False, "H не найдено в результате парсинга", None
    
    # Валидируем Q и H
    q_valid, q_error = validate_q(q_value, "m3/h")
    h_valid, h_error = validate_h(h_value, "m")
    
    if not q_valid:
        return False, q_error, None
    
    if not h_valid:
        return False, h_error, None
    
    # Все валидно
    return True, None, {
        "q": q_value,
        "h": h_value,
        "q_validated": True,
        "h_validated": True
    }
