from wms.extensions import db
from wms.models import Nomenclature, ProductCategory


def test_nomenclature_hides_product_kind_column(db, client_logged_in):
    category = ProductCategory(name="Тестовый вид", keywords="тестовый-вид")
    item = Nomenclature(
        sku="VISIBLE-COLUMNS-1",
        barcode="990000000099",
        name="Товар для проверки колонок",
        size="48",
        unit="шт",
        category=category,
    )
    db.session.add_all([category, item])
    db.session.commit()

    html = client_logged_in.get("/nomenclature/").get_data(as_text=True)

    assert "<th>Размер</th>" in html
    assert "<th>Вид</th>" not in html
    assert 'name="category_id"' not in html
    assert "Тестовый вид" not in html
