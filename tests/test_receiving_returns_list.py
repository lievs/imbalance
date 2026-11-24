"""Список возвратов в самостоятельной версии не содержит статусов 1С."""

from datetime import datetime

from wms.extensions import db
from wms.models import Nomenclature, ReceivingDocument, SupplierReturn, Warehouse


def _make_warehouse(code="WH-RL"):
    wh = Warehouse(code=code, name="Тест склад возвратов")
    db.session.add(wh)
    db.session.commit()
    return wh


def _make_item(barcode, name="Товар возврата"):
    item = Nomenclature(sku=barcode, barcode=barcode, name=name, unit="шт")
    db.session.add(item)
    db.session.commit()
    return item


def test_returns_list_shows_returns_without_one_c_status(db, client_logged_in):
    wh = _make_warehouse("WH-RL-1")
    item = _make_item("6660000001", "Товар со статусом")
    doc = ReceivingDocument(
        number="НАКЛ-RL-1",
        warehouse_id=wh.id,
        supplier="ИП Тестов",
        order_number="Ш-001",
        invoice_file_name="накладная.xlsx",
    )
    db.session.add(doc)
    db.session.commit()

    pending = SupplierReturn(
        warehouse_id=wh.id,
        nomenclature_id=item.id,
        qty=3,
        receiving_document_id=doc.id,
        supplier_name="ИП Тестов",
        invoice_number="НАКЛ-RL-1",
    )
    synced = SupplierReturn(
        warehouse_id=wh.id,
        nomenclature_id=item.id,
        qty=2,
        receiving_document_id=doc.id,
        supplier_name="ИП Тестов",
        invoice_number="НАКЛ-RL-1",
        synced_to_1c_at=datetime.utcnow(),
    )
    manual = SupplierReturn(
        warehouse_id=wh.id,
        nomenclature_id=item.id,
        qty=1,
    )
    db.session.add_all([pending, synced, manual])
    db.session.commit()

    html = client_logged_in.get("/receiving/returns").get_data(as_text=True)

    assert "Ожидает выгрузки" not in html
    assert "Выгружен" not in html
    assert ">1С<" not in html
    assert "НАКЛ-RL-1" in html


def test_returns_list_shows_all_returns_regardless_of_old_sync_field(db, client_logged_in):
    wh = _make_warehouse("WH-RL-2")
    item = _make_item("6660000002", "Товар фильтра")
    doc = ReceivingDocument(
        number="НАКЛ-RL-2",
        warehouse_id=wh.id,
        invoice_file_name="накладная.xlsx",
    )
    db.session.add(doc)
    db.session.commit()

    db.session.add_all(
        [
            SupplierReturn(
                warehouse_id=wh.id,
                nomenclature_id=item.id,
                qty=1,
                receiving_document_id=doc.id,
                invoice_number="НАКЛ-RL-2",
                synced_to_1c_at=datetime.utcnow(),
            ),
            SupplierReturn(
                warehouse_id=wh.id,
                nomenclature_id=item.id,
                qty=4,
                receiving_document_id=doc.id,
                invoice_number="НАКЛ-RL-2",
            ),
        ]
    )
    db.session.commit()

    html = client_logged_in.get("/receiving/returns").get_data(as_text=True)

    assert "4.0 шт" in html
    assert "1.0 шт" in html
    assert "Ожидает выгрузки" not in html
