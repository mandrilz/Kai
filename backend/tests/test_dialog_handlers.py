import os
import sys


# Ensure backend/ is on sys.path when running `pytest` from repository root
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def test_selection_by_point_prefers_stock_for_k144(monkeypatch):
    """
    Для серии К144 при воде и t >= 0 (или не указана) должны предпочитаться модели со складской программой /04A|/04А/.
    Мы проверяем это через сохранённый last_selected_pump.
    """
    from services.dialog_handlers import selection_by_point as mod

    calls = []

    def fake_update_state(chat_id, updates, **kwargs):
        calls.append(("update_state", chat_id, updates, kwargs))

    def fake_set_last_question(chat_id, q, **kwargs):
        calls.append(("set_last_question", chat_id, q, kwargs))

    def fake_select_by_working_point(q, h, h_st=0.0, top_n=50):
        # Важно: серия К144 и две модели — одна складская /04A/, другая нет.
        return [
            {"articul": "NO_STOCK", "brand": "Кометта", "model": "K144 10/99A/", "series": "К144", "power": 1.1, "q_work": q, "h_work": h, "error": 0.1},
            {"articul": "STOCK", "brand": "Кометта", "model": "K144 10/04A/", "series": "К144", "power": 1.1, "q_work": q, "h_work": h, "error": 0.2},
        ]

    monkeypatch.setattr(mod, "update_state", fake_update_state)
    monkeypatch.setattr(mod, "set_last_question", fake_set_last_question)
    monkeypatch.setattr(mod, "select_by_working_point", fake_select_by_working_point)

    chat_id = "00000000-0000-0000-0000-000000000001"
    res = mod.handle_selection_by_point(
        chat_id=chat_id,
        message="Q=10 H=20",
        data={"q": 10.0, "h": 20.0, "pump_type_info": {"series": ["К144"], "type_name": "моноблочный"}},
        context={"state": {"fluid": "вода", "temperature_c": None}},
        pending_slot=None,
        slot_result={"updates": {}, "next_slot": None, "next_question": None},
        updates={},
    )

    assert res.immediate_response is None
    # Ищем обновление last_selected_pump
    last_selected = None
    for kind, _cid, updates, _kwargs in calls:
        if kind == "update_state" and isinstance(updates, dict) and "last_selected_pump" in updates:
            last_selected = updates["last_selected_pump"]
            break
    assert last_selected is not None
    assert last_selected["articul"] == "STOCK"


def test_selection_by_point_filters_by_body_material_code(monkeypatch):
    """
    Если задан body_material_code, должен применяться фильтр по /{code}X/ в модели.
    """
    from services.dialog_handlers import selection_by_point as mod

    calls = []

    def fake_update_state(chat_id, updates, **kwargs):
        calls.append(("update_state", chat_id, updates, kwargs))

    def fake_set_last_question(chat_id, q, **kwargs):
        calls.append(("set_last_question", chat_id, q, kwargs))

    def fake_select_by_working_point(q, h, h_st=0.0, top_n=50):
        return [
            {"articul": "WRONG", "brand": "Кометта", "model": "K144 10/04A/", "series": "К144", "power": 1.1, "q_work": q, "h_work": h, "error": 0.1},
            {"articul": "OK", "brand": "Кометта", "model": "K144 10/16A/", "series": "К144", "power": 1.1, "q_work": q, "h_work": h, "error": 0.2},
        ]

    monkeypatch.setattr(mod, "update_state", fake_update_state)
    monkeypatch.setattr(mod, "set_last_question", fake_set_last_question)
    monkeypatch.setattr(mod, "select_by_working_point", fake_select_by_working_point)

    chat_id = "00000000-0000-0000-0000-000000000002"
    res = mod.handle_selection_by_point(
        chat_id=chat_id,
        message="Q=10 H=20",
        data={"q": 10.0, "h": 20.0, "body_material_code": "16"},
        context={"state": {"fluid": "вода", "temperature_c": 20.0}},
        pending_slot=None,
        slot_result={"updates": {}, "next_slot": None, "next_question": None},
        updates={},
    )

    assert res.immediate_response is None
    last_selected = None
    for kind, _cid, updates, _kwargs in calls:
        if kind == "update_state" and isinstance(updates, dict) and "last_selected_pump" in updates:
            last_selected = updates["last_selected_pump"]
            break
    assert last_selected is not None
    assert last_selected["articul"] == "OK"


def test_analog_by_model_returns_confirmation(monkeypatch):
    from services.dialog_handlers import analog_by_model as mod

    calls = []

    def fake_update_state(chat_id, updates, **kwargs):
        calls.append((chat_id, updates))

    monkeypatch.setattr(mod, "update_state", fake_update_state)
    monkeypatch.setattr(mod, "get_analog_confirmation", lambda model: f"CONFIRM {model}")

    res = mod.handle_analog_by_model(
        chat_id="00000000-0000-0000-0000-000000000003",
        message="нужен аналог",
        data={"model": "CNP CDM 1-3", "brand": "CNP", "model_only": "CDM 1-3"},
        context={"state": {}},
    )

    assert res.immediate_response == "CONFIRM CNP CDM 1-3"
    assert any("pending_analog_confirmation" in upd for _cid, upd in calls if isinstance(upd, dict))


def test_file_upload_success(monkeypatch):
    from api.types import Attachment
    from services.dialog_handlers import file_upload as mod

    def fake_process_file(filename, content_type, base64):
        return {"success": True, "model": "TEST_MODEL", "brand": "TEST_BRAND", "power": 5}

    monkeypatch.setattr(mod, "process_file", fake_process_file)

    res = mod.handle_file_upload(
        chat_id="00000000-0000-0000-0000-000000000004",
        attachments=[
            Attachment(filename="a.pdf", content_type="application/pdf", base64="AAAA"),
        ],
    )

    text = "\n".join(res.response_parts)
    assert "Извлёк данные из файла" in text
    assert "Модель: TEST_MODEL" in text
