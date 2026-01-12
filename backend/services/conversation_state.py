"""
Управление состоянием диалога с историей сообщений и слотами.
Поддерживает работу с chat_id (БД) и session_id (legacy, in-memory).
"""
from typing import Dict, Any, Optional, List
import json
import os
from datetime import datetime
from uuid import UUID
from models import Chat, Message, ConversationState, get_session, select
from sqlmodel import Session

# Временное хранилище для значений температуры без знака (для chat_id)
_temp_without_sign: Dict[str, float] = {}

# Legacy: глобальное хранилище для session_id (для обратной совместимости)
_conversations: Dict[str, Dict[str, Any]] = {}


# Схема слотов для подбора насоса
SLOT_SCHEMA = {
    "fluid": {"type": str, "description": "Тип жидкости (вода, этиленгликоль, масло и т.д.)"},
    "temperature_c": {"type": float, "description": "Температура жидкости в градусах Цельсия"},
    "flow_m3h": {"type": float, "description": "Расход в м³/ч"},
    "head_m": {"type": float, "description": "Напор в метрах"},
    "viscosity": {"type": float, "description": "Вязкость (если нужно)"},
    "concentration": {"type": float, "description": "Концентрация (для этиленгликоля и т.д.)"},
    "solids": {"type": bool, "description": "Наличие твердых частиц/примесей"},
    "installation": {"type": str, "description": "Тип установки (вертикальный/горизонтальный)"},
    "materials": {"type": str, "description": "Требуемые материалы (A/E/X/H)"},
    "body_material_code": {"type": str, "description": "Материал корпуса насоса (код: 04=304, 16=316, 25=чугун)"},
    "h_st": {"type": float, "description": "Статический напор сети"},
    "pending_analog_confirmation": {"type": dict, "description": "Ожидание подтверждения модели для поиска аналога"},
    "pump_type_info": {"type": dict, "description": "Информация о типе насоса (серия, тип и т.д.)"},
    "last_selected_pump": {"type": dict, "description": "Информация о последнем выбранном насосе (articul, model, brand и т.д.)"},
}


def _is_uuid(s: str) -> bool:
    """Проверяет, является ли строка UUID."""
    try:
        UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


def get_conversation(chat_id: str, session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Получает полное состояние диалога из БД (для chat_id) или памяти (для session_id).
    
    Args:
        chat_id: ID чата (UUID) или session_id (legacy)
        session: Сессия БД (опционально, создается автоматически)
    
    Returns:
        {
            "messages": List[Dict],
            "state": Dict,
            "pending_slot": str | None,
            "last_question": str | None,
            "dialog_summary": str | None,
            "updated_at": str,
            "created_at": str
        }
    """
    if not chat_id or not isinstance(chat_id, str) or not chat_id.strip():
        raise ValueError(f"chat_id не может быть пустым: {chat_id}")
    
    chat_id = chat_id.strip()
    
    # Если это UUID (chat_id) - работаем с БД
    if _is_uuid(chat_id):
        return _get_conversation_from_db(chat_id, session)
    else:
        # Legacy: session_id - работаем с памятью
        return _get_conversation_from_memory(chat_id)


def _get_conversation_from_db(chat_id: str, session: Optional[Session] = None) -> Dict[str, Any]:
    """Получает состояние диалога из БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        chat = session.get(Chat, chat_uuid)
        
        if not chat:
            raise ValueError(f"Чат {chat_id} не найден")
        
        # Загружаем состояние
        conv_state = session.exec(
            select(ConversationState).where(ConversationState.chat_id == chat_uuid)
        ).first()
        
        if not conv_state:
            # Создаем пустое состояние
            conv_state = ConversationState(chat_id=chat_uuid)
            session.add(conv_state)
            session.commit()
            session.refresh(conv_state)
        
        # Загружаем сообщения
        messages = session.exec(
            select(Message)
            .where(Message.chat_id == chat_uuid)
            .order_by(Message.created_at.asc())
        ).all()
        
        # Парсим state из JSON
        try:
            state = json.loads(conv_state.state) if conv_state.state else {}
        except:
            state = {slot: None for slot in SLOT_SCHEMA.keys()}
        
        # Формируем результат
        return {
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
            "state": {slot: state.get(slot) for slot in SLOT_SCHEMA.keys()},
            "pending_slot": conv_state.pending_slot,
            "last_question": conv_state.last_question,
            "dialog_summary": conv_state.dialog_summary,
            "updated_at": conv_state.updated_at.isoformat(),
            "created_at": chat.created_at.isoformat(),
        }
    finally:
        if close_session:
            session.close()


def _get_conversation_from_memory(session_id: str) -> Dict[str, Any]:
    """Legacy: получает состояние диалога из памяти."""
    if session_id not in _conversations:
        _conversations[session_id] = {
            "messages": [],
            "state": {slot: None for slot in SLOT_SCHEMA.keys()},
            "pending_slot": None,
            "last_question": None,
            "dialog_summary": None,
            "updated_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
    return _conversations[session_id]


def add_message(chat_id: str, role: str, content: str, session: Optional[Session] = None, attachments: Optional[str] = None) -> None:
    """Добавляет сообщение в историю диалога (БД или память)."""
    if _is_uuid(chat_id):
        _add_message_to_db(chat_id, role, content, session, attachments)
    else:
        _add_message_to_memory(chat_id, role, content)


def _add_message_to_db(chat_id: str, role: str, content: str, session: Optional[Session] = None, attachments: Optional[str] = None) -> None:
    """Добавляет сообщение в БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        
        # Создаем сообщение
        message = Message(
            chat_id=chat_uuid,
            role=role,
            content=content,
            attachments=json.dumps(attachments) if attachments else None,
        )
        session.add(message)
        
        # Обновляем updated_at чата
        chat = session.get(Chat, chat_uuid)
        if chat:
            chat.updated_at = datetime.utcnow()
            session.add(chat)
        
        session.commit()
        
        # Авто-резюме если диалог длинный
        messages_count = session.exec(
            select(Message).where(Message.chat_id == chat_uuid)
        ).all()
        if len(messages_count) > 30:
            generate_summary(chat_id, session)
    finally:
        if close_session:
            session.close()


def _add_message_to_memory(session_id: str, role: str, content: str) -> None:
    """Legacy: добавляет сообщение в память."""
    conv = _get_conversation_from_memory(session_id)
    conv["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    conv["updated_at"] = datetime.now().isoformat()
    
    if len(conv["messages"]) > 30:
        generate_summary(session_id)


def update_state(chat_id: str, updates: Dict[str, Any], pending_slot: Optional[str] = None, keep_pending_if_not_set: bool = True, session: Optional[Session] = None) -> None:
    """Обновляет слоты состояния (БД или память)."""
    if _is_uuid(chat_id):
        _update_state_in_db(chat_id, updates, pending_slot, keep_pending_if_not_set, session)
    else:
        _update_state_in_memory(chat_id, updates, pending_slot, keep_pending_if_not_set)


def _update_state_in_db(chat_id: str, updates: Dict[str, Any], pending_slot: Optional[str] = None, keep_pending_if_not_set: bool = True, session: Optional[Session] = None) -> None:
    """Обновляет состояние в БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        conv_state = session.exec(
            select(ConversationState).where(ConversationState.chat_id == chat_uuid)
        ).first()
        
        if not conv_state:
            conv_state = ConversationState(chat_id=chat_uuid)
            session.add(conv_state)
            session.commit()
            session.refresh(conv_state)
        
        # Парсим текущее состояние
        try:
            state = json.loads(conv_state.state) if conv_state.state else {}
        except:
            state = {}
        
        # Обновляем слоты
        for slot, value in updates.items():
            if slot in SLOT_SCHEMA:
                slot_type = SLOT_SCHEMA[slot]["type"]
                if value is not None:
                    try:
                        if slot_type == float:
                            state[slot] = float(value)
                        elif slot_type == bool:
                            state[slot] = bool(value)
                        elif slot_type == str:
                            state[slot] = str(value)
                        elif slot_type == dict:
                            # Для dict (например, pump_type_info) нужно убедиться, что все значения JSON-сериализуемы
                            # Конвертируем Enum в строки, если есть (рекурсивно обрабатываем вложенные структуры)
                            if isinstance(value, dict):
                                def _make_serializable(obj):
                                    """Рекурсивно конвертирует объекты в JSON-сериализуемые значения"""
                                    if isinstance(obj, dict):
                                        return {k: _make_serializable(v) for k, v in obj.items()}
                                    elif isinstance(obj, list):
                                        return [_make_serializable(item) for item in obj]
                                    elif hasattr(obj, 'value') and hasattr(obj, '__class__'):
                                        # Это Enum - конвертируем в строку
                                        try:
                                            return obj.value
                                        except:
                                            return str(obj)
                                    else:
                                        return obj
                                
                                serializable_value = _make_serializable(value)
                                state[slot] = serializable_value
                            else:
                                state[slot] = value
                        else:
                            state[slot] = value
                    except (ValueError, TypeError) as e:
                        # Если ошибка при конвертации - пытаемся сохранить как есть
                        state[slot] = value
        
        # Обновляем pending_slot
        if pending_slot is not None:
            conv_state.pending_slot = pending_slot
        elif not keep_pending_if_not_set:
            conv_state.pending_slot = None
        
        # Сохраняем состояние
        # ВАЖНО: убеждаемся, что state полностью сериализуем в JSON
        # Если есть ошибка, пытаемся сериализовать с обработкой специальных типов
        try:
            conv_state.state = json.dumps(state, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            # Если все еще ошибка, делаем дополнительную очистку
            def _clean_for_json(obj):
                """Дополнительная очистка для JSON сериализации"""
                if isinstance(obj, dict):
                    return {k: _clean_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [_clean_for_json(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    return str(obj)
                else:
                    return obj
            
            cleaned_state = _clean_for_json(state)
            conv_state.state = json.dumps(cleaned_state, ensure_ascii=False, default=str)
        
        conv_state.updated_at = datetime.utcnow()
        session.add(conv_state)
        session.commit()
        
        # Логирование
        _log_state_update(chat_id, updates, pending_slot)
    finally:
        if close_session:
            session.close()


def _update_state_in_memory(session_id: str, updates: Dict[str, Any], pending_slot: Optional[str] = None, keep_pending_if_not_set: bool = True) -> None:
    """Legacy: обновляет состояние в памяти."""
    conv = _get_conversation_from_memory(session_id)
    
    for slot, value in updates.items():
        if slot in SLOT_SCHEMA:
            slot_type = SLOT_SCHEMA[slot]["type"]
            if value is not None:
                try:
                    if slot_type == float:
                        conv["state"][slot] = float(value)
                    elif slot_type == bool:
                        conv["state"][slot] = bool(value)
                    elif slot_type == str:
                        conv["state"][slot] = str(value)
                    else:
                        conv["state"][slot] = value
                except (ValueError, TypeError):
                    conv["state"][slot] = value
    
    if pending_slot is not None:
        conv["pending_slot"] = pending_slot
    elif not keep_pending_if_not_set:
        conv["pending_slot"] = None
    
    conv["updated_at"] = datetime.now().isoformat()
    _log_state_update(session_id, updates, pending_slot)


def _log_state_update(chat_id: str, updates: Dict[str, Any], pending_slot: Optional[str]) -> None:
    """Логирует обновление состояния."""
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "conversation_state.py:update_state",
                "message": "State updated",
                "data": {
                    "chat_id": chat_id,
                    "updates": updates,
                    "pending_slot": pending_slot
                },
                "runId": "state",
            }, ensure_ascii=False) + "\n")
    except:
        pass


def set_last_question(chat_id: str, question: str, session: Optional[Session] = None) -> None:
    """Устанавливает последний заданный вопрос."""
    if _is_uuid(chat_id):
        _set_last_question_in_db(chat_id, question, session)
    else:
        _set_last_question_in_memory(chat_id, question)


def _set_last_question_in_db(chat_id: str, question: str, session: Optional[Session] = None) -> None:
    """Устанавливает последний вопрос в БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        conv_state = session.exec(
            select(ConversationState).where(ConversationState.chat_id == chat_uuid)
        ).first()
        
        if conv_state:
            conv_state.last_question = question
            conv_state.updated_at = datetime.utcnow()
            session.add(conv_state)
            session.commit()
    finally:
        if close_session:
            session.close()


def _set_last_question_in_memory(session_id: str, question: str) -> None:
    """Legacy: устанавливает последний вопрос в памяти."""
    conv = _get_conversation_from_memory(session_id)
    conv["last_question"] = question
    conv["updated_at"] = datetime.now().isoformat()


def get_recent_messages(chat_id: str, n: int = 10, session: Optional[Session] = None) -> List[Dict[str, str]]:
    """Возвращает последние N сообщений."""
    conv = get_conversation(chat_id, session)
    return conv["messages"][-n:]


def get_context_for_model(chat_id: str, max_messages: int = 20, session: Optional[Session] = None) -> Dict[str, Any]:
    """Формирует контекст для модели."""
    conv = get_conversation(chat_id, session)
    
    # Дополняем контекст состоянием материалов (session_state.py)
    try:
        from services.session_state import get_session_state
        materials_state = get_session_state(chat_id).copy()
    except Exception:
        materials_state = None
    
    return {
        "chat_id": chat_id,  # Используем chat_id вместо session_id
        "session_id": chat_id,  # Для обратной совместимости
        "state": conv["state"].copy(),
        "pending_slot": conv["pending_slot"],
        "last_question": conv["last_question"],
        "dialog_summary": conv["dialog_summary"],
        "recent_messages": get_recent_messages(chat_id, max_messages, session),
        "full_message_count": len(conv["messages"]),
        "materials_state": materials_state,
    }


def generate_summary(chat_id: str, session: Optional[Session] = None) -> None:
    """Генерирует краткое резюме диалога."""
    if _is_uuid(chat_id):
        _generate_summary_in_db(chat_id, session)
    else:
        _generate_summary_in_memory(chat_id)


def _generate_summary_in_db(chat_id: str, session: Optional[Session] = None) -> None:
    """Генерирует резюме в БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        conv_state = session.exec(
            select(ConversationState).where(ConversationState.chat_id == chat_uuid)
        ).first()
        
        if not conv_state:
            return
        
        # Парсим состояние
        try:
            state = json.loads(conv_state.state) if conv_state.state else {}
        except:
            state = {}
        
        filled_slots = {k: v for k, v in state.items() if v is not None}
        
        summary_parts = []
        if filled_slots.get("fluid"):
            summary_parts.append(f"Жидкость: {filled_slots['fluid']}")
        if filled_slots.get("temperature_c"):
            summary_parts.append(f"Температура: {filled_slots['temperature_c']}°C")
        if filled_slots.get("flow_m3h"):
            summary_parts.append(f"Расход: {filled_slots['flow_m3h']} м³/ч")
        if filled_slots.get("head_m"):
            summary_parts.append(f"Напор: {filled_slots['head_m']} м")
        
        if summary_parts:
            conv_state.dialog_summary = ". ".join(summary_parts) + "."
        else:
            conv_state.dialog_summary = "Диалог начат, параметры уточняются."
        
        conv_state.updated_at = datetime.utcnow()
        session.add(conv_state)
        session.commit()
    finally:
        if close_session:
            session.close()


def _generate_summary_in_memory(session_id: str) -> None:
    """Legacy: генерирует резюме в памяти."""
    conv = _get_conversation_from_memory(session_id)
    
    if len(conv["messages"]) <= 20:
        return
    
    filled_slots = {k: v for k, v in conv["state"].items() if v is not None}
    
    summary_parts = []
    if filled_slots.get("fluid"):
        summary_parts.append(f"Жидкость: {filled_slots['fluid']}")
    if filled_slots.get("temperature_c"):
        summary_parts.append(f"Температура: {filled_slots['temperature_c']}°C")
    if filled_slots.get("flow_m3h"):
        summary_parts.append(f"Расход: {filled_slots['flow_m3h']} м³/ч")
    if filled_slots.get("head_m"):
        summary_parts.append(f"Напор: {filled_slots['head_m']} м")
    
    if summary_parts:
        conv["dialog_summary"] = ". ".join(summary_parts) + "."
    else:
        conv["dialog_summary"] = "Диалог начат, параметры уточняются."
    
    conv["messages"] = conv["messages"][-10:]
    conv["updated_at"] = datetime.now().isoformat()


def clear_conversation(chat_id: str, session: Optional[Session] = None) -> None:
    """Очищает диалог."""
    if _is_uuid(chat_id):
        # В БД не удаляем, только очищаем состояние
        _clear_conversation_in_db(chat_id, session)
    else:
        _clear_conversation_in_memory(chat_id)
    
    # Очищаем состояние материалов
    try:
        from services.session_state import clear_session_state
        clear_session_state(chat_id)
    except Exception:
        pass
    
    # Очищаем временное значение температуры
    clear_temp_without_sign(chat_id)


def _clear_conversation_in_db(chat_id: str, session: Optional[Session] = None) -> None:
    """Очищает состояние в БД."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    
    try:
        chat_uuid = UUID(chat_id)
        conv_state = session.exec(
            select(ConversationState).where(ConversationState.chat_id == chat_uuid)
        ).first()
        
        if conv_state:
            conv_state.state = "{}"
            conv_state.pending_slot = None
            conv_state.last_question = None
            conv_state.dialog_summary = None
            conv_state.updated_at = datetime.utcnow()
            session.add(conv_state)
            session.commit()
    finally:
        if close_session:
            session.close()


def _clear_conversation_in_memory(session_id: str) -> None:
    """Legacy: очищает диалог в памяти."""
    if session_id in _conversations:
        del _conversations[session_id]


# Функции для работы с температурой без знака
def get_temp_without_sign(chat_id: str) -> Optional[float]:
    """Получает сохраненное значение температуры без знака."""
    return _temp_without_sign.get(chat_id)


def set_temp_without_sign(chat_id: str, temp: float) -> None:
    """Сохраняет значение температуры без знака."""
    _temp_without_sign[chat_id] = temp


def clear_temp_without_sign(chat_id: str) -> None:
    """Очищает сохраненное значение температуры без знака."""
    if chat_id in _temp_without_sign:
        del _temp_without_sign[chat_id]


# Функция parse_short_answer остается без изменений (использует chat_id)
def parse_short_answer(text: str, pending_slot: Optional[str], chat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Парсит ответы с привязкой к pending_slot.
    """
    if not pending_slot:
        return None
    
    text_lower = text.lower().strip()
    
    # Специальная обработка для температуры
    if pending_slot == "temperature_c" and chat_id:
        saved_temp = get_temp_without_sign(chat_id)
        if saved_temp is not None:
            # Отрицательная температура (минус)
            if any(word in text_lower for word in ["минус", "минусовая", "отрицательная", "ниже нуля", "-", "нет, минус", "минус"]):
                clear_temp_without_sign(chat_id)
                return {
                    "updates": {"temperature_c": -saved_temp},
                    "confidence": 0.95,
                    "next_slot": None,
                    "needs_sign_clarification": False
                }
            # Положительная температура (плюс) или подтверждение
            elif any(word in text_lower for word in ["плюс", "плюсовая", "положительная", "выше нуля", "+", "плюс"]):
                clear_temp_without_sign(chat_id)
                return {
                    "updates": {"temperature_c": saved_temp},
                    "confidence": 0.95,
                    "next_slot": None,
                    "needs_sign_clarification": False
                }
            # Положительные ответы ("да", "верно", "ага", "конечно") - подтверждают положительную температуру
            # Это используется при уточнении: "Вода +20 градусов, верно?" -> "да" = +20°C
            elif any(word in text_lower for word in ["да", "верно", "ага", "конечно", "правильно", "точно", 
                                                      "yes", "correct", "right", "точно", "именно так", "согласен"]):
                clear_temp_without_sign(chat_id)
                # По умолчанию предполагаем положительную температуру (как было в вопросе)
                return {
                    "updates": {"temperature_c": saved_temp},
                    "confidence": 0.9,
                    "next_slot": None,
                    "needs_sign_clarification": False
                }
    
    # Парсинг температуры
    if pending_slot == "temperature_c":
        import re
        
        minus_word_match = re.search(r'минус\s+(\d+(?:[.,]\d+)?)', text_lower)
        if minus_word_match:
            try:
                temp = -float(minus_word_match.group(1).replace(',', '.'))
                if -50 <= temp <= 200:
                    return {
                        "updates": {"temperature_c": temp},
                        "confidence": 0.9,
                        "next_slot": None,
                        "needs_sign_clarification": False
                    }
            except (ValueError, IndexError):
                pass
        
        plus_word_match = re.search(r'плюс\s+(\d+(?:[.,]\d+)?)', text_lower)
        if plus_word_match:
            try:
                temp = float(plus_word_match.group(1).replace(',', '.'))
                if -50 <= temp <= 200:
                    return {
                        "updates": {"temperature_c": temp},
                        "confidence": 0.9,
                        "next_slot": None,
                        "needs_sign_clarification": False
                    }
            except (ValueError, IndexError):
                pass
        
        patterns_with_sign = [
            r'([+-]\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|с\b|c\b)',
            r'([+-]\d+(?:[.,]\d+)?)\s*(?:°|c\b|с\b)',
        ]
        for pattern in patterns_with_sign:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp = float(temp_str)
                    if -50 <= temp <= 200:
                        return {
                            "updates": {"temperature_c": temp},
                            "confidence": 0.9,
                            "next_slot": None,
                            "needs_sign_clarification": False
                        }
                except (ValueError, IndexError):
                    pass
        
        patterns_without_sign = [
            r'(\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|с\b|c\b)',
            r'(?:темп|temp)[\s:]+(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*(?:°|c\b|с\b)',
            r'(\d+(?:[.,]\d+)?)(?:\s|$)'
        ]
        for pattern in patterns_without_sign:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp = float(temp_str)
                    if -50 <= temp <= 200:
                        if chat_id:
                            set_temp_without_sign(chat_id, temp)
                        return {
                            "updates": {},
                            "confidence": 0.7,
                            "next_slot": "temperature_c",
                            "needs_sign_clarification": True,
                            "detected_value": temp
                        }
                except (ValueError, IndexError):
                    pass
    
    # Парсинг расхода
    elif pending_slot == "flow_m3h":
        from services.q_extractor import extract_q_from_text
        q_data = extract_q_from_text(text)
        if q_data and q_data.get("q_m3h"):
            return {
                "updates": {"flow_m3h": q_data["q_m3h"]},
                "confidence": q_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг напора
    elif pending_slot == "head_m":
        from services.h_extractor import extract_h_from_text
        h_data = extract_h_from_text(text)
        if h_data and h_data.get("h_m"):
            return {
                "updates": {"head_m": h_data["h_m"]},
                "confidence": h_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг статического напора
    elif pending_slot == "h_st":
        from services.h_extractor import extract_h_from_text
        h_data = extract_h_from_text(text)
        if h_data and h_data.get("h_m"):
            return {
                "updates": {"h_st": h_data["h_m"]},
                "confidence": h_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг жидкости
    elif pending_slot == "fluid":
        fluid_keywords = {
            "этиленгликоль": "этиленгликоль",
            "пропиленгликоль": "пропиленгликоль",
            "вода": "вода",
            "water": "вода",
            "масло": "масло",
            "oil": "масло",
            "гликоль": "этиленгликоль",
            "антифриз": "этиленгликоль"
        }
        for keyword, fluid in fluid_keywords.items():
            if keyword in text_lower:
                return {
                    "updates": {"fluid": fluid},
                    "confidence": 0.85,
                    "next_slot": None
                }
    
    # Парсинг наличия примесей
    elif pending_slot == "solids":
        if any(word in text_lower for word in ["да", "yes", "есть", "присутствуют", "имеются"]):
            return {
                "updates": {"solids": True},
                "confidence": 0.8,
                "next_slot": None
            }
        elif any(word in text_lower for word in ["нет", "no", "нету", "отсутствуют", "без"]):
            return {
                "updates": {"solids": False},
                "confidence": 0.8,
                "next_slot": None
            }
    
    return None
