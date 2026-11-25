"""Поиск товара вручную должен находить каждое слово запроса отдельной
подстрокой (в любом порядке), а не всю фразу целиком — иначе "кар беж" не
находит "Кардиган бежевый", хотя такой подстроки в названии нет."""

from wms.extensions import db
from wms.models import Nomenclature


def _make_item():
    item = Nomenclature(
        sku="SKU1", barcode="1111111111", name="Кардиган бежевый 44-46", unit="шт"
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_search_finds_by_multiple_words_any_order(db, client_logged_in):
    _make_item()

    resp = client_logged_in.get("/api/nomenclature/search?q=" + "кар беж")
    names = [row["name"] for row in resp.get_json()]

    assert "Кардиган бежевый 44-46" in names


def test_search_requires_all_words_to_match(db, client_logged_in):
    _make_item()

    # "кар" встречается, "синий" - нет: строка не должна найтись.
    resp = client_logged_in.get("/api/nomenclature/search?q=" + "кар синий")

    assert resp.get_json() == []


def test_search_result_shows_size_and_can_be_found_by_size(db, client_logged_in):
    item = Nomenclature(
        sku="SIZE-SKU",
        barcode="2222222222",
        name="Блузка Бохо муслиновая",
        size="48",
        unit="шт",
    )
    db.session.add(item)
    db.session.commit()

    rows = client_logged_in.get("/api/nomenclature/search?q=48").get_json()

    assert len(rows) == 1
    assert rows[0]["size"] == "48"
    assert "размер 48" in rows[0]["label"]


def test_search_empty_query_returns_empty_list(db, client_logged_in):
    _make_item()

    resp = client_logged_in.get("/api/nomenclature/search?q=")

    assert resp.get_json() == []
