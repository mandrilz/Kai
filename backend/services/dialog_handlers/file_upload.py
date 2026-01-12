from typing import List

from api.chat import Attachment
from services.dialog_handlers.types import HandlerResult
from services.file_extractors import process_file


def handle_file_upload(chat_id: str, attachments: List[Attachment]) -> HandlerResult:
    res = HandlerResult()
    try:
        if not attachments:
            res.response_parts.append("Прикрепите файл (PDF или изображение), и я попробую извлечь данные.")
            return res

        res.response_parts.append("Обрабатываю файл...\n")

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
                    "chat.py:generate_komettik_response:FILE_UPLOAD:process_file",
                    context={"filename": attachment.filename, "content_type": attachment.content_type},
                    session_id=chat_id,
                )
                continue

        if extracted_data and extracted_data.get("success"):
            model = extracted_data.get("model")
            brand = extracted_data.get("brand")
            power = extracted_data.get("power")

            res.response_parts.append("Извлёк данные из файла:\n")

            if model:
                res.response_parts.append(f"Модель: {model}")
            if brand:
                res.response_parts.append(f"Бренд: {brand}")
            if power:
                res.response_parts.append(f"Мощность: {power} кВт")

            if model:
                res.response_parts.append(f"\nЯ правильно понял модель {model}?")
                res.response_parts.append("Если да, могу найти аналог или подобрать насос по параметрам.")
            else:
                res.response_parts.append("\nНе удалось извлечь модель. Попробуйте указать её вручную.")
        else:
            res.response_parts.append(
                "Не удалось обработать файл. "
                "Попробуйте указать модель насоса в тексте сообщения."
            )
        return res
    except Exception as e:
        from services.error_handler import log_error
        log_error(
            e,
            "chat.py:generate_komettik_response:FILE_UPLOAD",
            context={"attachments_count": len(attachments) if attachments else 0},
            session_id=chat_id,
        )
        res.response_parts.append(
            "Извините, произошла ошибка при обработке файла. "
            "Пожалуйста, попробуйте ещё раз или укажите модель насоса в тексте сообщения."
        )
        return res

