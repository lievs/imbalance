import io

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def _workbook(title, headers, widths):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    fill = PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid")
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(1, column, header)
        cell.font = Font(bold=True)
        cell.fill = fill
        sheet.column_dimensions[get_column_letter(column)].width = widths[column - 1]
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    return workbook, sheet


def _bytes(workbook):
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_recipient_warehouses_template():
    workbook, sheet = _workbook(
        "Склады-получатели",
        ["Код", "Тип", "Наименование", "Адрес", "Получатель на стикере", "Активен"],
        [18, 18, 30, 36, 48, 12],
    )
    sheet.append(["", "WB", "Коледино", "", "ООО Пример, адрес, телефон", "Да"])
    sheet.append(["", "Ozon", "Хоругвино", "", "ООО Пример, адрес, телефон", "Да"])
    return _bytes(workbook)


def build_box_picking_template():
    workbook, _ = _workbook("Короба", ["Номер короба"], [24])
    return _bytes(workbook)


def _load_rows(file_stream):
    try:
        workbook = load_workbook(io.BytesIO(file_stream.read()), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        return [], [f"Не удалось открыть Excel-файл: {exc}"]
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return [], ["Excel-файл пуст"]
    return rows, []


def read_box_codes(file_stream):
    rows, errors = _load_rows(file_stream)
    if errors:
        return [], errors
    header = str(rows[0][0] or "").strip().casefold() if rows[0] else ""
    if header not in {"номер короба", "короб", "box", "box number"}:
        return [], ["В первой колонке ожидается заголовок «Номер короба»"]
    codes = []
    for row_number, row in enumerate(rows[1:], start=2):
        value = row[0] if row else None
        if value is None or str(value).strip() == "":
            continue
        code = str(value).strip()
        if code not in codes:
            codes.append(code)
    return codes, []


def read_recipient_warehouses(file_stream):
    rows, errors = _load_rows(file_stream)
    if errors:
        return [], errors
    headers = {
        str(value or "").strip().casefold(): index
        for index, value in enumerate(rows[0])
    }
    required = ("тип", "наименование")
    missing = [name for name in required if name not in headers]
    if missing:
        return [], [f"В шаблоне нет колонок: {', '.join(missing)}"]

    def value(row, name):
        index = headers.get(name)
        if index is None or index >= len(row) or row[index] is None:
            return ""
        return str(row[index]).strip()

    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not row or all(item is None or str(item).strip() == "" for item in row):
            continue
        records.append(
            {
                "row": row_number,
                "code": value(row, "код"),
                "type": value(row, "тип"),
                "name": value(row, "наименование"),
                "address": value(row, "адрес"),
                "recipient_info": value(row, "получатель на стикере"),
                "active": value(row, "активен"),
            }
        )
    return records, []
