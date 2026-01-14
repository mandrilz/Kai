"""
Domain service для поиска аналогов насосов конкурентов.

PR5: Отделяет бизнес-логику поиска аналогов от диалоговой логики.
Содержит только поиск и расчеты, без форматирования ответов.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from services.selector import find_analog_by_model, find_competitor_model
from services.data_loader import load_competitors_data


@dataclass
class AnalogLookupRequest:
    """Запрос на поиск аналога."""
    # ИСПРАВЛЕНО: model теперь Optional, т.к. может быть поиск только по brand
    model: Optional[str] = None  # Модель конкурента (опционально, может быть только brand)
    brand: Optional[str] = None  # Бренд (опционально)
    model_only: Optional[str] = None  # Только модель без бренда
    top_n: int = 3  # Количество аналогов для возврата


@dataclass
class AnalogLookupResult:
    """Результат поиска аналога."""
    competitor_data: Optional[Dict[str, Any]]  # Данные модели конкурента
    analogs: List[Dict[str, Any]]  # Список аналогов Кометта
    found: bool  # Найдена ли модель конкурента
    has_analogs: bool  # Есть ли аналоги


class AnalogLookupService:
    """
    Сервис для поиска аналогов насосов конкурентов.
    
    Содержит только бизнес-логику:
    - Поиск модели конкурента
    - Поиск аналогов
    - Валидация данных
    
    Без диалоговой логики:
    - Форматирование ответов
    - Управление состоянием
    - Генерация вопросов
    """
    
    def find_analog(self, request: AnalogLookupRequest) -> AnalogLookupResult:
        """
        Ищет аналоги для модели конкурента.
        
        ИСПРАВЛЕНО: Если указан только brand без model, использует find_by_brand().
        
        Args:
            request: Запрос на поиск аналога
            
        Returns:
            AnalogLookupResult с найденными аналогами
        """
        # Если указан только brand без model - используем find_by_brand
        if request.brand and not request.model and not request.model_only:
            result = self.find_by_brand(request.brand, top_n=request.top_n)
            if result:
                competitor_data, analogs = result
                return AnalogLookupResult(
                    competitor_data=competitor_data,
                    analogs=analogs or [],
                    found=competitor_data is not None,
                    has_analogs=bool(analogs)
                )
            else:
                return AnalogLookupResult(
                    competitor_data=None,
                    analogs=[],
                    found=False,
                    has_analogs=False
                )
        
        # Проверяем, что есть хотя бы model или model_only
        if not request.model and not request.model_only:
            return AnalogLookupResult(
                competitor_data=None,
                analogs=[],
                found=False,
                has_analogs=False
            )
        
        # Определяем модель для поиска
        # ИСПРАВЛЕНО: Используем request.model или request.model_only
        model_to_search = request.model or request.model_only
        
        # Ищем модель конкурента
        competitor_data, analogs = find_analog_by_model(
            competitor_model=model_to_search,
            top_n=request.top_n
        )
        
        return AnalogLookupResult(
            competitor_data=competitor_data,
            analogs=analogs or [],
            found=competitor_data is not None,
            has_analogs=bool(analogs)
        )
    
    def find_by_brand(self, brand: str, top_n: int = 3) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Ищет аналоги для первого найденного насоса бренда.
        
        Args:
            brand: Название бренда
            top_n: Количество аналогов
            
        Returns:
            Tuple (competitor_data, analogs) или None
        """
        df_comp = load_competitors_data()
        brand_matches = df_comp[df_comp["brand"].astype(str).str.upper() == brand.upper()]
        
        if brand_matches.empty:
            return None
        
        first_row = brand_matches.iloc[0]
        model = f"{first_row.get('brand', '')} {first_row.get('model', '')}".strip()
        
        if model:
            return find_analog_by_model(model, top_n=top_n)
        
        return None
