"""
Извлечение данных из файлов (PDF, изображения).
"""
import base64
import io
import re
from typing import Dict, Optional, Any
import pdfplumber
from PIL import Image
try:
    import pytesseract
    # Проверка доступности pytesseract (опционально)
    try:
        pytesseract.get_tesseract_version()
        TESSERACT_AVAILABLE = True
    except:
        TESSERACT_AVAILABLE = False
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None


def extract_from_pdf(base64_content: str) -> Dict[str, Any]:
    """
    Извлекает текст и данные из PDF файла.
    
    Args:
        base64_content: содержимое PDF в base64
        
    Returns:
        словарь с извлечёнными данными
    """
    try:
        pdf_bytes = base64.b64decode(base64_content)
        pdf_file = io.BytesIO(pdf_bytes)
        
        text_parts = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        full_text = "\n".join(text_parts)
        
        # Извлекаем данные
        extracted = extract_model_data(full_text)
        
        return {
            "success": True,
            "text": full_text,
            "model": extracted.get("model"),
            "brand": extracted.get("brand"),
            "power": extracted.get("power"),
            "raw_text": full_text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": ""
        }


def extract_from_image(base64_content: str, content_type: str) -> Dict[str, Any]:
    """
    Извлекает текст из изображения с помощью OCR.
    
    Args:
        base64_content: содержимое изображения в base64
        content_type: MIME тип (image/png, image/jpeg и т.д.)
        
    Returns:
        словарь с извлечёнными данными
    """
    if not TESSERACT_AVAILABLE or pytesseract is None:
        return {
            "success": False,
            "error": "OCR не доступен (pytesseract не установлен или Tesseract не найден)",
            "text": ""
        }
    
    try:
        image_bytes = base64.b64decode(base64_content)
        image = Image.open(io.BytesIO(image_bytes))
        
        # OCR
        text = pytesseract.image_to_string(image, lang="eng+rus")
        
        # Извлекаем данные
        extracted = extract_model_data(text)
        
        return {
            "success": True,
            "text": text,
            "model": extracted.get("model"),
            "brand": extracted.get("brand"),
            "power": extracted.get("power"),
            "raw_text": text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": ""
        }


def extract_model_data(text: str) -> Dict[str, Optional[str]]:
    """
    Извлекает модель, бренд и мощность из текста с помощью regex.
    
    Args:
        text: текст для анализа
        
    Returns:
        словарь с model, brand, power
    """
    text_upper = text.upper()
    
    # Поиск модели
    model = None
    model_patterns = [
        r"MODEL[:\s]+([A-Z0-9\s\-]+)",
        r"МОДЕЛЬ[:\s]+([A-Z0-9\s\-]+)",
        r"(CNP\s+[A-Z0-9\s\-]+)",
        r"(GRUNDFOS\s+[A-Z0-9\s\-]+)",
        r"(WILO\s+[A-Z0-9\s\-]+)",
        r"(PEDROLLO\s+[A-Z0-9\s\-]+)",
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text_upper)
        if match:
            model = match.group(1).strip()
            if len(model) >= 3:
                break
    
    # Поиск бренда
    brand = None
    brand_keywords = ["CNP", "GRUNDFOS", "WILO", "PEDROLLO", "КОМЕТТА", "KOMETTA"]
    for keyword in brand_keywords:
        if keyword in text_upper:
            brand = keyword
            break
    
    # Поиск мощности
    power = None
    power_patterns = [
        r"POWER[:\s]+(\d+\.?\d*)\s*KW",
        r"МОЩНОСТЬ[:\s]+(\d+\.?\d*)\s*КВТ",
        r"(\d+\.?\d*)\s*KW",
        r"(\d+\.?\d*)\s*КВТ",
    ]
    
    for pattern in power_patterns:
        match = re.search(pattern, text_upper)
        if match:
            try:
                power = float(match.group(1))
                break
            except:
                pass
    
    return {
        "model": model,
        "brand": brand,
        "power": str(power) if power else None
    }


def process_file(filename: str, content_type: str, base64_content: str) -> Dict[str, Any]:
    """
    Обрабатывает файл (PDF или изображение).
    
    Args:
        filename: имя файла
        content_type: MIME тип
        base64_content: содержимое в base64
        
    Returns:
        словарь с результатами обработки
    """
    if content_type == "application/pdf":
        return extract_from_pdf(base64_content)
    elif content_type.startswith("image/"):
        return extract_from_image(base64_content, content_type)
    else:
        return {
            "success": False,
            "error": f"Неподдерживаемый тип файла: {content_type}",
            "text": ""
        }

