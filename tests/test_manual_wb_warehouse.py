from wms.extensions import db
from wms.models import Warehouse


def test_wb_warehouse_can_be_created_manually(client_logged_in):
    response = client_logged_in.post(
        "/warehouses/create",
        data={
            "warehouse_type": "wb",
            "name": "ВБ: коледино",
            "address": "Тестовый адрес",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    warehouse = Warehouse.query.filter_by(marketplace="wb").one()
    assert warehouse.name == "Коледино"
    assert warehouse.marketplace_city == "Коледино"
    assert warehouse.address == "Тестовый адрес"
    assert "ВБ" in response.get_data(as_text=True)
    assert "Коледино" in response.get_data(as_text=True)


def test_duplicate_manual_wb_warehouse_is_rejected(client_logged_in):
    db.session.add(
        Warehouse(
            code="WH-WB-OLD",
            name="Коледино",
            marketplace="wb",
            marketplace_city="Коледино",
        )
    )
    db.session.commit()

    response = client_logged_in.post(
        "/warehouses/create",
        data={"warehouse_type": "wb", "name": "wb - КОЛЕДИНО"},
        follow_redirects=True,
    )

    assert "уже существует" in response.get_data(as_text=True)
    assert Warehouse.query.filter_by(marketplace="wb").count() == 1


def test_existing_warehouse_form_still_creates_own_warehouse(client_logged_in):
    response = client_logged_in.post(
        "/warehouses/create",
        data={"name": "Ручной собственный склад", "address": "Адрес"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    warehouse = Warehouse.query.filter_by(name="Ручной собственный склад").one()
    assert warehouse.marketplace is None
    assert warehouse.marketplace_city is None
