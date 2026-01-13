from enum import Enum
from typing import Dict, Any, Optional


class FSMState(str, Enum):
    INTENT_DETECTION = "INTENT_DETECTION"
    SLOT_FILLING = "SLOT_FILLING"
    RESPONSE_GENERATION = "RESPONSE_GENERATION"
    FOLLOW_UP = "FOLLOW_UP"


class DialogState:
    """
    Класс для хранения состояния FSM диалога.
    """
    def __init__(
        self,
        current_state: FSMState = FSMState.INTENT_DETECTION,
        intent: Optional[str] = None,
        slots: Dict[str, Any] = None,
        pending_slot: Optional[str] = None,
        last_question: Optional[str] = None,
        data: Dict[str, Any] = None,
    ):
        self.current_state = current_state
        self.intent = intent
        self.slots = slots if slots is not None else {}
        self.pending_slot = pending_slot
        self.last_question = last_question
        self.data = data if data is not None else {}

    def to_dict(self):
        """Сериализует состояние в словарь для сохранения."""
        return {
            "current_state": self.current_state.value if isinstance(self.current_state, FSMState) else self.current_state,
            "intent": self.intent,
            "slots": self.slots,
            "pending_slot": self.pending_slot,
            "last_question": self.last_question,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Восстанавливает состояние из словаря."""
        current_state_str = data.get("current_state", FSMState.INTENT_DETECTION.value)
        try:
            current_state = FSMState(current_state_str)
        except ValueError:
            current_state = FSMState.INTENT_DETECTION
        
        return cls(
            current_state=current_state,
            intent=data.get("intent"),
            slots=data.get("slots", {}),
            pending_slot=data.get("pending_slot"),
            last_question=data.get("last_question"),
            data=data.get("data", {}),
        )

