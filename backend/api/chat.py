"""
Legacy-API модуль.

Роут `/api/chat` удалён (клиенты используют `/api/chats/*` + FSM),
но в этом модуле остаются общие функции генерации ответа и SSE-стрима,
которые используются в `api/chats.py`.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import random
import os
from datetime import datetime
from services.intents import detect_intent, Intent, extract_qh_from_text
from services.selector import select_by_working_point, find_analog_by_model
from services.file_extractors import process_file
from services.data_loader import load_kometta_data
from services.text_normalize import normalize_user_text
from services.conversation_state import (
    get_conversation, add_message, update_state, set_last_question,
    get_context_for_model, clear_conversation
)
from services.slot_extractor import (
    extract_slot_updates, get_next_empty_slot, should_trigger_selection
)
from api.types import Attachment
from services.dialog_handlers.off_topic import handle_off_topic
from services.dialog_handlers.selection_by_point import handle_selection_by_point
from services.dialog_handlers.analog_by_model import handle_analog_by_model
from services.dialog_handlers.file_upload import handle_file_upload
from services.dialog_handlers.diagnostics import handle_diagnostics
from services.dialog_handlers.documentation import handle_documentation
from services.dialog_handlers.pump_type import handle_pump_type
from services.dialog_handlers.materials_query import handle_materials_query
from services.dialog_handlers.tech_qa import handle_tech_qa

# Глобальная переменная для пути к логу (избегаем повторных вызовов os.getenv)
DEBUG_LOG_PATH = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")


def generate_komettik_response(
    intent: str,
    data: Dict[str, Any],
    message: str,
    attachments: List[Attachment],
    chat_id: str = "default",
    skip_slot_extraction: bool = False,
) -> str:
    """
    Генерирует ответ Кометтика на основе интента.
    
    Args:
        intent: тип интента
        data: дополнительные данные
        message: сообщение пользователя
        attachments: вложения
        chat_id: ID чата для сохранения контекста
        skip_slot_extraction: если True — не выполняет slot filling внутри (используется FSM-оркестратором)
    """
    try:
        # Шаг A: NLU/Extractor - извлекаем обновления слотов
        try:
            context = get_context_for_model(chat_id)
            # Убеждаемся, что context - это dict и содержит state
            if not isinstance(context, dict):
                context = {"state": {}, "pending_slot": None, "last_question": None, "dialog_summary": None, "recent_messages": [], "full_message_count": 0}
            if "state" not in context or not isinstance(context["state"], dict):
                context["state"] = {}
            pending_slot = context.get("pending_slot")
        except Exception as e:
            # Если ошибка при загрузке контекста, создаем пустой
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading context: {str(e)}\n{traceback.format_exc()}")
            context = {"state": {}, "pending_slot": None, "last_question": None, "dialog_summary": None, "recent_messages": [], "full_message_count": 0}
            pending_slot = None

        # Извлекаем обновления слотов из сообщения (если не отключено FSM-оркестратором)
        if not skip_slot_extraction:
            slot_result = extract_slot_updates(message, context, pending_slot, chat_id=chat_id)
            updates = slot_result.get("updates", {})
            confidence = slot_result.get("confidence", 0.0)
            next_slot = slot_result.get("next_slot")  # КРИТИЧНО: берем next_slot из extractor

            # КРИТИЧНО: Обновляем состояние с правильной логикой pending_slot
            # Если updates есть - обновляем слоты и устанавливаем next_slot
            # Если updates нет, но next_slot есть - сохраняем pending_slot (не сбрасываем!)
            if updates:
                # Обновляем слоты и устанавливаем next_slot (может быть None если все заполнено)
                update_state(chat_id, updates, pending_slot=next_slot, keep_pending_if_not_set=False)
                context["state"].update(updates)  # Обновляем локальный контекст
            elif next_slot is not None:
                # Не распарсили, но extractor вернул next_slot - сохраняем его
                # КРИТИЧНО: не передаем updates={}, только обновляем pending_slot
                update_state(chat_id, {}, pending_slot=next_slot, keep_pending_if_not_set=False)
            # Если и updates нет, и next_slot None - ничего не делаем (pending_slot сохраняется)

            # Устанавливаем последний вопрос если есть
            if slot_result.get("next_question"):
                set_last_question(chat_id, slot_result["next_question"])
        else:
            slot_result = {"updates": {}, "confidence": 0.0, "next_slot": None, "next_question": None}
            updates = {}
            confidence = 0.0
            next_slot = None
        
        # Сообщение пользователя уже сохранено в chats.py перед вызовом generate_komettik_response
        # Не сохраняем его повторно здесь, чтобы избежать дублирования
        # add_message(chat_id, "user", message)
        
        # КРИТИЧНО: Если пользователь подтвердил температуру (pending_slot был temperature_c и temperature_c обновлена),
        # и есть Q и H в состоянии - автоматически выполняем подбор, даже если intent другой
        if (pending_slot == "temperature_c" and 
            updates.get("temperature_c") is not None and 
            not slot_result.get("next_question") and  # Температура подтверждена, не нужно уточнять
            context["state"].get("flow_m3h") and 
            context["state"].get("head_m")):
            # Автоматически переключаемся на подбор по рабочей точке
            intent = Intent.SELECTION_BY_POINT
            data = {
                "q": context["state"].get("flow_m3h"),
                "h": context["state"].get("head_m"),
                "pump_type_info": context["state"].get("pump_type_info"),  # Сохраняем тип насоса, если был определен
            }
        
        response_parts = []
        
        if intent == Intent.OFF_TOPIC:
            result = handle_off_topic()
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.SELECTION_BY_POINT:
            result = handle_selection_by_point(
                chat_id=chat_id,
                message=message,
                data=data,
                context=context,
                pending_slot=pending_slot,
                slot_result=slot_result,
                updates=updates,
            )
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)

        elif intent == Intent.ANALOG_BY_MODEL:
            result = handle_analog_by_model(
                chat_id=chat_id,
                message=message,
                data=data,
                context=context,
            )
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)

        elif intent == Intent.FILE_UPLOAD:
            result = handle_file_upload(chat_id, attachments)
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.DIAGNOSTICS:
            result = handle_diagnostics(message=message, data=data)
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.DOCUMENTATION:
            result = handle_documentation(message=message, data=data)
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.PUMP_TYPE:
            result = handle_pump_type(message=message, data=data)
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.MATERIALS_QUERY:
            result = handle_materials_query(chat_id=chat_id, message=message, data=data)
            response_parts.extend(result.response_parts)
        
        elif intent == Intent.TECH_QA:
            result = handle_tech_qa(chat_id=chat_id, message=message, data=data, context=context)
            if result.immediate_response is not None:
                return result.immediate_response
            response_parts.extend(result.response_parts)
        
        response_text = "\n".join(response_parts)
        
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "c:\\Users\\Admin\\Desktop\\1\\.cursor\\debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:generate_komettik_response",
                    "message": "Response generated",
                    "data": {
                        "intent": intent,
                        "response_length": len(response_text),
                        "response_preview": response_text[:100] if response_text else "",
                        "has_response": bool(response_text and response_text.strip())
                    },
                    "sessionId": "kb-fallback",
                    "runId": "pre-fix",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        
        # KB Fallback: Если это вопрос и нет хорошего ответа - ищем в KB
        from services.question_detection import is_question, should_use_kb_fallback
        
        is_q, reason = is_question(message)
        
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "chat.py:generate_komettik_response",
                    "message": "Question detection",
                    "data": {
                        "is_question": is_q,
                        "reason": reason,
                        "message": message[:100]
                    },
                    "sessionId": "kb-fallback",
                    "runId": "pre-fix",
                    "hypothesisId": "B"
                }) + "\n")
        except: pass
        # #endregion
        
        if is_q:
            # Проверяем, нужен ли KB fallback
            needs_fallback = should_use_kb_fallback(intent, response_text)
            
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "chat.py:generate_komettik_response",
                        "message": "KB fallback check",
                        "data": {
                            "intent": intent,
                            "needs_fallback": needs_fallback,
                            "response_length": len(response_text),
                            "is_tech_qa": intent == Intent.TECH_QA
                        },
                        "sessionId": "kb-fallback",
                        "runId": "pre-fix",
                        "hypothesisId": "C"
                    }) + "\n")
            except: pass
            # #endregion
            
            # Если это не TECH_QA или нужен fallback - ищем в KB
            if intent != Intent.TECH_QA or needs_fallback:
                try:
                    from services.kb.search import search
                    from services.kb.summarize import format_answer
                    
                    # Используем контекст для улучшения поиска
                    context_text = ""
                    if context.get("recent_messages"):
                        user_messages = [msg for msg in context["recent_messages"][-5:] if msg.get("role") == "user"]
                        if user_messages:
                            context_text = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
                    
                    enhanced_query = f"{context_text} {message}".strip() if context_text else message
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now().isoformat(),
                                "location": "chat.py:generate_komettik_response",
                                "message": "KB search triggered",
                                "data": {
                                    "query": enhanced_query[:200],
                                    "intent": intent,
                                    "original_response_length": len(response_text)
                                },
                                "sessionId": "kb-fallback",
                                "runId": "pre-fix",
                                "hypothesisId": "D"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    hits = search(enhanced_query, limit=5)
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now().isoformat(),
                                "location": "chat.py:generate_komettik_response",
                                "message": "KB search results",
                                "data": {
                                    "hits_count": len(hits),
                                    "hits_preview": [{"url": h.get("url", ""), "title": h.get("title", "")} for h in hits[:3]]
                                },
                                "sessionId": "kb-fallback",
                                "runId": "pre-fix",
                                "hypothesisId": "D"
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    if hits:
                        # Если нашли результаты в KB - используем их
                        kb_answer = format_answer(enhanced_query, hits, max_bullets=7)
                        
                        # Если был ответ от handler'а, добавляем KB ответ после него
                        if response_text and response_text.strip() and intent != Intent.OFF_TOPIC:
                            response_text = f"{response_text}\n\n{kb_answer}"
                        else:
                            response_text = kb_answer
                        
                        # #region agent log
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "timestamp": datetime.now().isoformat(),
                                    "location": "chat.py:generate_komettik_response",
                                    "message": "KB fallback applied",
                                    "data": {
                                        "final_response_length": len(response_text),
                                        "kb_answer_length": len(kb_answer)
                                    },
                                    "sessionId": "kb-fallback",
                                    "runId": "pre-fix",
                                    "hypothesisId": "D"
                                }) + "\n")
                        except: pass
                        # #endregion
                except Exception as kb_error:
                    # Логируем ошибку KB, но не ломаем основной ответ
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now().isoformat(),
                                "location": "chat.py:generate_komettik_response",
                                "message": "KB search error",
                                "data": {
                                    "error": str(kb_error)
                                },
                                "sessionId": "kb-fallback",
                                "runId": "pre-fix",
                                "hypothesisId": "ERROR"
                            }) + "\n")
                    except: pass
                    # #endregion
                    pass
        
        # НЕ сохраняем ответ здесь - он будет сохранен после завершения стриминга в chats.py
        # Это гарантирует, что сообщение будет в БД когда фронтенд загрузит историю
        
        return response_text
    except Exception as e:
        # Используем единую систему обработки ошибок
        from services.error_handler import handle_error
        
        error_message = handle_error(
            e,
            "chat.py:generate_komettik_response",
            context={"intent": intent},
            session_id=chat_id,
            user_message=message
        )
        
        return error_message


async def stream_response(text: str, correlation_id: Optional[str] = None):
    """
    Потоковая передача ответа (SSE).
    Обрабатывает edge cases: пустой текст, очень длинный текст, спецсимволы.
    
    Args:
        text: Текст для стриминга
        correlation_id: Correlation ID для логирования (опционально)
    """
    # Логируем начало стриминга с correlation_id
    if correlation_id:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"[{correlation_id}] Starting SSE stream, text length: {len(text)}")
    if not text or not text.strip():
        # Пустой ответ - отправляем сразу
        yield f"data: {json.dumps({'type': 'token', 'content': text or ''})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return
    
    # Разбиваем на слова, но ограничиваем максимальное количество для производительности
    words = text.split(" ")
    max_words = 1000  # Защита от слишком длинных ответов
    
    if len(words) > max_words:
        # Для очень длинных ответов отправляем большими блоками
        chunk_size = 50
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            # Добавляем correlation_id в каждое SSE событие
            event_data = {'type': 'token', 'content': chunk}
            if correlation_id:
                event_data['correlation_id'] = correlation_id
            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(0.05)
    else:
        # Обычный режим - по одному слову
        for i, word in enumerate(words):
            if i > 0:
                space_event = {'type': 'token', 'content': ' '}
                if correlation_id:
                    space_event['correlation_id'] = correlation_id
                yield f"data: {json.dumps(space_event)}\n\n"
                await asyncio.sleep(0.05)  # Небольшая задержка между словами
            
            # Экранируем спецсимволы в JSON
            try:
                event_data = {'type': 'token', 'content': word}
                if correlation_id:
                    event_data['correlation_id'] = correlation_id
                word_json = json.dumps(event_data)
            except (UnicodeEncodeError, TypeError):
                # Если не удалось сериализовать, заменяем проблемные символы
                word_safe = word.encode('utf-8', errors='replace').decode('utf-8')
                event_data = {'type': 'token', 'content': word_safe}
                if correlation_id:
                    event_data['correlation_id'] = correlation_id
                word_json = json.dumps(event_data)
            
            yield f"data: {word_json}\n\n"
            await asyncio.sleep(0.1)  # Задержка для эффекта печатания
    
    # Финальное событие с correlation_id
    done_event = {'type': 'done'}
    if correlation_id:
        done_event['correlation_id'] = correlation_id
    yield f"data: {json.dumps(done_event)}\n\n"
