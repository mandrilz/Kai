"""
Domain service для обработки технических вопросов.

PR5: Отделяет бизнес-логику поиска ответов от диалоговой логики.
Содержит только поиск в базе знаний, без форматирования ответов.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from services.kb.search import search
from services.pump_types import list_available_pump_types, get_pump_components_description


class SpecialQueryType(str, Enum):
    """Типы специальных запросов."""
    NONE = "none"
    PUMP_TYPES = "pump_types"
    COMPONENTS = "components"


@dataclass
class TechQARequest:
    """Запрос на технический вопрос."""
    query: str  # Текст вопроса
    context: Optional[List[Dict[str, Any]]] = None  # Контекст предыдущих сообщений
    limit: int = 5  # Количество результатов поиска


@dataclass
class TechQAResult:
    """Результат обработки технического вопроса."""
    # ИСПРАВЛЕНО: found с дефолтом, чтобы избежать TypeError
    found: bool = False  # Найдены ли результаты
    hits: List[Dict[str, Any]] = None  # Найденные результаты поиска (сырые)
    special_query_type: SpecialQueryType = SpecialQueryType.NONE  # Тип специального запроса
    pump_types: List[str] = None  # Список типов насосов (для PUMP_TYPES)
    components_description: Optional[str] = None  # Описание компонентов (для COMPONENTS)
    
    def __post_init__(self):
        """Инициализация полей по умолчанию."""
        if self.hits is None:
            self.hits = []
        if self.pump_types is None:
            self.pump_types = []


class TechQAService:
    """
    Сервис для обработки технических вопросов.
    
    Содержит только бизнес-логику:
    - Поиск в базе знаний
    - Обработка специальных запросов (типы насосов, компоненты)
    
    Без диалоговой логики:
    - Форматирование ответов (делает ResponseBuilder в PR6)
    - Управление состоянием
    - Генерация вопросов
    """
    
    def answer_question(self, request: TechQARequest) -> TechQAResult:
        """
        Обрабатывает технический вопрос.
        
        ИСПРАВЛЕНО: Возвращает структурированные данные без форматирования.
        Форматирование выполняется в ResponseBuilder (PR6).
        
        Args:
            request: Запрос на обработку вопроса
            
        Returns:
            TechQAResult со структурированными данными
        """
        query_lower = request.query.lower()
        
        # Обработка специальных запросов о типах насосов
        if any(phrase in query_lower for phrase in [
            "какие типы насосов", "какие типы есть", "типы насосов в ассортименте",
            "какие насосы есть", "какие насосы в линейке", "ассортимент насосов"
        ]):
            types_list = list_available_pump_types()
            
            return TechQAResult(
                found=True,
                hits=[],
                special_query_type=SpecialQueryType.PUMP_TYPES,
                pump_types=types_list,
                components_description=None
            )
        
        # Обработка запросов о компонентах насоса
        if any(phrase in query_lower for phrase in [
            "из чего состоит насос", "компоненты насоса", "части насоса",
            "состав насоса", "устройство насоса", "конструкция насоса"
        ]):
            components_text = get_pump_components_description()
            
            return TechQAResult(
                found=True,
                hits=[],
                special_query_type=SpecialQueryType.COMPONENTS,
                pump_types=[],
                components_description=components_text
            )
        
        # Формируем расширенный запрос с контекстом
        enhanced_query = self._enhance_query(request.query, request.context)
        
        # Выполняем поиск
        hits = search(enhanced_query, limit=request.limit)
        
        # Если не нашли с контекстом, пробуем без контекста
        if not hits:
            hits = search(request.query, limit=request.limit)
        
        # ИСПРАВЛЕНО: Возвращаем сырые hits, форматирование в ResponseBuilder
        return TechQAResult(
            found=bool(hits),
            hits=hits or [],
            special_query_type=SpecialQueryType.NONE,
            pump_types=[],
            components_description=None
        )
    
    def _enhance_query(self, query: str, context: Optional[List[Dict[str, Any]]]) -> str:
        """
        Расширяет запрос контекстом из предыдущих сообщений.
        
        Args:
            query: Оригинальный запрос
            context: Контекст предыдущих сообщений
            
        Returns:
            Расширенный запрос
        """
        if not context:
            return query
        
        # Берем последние 3 сообщения пользователя для контекста
        user_messages = [
            msg for msg in context[-5:]
            if msg.get("role") == "user"
        ]
        
        if not user_messages:
            return query
        
        context_text = " ".join([
            msg.get("content", "") for msg in user_messages[-3:]
        ])
        
        return f"{context_text} {query}".strip()
