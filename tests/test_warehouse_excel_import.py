import io

from openpyxl import Workbook, load_workbook

from wms.models import Warehouse


def _xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_recipient_warehouses_template(client_logged_in):
    response = client_logged_in.get("/warehouses/recipients-template.xlsx")
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.data))["Склады-получатели"]
    assert [cell.value for cell in sheet[1]] == [
        "Код",
        "Тип",
        "Наименование",
        "Адрес",
        "Получатель на стикере",
        "Активен",
    ]


def test_recipient_warehouses_import_creates_and_updates(db, client_logged_in):
    headers = ["Код", "Тип", "Наименование", "Адрес", "Получатель на стикере", "Активен"]
    first = _xlsx([headers, ["", "WB", "Коледино", "Адрес 1", "ООО Получатель", "Да"]])
    response = client_logged_in.post(
        "/warehouses/recipients-import",
        data={"file": (first, "warehouses.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    warehouse = Warehouse.query.filter_by(marketplace="wb", marketplace_city="Коледино").one()
    assert warehouse.address == "Адрес 1"
    assert warehouse.recipient_info == "ООО Получатель"
    assert warehouse.is_recipient is True

    second = _xlsx([headers, [warehouse.code, "WB", "Коледино", "Адрес 2", "Новый получатель", "Нет"]])
    client_logged_in.post(
        "/warehouses/recipients-import",
        data={"file": (second, "warehouses.xlsx")},
        content_type="multipart/form-data",
    )
    db.session.refresh(warehouse)
    assert Warehouse.query.filter_by(marketplace="wb", marketplace_city="Коледино").count() == 1
    assert warehouse.address == "Адрес 2"
    assert warehouse.recipient_info == "Новый получатель"
    assert warehouse.is_active is False
