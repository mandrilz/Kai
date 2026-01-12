"""
API endpoint для генерации графиков кривых насосов.
Полная интеграция логики из app.py
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
import matplotlib
matplotlib.use('Agg')  # Неинтерактивный backend
import matplotlib.pyplot as plt
import io
import numpy as np
from services.selector import get_pump_curve_data, find_competitor_model
from services.curve_math import (
    calculate_h, 
    extract_curve_points, 
    approximate_curve,
    choose_fit_points_4,
    calculate_network_coeffs,
    network_curve_func,
    find_operating_point,
    get_q_for_h
)

router = APIRouter()

PLOT_BG = "none"  # transparent for dark/light themes
PLOT_TEXT = "#EDEDED"
PLOT_TICK = "#B5B5B5"
PLOT_GRID = "#B5B5B5"
PLOT_SPINE = "#3A3A3A"


def apply_ui_plot_style(fig, ax):
    """
    Делает график читаемым на тёмном bubble UI:
    - прозрачный фон (чтобы подложка сообщения задавала цвет)
    - светлые подписи/тики
    - аккуратная сетка
    - легенда без белого бокса
    """
    try:
        fig.patch.set_alpha(0)
        fig.patch.set_facecolor(PLOT_BG)
    except Exception:
        pass
    try:
        ax.set_facecolor(PLOT_BG)
    except Exception:
        pass

    # Оси/тики
    ax.tick_params(axis="both", colors=PLOT_TICK, labelsize=11)
    ax.xaxis.label.set_color(PLOT_TEXT)
    ax.yaxis.label.set_color(PLOT_TEXT)
    ax.xaxis.label.set_fontsize(13)
    ax.yaxis.label.set_fontsize(13)
    ax.xaxis.label.set_fontweight("bold")
    ax.yaxis.label.set_fontweight("bold")

    # Spine colors
    for spine in ax.spines.values():
        spine.set_color(PLOT_SPINE)
        spine.set_linewidth(1.0)

    # Grid
    ax.grid(True, alpha=0.18, color=PLOT_GRID, linewidth=0.8)

    # Legend (no white box)
    leg = ax.get_legend()
    if leg is not None:
        leg.set_frame_on(False)
        for t in leg.get_texts():
            t.set_color(PLOT_TEXT)
            t.set_fontsize(10)


class PlotRequest(BaseModel):
    """Запрос на построение графика сравнения (старый формат)"""
    kometta_articul: Optional[str] = None
    competitor_model: Optional[str] = None
    q_min: Optional[float] = None
    q_max: Optional[float] = None
    
    def validate(self):
        """Валидация запроса."""
        if not self.kometta_articul or not self.kometta_articul.strip():
            raise ValueError("kometta_articul не может быть пустым")
        
        if self.q_min is not None and self.q_max is not None:
            if self.q_min >= self.q_max:
                raise ValueError("q_min должен быть меньше q_max")
        
        if self.q_min is not None and self.q_min < 0:
            raise ValueError("q_min не может быть отрицательным")
        
        if self.q_max is not None and self.q_max < 0:
            raise ValueError("q_max не может быть отрицательным")


class ComparePlotRequest(BaseModel):
    """
    Запрос на построение графика сравнения (MVP-формат).
    По ТЗ: POST /api/plot/compare → PNG.
    """
    kometta_articul: str
    competitor_articul: Optional[str] = None
    competitor_model: Optional[str] = None
    q_min: Optional[float] = None
    q_max: Optional[float] = None

    def validate(self):
        if not self.kometta_articul or not self.kometta_articul.strip():
            raise ValueError("kometta_articul не может быть пустым")
        if self.q_min is not None and self.q_max is not None and self.q_min >= self.q_max:
            raise ValueError("q_min должен быть меньше q_max")
        if self.q_min is not None and self.q_min < 0:
            raise ValueError("q_min не может быть отрицательным")
        if self.q_max is not None and self.q_max < 0:
            raise ValueError("q_max не может быть отрицательным")


class AdvancedPlotRequest(BaseModel):
    """Расширенный запрос с поддержкой всех режимов из app.py"""
    mode: str = "1"  # "1" - один насос, "2" - параллельно одинаковые, "3" - параллельно разные, "4" - последовательно
    # Насос 1
    pump1_articul: Optional[str] = None
    pump1_points: Optional[List[Dict[str, float]]] = None  # [{"q": 0, "h": 100}, ...]
    # Насос 2 (для режима 3)
    pump2_articul: Optional[str] = None
    pump2_points: Optional[List[Dict[str, float]]] = None
    # Сеть
    h_st: float = 20.0  # Статический напор
    q_p: float = 100.0  # Q рабочей точки
    h_p: float = 60.0   # H рабочей точки
    # Количество насосов (для режимов 2 и 4)
    num_pumps: int = 2
    # Для режима 3
    n1: int = 1  # Количество насосов группы 1
    n2: int = 1  # Количество насосов группы 2
    
    def validate(self):
        """Валидация запроса."""
        # Валидация режима
        if self.mode not in ["1", "2", "3", "4"]:
            raise ValueError(f"Неподдерживаемый режим: {self.mode}. Поддерживаются: 1, 2, 3, 4")
        
        # Валидация насоса 1
        if not self.pump1_articul and not self.pump1_points:
            raise ValueError("Необходимо указать pump1_articul или pump1_points")
        
        if self.pump1_points:
            if len(self.pump1_points) < 2:
                raise ValueError("pump1_points должен содержать минимум 2 точки")
            for point in self.pump1_points:
                if "q" not in point or "h" not in point:
                    raise ValueError("Каждая точка в pump1_points должна содержать 'q' и 'h'")
        
        # Валидация насоса 2 (для режима 3)
        if self.mode == "3":
            if not self.pump2_articul and not self.pump2_points:
                raise ValueError("Для режима 3 необходимо указать pump2_articul или pump2_points")
            
            if self.pump2_points:
                if len(self.pump2_points) < 2:
                    raise ValueError("pump2_points должен содержать минимум 2 точки")
                for point in self.pump2_points:
                    if "q" not in point or "h" not in point:
                        raise ValueError("Каждая точка в pump2_points должна содержать 'q' и 'h'")
        
        # Валидация параметров сети
        if self.h_st < 0:
            raise ValueError("h_st не может быть отрицательным")
        
        if self.q_p <= 0:
            raise ValueError("q_p должен быть положительным")
        
        if self.h_p <= 0:
            raise ValueError("h_p должен быть положительным")
        
        # Валидация количества насосов
        if self.num_pumps < 1:
            raise ValueError("num_pumps должен быть >= 1")
        
        if self.mode == "3":
            if self.n1 < 1 or self.n2 < 1:
                raise ValueError("n1 и n2 должны быть >= 1")


def get_pump_coeffs_from_data(pump_data: Optional[Dict[str, Any]] = None, points: Optional[List[Dict[str, float]]] = None) -> Optional[Tuple[float, float, float, float]]:
    """
    Получает коэффициенты насоса из данных или точек.
    
    Args:
        pump_data: данные насоса (с coefficients)
        points: список точек [{"q": 0, "h": 100}, ...]
        
    Returns:
        (a, b, c, d) или None
    """
    if pump_data and "coefficients" in pump_data:
        coeffs = pump_data["coefficients"]
        return coeffs["a"], coeffs["b"], coeffs["c"], coeffs["d"]
    
    if points and len(points) >= 2:
        q_points = [p["q"] for p in points]
        h_points = [p["h"] for p in points]
        return approximate_curve(q_points, h_points)
    
    return None


def generate_advanced_plot(request: AdvancedPlotRequest) -> bytes:
    """
    Генерирует график с поддержкой всех режимов из app.py.
    """
    # Переменная для сохранения последних combined_points (режим 3) - как в app.py
    combined_points = None
    
    # 1. Получаем коэффициенты насоса 1
    pump1_coeffs = None
    pump1_data = None
    q_min_1 = 0.0
    q_max_1 = 100.0
    
    if request.pump1_articul:
        pump1_data = get_pump_curve_data(request.pump1_articul)
        if pump1_data:
            pump1_coeffs = get_pump_coeffs_from_data(pump1_data)
            if pump1_data.get("q_points"):
                q_min_1 = min(pump1_data["q_points"])
                q_max_1 = max(pump1_data["q_points"])
    elif request.pump1_points:
        pump1_coeffs = get_pump_coeffs_from_data(points=request.pump1_points)
        if pump1_coeffs:
            q_min_1 = min(p["q"] for p in request.pump1_points)
            q_max_1 = max(p["q"] for p in request.pump1_points)
    
    if pump1_coeffs is None:
        raise HTTPException(status_code=400, detail="Не указаны данные насоса 1")
    
    a1, b1, c1, d1 = pump1_coeffs
    
    # 2. Получаем коэффициенты насоса 2 (для режима 3)
    pump2_coeffs = None
    q_min_2 = 0.0
    q_max_2 = 100.0
    
    if request.mode == "3":
        if request.pump2_articul:
            pump2_data = get_pump_curve_data(request.pump2_articul)
            if pump2_data:
                pump2_coeffs = get_pump_coeffs_from_data(pump2_data)
                if pump2_data.get("q_points"):
                    q_min_2 = min(pump2_data["q_points"])
                    q_max_2 = max(pump2_data["q_points"])
        elif request.pump2_points:
            pump2_coeffs = get_pump_coeffs_from_data(points=request.pump2_points)
            if pump2_coeffs:
                q_min_2 = min(p["q"] for p in request.pump2_points)
                q_max_2 = max(p["q"] for p in request.pump2_points)
        
        if pump2_coeffs is None:
            raise HTTPException(status_code=400, detail="Для режима 3 необходимо указать данные насоса 2")
    
    # 3. Вычисляем сетевую кривую
    s = calculate_network_coeffs(request.h_st, request.q_p, request.h_p)
    def net_func(q):
        return network_curve_func(q, request.h_st, s)
    
    # 4. Подготавливаем сценарии (кривые для построения)
    scenarios = []
    
    def get_safe_h(q, coeffs):
        if coeffs is None:
            return 0.0
        a, b, c, d = coeffs
        val = calculate_h(q, a, b, c, d)
        return val if val is not None and val >= 0 else 0.0
    
    if request.mode == "1":
        # Один насос / Одна сеть
        scenarios.append({
            "name": "Насос 1",
            "func": lambda Q: get_safe_h(Q, pump1_coeffs),
            "q_range": (q_min_1, q_max_1),
            "color": "#003366"
        })
    
    elif request.mode == "2":
        # Параллельно (Одинаковые)
        for i in range(1, request.num_pumps + 1):
            def make_func(n):
                return lambda Q: get_safe_h(Q / n, pump1_coeffs)
            scenarios.append({
                "name": f"{i} Насос(а/ов)",
                "func": make_func(i),
                "q_range": (q_min_1 * i, q_max_1 * i),
                "color": f"rgba(0, 51, 102, {0.4 + 0.6 * i/request.num_pumps})"
            })
    
    elif request.mode == "4":
        # Последовательно (Одинаковые)
        for i in range(1, request.num_pumps + 1):
            def make_func(n):
                return lambda Q: n * get_safe_h(Q, pump1_coeffs)
            scenarios.append({
                "name": f"{i} Насос(а/ов)",
                "func": make_func(i),
                "q_range": (q_min_1, q_max_1),
                "color": f"rgba(0, 51, 102, {0.4 + 0.6 * i/request.num_pumps})"
            })
    
    elif request.mode == "3":
        # Параллельно (Разные) - полностью идентично app.py
        # Определяем доминирующую группу (больший напор при Q=0)
        h1_shutoff = get_safe_h(0, pump1_coeffs)
        h2_shutoff = get_safe_h(0, pump2_coeffs)
        
        # Default: Group 1 is dominant (как в app.py)
        dom_coeffs = pump1_coeffs
        sec_coeffs = pump2_coeffs
        dom_n = request.n1
        sec_n = request.n2
        dom_name = "Гр1"
        sec_name = "Гр2"
        dom_q_min = q_min_1
        dom_q_max = q_max_1
        sec_q_min = q_min_2
        sec_q_max = q_max_2
        
        if h2_shutoff > h1_shutoff:
            # Group 2 is dominant
            dom_coeffs = pump2_coeffs
            sec_coeffs = pump1_coeffs
            dom_n = request.n2
            sec_n = request.n1
            dom_name = "Гр2"
            sec_name = "Гр1"
            dom_q_min = q_min_2
            dom_q_max = q_max_2
            sec_q_min = q_min_1
            sec_q_max = q_max_1
        
        total_pumps = dom_n + sec_n
        
        for k in range(1, total_pumps + 1):
            curr_dom = min(k, dom_n)
            curr_sec = max(0, k - dom_n)
            
            if curr_sec == 0:
                # Case A: Only Dominant pumps (Standard Parallel) - как в app.py
                def make_func(n):
                    return lambda Q: get_safe_h(Q / n, dom_coeffs)
                scenarios.append({
                    "name": f"{k}x{dom_name} (N={k})",
                    "func": make_func(curr_dom),
                    "q_range": (dom_q_min * curr_dom, dom_q_max * curr_dom),
                    "color": f"rgba(0, 51, 102, {0.3 + 0.7 * k/total_pumps})"
                })
            else:
                # Смешанная группа
                h_dom_max = get_safe_h(0, dom_coeffs)
                h_dom_min = get_safe_h(dom_q_max, dom_coeffs)
                h_sec_max = get_safe_h(0, sec_coeffs)
                h_sec_min = get_safe_h(sec_q_max, sec_coeffs)
                
                h_range_max = min(h_dom_max, h_sec_max)
                h_range_min = max(h_dom_min, h_sec_min)
                
                if h_range_max > h_range_min:
                    h_points = np.linspace(h_range_min, h_range_max, 4)
                    combined_points = []
                    for h in h_points:
                        # В app.py: get_q_for_h(h, dom_coeffs, 0, dom_q_max * 1.5)
                        # где dom_coeffs это кортеж (a, b, c, d), распаковываем его
                        q_d = get_q_for_h(h, *dom_coeffs, 0, dom_q_max * 1.5)
                        q_s = get_q_for_h(h, *sec_coeffs, 0, sec_q_max * 1.5)
                        q_tot = curr_dom * q_d + curr_sec * q_s
                        combined_points.append([q_tot, h])
                    
                    combined_points_fit = np.array(combined_points)
                    combined_q_max = np.max(combined_points_fit[:, 0])
                    combined_q_min = np.min(combined_points_fit[:, 0])
                    
                    # Fit new polynomial - используем calculate_pump_coeffs логику (через approximate_curve)
                    # В app.py: combined_coeffs = calculate_pump_coeffs(combined_points_fit)
                    # combined_points_fit это массив [[q, h], ...], нужно преобразовать
                    q_list = combined_points_fit[:, 0].tolist()
                    h_list = combined_points_fit[:, 1].tolist()
                    combined_coeffs = approximate_curve(q_list, h_list)
                    
                    if combined_coeffs is not None:
                        def make_mixed_func(coeffs):
                            return lambda Q: get_safe_h(Q, coeffs)
                        scenarios.append({
                            "name": f"{curr_dom}x{dom_name} + {curr_sec}x{sec_name} (N={k})",
                            "func": make_mixed_func(combined_coeffs),
                            "q_range": (combined_q_min, combined_q_max),  # Start from calculated min Q (как в app.py)
                            "color": f"rgba(0, 51, 102, {0.3 + 0.7 * k/total_pumps})"
                        })
                        
                        # Save the LAST combined points for visualization (как в app.py)
                        if k == total_pumps:
                            combined_points = combined_points_fit
    
    # 5. Строим график
    fig, ax = plt.subplots(figsize=(10, 6))
    
    global_max_q = 0.0
    global_max_h = 0.0
    operating_points = []
    
    for sc in scenarios:
        q_start, q_end = sc["q_range"]
        q_start = max(0, q_start)
        global_max_q = max(global_max_q, q_end)
        
        # Находим рабочую точку (как в app.py)
        Q_op, H_op = find_operating_point(sc["func"], net_func, (0.1, q_end))
        
        if Q_op is not None:
            operating_points.append((Q_op, H_op, sc["name"]))
            global_max_h = max(global_max_h, H_op)
            
            # Plot Pump Curve strictly in range (как в app.py)
            q_plot = np.linspace(q_start, q_end, 100)
            h_plot = []
            valid_q = []
            for q in q_plot:
                h = sc["func"](q)
                if h is not None and h >= 0:
                    h_plot.append(h)
                    valid_q.append(q)
            if h_plot:
                global_max_h = max(global_max_h, max(h_plot))
            ax.plot(valid_q, h_plot, color=sc["color"], linewidth=3, label=sc["name"])
        else:
            # Fallback plot (как в app.py)
            q_plot = np.linspace(q_start, q_end, 100)
            h_plot = [sc["func"](q) for q in q_plot]
            # Filter negative
            h_plot = [h if h >= 0 else 0 for h in h_plot]
            ax.plot(q_plot, h_plot, color=sc["color"], linewidth=3, linestyle='--', label=sc["name"])
            if h_plot:
                global_max_h = max(global_max_h, max(h_plot))
    
    # Строим сетевую кривую
    if operating_points:
        net_max_q = max(op[0] for op in operating_points)
    else:
        net_max_q = global_max_q * 1.1 if global_max_q > 0 else 100
    
    q_net = np.linspace(0, net_max_q, 100)
    h_net = [net_func(q) for q in q_net]
    if h_net:
        global_max_h = max(global_max_h, max(h_net))
    ax.plot(q_net, h_net, color='#FF6600', linewidth=3, label='Сеть')
    
    # Отмечаем рабочие точки
    for op in operating_points:
        ax.scatter([op[0]], [op[1]], color='red', s=120, marker='x', linewidths=3, zorder=5, label=f'Р.Т. {op[2]}' if op == operating_points[0] else '')
        ax.annotate(f"{op[1]:.1f}", (op[0], op[1]), textcoords="offset points", xytext=(10, 10), fontsize=10)
    
    # Отмечаем точку сети (Design)
    ax.scatter([request.q_p], [request.h_p], color='orange', s=100, marker='o', linewidths=2, edgecolors='black', label='Точка Сети (Design)', zorder=5)
    
    # Plot Interpolation Points (Mode 3) - как в app.py
    if request.mode == "3" and combined_points is not None:
        ax.scatter(combined_points[:, 0], combined_points[:, 1], color='purple', s=100, marker='D', linewidths=1, edgecolors='black', label='Опорные точки (Финал)', zorder=5)
    
    # Настройка осей
    ax.set_xlabel("Подача Q, м³/ч")
    ax.set_ylabel("Напор H, м")
    # По ТЗ: заголовка быть не должно
    ax.set_title("")
    ax.set_xlim(0, global_max_q * 1.1)
    ax.set_ylim(0, global_max_h * 1.1)
    ax.grid(True, alpha=0.3, which='both')
    ax.axhline(y=0, color='black', linewidth=2)
    ax.axvline(x=0, color='black', linewidth=2)
    ax.legend(loc='upper right')

    apply_ui_plot_style(fig, ax)
    
    # Сохраняем
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', transparent=True, pad_inches=0.02)
    plt.close()
    
    buf.seek(0)
    return buf.read()


@router.get("/plot/compare")
async def plot_compare(
    kometta_articul: str = Query(..., description="Артикул насоса Кометта"),
    competitor_articul: Optional[str] = Query(None, description="Артикул насоса конкурента"),
    q_min: Optional[float] = Query(None, description="Минимальный расход Q"),
    q_max: Optional[float] = Query(None, description="Максимальный расход Q")
):
    """
    Генерирует график сравнения кривых насосов (GET endpoint для использования в ссылках).
    """
    try:
        # Создаем объект запроса для валидации
        request = PlotRequest(
            kometta_articul=kometta_articul,
            competitor_model=competitor_articul,  # Используем competitor_model для совместимости
            q_min=q_min,
            q_max=q_max
        )
        
        # Валидация запроса
        try:
            request.validate()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        if not request.kometta_articul:
            raise HTTPException(status_code=400, detail="Не указан артикул насоса Кометта")
        
        kometta_data = get_pump_curve_data(request.kometta_articul)
        if not kometta_data:
            raise HTTPException(status_code=404, detail=f"Насос с артикулом {request.kometta_articul} не найден")
        
        competitor_data = None
        if request.competitor_model:
            # Если competitor_model это артикул (число), ищем в базе Кометта
            if request.competitor_model.isdigit():
                competitor_pump = get_pump_curve_data(request.competitor_model)
                if competitor_pump:
                    competitor_data = {
                        "model": competitor_pump.get('model', f"Артикул {request.competitor_model}"),
                        "brand": "Кометта",
                        "q_points": competitor_pump.get("q_points", []),
                        "h_points": competitor_pump.get("h_points", []),
                        "coefficients": competitor_pump.get("coefficients", {})
                    }
            else:
                # Иначе ищем в базе конкурентов
                comp_result = find_competitor_model(request.competitor_model)
                if comp_result:
                    row = comp_result["row"]
                    q_points, h_points = extract_curve_points(row)
                    
                    # Для кубического полинома (как app.py) нужны ровно 4 опорные точки
                    raw_points = list(zip(q_points or [], h_points or []))
                    raw_points = [(float(q), float(h)) for q, h in raw_points if q is not None and h is not None]
                    raw_points.sort(key=lambda p: p[0])

                    fit_points = choose_fit_points_4(raw_points) if len(raw_points) >= 4 else None
                    if fit_points and len(fit_points) == 4:
                        q_fit = [p[0] for p in fit_points]
                        h_fit = [p[1] for p in fit_points]
                        coeffs = approximate_curve(q_fit, h_fit)
                        if coeffs is None:
                            raise HTTPException(status_code=400, detail=f"Не удалось аппроксимировать кривую для конкурента: {request.competitor_model}")
                        a, b, c, d = coeffs
                        competitor_data = {
                            "model": comp_result["model"],
                            "brand": comp_result["brand"],
                            "q_points": q_points,
                            "h_points": h_points,
                            "coefficients": {"a": a, "b": b, "c": c, "d": d}
                        }
                    else:
                        raise HTTPException(status_code=400, detail=f"Для конкурента {request.competitor_model} недостаточно точек кривой (нужно ≥4)")
        
        # Проверяем наличие коэффициентов для построения графика
        coeffs_kometta = kometta_data.get("coefficients")
        q_points_kometta = kometta_data.get("q_points", [])
        h_points_kometta = kometta_data.get("h_points", [])
        
        # Если нет коэффициентов, но есть точки - пытаемся аппроксимировать (как app.py: ровно 4 точки)
        if not coeffs_kometta or not isinstance(coeffs_kometta, dict):
            raw_points = list(zip(q_points_kometta or [], h_points_kometta or []))
            raw_points = [(float(q), float(h)) for q, h in raw_points if q is not None and h is not None]
            raw_points.sort(key=lambda p: p[0])

            fit_points = choose_fit_points_4(raw_points) if len(raw_points) >= 4 else None
            if fit_points and len(fit_points) == 4:
                q_fit = [p[0] for p in fit_points]
                h_fit = [p[1] for p in fit_points]
                coeffs = approximate_curve(q_fit, h_fit)
                if coeffs is not None:
                    a, b, c, d = coeffs
                    coeffs_kometta = {"a": a, "b": b, "c": c, "d": d}
                else:
                    raise HTTPException(status_code=400, detail=f"Для насоса {request.kometta_articul} не удалось аппроксимировать кривую (solve failed)")
            else:
                raise HTTPException(status_code=400, detail=f"Для насоса {request.kometta_articul} недостаточно точек кривой (нужно ≥4)")
        
        # Проверяем наличие всех необходимых коэффициентов
        if not all(key in coeffs_kometta for key in ["a", "b", "c", "d"]):
            raise HTTPException(
                status_code=400,
                detail=f"Для насоса с артикулом {request.kometta_articul} неполные данные кривой. Невозможно построить график."
            )
        
        # Используем улучшенный график (как в app.py)
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Определяем диапазон Q
        q_min = request.q_min if request.q_min is not None else (min(q_points_kometta) if q_points_kometta else 0)
        q_max = request.q_max if request.q_max is not None else (max(q_points_kometta) if q_points_kometta else 100)
        
        # Если есть competitor, расширяем диапазон
        if competitor_data and competitor_data.get("q_points"):
            q_min = min(q_min, min(competitor_data["q_points"]))
            q_max = max(q_max, max(competitor_data["q_points"]))
        
        q_plot = np.linspace(max(0, q_min), q_max * 1.1, 100)
        h_plot_kometta = [calculate_h(q, coeffs_kometta["a"], coeffs_kometta["b"], coeffs_kometta["c"], coeffs_kometta["d"]) for q in q_plot]
        
        # Фильтруем отрицательные значения H
        valid_indices = [i for i, h in enumerate(h_plot_kometta) if h >= 0]
        q_plot_kometta = [q_plot[i] for i in valid_indices]
        h_plot_kometta = [h_plot_kometta[i] for i in valid_indices]
        
        # Кривая Кометта - используем оранжевый цвет (#E49E00) для соответствия новой теме
        ax.plot(q_plot_kometta, h_plot_kometta, color='#E49E00', linewidth=3, label=f"Кометта {kometta_data['model']}")
        
        # Отмечаем опорные точки
        if q_points_kometta and h_points_kometta:
            ax.scatter(q_points_kometta, h_points_kometta, color='#E49E00', s=80, alpha=0.7, marker='o', edgecolors='black', linewidths=1, zorder=5)
        
        if competitor_data:
            coeffs_comp = competitor_data.get("coefficients")
            # Если пользователь запросил сравнение, но коэффициентов нет — возвращаем понятную 400
            if (not isinstance(coeffs_comp, dict)) or (not all(k in coeffs_comp for k in ["a", "b", "c", "d"])):
                raise HTTPException(
                    status_code=400,
                    detail=f"Для конкурента '{request.competitor_model}' недостаточно данных кривой (нужно ≥4 точки)."
                )
            h_plot_comp = [calculate_h(q, coeffs_comp["a"], coeffs_comp["b"], coeffs_comp["c"], coeffs_comp["d"]) for q in q_plot]
            
            # Фильтруем отрицательные значения H
            valid_indices_comp = [i for i, h in enumerate(h_plot_comp) if h >= 0]
            q_plot_comp = [q_plot[i] for i in valid_indices_comp]
            h_plot_comp = [h_plot_comp[i] for i in valid_indices_comp]
            
            # Кривая конкурента - используем синий цвет для контраста
            ax.plot(q_plot_comp, h_plot_comp, color='#0066CC', linewidth=3, linestyle='--', label=f"{competitor_data['brand']} {competitor_data['model']}")
            
            if competitor_data.get("q_points") and competitor_data.get("h_points"):
                ax.scatter(competitor_data["q_points"], competitor_data["h_points"], color='#0066CC', s=80, alpha=0.7, marker='s', edgecolors='black', linewidths=1, zorder=5)
        
        # Улучшаем стиль графика (как в app.py)
        max_h = max(h_plot_kometta) if h_plot_kometta else 100
        if competitor_data and h_plot_comp:
            max_h = max(max_h, max(h_plot_comp))
        
        ax.set_xlabel("Подача Q, м³/ч")
        ax.set_ylabel("Напор H, м")
        # По ТЗ: заголовка быть не должно
        ax.set_title("")
        ax.set_xlim(0, q_max * 1.1)
        ax.set_ylim(0, max_h * 1.1)
        ax.axhline(y=0, color='black', linewidth=2)
        ax.axvline(x=0, color='black', linewidth=2)
        
        # Сетка (как в app.py)
        ax.grid(True, alpha=0.3, which='both')
        ax.grid(True, alpha=0.15, which='minor')
        
        ax.legend(loc='upper right')

        apply_ui_plot_style(fig, ax)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', transparent=True, pad_inches=0.02)
        plt.close()
        
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")
    
    except HTTPException:
        raise
    except Exception as e:
        # Логируем ошибку для отладки
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка генерации графика для артикула {kometta_articul}: {str(e)}\n{traceback.format_exc()}")
        
        # Используем единую систему обработки ошибок
        from services.error_handler import log_error
        log_error(e, "plot.py:plot_compare", 
                 context={"kometta_articul": kometta_articul, "competitor_articul": competitor_articul},
                 session_id=None)
        
        raise HTTPException(status_code=500, detail=f"Ошибка генерации графика: {str(e)}")


@router.post("/plot/compare")
async def plot_compare_post(payload: ComparePlotRequest):
    """
    MVP endpoint по ТЗ: POST /api/plot/compare
    Возвращает PNG с кривыми Q-H (Кометта vs конкурент).
    """
    try:
        payload.validate()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    competitor = payload.competitor_articul or payload.competitor_model
    return await plot_compare(
        kometta_articul=payload.kometta_articul,
        competitor_articul=competitor,
        q_min=payload.q_min,
        q_max=payload.q_max,
    )


@router.post("/plot/advanced")
async def plot_advanced(request: AdvancedPlotRequest):
    """
    Генерирует график с поддержкой всех режимов из app.py.
    """
    try:
        # Валидация запроса
        try:
            request.validate()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        image_bytes = generate_advanced_plot(request)
        return Response(content=image_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        # Используем единую систему обработки ошибок
        from services.error_handler import log_error
        log_error(e, "plot.py:plot_advanced", 
                 context={"mode": request.mode, "pump1_articul": request.pump1_articul},
                 session_id=None)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации графика: {str(e)}")
