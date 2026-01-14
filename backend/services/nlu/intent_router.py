"""
Роутер интентов на основе правил.
Применяет правила по приоритету и возвращает первый подходящий интент.
"""
from typing import Dict, Any
from services.nlu.types import Intent, IntentResult
from services.nlu.intent_rules.file_upload import check_file_upload
from services.nlu.intent_rules.diagnostics import check_diagnostics
from services.nlu.intent_rules.documentation import check_documentation
from services.nlu.intent_rules.analog_by_model import check_analog_by_model
from services.nlu.intent_rules.selection_by_point import check_selection_by_point
from services.nlu.intent_rules.materials_query import check_materials_query
from services.nlu.intent_rules.tech_qa import check_tech_qa
from services.nlu.intent_rules.pump_type import check_pump_type


def route_intent(
    message: str,
    has_attachments: bool = False,
    context: Dict[str, Any] = None,
    already_normalized: bool = False
) -> IntentResult:
    """
    Определяет интент сообщения, применяя правила по приоритету.
    
    Порядок применения правил (по приоритету):
    1. FILE_UPLOAD - самый специфичный, проверяем первым
    2. DIAGNOSTICS - специфичные проблемы с насосом
    3. DOCUMENTATION - запросы документации, графиков, сравнения
    4. ANALOG_BY_MODEL - поиск аналогов (до SELECTION, чтобы не путать с Q/H)
    5. SELECTION_BY_POINT - подбор по рабочей точке
    6. MATERIALS_QUERY - запросы о материалах
    7. TECH_QA - технические вопросы (до PUMP_TYPE, чтобы вопросы шли в KB)
    8. PUMP_TYPE - запросы по типу насоса
    9. OFF_TOPIC - по умолчанию
    
    Args:
        message: Текст сообщения (будет нормализован, если already_normalized=False)
        has_attachments: Есть ли вложения
        context: Контекст диалога (state, recent_messages, dialog_summary)
        already_normalized: Уже нормализовано ли сообщение (для избежания двойной нормализации)
        
    Returns:
        IntentResult с определенным интентом
    """
    if context is None:
        context = {}
    
    # PR3: Нормализуем сообщение для гарантии корректной обработки
    # ИСПРАВЛЕНО: Нормализуем только если еще не нормализовано
    if not already_normalized:
        from services.nlu.preprocess import normalize_text
        message = normalize_text(message)
    
    # Применяем правила по приоритету
    # 1. FILE_UPLOAD
    result = check_file_upload(message, has_attachments, context)
    if result:
        return result
    
    # 2. DIAGNOSTICS
    result = check_diagnostics(message, context)
    if result:
        return result
    
    # 3. DOCUMENTATION
    result = check_documentation(message, context)
    if result:
        return result
    
    # 4. ANALOG_BY_MODEL (до SELECTION, чтобы не путать модели с Q/H)
    result = check_analog_by_model(message, context)
    if result:
        return result
    
    # 5. SELECTION_BY_POINT
    result = check_selection_by_point(message, context)
    if result:
        return result
    
    # 6. MATERIALS_QUERY
    result = check_materials_query(message, context)
    if result:
        return result
    
    # 7. TECH_QA (до PUMP_TYPE, чтобы вопросы шли в KB)
    result = check_tech_qa(message, context)
    if result:
        return result
    
    # 8. PUMP_TYPE
    result = check_pump_type(message, context)
    if result:
        return result
    
    # 9. OFF_TOPIC - по умолчанию
    return IntentResult(
        intent=Intent.OFF_TOPIC,
        data={},
        confidence=0.5
    )
