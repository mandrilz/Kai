"""
Математика кривых насосов.
Аппроксимация кривой H(Q) и расчёт рабочей точки.
"""
import numpy as np
from scipy.optimize import root_scalar
from typing import List, Tuple, Optional
import warnings
import pandas as pd

warnings.filterwarnings("ignore")


def approximate_curve(q_points: List[float], h_points: List[float]) -> Optional[Tuple[float, float, float, float]]:
    """
    Вычисляет коэффициенты a, b, c, d для H = aQ^3 + bQ^2 + cQ + d
    на основе точек (Q, H).
    
    ИДЕНТИЧНО app.py calculate_pump_coeffs:
    - Строго для 4 точек использует np.linalg.solve
    - Если точек НЕ 4 -> возвращает None (без polyfit)
    - Возвращает None при ошибке
    
    Args:
        q_points: список значений расхода Q
        h_points: список значений напора H
        
    Returns:
        (a, b, c, d) - коэффициенты полинома или None
    """
    # В app.py: строго 4 точки, иначе None
    if len(q_points) != 4 or len(h_points) != 4:
        return None
    
    Q = np.array(q_points)
    H = np.array(h_points)
    
    # System of equations: a*Q^3 + b*Q^2 + c*Q + d = H
    # В app.py: A = np.vstack([Q**3, Q**2, Q, np.ones(len(Q))]).T
    A = np.vstack([Q**3, Q**2, Q, np.ones(len(Q))]).T
    
    try:
        coeffs = np.linalg.solve(A, H)
        # В app.py: return coeffs # [a, b, c, d]
        # Возвращаем как кортеж (для совместимости)
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
        h_st: статический напор (м), если None - используется 0.0
        q_p: расход рабочей точки (м³/ч)
        h_p: напор рабочей точки (м)
        
    Returns:
        коэффициент S
    """
    # Обрабатываем None для h_st (по умолчанию 0.0)
    if h_st is None:
        h_st = 0.0
    
    if q_p == 0:
        return 0.0
    s = (h_p - h_st) / (q_p ** 2)
    return float(s)


def network_curve_func(q: float, h_st: float, s: float) -> float:
    """
    Вычисляет напор сети для заданного расхода.
    
    Args:
        q: расход (м³/ч)
        h_st: статический напор (м), если None - используется 0.0
        s: коэффициент сопротивления сети
        
    Returns:
        напор сети H_net
    """
    # Обрабатываем None для h_st (по умолчанию 0.0)
    if h_st is None:
        h_st = 0.0
    return h_st + s * (q ** 2)


def get_q_for_h(h_val: float, a: float, b: float, c: float, d: float, q_min: float = 0.0, q_max: float = 10000.0) -> float:
    """
    Находит Q такое, что pump_curve(Q) = h_val.
    
    ИДЕНТИЧНО app.py get_q_for_h:
    - h_max = pump_curve(q_min) (только в q_min, без поиска по всей кривой)
    - if h_val > h_max: return 0
    - root_scalar(func, bracket=(q_min, q_max), method='brentq')
    - except -> return 0
    
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
        # В app.py: h_max = pump_curve_func(q_min, coeffs)
        h_max = calculate_h(q_min, a, b, c, d)
        if h_val > h_max:
            return 0
        
        # В app.py: sol = root_scalar(func, bracket=(q_min, q_max), method='brentq')
        sol = root_scalar(func, bracket=(q_min, q_max), method='brentq')
        if sol.converged:
            return sol.root
    except:
        # В app.py: except: pass; return 0
        pass
    return 0


def find_operating_point(
    pump_func,
    net_func,
    q_guess_range: Tuple[float, float] = (0.0, 10000.0),
    q_max_raw: Optional[float] = None,
    auto_bracket: bool = True
) -> Tuple[Optional[float], Optional[float]]:
    """
    Находит рабочую точку пересечения кривой насоса и сетевой кривой.
    
    ИСПРАВЛЕНО: Добавлен авто-поиск брекета для устранения "root not found".
    Не меняет математику app.py - всё равно использует brentq.
    
    Args:
        pump_func: функция насоса H = f(Q)
        net_func: функция сети H = f(Q)
        q_guess_range: диапазон поиска Q (начальный брекет)
        q_max_raw: максимальный Q из RAW_POINTS (для расширения диапазона поиска)
        auto_bracket: если True - автоматически ищет брекет с сменой знака
        
    Returns:
        (Q_op, H_op) или (None, None) если точка не найдена
    """
    def error_func(q):
        return pump_func(q) - net_func(q)
    
    # Определяем диапазон поиска
    q_min = max(0.1, q_guess_range[0])
    q_max = q_guess_range[1]
    if q_max_raw is not None:
        q_max = max(q_max, q_max_raw * 1.05)  # Расширяем до 105% от максимального Q
    
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
                "location": "curve_math.py:find_operating_point",
                "message": "Finding operating point: initial bracket",
                "data": {
                    "q_min": q_min,
                    "q_max": q_max,
                    "q_max_raw": q_max_raw,
                    "auto_bracket": auto_bracket
                },
                "sessionId": "selection",
                "runId": "operating_point",
                "hypothesisId": "F"
            }) + "\n")
    except: pass
    # #endregion
    
    # Сначала пробуем стандартный брекет (как в app.py)
    try:
        sol = root_scalar(error_func, bracket=(q_min, q_max), method='brentq')
        if sol.converged:
            q_op = sol.root
            h_op = pump_func(q_op)
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "curve_math.py:find_operating_point",
                        "message": "Operating point found: standard bracket",
                        "data": {
                            "q_op": round(q_op, 2),
                            "h_op": round(h_op, 2),
                            "bracket": [q_min, q_max]
                        },
                        "sessionId": "selection",
                        "runId": "operating_point",
                        "hypothesisId": "F"
                    }) + "\n")
            except: pass
            # #endregion
            return float(q_op), float(h_op)
    except ValueError as e:
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "curve_math.py:find_operating_point",
                    "message": "Standard bracket failed",
                    "data": {
                        "error": str(e),
                        "bracket": [q_min, q_max]
                    },
                    "sessionId": "selection",
                    "runId": "operating_point",
                    "hypothesisId": "F"
                }) + "\n")
        except: pass
        # #endregion
        pass
    
    # Если не получилось и включен авто-поиск брекета
    if auto_bracket:
        try:
            # Ищем смену знака на сетке
            n_points = 120  # Количество точек для поиска
            q_grid = np.linspace(q_min, q_max, n_points)
            errors = [error_func(q) for q in q_grid]
            
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "curve_math.py:find_operating_point",
                        "message": "Auto-bracket search: scanning grid",
                        "data": {
                            "n_points": n_points,
                            "error_range": [round(min(errors), 2), round(max(errors), 2)] if errors else None,
                            "sign_changes": sum(1 for i in range(len(errors) - 1) if errors[i] * errors[i + 1] <= 0)
                        },
                        "sessionId": "selection",
                        "runId": "operating_point",
                        "hypothesisId": "F"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Ищем соседние точки где error меняет знак
            sign_changes_found = 0
            for i in range(len(errors) - 1):
                if errors[i] * errors[i + 1] <= 0:  # Смена знака
                    sign_changes_found += 1
                    bracket_q_min = q_grid[i]
                    bracket_q_max = q_grid[i + 1]
                    
                    # Убеждаемся, что bracket_q_min < bracket_q_max
                    if bracket_q_min >= bracket_q_max:
                        continue
                    
                    try:
                        sol = root_scalar(error_func, bracket=(bracket_q_min, bracket_q_max), method='brentq')
                        if sol.converged:
                            q_op = sol.root
                            h_op = pump_func(q_op)
                            # #region agent log
                            try:
                                with open(log_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "timestamp": datetime.now().isoformat(),
                                        "location": "curve_math.py:find_operating_point",
                                        "message": "Operating point found: auto-bracket",
                                        "data": {
                                            "q_op": round(q_op, 2),
                                            "h_op": round(h_op, 2),
                                            "bracket": [round(bracket_q_min, 2), round(bracket_q_max, 2)],
                                            "sign_change_index": i
                                        },
                                        "sessionId": "selection",
                                        "runId": "operating_point",
                                        "hypothesisId": "F"
                                    }) + "\n")
                            except: pass
                            # #endregion
                            return float(q_op), float(h_op)
                    except ValueError as e:
                        # #region agent log
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "timestamp": datetime.now().isoformat(),
                                    "location": "curve_math.py:find_operating_point",
                                    "message": "Auto-bracket attempt failed",
                                    "data": {
                                        "bracket": [round(bracket_q_min, 2), round(bracket_q_max, 2)],
                                        "error": str(e)
                                    },
                                    "sessionId": "selection",
                                    "runId": "operating_point",
                                    "hypothesisId": "F"
                                }) + "\n")
                        except: pass
                        # #endregion
                        continue
            
            # #region agent log
            if sign_changes_found == 0:
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "curve_math.py:find_operating_point",
                            "message": "No sign change found in grid",
                            "data": {
                                "q_range": [q_min, q_max],
                                "error_range": [round(min(errors), 2), round(max(errors), 2)] if errors else None
                            },
                            "sessionId": "selection",
                            "runId": "operating_point",
                            "hypothesisId": "F"
                        }) + "\n")
                except: pass
            # #endregion
        except Exception as e:
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "curve_math.py:find_operating_point",
                        "message": "Auto-bracket search exception",
                        "data": {"error": str(e)},
                        "sessionId": "selection",
                        "runId": "operating_point",
                        "hypothesisId": "F"
                    }) + "\n")
            except: pass
            # #endregion
            pass
    
    # #region agent log
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "curve_math.py:find_operating_point",
                "message": "Operating point not found",
                "data": {
                    "q_range": [q_min, q_max],
                    "auto_bracket": auto_bracket
                },
                "sessionId": "selection",
                "runId": "operating_point",
                "hypothesisId": "F"
            }) + "\n")
    except: pass
    # #endregion
    
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


def extract_points(row: dict, schema: str = "kometta") -> List[Tuple[float, float]]:
    """
    Нормализованная функция извлечения точек кривой из строки DataFrame.
    Работает с форматами Kometta и Competitors.
    
    Args:
        row: строка DataFrame
        schema: "kometta" или "competitors"
            - kometta: пары идут как graphic_h_1, graphic_q_1, graphic_h_2, graphic_q_2, ... (до 11)
            - competitors: сначала graphic_q_1..graphic_q_14, потом graphic_h_1..graphic_h_14
    
    Returns:
        points: список кортежей [(q1, h1), (q2, h2), ...] - только валидные, без NaN, отсортированные по Q
    """
    points = []
    
    if schema == "kometta":
        # Формат Kometta: graphic_h_1, graphic_q_1, graphic_h_2, graphic_q_2, ...
        for i in range(1, 12):  # до 11 точек
            h_col = f"graphic_h_{i}"
            q_col = f"graphic_q_{i}"
            
            if h_col in row and q_col in row:
                h_val = row[h_col]
                q_val = row[q_col]
                
                # Пропускаем NaN, None, 0 если точка явно пустая
                if (not (pd.isna(h_val) or pd.isna(q_val) or h_val == 0 or q_val == 0)):
                    try:
                        h = float(h_val)
                        q = float(q_val)
                        if h > 0 and q > 0:  # Только положительные значения
                            points.append((q, h))
                    except (ValueError, TypeError):
                        continue
    
    elif schema == "competitors":
        # Формат Competitors: сначала graphic_q_1..graphic_q_14, потом graphic_h_1..graphic_h_14
        q_list = []
        h_list = []
        
        for i in range(1, 15):  # до 14 точек
            q_col = f"graphic_q_{i}"
            h_col = f"graphic_h_{i}"
            
            if q_col in row:
                q_val = row[q_col]
                if not (pd.isna(q_val) or q_val == 0):
                    try:
                        q = float(q_val)
                        if q > 0:
                            q_list.append(q)
                    except (ValueError, TypeError):
                        pass
            
            if h_col in row:
                h_val = row[h_col]
                if not (pd.isna(h_val) or h_val == 0):
                    try:
                        h = float(h_val)
                        if h > 0:
                            h_list.append(h)
                    except (ValueError, TypeError):
                        pass
        
        # Объединяем пары (предполагаем, что индексы соответствуют)
        min_len = min(len(q_list), len(h_list))
        for i in range(min_len):
            points.append((q_list[i], h_list[i]))
    
    # Сортируем по Q возрастанию
    points.sort(key=lambda x: x[0])
    
    # Убираем дубликаты Q (оставляем одну точку, например с максимальным H)
    if points:
        unique_points = []
        current_q = points[0][0]
        current_points = [points[0]]
        
        for q, h in points[1:]:
            if abs(q - current_q) < 1e-6:  # Дубликат Q (с учетом погрешности)
                current_points.append((q, h))
            else:
                # Сохраняем точку с максимальным H из дубликатов
                unique_points.append(max(current_points, key=lambda x: x[1]))
                current_q = q
                current_points = [(q, h)]
        
        # Добавляем последнюю группу
        if current_points:
            unique_points.append(max(current_points, key=lambda x: x[1]))
        
        points = unique_points
    
    return points


def choose_fit_points_4(raw_points: List[Tuple[float, float]]) -> Optional[List[Tuple[float, float]]]:
    """
    Выбирает детерминированно 4 опорные точки из RAW_POINTS для аппроксимации кубиком.
    
    Алгоритм:
    1. Если точек < 4 → возвращает None (skip pump)
    2. Выбирает 4 точки:
       - p0 = min Q
       - p3 = max Q
       - p1 = ближайшая к Q_min + 1/3*(Q_max-Q_min)
       - p2 = ближайшая к Q_min + 2/3*(Q_max-Q_min)
    3. Убеждается, что все 4 точки имеют разные Q (если совпали — сдвигает выбор)
    
    Args:
        raw_points: список кортежей [(q1, h1), (q2, h2), ...] - отсортированные по Q
        
    Returns:
        fit_points: список из 4 кортежей [(q, h), ...] или None если точек < 4
    """
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
                "location": "curve_math.py:choose_fit_points_4",
                "message": "Choosing 4 fit points",
                "data": {
                    "raw_points_count": len(raw_points),
                    "raw_points_sample": [(round(p[0], 2), round(p[1], 2)) for p in raw_points[:10]] if raw_points else []
                },
                "sessionId": "selection",
                "runId": "fit_points_selection",
                "hypothesisId": "E"
            }) + "\n")
    except: pass
    # #endregion
    
    if len(raw_points) < 4:
        return None
    
    # Уже отсортированы по Q
    q_min = raw_points[0][0]
    q_max = raw_points[-1][0]
    q_range = q_max - q_min
    
    if q_range < 1e-6:  # Все точки имеют одинаковый Q
        return None
    
    # Выбираем 4 точки
    p0 = raw_points[0]  # min Q
    p3 = raw_points[-1]  # max Q
    
    # Целевые Q для p1 и p2
    target_q1 = q_min + q_range / 3.0
    target_q2 = q_min + 2.0 * q_range / 3.0
    
    # Находим ближайшие точки
    p1 = min(raw_points, key=lambda p: abs(p[0] - target_q1))
    p2 = min(raw_points, key=lambda p: abs(p[0] - target_q2))
    
    # Убеждаемся, что все 4 точки имеют разные Q
    fit_points = [p0, p1, p2, p3]
    q_values = [p[0] for p in fit_points]
    
    # Проверяем на дубликаты Q
    if len(set(q_values)) < 4:
        # Есть дубликаты - выбираем альтернативные точки
        # Для p1 и p2 ищем соседние точки, если совпали
        if abs(p1[0] - p0[0]) < 1e-6 or abs(p1[0] - p2[0]) < 1e-6 or abs(p1[0] - p3[0]) < 1e-6:
            # Ищем альтернативную точку для p1
            for p in raw_points:
                if (abs(p[0] - p0[0]) > 1e-6 and abs(p[0] - p2[0]) > 1e-6 and 
                    abs(p[0] - p3[0]) > 1e-6 and abs(p[0] - target_q1) < abs(p1[0] - target_q1) * 2):
                    p1 = p
                    break
        
        if abs(p2[0] - p0[0]) < 1e-6 or abs(p2[0] - p1[0]) < 1e-6 or abs(p2[0] - p3[0]) < 1e-6:
            # Ищем альтернативную точку для p2
            for p in raw_points:
                if (abs(p[0] - p0[0]) > 1e-6 and abs(p[0] - p1[0]) > 1e-6 and 
                    abs(p[0] - p3[0]) > 1e-6 and abs(p[0] - target_q2) < abs(p2[0] - target_q2) * 2):
                    p2 = p
                    break
        
        fit_points = [p0, p1, p2, p3]
        q_values = [p[0] for p in fit_points]
        
        # Если все еще есть дубликаты - возвращаем None
        if len(set(q_values)) < 4:
            return None
    
    return fit_points


def select_4_points(q_points: List[float], h_points: List[float]) -> Tuple[List[float], List[float]]:
    """
    Выбирает ровно 4 ключевые точки из списка точек для аппроксимации.
    Если точек меньше 4, возвращает все точки.
    Если точек больше 4, выбирает: [minQ, 1/3, 2/3, maxQ] по индексам после сортировки.
    
    Args:
        q_points: список расходов Q
        h_points: список напоров H
        
    Returns:
        (q_selected, h_selected) - ровно 4 точки или меньше если исходных меньше
    """
    if len(q_points) < 4:
        return q_points, h_points
    
    # Сортируем по Q
    sorted_pairs = sorted(zip(q_points, h_points), key=lambda x: x[0])
    sorted_q = [p[0] for p in sorted_pairs]
    sorted_h = [p[1] for p in sorted_pairs]
    
    n = len(sorted_q)
    # Выбираем индексы: [0, n//3, 2*n//3, n-1]
    indices = [0, n // 3, 2 * n // 3, n - 1]
    
    q_selected = [sorted_q[i] for i in indices]
    h_selected = [sorted_h[i] for i in indices]
    
    return q_selected, h_selected

