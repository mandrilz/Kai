"""
Общие типы для API endpoints.
"""
from pydantic import BaseModel


class Attachment(BaseModel):
    filename: str
    content_type: str
    base64: str
