from wms.extensions import db
from wms.models import ReceivingDocument, Warehouse


def test_receiving_uses_fixed_warehouse_and_existing_boxes_only(
    client_logged_in, app
):
    with app.app_context():
        warehouse = Warehouse(code="WH-RBC-1", name="Склад приемки")
        other = Warehouse(code="WH-RBC-2", name="Другой склад")
        db.session.add_all([warehouse, other])
        db.session.flush()
        doc = ReceivingDocument(number="RBC-0001", warehouse_id=warehouse.id)
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    response = client_logged_in.get(f"/receiving/{doc_id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Склад: Склад приемки" in html
    assert 'name="warehouse_id"' not in html
    assert f"/receiving/{doc_id}/change-warehouse" not in html

    assert "Отсканируйте или введите номер существующего короба" in html
    assert f"/receiving/{doc_id}/boxes/select" in html
    assert 'data-camera-scan-target="#boxNumberInput"' in html
    assert "Создать новый короб" not in html
    assert 'name="cabinet_id"' not in html
    assert f"/receiving/{doc_id}/boxes/create" not in html
