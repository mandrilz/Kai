"""
Математика кривых насосов.
Аппроксимация кривой H(Q) и расчёт рабочей точки.
"""
import numpy as np
from scipy.optimize import root_scalar
from typing import List, Tuple, Optional
import warnings

warnings.filterwarnings("ignore")


def approximate_curve(q_points: List[float], h_points: List[float]) -> Optional[Tuple[float, float, float, float]]:
    """
    Вычисляет коэффициенты a, b, c, d для H = aQ^3 + bQ^2 + cQ + d
    на основе точек (Q, H).
    
    ИДЕНТИЧНО app.py calculate_pump_coeffs:
    - Принимает точки как есть (без фильтрации NaN/нулей)
    - Решает систему уравнений для любого количества точек
    - Возвращает None при ошибке
    
    Args:
        q_points: список значений расхода Q
        h_points: список значений напора H
        
    Returns:
        (a, b, c, d) - коэффициенты полинома или None
    """
    # В app.py: Q = np.array([p[0] for p in points]), H = np.array([p[1] for p in points])
    # НО: в моем случае уже есть два списка, преобразуем в массив
    Q = np.array(q_points)
    H = np.array(h_points)
    
    # В app.py НЕТ фильтрации NaN и нулей! Берем точки как есть
    # System of equations: a*Q^3 + b*Q^2 + c*Q + d = H
    # В app.py: A = np.vstack([Q**3, Q**2, Q, np.ones(len(Q))]).T
    A = np.vstack([Q**3, Q**2, Q, np.ones(len(Q))]).T
    
    try:
        coeffs = np.linalg.solve(A, H)
        # В app.py: return coeffs # [a, b, c, d]
        # Возвращаем как кортеж (для совместимости с остальным кодом)
        return float(coeffs[0]), float(coeffs[1]), float(coeffs[2]), float(coeffs[3])
    except np.linalg.LinAlgError:
        # В app.py: return None
        return None


def calculate_h(q: float, a: float, b: float, c: float, d: float) -> float:
    """
    Вычисляет напор H для заданного расхода Q по аппроксимированной кривой.
    
    Args:
        q: расход
        a, b, c, d: коэффициенты полинома
        
    Returns:
        напор H
    """
    return a * (q ** 3) + b * (q ** 2) + c * q + d


def calculate_working_point(
    q_user: float,
    h_user: float,
    a: float,
    b: float,
    c: float,
    d: float,
    h_st: float = 0.0,
    s: float = 0.0
) -> Tuple[float, float]:
    """
    Вычисляет рабочую точку насоса с учётом сетевой кривой.
    
    Сетевая кривая: H_net = H_st + S*Q²
    
    Args:
        q_user: желаемый расход пользователя
        h_user: желаемый напор пользователя
        a, b, c, d: коэффициенты кривой насоса
        h_st: статический напор сети
        s: коэффициент сопротивления сети
        
    Returns:
        (Q_work, H_work) - рабочая точка
    """
    if s == 0 and h_st == 0:
        # Просто проверяем точку на кривой
        h_pump = calculate_h(q_user, a, b, c, d)
        return q_user, h_pump
    
    # Ищем пересечение кривой насоса и сетевой кривой
    def equation(q):
        h_pump = calculate_h(q, a, b, c, d)
        h_net = h_st + s * (q ** 2)
        return h_pump - h_net
    
    try:
        result = root_scalar(equation, bracket=[0.1, q_user * 2], method='brentq')
        q_work = result.root
        h_work = calculate_h(q_work, a, b, c, d)
        return q_work, h_work
    except (ValueError, RuntimeError):
        # Если не нашли пересечение, возвращаем точку на кривой
        h_pump = calculate_h(q_user, a, b, c, d)
        return q_user, h_pump


def calculate_rmse(
    q_points: List[float],
    h_points_actual: List[float],
    a: float,
    b: float,
    c: float,
    d: float
) -> float:
    """
    Вычисляет RMSE между фактическими точками и аппроксимированной кривой.
    
    Args:
        q_points: список расходов
        h_points_actual: список фактических напоров
        a, b, c, d: коэффициенты аппроксимации
        
    Returns:
        RMSE
    """
    h_predicted = [calculate_h(q, a, b, c, d) for q in q_points]
    errors = [(h_act - h_pred) ** 2 for h_act, h_pred in zip(h_points_actual, h_predicted)]
    return np.sqrt(np.mean(errors))


def calculate_network_coeffs(h_st: float, q_p: float, h_p: float) -> float:
    """
    Вычисляет коэффициент S для сетевой кривой: H_net = H_st + S * Q^2
    
    Args:
        h_st: статический напор (м)
        q_p: расход рабочей точки (м³/ч)
        h_p: напор рабочей точки (м)
        
    Returns:
        коэффициент S
    """
    if q_p == 0:
        return 0.0
    s = (h_p - h_st) / (q_p ** 2)
    return float(s)


def network_curve_func(q: float, h_st: float, s: float) -> float:
    """
    Вычисляет напор сети для заданного расхода.
    
    Args:
        q: расход (м³/ч)
        h_st: статический напор (м)
        s: коэффициент сопротивления сети
        
    Returns:
        напор сети H_net
    """
    return h_st + s * (q ** 2)


def get_q_for_h(h_val: float, a: float, b: float, c: float, d: float, q_min: float = 0.0, q_max: float = 10000.0) -> float:
    """
    Находит Q такое, что pump_curve(Q) = h_val.
    
    Args:
        h_val: заданный напор (м)
        a, b, c, d: коэффициенты кривой насоса
        q_min, q_max: диапазон поиска Q
        
    Returns:
        расход Q (м³/ч) или 0 если решение не найдено
    """
    def func(q):
        return calculate_h(q, a, b, c, d) - h_val
    
    try:
        # Проверяем, возможно ли решение в диапазоне
        h_max = calculate_h(q_min, a, b, c, d)
        if h_val > h_max:
            return 0.0
        
        sol = root_scalar(func, bracket=(q_min, q_max), method='brentq')
        if sol.converged:
            return float(sol.root)
    except:
        # В app.py: except: pass
        pass
    return 0.0


def find_operating_point(
    pump_func,
    net_func,
    q_guess_range: Tuple[float, float] = (0.0, 10000.0)
) -> Tuple[Optional[float], Optional[float]]:
    """
    Находит рабочую точку пересечения кривой насоса и сетевой кривой.
    
    Args:
        pump_func: функция насоса H = f(Q)
        net_func: функция сети H = f(Q)
        q_guess_range: диапазон поиска Q
        
    Returns:
        (Q_op, H_op) или (None, None) если точка не найдена
    """
    def error_func(q):
        return pump_func(q) - net_func(q)
    
    try:
        # Try to find a root in the reasonable range
        # We assume Q > 0 (как в app.py)
        sol = root_scalar(error_func, bracket=q_guess_range, method='brentq')
        if sol.converged:
            q_op = sol.root
            h_op = pump_func(q_op)
            return float(q_op), float(h_op)
    except ValueError:
        # В app.py: except ValueError: pass
        pass
    return None, None


def extract_curve_points(row: dict, prefix: str = "graphic") -> Tuple[List[float], List[float]]:
    """
    Извлекает точки кривой из строки DataFrame.
    
    Args:
        row: строка DataFrame
        prefix: префикс колонок (graphic_q_1, graphic_h_1, ...)
        
    Returns:
        (q_points, h_points)
    """
    q_points = []
    h_points = []
    
    for i in range(1, 15):  # graphic_q_1 ... graphic_q_14
        q_col = f"{prefix}_q_{i}"
        h_col = f"{prefix}_h_{i}"
        
        if q_col in row and h_col in row:
            q_val = row[q_col]
            h_val = row[h_col]
            
            # Пропускаем NaN и нули
            if not (np.isnan(q_val) or np.isnan(h_val) or q_val == 0 or h_val == 0):
                q_points.append(float(q_val))
                h_points.append(float(h_val))
    
    return q_points, h_points

