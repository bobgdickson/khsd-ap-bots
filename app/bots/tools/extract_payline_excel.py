from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

import xml.etree.ElementTree as ET

from agents import function_tool

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"main": MAIN_NS}
NS_PKG = {"pkg": PKG_NS}

COLUMN_REF = re.compile(r"([A-Z]+)")
DATE_HEADER_HINTS = ("date", "begin", "end", "month")
EXCEL_EPOCH = datetime(1899, 12, 30)


def _load_shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    strings: list[str] = []
    for si in root.findall("main:si", NS):
        fragments = [node.text or "" for node in si.findall(".//main:t", NS)]
        strings.append("".join(fragments))
    return strings


def _sheet_targets(book: zipfile.ZipFile) -> list[tuple[str, str]]:
    try:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels_root = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return []

    id_to_target: dict[str, str] = {}
    for rel in rels_root.findall("pkg:Relationship", NS_PKG):
        rel_id = rel.get("Id")
        target = rel.get("Target")
        if rel_id and target:
            id_to_target[rel_id] = target

    sheets_node = workbook.find("main:sheets", NS)
    if sheets_node is None:
        return []

    resolved: list[tuple[str, str]] = []
    for sheet in sheets_node.findall("main:sheet", NS):
        name = (sheet.get("name") or "").strip()
        rel_id = sheet.get(f"{{{REL_NS}}}id")
        if not rel_id:
            continue
        target = id_to_target.get(rel_id)
        if not target:
            continue
        normalized = _normalize_target(target)
        if normalized:
            resolved.append((name, normalized))
    return resolved


def _normalize_target(target: str) -> str:
    cleaned = target.strip()
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")
    if cleaned.startswith("../"):
        cleaned = cleaned[3:]
    if not cleaned.startswith("xl/"):
        cleaned = f"xl/{cleaned}"
    return cleaned


def _column_from_ref(cell_ref: str | None) -> str:
    if not cell_ref:
        return ""
    match = COLUMN_REF.match(cell_ref)
    return match.group(1) if match else ""


def _column_index(column: str) -> int:
    index = 0
    for char in column:
        index = index * 26 + (ord(char.upper()) - ord("A") + 1)
    return index


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "s":
        value_node = cell.find("main:v", NS)
        if value_node is None or value_node.text is None:
            return ""
        try:
            index = int(value_node.text)
        except ValueError:
            return ""
        return shared[index] if 0 <= index < len(shared) else ""

    if cell_type == "inlineStr":
        fragments = [node.text or "" for node in cell.findall(".//main:t", NS)]
        return "".join(fragments)

    value_node = cell.find("main:v", NS)
    return value_node.text.strip() if value_node is not None and value_node.text else ""


def _iter_sheet_rows(
    book: zipfile.ZipFile,
    sheet_path: str,
    shared: list[str],
) -> Iterator[tuple[int | None, dict[str, str]]]:
    try:
        sheet_root = ET.fromstring(book.read(sheet_path))
    except KeyError:
        return iter(())

    for row in sheet_root.findall("main:sheetData/main:row", NS):
        idx_text = row.get("r") or ""
        try:
            idx = int(idx_text)
        except ValueError:
            idx = None

        row_data: dict[str, str] = {}
        has_value = False
        for cell in row.findall("main:c", NS):
            column = _column_from_ref(cell.get("r"))
            value = _cell_text(cell, shared)
            if value:
                has_value = True
            row_data[column] = value
        if not has_value:
            continue
        yield idx, row_data


def _parse_sheet_meta(name: str) -> tuple[str, str]:
    cleaned = (name or "").strip()
    if "_" not in cleaned:
        return cleaned, ""
    requester, remainder = cleaned.split("_", 1)
    return requester.strip(), remainder.replace("_", " ").strip()


def _expand_columns(
    column_order: list[str],
    row_data: dict[str, str],
) -> list[str]:
    for column in sorted(row_data, key=_column_index):
        if column not in column_order:
            column_order.append(column)
    return column_order


def _row_values(column_order: list[str], row_data: dict[str, str]) -> list[str]:
    return [row_data.get(column, "") for column in column_order]


def _format_table(header: list[str], rows: list[list[str]]) -> str:
    lines: list[str] = []
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for row in rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def _detect_date_columns(header: list[str]) -> set[int]:
    date_columns: set[int] = set()
    for idx, title in enumerate(header):
        normalized = (title or "").lower()
        if any(hint in normalized for hint in DATE_HEADER_HINTS):
            date_columns.add(idx)
    return date_columns


def _format_excel_date(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        numeric = float(text)
    except ValueError:
        return text

    try:
        date_value = EXCEL_EPOCH + timedelta(days=numeric)
    except OverflowError:
        return text

    return f"{date_value.month}/{date_value.day}/{date_value.year}"


@function_tool
def extract_payline_excel(
    input: str,
    *,
    max_rows_per_sheet: int = 200,
    max_sheets: int = 6,
    include_empty_sheets: bool = False,
) -> dict:
    """Return lightweight sheet tables for LLM consumption."""
    path = Path(input).expanduser().resolve()
    if not path.exists():
        return {
            "success": False,
            "sheets": [],
            "warnings": [f"File not found: {path}"],
        }

    sheets_payload: list[dict] = []
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(path) as book:
            shared = _load_shared_strings(book)
            targets = _sheet_targets(book)
            for sheet_name, sheet_path in targets:
                if max_sheets and len(sheets_payload) >= max_sheets:
                    warnings.append(
                        f"Workbook truncated to first {max_sheets} sheets"
                    )
                    break

                hr_requestor, month_requested = _parse_sheet_meta(sheet_name)

                column_order: list[str] = []
                header_values: list[str] | None = None
                date_columns: set[int] = set()
                data_rows: list[list[str]] = []
                total_rows = 0

                for row_number, row_data in _iter_sheet_rows(book, sheet_path, shared):
                    column_order = _expand_columns(column_order, row_data)
                    values = _row_values(column_order, row_data)

                    if header_values is None:
                        header_values = values
                        date_columns = _detect_date_columns(header_values)
                        continue

                    if date_columns:
                        values = [
                            _format_excel_date(cell) if idx in date_columns else cell
                            for idx, cell in enumerate(values)
                        ]

                    if not any(values):
                        continue

                    total_rows += 1
                    if max_rows_per_sheet and total_rows > max_rows_per_sheet:
                        warnings.append(
                            f"Sheet '{sheet_name}' truncated after {max_rows_per_sheet} rows"
                        )
                        break

                    data_rows.append(values)

                if header_values is None:
                    if include_empty_sheets:
                        sheets_payload.append(
                            {
                                "sheet_name": sheet_name,
                                "hr_requestor": hr_requestor,
                                "month_requested": month_requested,
                                "row_count": 0,
                                "table": "",
                            }
                        )
                    continue

                table_text = _format_table(header_values, data_rows)
                sheets_payload.append(
                    {
                        "sheet_name": sheet_name,
                        "hr_requestor": hr_requestor,
                        "month_requested": month_requested,
                        "row_count": len(data_rows),
                        "table": table_text,
                    }
                )
    except zipfile.BadZipFile:
        return {
            "success": False,
            "sheets": [],
            "warnings": ["Invalid Excel file: unable to open archive"],
        }
    except Exception as exc:
        return {
            "success": False,
            "sheets": [],
            "warnings": [f"Unexpected error: {type(exc).__name__}: {exc}"],
        }

    return {"success": True, "sheets": sheets_payload, "warnings": warnings or None}
