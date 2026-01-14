"""
NLU (Natural Language Understanding) модуль.
Предоставляет типы, предобработку текста и компоненты для понимания пользовательских сообщений.
"""
from .types import (
    Intent,
    NormalizedMessage,
    SlotUpdates,
    IntentResult,
    SlotFillResult,
    NLUContext,
    NLUResult,
)
from .preprocess import (
    normalize_text,
    normalize_numbers,
    normalize_units,
    normalize_lookalikes,
)

__all__ = [
    "Intent",
    "NormalizedMessage",
    "SlotUpdates",
    "IntentResult",
    "SlotFillResult",
    "NLUContext",
    "NLUResult",
    "normalize_text",
    "normalize_numbers",
    "normalize_units",
    "normalize_lookalikes",
]
