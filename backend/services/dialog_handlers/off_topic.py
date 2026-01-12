from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import (
    get_off_topic_intro,
    get_off_topic_capabilities,
)


def handle_off_topic() -> HandlerResult:
    res = HandlerResult()
    res.response_parts.extend(get_off_topic_intro())
    res.response_parts.append("\n\nМогу помочь с:")
    res.response_parts.extend(get_off_topic_capabilities())
    return res

