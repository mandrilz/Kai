"""
Единый orchestrator для управления диалогом.

PR4: Dialogue manager - единый orchestrator решения.

Координирует:
- NLU (intent detection + slot filling) через новые модули PR1-PR3
- Управление состоянием диалога
- Вызов handlers для генерации ответов
- FSM управление (опционально)

Архитектура:
1. Нормализация сообщения (preprocess)
2. Определение интента (intent_router)
3. Заполнение слотов (slot_filler)
4. Генерация ответа (handlers)
5. Обновление состояния
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from sqlmodel import Session

from services.nlu.preprocess import normalize_text
from services.nlu.intent_router import route_intent
from services.nlu.slot_filler import fill_slots
from services.nlu.types import (
    Intent, IntentResult, SlotFillResult, NormalizedMessage, NLUContext, NLUResult
)
from services.conversation_state import (
    get_context_for_model,
    update_state,
    set_last_question,
    get_state_meta,
    update_state_meta,
)
from services.dialog_fsm.state import FSMState
from services.dialog_fsm.followups import ensure_followups
from api.types import Attachment
from services.response_builder import ResponseBuilder
from services.domain import (
    PumpSelectionService, PumpSelectionRequest,
    AnalogLookupService, AnalogLookupRequest,
    DocumentationService, DocumentationRequest,
    TechQAService, TechQARequest
)


@dataclass
class DialogueTurn:
    """Один ход диалога (сообщение пользователя)."""
    chat_id: str
    message: str
    attachments: List[Attachment] = None
    session: Optional[Session] = None


@dataclass
class DialogueResult:
    """Результат обработки хода диалога."""
    response: str  # Текст ответа
    intent: Intent  # Определенный интент
    slot_updates: Dict[str, Any]  # Обновления слотов
    next_slot: Optional[str] = None  # Следующий слот для уточнения
    next_question: Optional[str] = None  # Вопрос для уточнения
    needs_clarification: bool = False  # Нужно ли уточнение


class DialogueManager:
    """
    Единый orchestrator для управления диалогом.
    
    Координирует все этапы обработки сообщения:
    1. Нормализация
    2. Определение интента
    3. Заполнение слотов
    4. Генерация ответа
    5. Обновление состояния
    """
    
    def __init__(self, use_fsm: bool = True):
        """
        Args:
            use_fsm: Использовать ли FSM для управления состоянием диалога
        """
        self.use_fsm = use_fsm
        self.response_builder = ResponseBuilder()
        # Domain services для вызова бизнес-логики
        self.pump_selection_service = PumpSelectionService()
        self.analog_lookup_service = AnalogLookupService()
        self.documentation_service = DocumentationService()
        self.tech_qa_service = TechQAService()
    
    def process_turn(self, turn: DialogueTurn) -> DialogueResult:
        """
        Обрабатывает один ход диалога.
        
        Args:
            turn: Ход диалога (сообщение пользователя)
            
        Returns:
            DialogueResult с ответом и метаданными
        """
        # 1. Нормализация сообщения
        normalized_text = normalize_text(turn.message)
        normalized_message = NormalizedMessage(
            original=turn.message,
            normalized=normalized_text,
            has_attachments=bool(turn.attachments)
        )
        
        # 2. Загрузка контекста
        context = get_context_for_model(turn.chat_id, session=turn.session)
        state = context.get("state", {}) if isinstance(context, dict) else {}
        pending_slot = context.get("pending_slot")
        recent_messages = context.get("recent_messages", [])
        
        # 3. Определение интента
        # ИСПРАВЛЕНО: Передаем уже нормализованный текст, route_intent не будет нормализовать повторно
        intent_result = self._detect_intent(
            normalized_text,
            has_attachments=normalized_message.has_attachments,
            context=context,
            already_normalized=True
        )
        
        # 4. Заполнение слотов
        # ИСПРАВЛЕНО: Передаем уже нормализованный текст с флагом already_normalized=True
        slot_result = self._fill_slots(
            normalized_text,
            state,
            pending_slot,
            turn.chat_id,
            already_normalized=True
        )
        
        # 5. Обновление состояния
        self._update_state(
            turn.chat_id,
            slot_result,
            turn.session
        )
        
        # ИСПРАВЛЕНО: Перезагружаем контекст после обновления состояния
        # чтобы followups видели актуальное состояние (включая meta/FSM/last_selected_pump)
        context_updated = get_context_for_model(turn.chat_id, session=turn.session)
        state_updated = context_updated.get("state", {}) if isinstance(context_updated, dict) else {}
        
        # 6. Выполнение бизнес-логики (domain services)
        domain_result = self._execute_domain_logic(
            intent_result,
            slot_result,
            context_updated,  # Используем обновленный контекст
            turn
        )
        
        # 7. Генерация ответа через ResponseBuilder
        response = self._generate_response(
            intent_result,
            slot_result,
            normalized_message,
            turn,
            context_updated,  # Используем обновленный контекст
            domain_result
        )
        
        # 8. Follow-ups (если нужно)
        if self.use_fsm:
            response = self._add_followups(
                response,
                intent_result.intent,
                state_updated,  # ИСПРАВЛЕНО: Используем актуальный state после обновления
                slot_result
            )
        
        return DialogueResult(
            response=response,
            intent=intent_result.intent,
            slot_updates=slot_result.updates.to_dict(),
            next_slot=slot_result.next_slot,
            next_question=slot_result.next_question,
            needs_clarification=slot_result.needs_clarification
        )
    
    def _detect_intent(
        self,
        message: str,
        has_attachments: bool = False,
        context: Dict[str, Any] = None,
        already_normalized: bool = False
    ) -> IntentResult:
        """
        Определяет интент сообщения.
        
        Args:
            message: Сообщение (нормализованное, если already_normalized=True)
            has_attachments: Есть ли вложения
            context: Контекст диалога
            already_normalized: Уже нормализовано ли сообщение
            
        Returns:
            IntentResult с определенным интентом
        """
        return route_intent(
            message=message,
            has_attachments=has_attachments,
            context=context or {},
            already_normalized=already_normalized
        )
    
    def _fill_slots(
        self,
        message: str,
        state: Dict[str, Any],
        pending_slot: Optional[str],
        chat_id: str,
        already_normalized: bool = False
    ) -> SlotFillResult:
        """
        Заполняет слоты из сообщения.
        
        Args:
            message: Сообщение (нормализованное, если already_normalized=True)
            state: Текущее состояние диалога
            pending_slot: Ожидаемый слот (если есть)
            chat_id: ID чата
            already_normalized: Уже нормализовано ли сообщение
            
        Returns:
            SlotFillResult с обновлениями слотов
        """
        return fill_slots(
            message=message,
            state=state,
            pending_slot=pending_slot,
            chat_id=chat_id,
            already_normalized=already_normalized
        )
    
    def _update_state(
        self,
        chat_id: str,
        slot_result: SlotFillResult,
        session: Optional[Session] = None
    ) -> None:
        """
        Обновляет состояние диалога на основе результатов slot filling.
        
        Args:
            chat_id: ID чата
            slot_result: Результат заполнения слотов
            session: Сессия БД
        """
        updates = slot_result.updates.to_dict()
        next_slot = slot_result.next_slot
        
        # ИСПРАВЛЕНО: Правильная логика обновления pending_slot
        # Если нужна уточнение и есть next_slot - устанавливаем pending_slot
        # Если нужна уточнение, но next_slot нет - не трогаем pending_slot (оставляем как есть)
        # Если уточнение не нужно - очищаем pending_slot
        if slot_result.needs_clarification:
            if next_slot is not None:
                # Нужна уточнение и есть следующий слот - устанавливаем
                pending_slot_to_set = next_slot
                keep_pending = False
            else:
                # Нужна уточнение, но next_slot нет - не трогаем (None означает "не менять")
                pending_slot_to_set = None
                keep_pending = True
        else:
            # Уточнение не нужно - очищаем pending_slot
            pending_slot_to_set = None
            keep_pending = False
        
        # Обновляем слоты
        if updates:
            update_state(
                chat_id,
                updates,
                pending_slot=pending_slot_to_set,
                keep_pending_if_not_set=keep_pending,
                session=session
            )
        elif pending_slot_to_set is not None:
            # Сохраняем pending_slot даже если обновлений нет
            update_state(
                chat_id,
                {},
                pending_slot=pending_slot_to_set,
                keep_pending_if_not_set=False,
                session=session
            )
        elif not slot_result.needs_clarification:
            # Очищаем pending_slot если уточнение не нужно
            update_state(
                chat_id,
                {},
                pending_slot=None,
                keep_pending_if_not_set=False,
                session=session
            )
        
        # Сохраняем вопрос для уточнения
        if slot_result.next_question:
            set_last_question(chat_id, slot_result.next_question, session=session)
    
    def _execute_domain_logic(
        self,
        intent_result: IntentResult,
        slot_result: SlotFillResult,
        context: Dict[str, Any],
        turn: DialogueTurn
    ):
        """
        Выполняет бизнес-логику через domain services.
        
        PR6: Вызывает domain services для получения данных,
        которые затем передаются в ResponseBuilder для форматирования.
        
        Args:
            intent_result: Результат определения интента
            slot_result: Результат заполнения слотов
            context: Контекст диалога
            turn: Ход диалога
            
        Returns:
            Результат domain service (PumpSelectionResult, AnalogLookupResult и т.д.)
        """
        intent = intent_result.intent
        data = intent_result.data or {}
        # ИСПРАВЛЕНО: state берется из обновленного контекста (context_updated из process_turn)
        state = context.get("state", {})
        
        # Объединяем state с обновлениями из slot_result
        effective_state = {**state, **slot_result.updates.to_dict()}
        
        if intent == Intent.SELECTION_BY_POINT:
            # Получаем параметры из эффективного состояния
            flow = effective_state.get("flow_m3h")
            head = effective_state.get("head_m")
            
            # Если нет Q или H - не вызываем domain service
            if flow is None or head is None:
                return None
            
            h_st = effective_state.get("h_st", 0.0)
            series_filter = effective_state.get("pump_type_info", {}).get("series") if isinstance(effective_state.get("pump_type_info"), dict) else None
            body_material_code = effective_state.get("body_material_code")
            fluid = effective_state.get("fluid")
            temperature_c = effective_state.get("temperature_c")
            
            request = PumpSelectionRequest(
                flow_m3h=flow,
                head_m=head,
                h_st=h_st,
                series_filter=series_filter if isinstance(series_filter, list) else ([series_filter] if series_filter else None),
                body_material_code=body_material_code,
                fluid=fluid,
                temperature_c=temperature_c
            )
            
            return self.pump_selection_service.select_pumps(request)
        
        elif intent == Intent.ANALOG_BY_MODEL:
            # ИСПРАВЛЕНО: Проверяем pending confirmation из обновленного state (context уже обновлен)
            pending_confirmation = state.get("pending_analog_confirmation")
            if pending_confirmation:
                # Обработка подтверждения - возвращаем None, чтобы ResponseBuilder обработал
                return None
            
            model = data.get("model")
            brand = data.get("brand")
            model_only = data.get("model_only")
            
            if not model and not brand:
                return None
            
            request = AnalogLookupRequest(
                model=model,
                brand=brand,
                model_only=model_only,
                top_n=3
            )
            
            return self.analog_lookup_service.find_analog(request)
        
        elif intent == Intent.DOCUMENTATION:
            action = data.get("action", "by_model")
            
            request = DocumentationRequest(
                action=action,
                model=data.get("model"),
                articul=data.get("articul"),
                articul2=data.get("articul2"),
                competitor_model=data.get("competitor_model")
            )
            
            return self.documentation_service.get_pump_info(request)
        
        elif intent == Intent.TECH_QA:
            query = data.get("query", turn.message)
            recent_messages = context.get("recent_messages", [])
            
            request = TechQARequest(
                query=query,
                context=recent_messages,
                limit=5
            )
            
            return self.tech_qa_service.answer_question(request)
        
        # Для остальных интентов domain logic не требуется
        return None
    
    def _generate_response(
        self,
        intent_result: IntentResult,
        slot_result: SlotFillResult,
        normalized_message: NormalizedMessage,
        turn: DialogueTurn,
        context: Dict[str, Any],
        domain_result=None
    ) -> str:
        """
        Генерирует ответ через ResponseBuilder или старые handlers (fallback).
        
        PR6: Использует ResponseBuilder для основных интентов с domain services.
        Для остальных интентов использует старые handlers как fallback.
        
        Args:
            intent_result: Результат определения интента
            slot_result: Результат заполнения слотов
            normalized_message: Нормализованное сообщение
            turn: Ход диалога
            context: Контекст диалога
            domain_result: Результат domain service
            
        Returns:
            Текст ответа
        """
        intent = intent_result.intent
        
        # Основные интенты - используем ResponseBuilder
        # ИСПРАВЛЕНО: Добавлен OFF_TOPIC в список интентов для ResponseBuilder
        if intent in [Intent.SELECTION_BY_POINT, Intent.ANALOG_BY_MODEL, 
                      Intent.DOCUMENTATION, Intent.TECH_QA, Intent.OFF_TOPIC]:
            return self.response_builder.build_response(
                intent=intent,
                intent_result=intent_result,
                slot_result=slot_result,
                context=context,
                message=normalized_message.original,
                domain_result=domain_result
            )
        
        # Остальные интенты - используем старые handlers как fallback
        # (пока не созданы domain services для них)
        return self._generate_response_legacy(
            intent_result,
            slot_result,
            normalized_message,
            turn,
            context
        )
    
    def _generate_response_legacy(
        self,
        intent_result: IntentResult,
        slot_result: SlotFillResult,
        normalized_message: NormalizedMessage,
        turn: DialogueTurn,
        context: Dict[str, Any]
    ) -> str:
        """
        Генерирует ответ через старые handlers (fallback для интентов без domain services).
        
        Args:
            intent_result: Результат определения интента
            slot_result: Результат заполнения слотов
            normalized_message: Нормализованное сообщение
            turn: Ход диалога
            context: Контекст диалога
            
        Returns:
            Текст ответа
        """
        intent = intent_result.intent
        data = intent_result.data or {}
        
        # Импортируем handlers
        # ИСПРАВЛЕНО: OFF_TOPIC теперь обрабатывается через ResponseBuilder, не импортируем handle_off_topic
        from services.dialog_handlers.file_upload import handle_file_upload
        from services.dialog_handlers.diagnostics import handle_diagnostics
        from services.dialog_handlers.pump_type import handle_pump_type
        from services.dialog_handlers.materials_query import handle_materials_query
        
        response_parts = []
        
        # Вызываем соответствующий handler
        # ИСПРАВЛЕНО: OFF_TOPIC обрабатывается через ResponseBuilder в _generate_response()
        if intent == Intent.FILE_UPLOAD:
            result = handle_file_upload(turn.chat_id, turn.attachments or [])
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.DIAGNOSTICS:
            result = handle_diagnostics(
                message=normalized_message.original,
                data=data
            )
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.PUMP_TYPE:
            result = handle_pump_type(
                message=normalized_message.original,
                data=data
            )
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.MATERIALS_QUERY:
            result = handle_materials_query(
                chat_id=turn.chat_id,
                message=normalized_message.original,
                data=data
            )
            response_parts.extend(result.response_parts)
        
        else:
            # Для неизвестных интентов используем ResponseBuilder с default response
            return self.response_builder.build_response(
                intent=intent,
                intent_result=intent_result,
                slot_result=slot_result,
                context=context,
                message=normalized_message.original,
                domain_result=None
            )
        
        return "\n".join(response_parts)
    
    def _add_followups(
        self,
        response: str,
        intent: Intent,
        state: Dict[str, Any],
        slot_result: SlotFillResult
    ) -> str:
        """
        Добавляет follow-up вопросы к ответу.
        
        Args:
            response: Текст ответа
            intent: Определенный интент
            state: Текущее состояние диалога
            slot_result: Результат заполнения слотов
            
        Returns:
            Ответ с follow-up вопросами
        """
        # Обновляем state из slot_result для передачи в followups
        updated_state = state.copy()
        updated_state.update(slot_result.updates.to_dict())
        return ensure_followups(response, intent.value, updated_state)


# Глобальный экземпляр менеджера (можно переиспользовать)
_default_manager = DialogueManager(use_fsm=True)


def process_dialogue_turn(
    chat_id: str,
    message: str,
    attachments: List[Attachment] = None,
    session: Optional[Session] = None,
    use_fsm: bool = True
) -> DialogueResult:
    """
    Удобная функция для обработки одного хода диалога.
    
    Args:
        chat_id: ID чата
        message: Сообщение пользователя
        attachments: Вложения (если есть)
        session: Сессия БД (опционально)
        use_fsm: Использовать ли FSM
        
    Returns:
        DialogueResult с ответом и метаданными
    """
    manager = DialogueManager(use_fsm=use_fsm)
    turn = DialogueTurn(
        chat_id=chat_id,
        message=message,
        attachments=attachments or [],
        session=session
    )
    return manager.process_turn(turn)
