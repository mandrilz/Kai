"""
Общие типы для NLU (Natural Language Understanding) модуля.
Определяет структуры данных для контекста, результатов и обновлений слотов.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    """Типы интентов пользователя."""
    SELECTION_BY_POINT = "selection_by_point"  # Подбор по рабочей точке (Q/H)
    ANALOG_BY_MODEL = "analog_by_model"  # Поиск аналога по модели
    DOCUMENTATION = "documentation"  # Запрос документации/характеристик
    TECH_QA = "tech_qa"  # Технический вопрос
    OFF_TOPIC = "off_topic"  # Не по теме
    FILE_UPLOAD = "file_upload"  # Загрузка файла
    PUMP_TYPE = "pump_type"  # Запрос по типу насоса
    MATERIALS_QUERY = "materials_query"  # Запрос о материалах
    DIAGNOSTICS = "diagnostics"  # Диагностика проблем с насосом


@dataclass
class NormalizedMessage:
    """Нормализованное сообщение пользователя."""
    original: str  # Оригинальный текст
    normalized: str  # Нормализованный текст (lowercase, единые единицы, числа)
    has_attachments: bool = False  # Есть ли вложения


@dataclass
class SlotUpdates:
    """Обновления слотов состояния диалога."""
    flow_m3h: Optional[float] = None  # Расход в м³/ч
    head_m: Optional[float] = None  # Напор в метрах
    fluid: Optional[str] = None  # Жидкость
    temperature_c: Optional[float] = None  # Температура в °C
    viscosity: Optional[float] = None  # Вязкость
    concentration: Optional[float] = None  # Концентрация
    solids: Optional[bool] = None  # Наличие примесей
    h_st: Optional[float] = None  # Статический напор
    installation: Optional[str] = None  # Тип установки
    materials: Optional[str] = None  # Материалы
    body_material_code: Optional[str] = None  # Код материала корпуса
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь, исключая None значения."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = value
        return result
    
    def has_updates(self) -> bool:
        """Проверяет, есть ли какие-либо обновления."""
        return any(v is not None for v in self.__dict__.values())


@dataclass
class IntentResult:
    """Результат определения интента."""
    intent: Intent  # Определенный интент
    data: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные
    confidence: float = 1.0  # Уверенность (0.0-1.0)


@dataclass
class SlotFillResult:
    """Результат заполнения слотов."""
    updates: SlotUpdates  # Обновления слотов
    confidence: float = 0.8  # Общая уверенность
    next_slot: Optional[str] = None  # Следующий слот для уточнения
    needs_clarification: bool = False  # Нужно ли уточнение
    next_question: Optional[str] = None  # Вопрос для уточнения
    note: Optional[str] = None  # Примечание


@dataclass
class NLUContext:
    """Контекст для NLU обработки."""
    chat_id: str  # ID чата
    message: str  # Сообщение пользователя
    has_attachments: bool = False  # Есть ли вложения
    state: Dict[str, Any] = field(default_factory=dict)  # Текущее состояние диалога
    pending_slot: Optional[str] = None  # Ожидаемый слот
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)  # Последние сообщения


@dataclass
class NLUResult:
    """Итоговый результат NLU обработки."""
    intent: IntentResult  # Определенный интент
    slot_updates: SlotFillResult  # Обновления слотов
    normalized_message: NormalizedMessage  # Нормализованное сообщение
