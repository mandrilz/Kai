"""
Domain services - бизнес-логика без диалоговой логики.

PR5: Business services - отделить 'посчитать' от 'сказать'.

Эти сервисы содержат только бизнес-логику:
- Расчеты и вычисления
- Поиск данных
- Валидация бизнес-правил

Без диалоговой логики:
- Форматирование ответов (делает ResponseBuilder в PR6)
- Управление состоянием диалога
- Генерация вопросов
"""
from services.domain.pump_selection import PumpSelectionService, PumpSelectionRequest, PumpSelectionResult
from services.domain.analog_lookup import AnalogLookupService, AnalogLookupRequest, AnalogLookupResult
from services.domain.documentation import DocumentationService, DocumentationRequest, DocumentationResult
from services.domain.tech_qa import TechQAService, TechQARequest, TechQAResult, SpecialQueryType

__all__ = [
    "PumpSelectionService",
    "PumpSelectionRequest",
    "PumpSelectionResult",
    "AnalogLookupService",
    "AnalogLookupRequest",
    "AnalogLookupResult",
    "DocumentationService",
    "DocumentationRequest",
    "DocumentationResult",
    "TechQAService",
    "TechQARequest",
    "TechQAResult",
    "SpecialQueryType",
]
