"""
ResponseBuilder - основной класс для форматирования ответов.

PR6: Форматирует ответы в стиле ChatGPT на основе результатов domain services.

Архитектура:
- ResponseBuilder НЕ вызывает domain services (это делает DialogueManager/handlers)
- ResponseBuilder получает готовые domain results и только форматирует их
- Чистое разделение: domain = бизнес-логика, builder = presentation
"""
from typing import Dict, Any, Optional, List, Union
from services.nlu.types import Intent, IntentResult, SlotFillResult
from services.domain import (
    PumpSelectionResult,
    AnalogLookupResult,
    DocumentationResult,
    TechQAResult, SpecialQueryType
)
from services.kb.summarize import format_answer


class ResponseBuilder:
    """
    Форматирует ответы в стиле ChatGPT на основе результатов domain services.
    
    PR6: Отделяет форматирование от бизнес-логики.
    
    Правило: ResponseBuilder НЕ вызывает domain services.
    Domain services вызываются в DialogueManager/handlers,
    а ResponseBuilder получает готовые результаты и только форматирует их.
    """
    
    def __init__(self):
        """Инициализация ResponseBuilder."""
        pass  # Нет сервисов - только форматирование
    
    def build_response(
        self,
        intent: Intent,
        intent_result: IntentResult,
        slot_result: SlotFillResult,
        context: Dict[str, Any],
        message: str,
        domain_result: Optional[Union[
            PumpSelectionResult,
            AnalogLookupResult,
            DocumentationResult,
            TechQAResult
        ]] = None
    ) -> str:
        """
        Формирует ответ на основе интента и результатов NLU.
        
        ИСПРАВЛЕНО: ResponseBuilder НЕ вызывает domain services.
        Domain services вызываются в DialogueManager/handlers,
        а ResponseBuilder получает готовый domain_result и только форматирует.
        
        Args:
            intent: Определенный интент
            intent_result: Результат определения интента
            slot_result: Результат заполнения слотов
            context: Контекст диалога
            message: Оригинальное сообщение пользователя
            domain_result: Готовый результат domain service (опционально)
            
        Returns:
            Форматированный ответ в стиле ChatGPT
        """
        # Если есть уточняющий вопрос - возвращаем его
        if slot_result.needs_clarification and slot_result.next_question:
            return slot_result.next_question
        
        if intent == Intent.OFF_TOPIC:
            return self._build_off_topic_response()
        
        if intent == Intent.SELECTION_BY_POINT:
            return self._build_selection_response(
                slot_result, context, domain_result
            )
        
        elif intent == Intent.ANALOG_BY_MODEL:
            return self._build_analog_response(
                intent_result, context, message, domain_result
            )
        
        elif intent == Intent.DOCUMENTATION:
            return self._build_documentation_response(
                intent_result, context, domain_result
            )
        
        elif intent == Intent.TECH_QA:
            return self._build_tech_qa_response(
                intent_result, context, message, domain_result
            )
        
        elif intent == Intent.PUMP_TYPE:
            return self._build_pump_type_response(intent_result, context)
        
        elif intent == Intent.MATERIALS_QUERY:
            return self._build_materials_response(intent_result, context)
        
        elif intent == Intent.FILE_UPLOAD:
            return self._build_file_upload_response(intent_result, context)
        
        elif intent == Intent.DIAGNOSTICS:
            return self._build_diagnostics_response(intent_result, context)
        
        else:
            return self._build_default_response(intent, context)
    
    def _build_selection_response(
        self,
        slot_result: SlotFillResult,
        context: Dict[str, Any],
        domain_result: Optional[PumpSelectionResult] = None
    ) -> str:
        """
        Форматирует ответ для подбора насосов.
        
        ИСПРАВЛЕНО: Не вызывает domain service, получает готовый результат.
        """
        state = context.get("state", {})
        
        # ИСПРАВЛЕНО: Учитываем обновления из slot_result
        updates = slot_result.updates.to_dict() if slot_result.updates else {}
        effective_state = {**state, **updates}
        
        # Получаем параметры из эффективного состояния
        flow = effective_state.get("flow_m3h")
        head = effective_state.get("head_m")
        h_st = effective_state.get("h_st", 0.0)
        fluid = effective_state.get("fluid")
        
        # Если нет Q или H - возвращаем вопрос
        # ИСПРАВЛЕНО: Проверяем is None, а не truthy
        if flow is None or head is None:
            if flow is None and head is None:
                return "Для подбора насоса мне нужны параметры рабочей точки:\n\n• **Расход (Q)** в м³/ч\n• **Напор (H)** в метрах\n\nУкажите, пожалуйста, эти значения."
            elif flow is None:
                return "Для подбора насоса нужен **расход (Q)** в м³/ч. Укажите, пожалуйста, расход."
            else:
                return "Для подбора насоса нужен **напор (H)** в метрах. Укажите, пожалуйста, напор."
        
        # ИСПРАВЛЕНО: Если нет domain_result - значит подбор не был выполнен
        if domain_result is None:
            return "Произошла ошибка при подборе насосов. Попробуйте еще раз."
        
        result = domain_result
        
        # Форматируем ответ
        response_parts = []
        
        # Вводная часть
        response_parts.append(f"Подбираю насосы для рабочей точки:\n• **Расход:** {flow:.2f} м³/ч\n• **Напор:** {head:.2f} м")
        if h_st > 0:
            response_parts.append(f"• **Статический напор:** {h_st:.2f} м")
        
        # Ошибки валидации
        if not result.is_valid:
            response_parts.append("\n⚠️ **Ошибка валидации параметров:**")
            for field, error in result.validation_errors.items():
                response_parts.append(f"• {field}: {error}")
            return "\n".join(response_parts)
        
        # Результаты подбора
        if not result.pumps:
            if result.body_material_filter_applied and result.body_material_no_matches:
                # ИСПРАВЛЕНО: body_material_code берем из effective_state
                body_material_code = effective_state.get("body_material_code")
                # ИСПРАВЛЕНО: Подстраховка от None для лучшего UX
                if body_material_code:
                    response_parts.append(f"\n❌ Не найдено насосов с материалом корпуса `{body_material_code}` для указанной рабочей точки.")
                else:
                    response_parts.append(f"\n❌ Не найдено насосов с указанным материалом корпуса для указанной рабочей точки.")
                response_parts.append("Показать ближайшие варианты без фильтра по материалу?")
            else:
                response_parts.append("\n❌ К сожалению, не удалось подобрать насосы для указанной рабочей точки.")
                response_parts.append("Попробуйте изменить параметры или обратитесь к специалисту.")
            return "\n".join(response_parts)
        
        # Найдены насосы
        response_parts.append(f"\n✅ Найдено насосов: {len(result.pumps)}")
        if result.total_found > len(result.pumps):
            response_parts.append(f"(всего найдено: {result.total_found}, показаны лучшие)")
        
        # Список насосов
        for i, pump in enumerate(result.pumps, 1):
            brand = pump.get("brand", "Кометта")
            model = pump.get("model", "")
            articul = pump.get("articul", "не указан")
            
            # Формируем название
            pump_name = f"{brand} {model}".strip() if model and str(model).lower() not in ["nan", "none", ""] else brand
            
            response_parts.append(f"\n**{i}. {pump_name}**")
            if pump.get("series") and pump.get("series") != "не указана":
                response_parts.append(f"   Серия: {pump['series']}")
            response_parts.append(f"   Артикул: {articul}")
            
            if pump.get("power", 0) > 0:
                response_parts.append(f"   Мощность: {pump['power']} кВт")
            
            q_work = pump.get("q_work", 0)
            h_work = pump.get("h_work", 0)
            response_parts.append(f"   Рабочая точка: Q = {q_work:.2f} м³/ч, H = {h_work:.2f} м")
            
            # Отклонение
            h_error = abs(h_work - head)
            h_error_percent = (h_error / max(head, 1e-6)) * 100
            response_parts.append(f"   Отклонение: {h_error:.2f} м ({h_error_percent:.1f}%)")
            
            # Ссылка на лист данных
            datasheet_url = pump.get("datasheet_url")
            if datasheet_url and isinstance(datasheet_url, str) and datasheet_url.strip():
                if datasheet_url.startswith(('http://', 'https://')):
                    response_parts.append(f"   📄 [Лист данных]({datasheet_url})")
                elif datasheet_url.startswith('/'):
                    base_url = "https://kometta.ru"
                    response_parts.append(f"   📄 [Лист данных]({base_url}{datasheet_url})")
        
        # Follow-up вопросы
        if not fluid:
            response_parts.append("\n💡 **Могу уточнить:**")
            response_parts.append("• Тип жидкости (вода, этиленгликоль и т.д.)")
            response_parts.append("• Температуру")
            response_parts.append("• Наличие примесей")
        
        response_parts.append("\n💬 **Что еще могу помочь?**")
        response_parts.append("• Сравнить насосы")
        response_parts.append("• Показать график характеристики")
        response_parts.append("• Подобрать по другим параметрам")
        
        return "\n".join(response_parts)
    
    def _build_analog_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any],
        message: str,
        domain_result: Optional[AnalogLookupResult] = None
    ) -> str:
        """
        Форматирует ответ для поиска аналогов.
        
        ИСПРАВЛЕНО: Не вызывает domain service, получает готовый результат.
        """
        data = intent_result.data or {}
        state = context.get("state", {})
        
        # ИСПРАВЛЕНО: Извлекаем переменные из data в начале функции
        model = data.get("model")
        brand = data.get("brand")
        model_only = data.get("model_only")
        
        # ИСПРАВЛЕНО: Проверяем pending confirmation ПЕРЕД проверкой domain_result
        # Если есть pending_confirmation, это значит, что нужно подтвердить модель
        # (domain_result будет None в этом случае, но это нормально)
        pending_confirmation = state.get("pending_analog_confirmation")
        if pending_confirmation:
            # Ожидается подтверждение модели - возвращаем вопрос для подтверждения
            model_to_confirm = pending_confirmation.get("model", "модель")
            return f"Вы имели в виду модель **{model_to_confirm}**? Пожалуйста, подтвердите (да/нет)."
        
        # ИСПРАВЛЕНО: Если нет domain_result - проверяем причину
        if domain_result is None:
            # Может быть несколько причин:
            # 1. Нет model и brand - просим указать
            if not model and not brand:
                return "Для поиска аналога укажите модель насоса конкурента или бренд."
            # 2. Есть model/brand, но domain service вернул None - ошибка поиска
            return "Произошла ошибка при поиске аналогов. Попробуйте еще раз или уточните модель."
        
        result = domain_result
        
        # Форматируем ответ
        response_parts = []
        
        if not result.found:
            if brand and not model:
                response_parts.append(f"❌ Не найдено моделей бренда **{brand}** в базе конкурентов.")
            else:
                model_display = model or model_only or "указанная модель"
                response_parts.append(f"❌ Модель **{model_display}** не найдена в базе конкурентов.")
            return "\n".join(response_parts)
        
        if not result.has_analogs:
            competitor_name = f"{result.competitor_data.get('brand', '')} {result.competitor_data.get('model', '')}".strip()
            response_parts.append(f"✅ Найдена модель **{competitor_name}** в базе конкурентов.")
            response_parts.append("\n❌ К сожалению, не удалось найти аналоги Кометта для этой модели.")
            return "\n".join(response_parts)
        
        # Найдены аналоги
        competitor_name = f"{result.competitor_data.get('brand', '')} {result.competitor_data.get('model', '')}".strip()
        response_parts.append(f"✅ Найдена модель **{competitor_name}** в базе конкурентов.")
        response_parts.append("\n**Аналоги Кометта:**\n")
        
        for i, analog in enumerate(result.analogs, 1):
            brand_analog = analog.get("brand", "Кометта")
            analog_model = analog.get("model", "")
            articul = analog.get("articul", "не указан")
            
            if not analog_model or analog_model.strip() == "" or analog_model.lower() in ["nan", "none", "не указана"]:
                analog_name = brand_analog
            else:
                analog_name = f"{brand_analog} {analog_model.strip()}"
            
            response_parts.append(f"**{i}. {analog_name}**")
            response_parts.append(f"   Артикул: {articul}")
            
            if analog.get("power", 0) > 0:
                response_parts.append(f"   Мощность: {analog['power']} кВт")
            
            response_parts.append(f"   Отклонение кривой: {analog['rmse']:.2f} м")
            
            datasheet_url = analog.get("datasheet_url")
            if datasheet_url and isinstance(datasheet_url, str) and datasheet_url.strip():
                if datasheet_url.startswith(('http://', 'https://')):
                    response_parts.append(f"   📄 [Лист данных]({datasheet_url})")
                elif datasheet_url.startswith('/'):
                    base_url = "https://kometta.ru"
                    response_parts.append(f"   📄 [Лист данных]({base_url}{datasheet_url})")
        
        response_parts.append("\n💡 Могу построить график сравнения характеристик. Хотите?")
        
        return "\n".join(response_parts)
    
    def _build_documentation_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any],
        domain_result: Optional[DocumentationResult] = None
    ) -> str:
        """
        Форматирует ответ для документации.
        
        ИСПРАВЛЕНО: Не вызывает domain service, получает готовый результат.
        """
        data = intent_result.data or {}
        action = data.get("action", "by_model")
        
        # ИСПРАВЛЕНО: Если нет domain_result - значит поиск не был выполнен
        if domain_result is None:
            if action == "by_model":
                model = data.get("model", "указанная модель")
                return f"❌ Насос с моделью **{model}** не найден в базе Кометта."
            elif action == "by_articul":
                articul = data.get("articul", "указанный артикул")
                return f"❌ Насос с артикулом **{articul}** не найден в базе Кометта."
            else:
                return "❌ Не удалось найти информацию о насосе."
        
        result = domain_result
        
        response_parts = []
        
        if not result.found:
            if action == "by_model":
                model = data.get("model", "указанная модель")
                response_parts.append(f"❌ Насос с моделью **{model}** не найден в базе Кометта.")
            elif action == "by_articul":
                articul = data.get("articul", "указанный артикул")
                response_parts.append(f"❌ Насос с артикулом **{articul}** не найден в базе Кометта.")
            else:
                response_parts.append("❌ Не удалось найти информацию о насосе.")
            return "\n".join(response_parts)
        
        # Форматируем информацию о насосе
        if result.pump_data:
            pump = result.pump_data
            model = pump.get("model", "не указана")
            articul = pump.get("articul", "не указан")
            series = pump.get("series", "не указана")
            power = pump.get("power", 0)
            
            response_parts.append(f"**Информация о насосе:**\n")
            response_parts.append(f"• Модель: {model}")
            response_parts.append(f"• Артикул: {articul}")
            if series != "не указана":
                response_parts.append(f"• Серия: {series}")
            if power > 0:
                response_parts.append(f"• Мощность: {power} кВт")
            
            datasheet_url = pump.get("datasheet_url")
            if datasheet_url:
                if datasheet_url.startswith(('http://', 'https://')):
                    response_parts.append(f"• 📄 [Лист данных]({datasheet_url})")
                elif datasheet_url.startswith('/'):
                    base_url = "https://kometta.ru"
                    response_parts.append(f"• 📄 [Лист данных]({base_url}{datasheet_url})")
            
            # ИСПРАВЛЕНО: Обработка pump_data2 (конкурент для plot)
            if result.pump_data2:
                competitor = result.pump_data2
                if competitor.get("is_competitor"):
                    competitor_name = f"{competitor.get('brand', '')} {competitor.get('model', '')}".strip()
                    response_parts.append(f"\n**Модель конкурента для сравнения:**")
                    response_parts.append(f"• {competitor_name}")
                    if result.has_curve:
                        # ПРИМЕЧАНИЕ: График сравнения будет генерироваться в PR7/интеграции
                        response_parts.append("\n💡 Могу построить график сравнения характеристик. Хотите?")
                else:
                    # Второй насос Кометта (для сравнения)
                    pump2 = competitor
                    model2 = pump2.get("model", "не указана")
                    articul2 = pump2.get("articul", "не указан")
                    response_parts.append(f"\n**Второй насос для сравнения:**")
                    response_parts.append(f"• Модель: {model2}")
                    response_parts.append(f"• Артикул: {articul2}")
            elif result.has_curve:
                response_parts.append("\n💡 Могу построить график характеристики насоса. Хотите?")
        
        # Материал корпуса
        if result.body_material_code:
            response_parts.append(f"\n**Материал корпуса:**")
            if result.body_material_description:
                response_parts.append(f"• Код: {result.body_material_code}")
                response_parts.append(f"• Описание: {result.body_material_description}")
            else:
                response_parts.append(f"• Код: {result.body_material_code}")
                response_parts.append("• Описание: не найдено")
        
        return "\n".join(response_parts)
    
    def _build_tech_qa_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any],
        message: str,
        domain_result: Optional[TechQAResult] = None
    ) -> str:
        """
        Форматирует ответ для технических вопросов.
        
        ИСПРАВЛЕНО: Не вызывает domain service, получает готовый результат.
        format_answer вызывается здесь (presentation layer) - это правильно.
        """
        data = intent_result.data or {}
        query = data.get("query", message)
        
        # ИСПРАВЛЕНО: Если нет domain_result - значит поиск не был выполнен
        if domain_result is None:
            return "❌ К сожалению, не удалось найти информацию по вашему запросу.\n\n💡 Попробуйте переформулировать вопрос или уточнить детали."
        
        result = domain_result
        
        response_parts = []
        
        # Специальные запросы
        if result.special_query_type == SpecialQueryType.PUMP_TYPES:
            response_parts.append("**Типы насосов в ассортименте Кометта:**\n")
            for i, pump_type in enumerate(result.pump_types, 1):
                response_parts.append(f"{i}. {pump_type}")
            return "\n".join(response_parts)
        
        if result.special_query_type == SpecialQueryType.COMPONENTS:
            if result.components_description:
                response_parts.append(result.components_description)
            return "\n".join(response_parts)
        
        # Обычный поиск в KB
        if not result.found:
            response_parts.append("❌ К сожалению, не удалось найти информацию по вашему запросу.")
            response_parts.append("\n💡 Попробуйте переформулировать вопрос или уточнить детали.")
            return "\n".join(response_parts)
        
        # Форматируем ответ из найденных результатов
        answer = format_answer(query, result.hits, max_bullets=7)
        response_parts.append(answer)
        
        return "\n".join(response_parts)
    
    def _build_pump_type_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any]
    ) -> str:
        """Форматирует ответ для запросов о типе насоса."""
        # TODO: Реализовать при необходимости
        return "Информация о типе насоса будет добавлена в следующей версии."
    
    def _build_materials_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any]
    ) -> str:
        """Форматирует ответ для запросов о материалах."""
        # TODO: Реализовать при необходимости
        return "Информация о материалах будет добавлена в следующей версии."
    
    def _build_file_upload_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any]
    ) -> str:
        """Форматирует ответ для загрузки файлов."""
        return "Обработка загруженных файлов будет добавлена в следующей версии."
    
    def _build_diagnostics_response(
        self,
        intent_result: IntentResult,
        context: Dict[str, Any]
    ) -> str:
        """Форматирует ответ для диагностики."""
        return "Диагностика будет добавлена в следующей версии."
    
    def _build_off_topic_response(self) -> str:
        """
        Форматирует ответ для оффтоп-запросов.
        
        PR6: Дружелюбный ответ с предложением возможностей бота.
        """
        response_parts = []
        response_parts.append("Извините, я специализируюсь на помощи с насосами Кометта.")
        response_parts.append("\n💡 **Что я могу помочь:**")
        response_parts.append("• Подобрать насос по рабочей точке (Q и H)")
        response_parts.append("• Найти аналог насоса конкурента")
        response_parts.append("• Получить информацию о насосе по модели или артикулу")
        response_parts.append("• Ответить на технические вопросы")
        response_parts.append("• Сравнить характеристики насосов")
        response_parts.append("• Помочь с диагностикой проблем")
        response_parts.append("\nЗадайте вопрос о насосах, и я постараюсь помочь!")
        
        return "\n".join(response_parts)
    
    def _build_default_response(
        self,
        intent: Intent,
        context: Dict[str, Any]
    ) -> str:
        """
        Форматирует ответ по умолчанию для необработанных интентов.
        
        ИСПРАВЛЕНО: Дружелюбный оффтоп-ответ с предложением вариантов.
        """
        response_parts = []
        response_parts.append("Извините, я пока не могу обработать этот запрос.")
        response_parts.append("\n💡 **Что я могу помочь:**")
        response_parts.append("• Подобрать насос по рабочей точке (Q и H)")
        response_parts.append("• Найти аналог насоса конкурента")
        response_parts.append("• Получить информацию о насосе по модели или артикулу")
        response_parts.append("• Ответить на технические вопросы")
        response_parts.append("• Сравнить характеристики насосов")
        response_parts.append("\nПопробуйте переформулировать запрос или задайте вопрос по-другому.")
        
        return "\n".join(response_parts)
