from services.dialog_handlers.types import HandlerResult


def handle_off_topic() -> HandlerResult:
    res = HandlerResult()
    res.response_parts.append(
        "Привет! Я Кометтик — инженер-помощник Кометта. "
        "Я помогаю с подбором насосов и поиском аналогов. "
        "Задайте вопрос по насосам, и я помогу!"
    )
    res.response_parts.append("\n\nМогу помочь с:")
    res.response_parts.append("• Подбором насоса по рабочей точке (Q и H)")
    res.response_parts.append("• Поиском аналога насоса конкурента")
    res.response_parts.append("• Анализом шильдика или документации")
    return res

