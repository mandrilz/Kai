"""
Пакет для управления диалогом.
Содержит единый orchestrator для координации NLU, slot filling и генерации ответов.
"""
from services.dialogue.manager import DialogueManager, DialogueTurn, DialogueResult

__all__ = ["DialogueManager", "DialogueTurn", "DialogueResult"]
