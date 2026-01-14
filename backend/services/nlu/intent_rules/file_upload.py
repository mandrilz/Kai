"""
Правило для определения интента FILE_UPLOAD.
"""
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult


def check_file_upload(
    message: str,
    has_attachments: bool,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос загрузкой файла.
    
    Args:
        message: Сообщение пользователя
        has_attachments: Есть ли вложения
        context: Контекст диалога
        
    Returns:
        IntentResult с FILE_UPLOAD или None
    """
    if has_attachments:
        return IntentResult(
            intent=Intent.FILE_UPLOAD,
            data={},
            confidence=1.0
        )
    
    return None
