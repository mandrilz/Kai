"""
Обработчик интента PUMP_TYPE - запросы по типу насоса.
"""
from typing import Dict, Any
import logging
from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import (
    get_pump_type_unknown,
    get_pump_type_error,
)
from services.selector import select_by_working_point
from services.slot_extractor import extract_qh_from_text

logger = logging.getLogger(__name__)


def handle_pump_type(
    *,
    message: str,
    data: Dict[str, Any],
) -> HandlerResult:
    """
    Обрабатывает запросы по типу насоса.
    
    Args:
        message: Текст сообщения пользователя
        data: Извлеченные данные из сообщения (intent detection)
    
    Returns:
        HandlerResult с частями ответа
    """
    result = HandlerResult()
    
    try:
        pump_type_info_raw = data.get("pump_type_info")
        
        # Убеждаемся, что pump_type_info - это dict
        if not isinstance(pump_type_info_raw, dict):
            pump_type_info = {}
        else:
            pump_type_info = pump_type_info_raw.copy()
        
        if pump_type_info:
            # Используем функцию генерации ответа из модуля pump_types
            from services.pump_types import generate_type_response, PumpTypeAvailability
            
            # ВАЖНО: pump_type_info может быть загружен из состояния, где availability - строка
            # Нужно нормализовать для правильного сравнения
            if isinstance(pump_type_info.get("availability"), str):
                availability_str = pump_type_info.get("availability")
                if availability_str == "available":
                    pump_type_info["availability"] = PumpTypeAvailability.AVAILABLE
                elif availability_str == "not_available":
                    pump_type_info["availability"] = PumpTypeAvailability.NOT_AVAILABLE
            
            try:
                type_response = generate_type_response(pump_type_info)
                result.response_parts.append(type_response)
            except Exception as e:
                logger.error(f"Error generating type response: {str(e)}")
                result.response_parts.append("Информация о типе насоса получена, но возникла ошибка при генерации ответа.")
            
            # Если тип есть у Кометта и есть Q/H в сообщении, сразу подбираем
            availability = pump_type_info.get("availability")
            is_available = (
                availability == PumpTypeAvailability.AVAILABLE or
                (isinstance(availability, str) and availability == "available")
            )
            
            if is_available:
                qh_data = extract_qh_from_text(message)
                if qh_data:
                    q = qh_data.get("q")
                    h = qh_data.get("h")
                    if q and h:
                        result.response_parts.append(f"\n\n---\n\n**Подбор по рабочей точке Q = {q} м³/ч, H = {h} м:**\n")
                        
                        # Фильтруем по серии, если известна
                        series_raw = pump_type_info.get("series")
                        if isinstance(series_raw, list):
                            series_list = series_raw
                        elif isinstance(series_raw, str):
                            series_list = [series_raw]
                        else:
                            series_list = []
                        pumps = select_by_working_point(q, h, top_n=50)
                        
                        if series_list:
                            # Фильтруем по серии
                            filtered_pumps = [p for p in pumps if any(s in p.get("model", "") or s in p.get("series", "") for s in series_list)]
                            if filtered_pumps:
                                pumps = filtered_pumps
                        
                        if pumps:
                            for i, pump in enumerate(pumps, 1):
                                # Формируем название: brand + model
                                brand = pump.get("brand", "Кометта")
                                model = pump.get("model", "")
                                
                                # Формируем имя: Brand + Model
                                pump_name_parts = []
                                if brand:
                                    pump_name_parts.append(str(brand).strip())
                                if model and str(model).lower() not in ["nan", "none", ""]:
                                    pump_name_parts.append(str(model).strip())
                                
                                pump_name = " ".join(pump_name_parts)
                                if not pump_name:
                                    pump_name = "Насос"
                                
                                result.response_parts.append(f"\n**{i}. {pump_name}**")
                                result.response_parts.append(f"\nАртикул: {pump.get('articul', 'не указан')}")
                                result.response_parts.append(f"\nМощность: {pump.get('power', 'не указана')} кВт")
                                result.response_parts.append(f"\nРабочая точка: Q = {pump.get('q_work', q):.1f} м³/ч, H = {pump.get('h_work', h):.1f} м")
                                error = pump.get('error', 0)
                                relative_error = pump.get('relative_error_percent', 0)
                                result.response_parts.append(f"\nОтклонение: {error:.2f} м ({relative_error:.1f}%)")
                                
                                datasheet_url = pump.get('datasheet_url')
                                if datasheet_url:
                                    result.response_parts.append(f"\n📄 [Лист данных]({datasheet_url})")
                                else:
                                    result.response_parts.append(f"\n📄 Лист данных: не доступен")
                        else:
                            result.response_parts.append("\nК сожалению, не нашёл подходящих насосов для указанной рабочей точки.")
        else:
            result.response_parts.append(get_pump_type_unknown())
    except Exception as e:
        from services.error_handler import log_error
        log_error(e, "pump_type.py:handle_pump_type", 
                 context={"intent": "PUMP_TYPE", "data": data}, session_id=None)
        result.response_parts.append(get_pump_type_error())
    
    return result
