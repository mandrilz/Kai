from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HandlerResult:
    """
    Унифицированный результат обработчика интента.
    - response_parts: части ответа, которые затем склеиваются через "\\n".join(...)
    - immediate_response: если нужно немедленно вернуть ответ (legacy поведение 'return' из ветки),
      например, при подтверждении модели в ANALOG_BY_MODEL.
    """

    response_parts: List[str] = field(default_factory=list)
    immediate_response: Optional[str] = None

