"""
Domain service для подбора насосов по рабочей точке.

PR5: Отделяет бизнес-логику подбора от диалоговой логики.
Содержит только расчеты и поиск данных, без форматирования ответов.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from services.selector import select_by_working_point
from services.parsing_validator import validate_qh


@dataclass
class PumpSelectionRequest:
    """Запрос на подбор насоса."""
    flow_m3h: float  # Расход в м³/ч
    head_m: float  # Напор в метрах
    h_st: float = 0.0  # Статический напор
    series_filter: Optional[List[str]] = None  # Фильтр по сериям (К377, К144 и т.д.)
    body_material_code: Optional[str] = None  # Код материала корпуса (04, 16, 25)
    fluid: Optional[str] = None  # Жидкость (для фильтрации)
    temperature_c: Optional[float] = None  # Температура (для фильтрации)


@dataclass
class PumpSelectionResult:
    """Результат подбора насоса."""
    pumps: List[Dict[str, Any]]  # Список подобранных насосов
    is_valid: bool  # Валидны ли входные параметры
    validation_errors: Dict[str, str]  # Ошибки валидации (если есть)
    total_found: int  # Всего найдено насосов (до фильтрации)
    body_material_filter_applied: bool = False  # Был ли применен фильтр по материалу
    body_material_no_matches: bool = False  # Нет совпадений по материалу (фильтр применен, но ничего не найдено)


class PumpSelectionService:
    """
    Сервис для подбора насосов по рабочей точке.
    
    Содержит только бизнес-логику:
    - Валидация параметров
    - Подбор насосов
    - Фильтрация по критериям
    
    Без диалоговой логики:
    - Форматирование ответов
    - Управление состоянием
    - Генерация вопросов
    """
    
    def select_pumps(self, request: PumpSelectionRequest) -> PumpSelectionResult:
        """
        Подбирает насосы по рабочей точке.
        
        Args:
            request: Запрос на подбор насоса
            
        Returns:
            PumpSelectionResult с подобранными насосами
        """
        # Валидация параметров
        is_valid, q_error, h_error = validate_qh(
            request.flow_m3h,
            request.head_m,
            "m3/h",
            "m"
        )
        
        validation_errors = {}
        if q_error:
            validation_errors["flow_m3h"] = q_error
        if h_error:
            validation_errors["head_m"] = h_error
        
        if not is_valid:
            return PumpSelectionResult(
                pumps=[],
                is_valid=False,
                validation_errors=validation_errors,
                total_found=0
            )
        
        # Определяем количество кандидатов для поиска
        # Если есть фильтры - берем больше кандидатов
        top_n = 200 if (request.series_filter or request.body_material_code) else 50
        
        # Выполняем подбор
        pumps = select_by_working_point(
            q=request.flow_m3h,
            h=request.head_m,
            h_st=request.h_st,
            top_n=top_n
        )
        
        total_found = len(pumps)
        
        # Применяем фильтры
        filter_result = self._apply_filters(
            pumps,
            series_filter=request.series_filter,
            body_material_code=request.body_material_code,
            fluid=request.fluid,
            temperature_c=request.temperature_c
        )
        
        return PumpSelectionResult(
            pumps=filter_result["pumps"],
            is_valid=True,
            validation_errors={},
            total_found=total_found,
            body_material_filter_applied=filter_result["body_material_filter_applied"],
            body_material_no_matches=filter_result["body_material_no_matches"]
        )
    
    def _apply_filters(
        self,
        pumps: List[Dict[str, Any]],
        series_filter: Optional[List[str]] = None,
        body_material_code: Optional[str] = None,
        fluid: Optional[str] = None,
        temperature_c: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Применяет фильтры к списку насосов.
        
        Args:
            pumps: Список насосов
            series_filter: Фильтр по сериям
            body_material_code: Фильтр по материалу корпуса
            fluid: Жидкость (для предпочтения складской программы)
            temperature_c: Температура (для предпочтения складской программы)
            
        Returns:
            Dict с отфильтрованным списком насосов и метаданными фильтрации
        """
        body_material_filter_applied = False
        body_material_no_matches = False
        
        # Фильтрация по серии
        if series_filter:
            pumps = self._filter_by_series(pumps, series_filter, fluid, temperature_c)
        
        # Фильтрация по материалу корпуса
        if body_material_code:
            body_material_filter_applied = True
            filter_result = self._filter_by_body_material(pumps, body_material_code)
            pumps = filter_result["pumps"]
            body_material_no_matches = filter_result["no_matches"]
        
        return {
            "pumps": pumps,
            "body_material_filter_applied": body_material_filter_applied,
            "body_material_no_matches": body_material_no_matches
        }
    
    def _filter_by_series(
        self,
        pumps: List[Dict[str, Any]],
        series_filter: List[str],
        fluid: Optional[str] = None,
        temperature_c: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Фильтрует насосы по серии."""
        def _norm(s: str) -> str:
            return (s or "").upper().replace("K", "К")
        
        series_norm = [_norm(s) for s in series_filter]
        
        filtered = []
        for p in pumps:
            model_s = _norm(str(p.get("model", "")))
            series_s = _norm(str(p.get("series", "")))
            if any(sn in model_s or sn == series_s for sn in series_norm):
                filtered.append(p)
        
        # Предпочтение складской программы для К144
        if any(sn == "К144" for sn in series_norm) and filtered:
            import re
            
            should_prefer_stock = (
                fluid == "вода" and
                (temperature_c is None or temperature_c >= 0)
            )
            
            def _is_stock_pref(p: Dict[str, Any]) -> int:
                m = str(p.get("model", "") or "")
                has_stock = bool(re.search(r"/0*4[АA]/", m, re.IGNORECASE))
                if should_prefer_stock:
                    # Для воды/плюсовой температуры - предпочитаем складскую программу
                    return 0 if has_stock else 1
                else:
                    # В остальных случаях - не предпочитаем, сортируем только по точности
                    return 0  # Все равны по приоритету складской программы
            
            filtered.sort(key=lambda p: (_is_stock_pref(p), p.get("error", 1e9)))
        
        return filtered
    
    def _filter_by_body_material(
        self,
        pumps: List[Dict[str, Any]],
        body_material_code: str
    ) -> Dict[str, Any]:
        """
        Фильтрует насосы по материалу корпуса.
        
        ИСПРАВЛЕНО: Не возвращает исходный список, если ничего не найдено.
        Вместо этого возвращает пустой список и флаг no_matches.
        
        Args:
            pumps: Список насосов
            body_material_code: Код материала корпуса
            
        Returns:
            Dict с отфильтрованным списком и флагом no_matches
        """
        import re
        
        code = str(body_material_code).strip()
        
        def _has_body_code(p: Dict[str, Any]) -> bool:
            m = str(p.get("model", "") or "")
            return re.search(rf"/\s*{re.escape(code)}\s*[A-Za-zА-Яа-я]\s*/", m) is not None
        
        filtered = [p for p in pumps if _has_body_code(p)]
        
        # ИСПРАВЛЕНО: Не подменяем результат, если ничего не найдено
        # ResponseBuilder в PR6 решит, что показывать пользователю
        return {
            "pumps": filtered,
            "no_matches": len(filtered) == 0 and len(pumps) > 0
        }
