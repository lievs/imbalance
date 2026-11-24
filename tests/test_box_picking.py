from wms.extensions import db
from wms.models import (
    Box,
    BoxPickingTask,
    BoxPickingTaskLine,
    Cell,
    Warehouse,
    Zone,
)


def _warehouse_with_boxes():
    warehouse = Warehouse(code="PICK-WH", name="Склад подбора")
    db.session.add(warehouse)
    db.session.flush()
    zone = Zone(warehouse_id=warehouse.id, code="A")
    db.session.add(zone)
    db.session.flush()
    cell = Cell(warehouse_id=warehouse.id, zone_id=zone.id, code="A001")
    db.session.add(cell)
    db.session.flush()
    boxes = [
        Box(box_number="BOX-800001", warehouse=warehouse, cell_id=cell.id, status="stored"),
        Box(box_number="BOX-800002", warehouse=warehouse, zone_id=zone.id, status="stored"),
    ]
    db.session.add_all(boxes)
    db.session.commit()
    return warehouse, boxes


def test_create_task_shows_current_box_locations(client_logged_in, app):
    with app.app_context():
        warehouse, boxes = _warehouse_with_boxes()
        warehouse_id = warehouse.id

    response = client_logged_in.post(
        "/box-picking/create",
        data={
            "warehouse_id": warehouse_id,
            "title": "Рейс №15",
            "box_codes": "BOX-800001\nBOX-800002",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Рейс №15" in html
    assert "ячейке A001" in html
    assert "ряду A" in html

    with app.app_context():
        task = BoxPickingTask.query.one()
        assert task.total_count() == 2
        assert task.status == "new"


def test_scan_only_task_boxes_and_complete_task(client_logged_in, app):
    with app.app_context():
        warehouse, boxes = _warehouse_with_boxes()
        task = BoxPickingTask(number="POD-900001", warehouse=warehouse)
        db.session.add(task)
        db.session.flush()
        db.session.add_all([BoxPickingTaskLine(task=task, box=box) for box in boxes])
        other = Box(box_number="BOX-800003", warehouse=warehouse)
        db.session.add(other)
        db.session.commit()
        task_id = task.id

    response = client_logged_in.post(
        f"/box-picking/{task_id}/scan",
        data={"box_code": "BOX-800003"},
        follow_redirects=True,
    )
    assert "не входит в это задание" in response.get_data(as_text=True)

    for number in ("BOX-800001", "BOX-800002"):
        client_logged_in.post(
            f"/box-picking/{task_id}/scan",
            data={"box_code": number},
            follow_redirects=True,
        )

    with app.app_context():
        task = db.session.get(BoxPickingTask, task_id)
        assert task.status == "completed"
        assert task.completed_at is not None
        assert task.picked_count() == 2


def test_removed_modules_are_not_registered_and_not_in_menu(client_logged_in, app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "box_picking.list_tasks" in endpoints
    assert not any(endpoint.startswith("production.") for endpoint in endpoints)
    assert not any(endpoint.startswith("production_orders.") for endpoint in endpoints)
    assert not any(endpoint.startswith("integration_1c.") for endpoint in endpoints)
    assert not any(endpoint.startswith("integration_ozon.") for endpoint in endpoints)
    assert not any(endpoint.startswith("integration_wb.") for endpoint in endpoints)
    assert not any(endpoint.startswith("mvb.") for endpoint in endpoints)

    html = client_logged_in.get("/").get_data(as_text=True)
    assert "Подбор коробов" in html
    assert "Производство" not in html
    assert "Обмен с 1С" not in html
    assert "МВБ Логистика" not in client_logged_in.get("/login").get_data(as_text=True)

    settings_html = client_logged_in.get("/users").get_data(as_text=True)
    assert "Обмен с Ozon" not in settings_html
    assert "Обмен с WB" not in settings_html
    assert "Сотрудник производства" not in settings_html
