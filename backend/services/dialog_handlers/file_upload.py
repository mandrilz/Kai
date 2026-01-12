from typing import List

from api.chat import Attachment
from services.dialog_handlers.types import HandlerResult
from services.file_extractors import process_file
from services.prompt_templates import (
    get_file_upload_no_file,
    get_file_upload_processing,
    get_file_upload_success,
    get_file_upload_failed,
    get_file_upload_error,
)


def handle_file_upload(chat_id: str, attachments: List[Attachment]) -> HandlerResult:
    res = HandlerResult()
    try:
        if not attachments:
            res.response_parts.append(get_file_upload_no_file())
            return res

        res.response_parts.append(get_file_upload_processing())

        extracted_data = None
        for attachment in attachments:
            try:
                result = process_file(
                    attachment.filename,
                    attachment.content_type,
                    attachment.base64,
                )
                if result.get("success"):
                    extracted_data = result
                    break
            except Exception as e:
                # Логируем ошибку обработки файла, но продолжаем с другими файлами
                from services.error_handler import log_error
                log_error(
                    e,
                    "dialog_handlers.file_upload:handle_file_upload:process_file",
                    context={"filename": attachment.filename, "content_type": attachment.content_type},
                    session_id=chat_id,
                )
                continue

        if extracted_data and extracted_data.get("success"):
            model = extracted_data.get("model")
            brand = extracted_data.get("brand")
            power = extracted_data.get("power")
            
            success_parts = get_file_upload_success(model=model, brand=brand, power=power)
            res.response_parts.extend(success_parts)
        else:
            res.response_parts.append(get_file_upload_failed())
        return res
    except Exception as e:
        from services.error_handler import log_error
        log_error(
            e,
            "dialog_handlers.file_upload:handle_file_upload",
            context={"attachments_count": len(attachments) if attachments else 0},
            session_id=chat_id,
        )
        res.response_parts.append(get_file_upload_error())
        return res

