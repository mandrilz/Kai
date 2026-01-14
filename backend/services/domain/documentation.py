"""
Domain service для работы с документацией насосов.

PR5: Отделяет бизнес-логику получения документации от диалоговой логики.
Содержит только поиск данных, без форматирования ответов.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from services.selector import get_pump_curve_data, get_pump_curve_data_by_model
from services.body_material import extract_body_material_code_from_model, describe_body_material


@dataclass
class DocumentationRequest:
    """Запрос на получение документации."""
    action: str  # Тип запроса: "by_model", "by_articul", "body_material_by_model", "body_material_by_articul", "compare", "plot"
    model: Optional[str] = None  # Модель насоса
    articul: Optional[str] = None  # Артикул насоса
    articul2: Optional[str] = None  # Второй артикул для сравнения
    competitor_model: Optional[str] = None  # Модель конкурента для графика


@dataclass
class DocumentationResult:
    """Результат получения документации."""
    # ИСПРАВЛЕНО: found и has_curve с дефолтами, чтобы избежать TypeError
    found: bool = False  # Найден ли насос
    has_curve: bool = False  # Есть ли данные кривой
    pump_data: Optional[Dict[str, Any]] = None  # Данные насоса
    pump_data2: Optional[Dict[str, Any]] = None  # Данные второго насоса (для сравнения)
    body_material_code: Optional[str] = None  # Код материала корпуса
    body_material_description: Optional[str] = None  # Описание материала


class DocumentationService:
    """
    Сервис для работы с документацией насосов.
    
    Содержит только бизнес-логику:
    - Поиск данных насоса
    - Извлечение информации о материале
    - Получение данных кривой
    
    Без диалоговой логики:
    - Форматирование ответов
    - Управление состоянием
    - Генерация вопросов
    """
    
    def get_pump_info(self, request: DocumentationRequest) -> DocumentationResult:
        """
        Получает информацию о насосе.
        
        Args:
            request: Запрос на получение документации
            
        Returns:
            DocumentationResult с данными насоса
        """
        if request.action == "by_articul" and request.articul:
            pump_data = get_pump_curve_data(request.articul)
            return DocumentationResult(
                pump_data=pump_data,
                found=pump_data is not None,
                has_curve=self._has_curve_data(pump_data) if pump_data else False
            )
        
        elif request.action == "by_model" and request.model:
            pump_data = get_pump_curve_data_by_model(request.model)
            return DocumentationResult(
                pump_data=pump_data,
                found=pump_data is not None,
                has_curve=self._has_curve_data(pump_data) if pump_data else False
            )
        
        elif request.action == "body_material_by_articul" and request.articul:
            pump_data = get_pump_curve_data(request.articul)
            if not pump_data:
                return DocumentationResult(
                    pump_data=None,
                    found=False,
                    has_curve=False
                )
            
            model = pump_data.get("model", "")
            code = extract_body_material_code_from_model(model)
            mat = describe_body_material(code) if code else None
            
            return DocumentationResult(
                pump_data=pump_data,
                body_material_code=code,
                body_material_description=mat,
                found=True,
                has_curve=self._has_curve_data(pump_data)
            )
        
        elif request.action == "body_material_by_model" and request.model:
            code = extract_body_material_code_from_model(request.model)
            mat = describe_body_material(code) if code else None
            
            return DocumentationResult(
                pump_data=None,
                body_material_code=code,
                body_material_description=mat,
                found=code is not None,
                has_curve=False
            )
        
        elif request.action == "compare" and request.articul and request.articul2:
            pump_data = get_pump_curve_data(request.articul)
            pump_data2 = get_pump_curve_data(request.articul2)
            
            return DocumentationResult(
                pump_data=pump_data,
                pump_data2=pump_data2,
                found=(pump_data is not None and pump_data2 is not None),
                has_curve=(
                    self._has_curve_data(pump_data) and
                    self._has_curve_data(pump_data2)
                ) if (pump_data and pump_data2) else False
            )
        
        elif request.action == "plot" and request.articul:
            pump_data = get_pump_curve_data(request.articul)
            
            # ИСПРАВЛЕНО: Если есть competitor_model, пытаемся найти данные конкурента
            if request.competitor_model:
                from services.selector import find_competitor_model, extract_curve_points
                competitor_data = find_competitor_model(request.competitor_model)
                if competitor_data:
                    # Добавляем данные конкурента в pump_data2 для использования в ResponseBuilder
                    competitor_row = competitor_data.get("row")
                    if competitor_row is not None:
                        q_points, h_points = extract_curve_points(competitor_row)
                        competitor_data_dict = {
                            "model": competitor_data.get("model", request.competitor_model),
                            "brand": competitor_data.get("brand", ""),
                            "q_points": q_points,
                            "h_points": h_points,
                            "is_competitor": True
                        }
                        # Используем pump_data2 для данных конкурента
                        return DocumentationResult(
                            pump_data=pump_data,
                            pump_data2=competitor_data_dict,
                            found=pump_data is not None,
                            has_curve=(
                                self._has_curve_data(pump_data) and
                                self._has_curve_data(competitor_data_dict)
                            ) if (pump_data and competitor_data_dict) else False
                        )
            
            return DocumentationResult(
                pump_data=pump_data,
                found=pump_data is not None,
                has_curve=self._has_curve_data(pump_data) if pump_data else False
            )
        
        return DocumentationResult(
            pump_data=None,
            found=False,
            has_curve=False
        )
    
    def _has_curve_data(self, pump_data: Dict[str, Any]) -> bool:
        """Проверяет, есть ли данные кривой."""
        q_points = pump_data.get("q_points", [])
        h_points = pump_data.get("h_points", [])
        return len(q_points) >= 3 and len(h_points) >= 3
