from wms.extensions import db
from wms.models import Box, BoxCabinet, Warehouse


def test_default_box_cabinets_are_seeded(app):
    with app.app_context():
        assert [row.prefix for row in BoxCabinet.query.order_by(BoxCabinet.id)] == [
            "A",
            "B",
            "IM",
            "V",
        ]


def test_bulk_create_uses_selected_cabinet_and_scan_still_finds_box(db, client_logged_in):
    warehouse = Warehouse(code="WH-CAB", name="Склад кабинетов")
    db.session.add(warehouse)
    db.session.commit()
    cabinet = BoxCabinet.query.filter_by(prefix="IM").one()

    response = client_logged_in.post(
        "/boxes/bulk-create",
        data={"warehouse_id": warehouse.id, "cabinet_id": cabinet.id, "count": 2},
    )

    assert response.status_code == 200
    boxes = Box.query.filter_by(warehouse_id=warehouse.id).order_by(Box.id).all()
    assert len(boxes) == 2
    assert all(box.cabinet_id == cabinet.id for box in boxes)
    assert all(box.box_number.startswith("IM-") for box in boxes)
    assert Box.find_by_scanned_code(boxes[0].barcode_value, warehouse.id).id == boxes[0].id
    assert "Кабинет IM" in response.get_data(as_text=True)


def test_bulk_create_requires_cabinet(db, client_logged_in):
    warehouse = Warehouse(code="WH-NOCAB", name="Склад без кабинета")
    db.session.add(warehouse)
    db.session.commit()

    response = client_logged_in.post(
        "/boxes/bulk-create",
        data={"warehouse_id": warehouse.id, "count": 1},
        follow_redirects=True,
    )

    assert "Выберите активный кабинет" in response.get_data(as_text=True)
    assert Box.query.filter_by(warehouse_id=warehouse.id).count() == 0


def test_cabinet_settings_change_future_prefix_only(db, client_logged_in):
    cabinet = BoxCabinet.query.filter_by(prefix="A").one()
    warehouse = Warehouse(code="WH-EDITCAB", name="Склад настройки")
    old_box = Box(
        box_number="A-999999",
        warehouse=warehouse,
        cabinet_id=cabinet.id,
    )
    db.session.add_all([warehouse, old_box])
    db.session.commit()

    response = client_logged_in.post(
        f"/boxes/cabinets/{cabinet.id}/update",
        data={"name": "Основной кабинет", "prefix": "AA", "is_active": "on"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    db.session.refresh(cabinet)
    db.session.refresh(old_box)
    assert cabinet.name == "Основной кабинет"
    assert cabinet.prefix == "AA"
    assert old_box.box_number == "A-999999"
    assert old_box.cabinet_id == cabinet.id
    assert Box.find_by_scanned_code("999999", warehouse.id).id == old_box.id


def test_inactive_cabinet_cannot_be_used_for_new_boxes(db, client_logged_in):
    warehouse = Warehouse(code="WH-INACTIVE-CAB", name="Склад неактивного кабинета")
    cabinet = BoxCabinet.query.filter_by(prefix="V").one()
    cabinet.is_active = False
    db.session.add(warehouse)
    db.session.commit()

    response = client_logged_in.post(
        "/boxes/bulk-create",
        data={"warehouse_id": warehouse.id, "cabinet_id": cabinet.id, "count": 1},
        follow_redirects=True,
    )

    assert "Выберите активный кабинет" in response.get_data(as_text=True)
    assert Box.query.filter_by(warehouse_id=warehouse.id).count() == 0
