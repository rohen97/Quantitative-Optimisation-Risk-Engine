#!/usr/bin/env python3
"""Read-only validation for a repaired Portfolio Tracker workbook.

This script deliberately reads XLSX files as ZIP/XML packages.  It does not open
Excel, recalculate formulas, save either workbook, or create a sidecar file.

Example:
    python scripts/validate_portfolio_repair.py \
      --source "C:\\path\\Portfolio Tracker_Yvonne Wolf_2026.07.27.xlsx" \
      --repaired "C:\\path\\Portfolio Tracker_Yvonne Wolf_2026.07.27_repaired.xlsx" \
      --expected-source-sha256 <64-hex-character-pre-repair-hash>

The expected source digest is mandatory: comparing the source only with itself
would not prove that the original workbook remained unchanged during repair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import posixpath
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"m": MAIN_NS, "r": REL_NS, "pr": PKG_REL_NS}
CELL_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
A1_REF_RE = re.compile(r"(?<![A-Za-z0-9_.])(?P<colabs>\$?)(?P<col>[A-Z]{1,3})(?P<rowabs>\$?)(?P<row>[1-9][0-9]*)")
STRUCTURAL_ERROR_TOKENS = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NAME!")
PROVIDER_MARKER_RE = re.compile(
    r"(?:#N/A|INVALID SECURITY|MANDATORY PARAMETER|REQUESTING DATA|RETRIEVING DATA|"
    r"GETTING_DATA|BLOOMBERG|BDP\s+ERROR|BDH\s+ERROR)",
    re.IGNORECASE,
)

RAW_PROVIDER_SHEETS = {
    "Bond prices",
    "Equity prices",
    "Gold prices",
    "Exchange rate - base SGD",
    "Exchange rate - base USD",
}

KNOWN_NOISE_SHEETS = {
    "Tables for weekly presentation",
    "Hedging",
    "Cash Transactions - analysis",
    "Exited Equity Positions",
}

REQUIRED_SHEETS = {
    "Transactions List",
    "Bond Transactions",
    "Equity Transactions",
    "Bonds maturity and cpn timeline",
    "BS P&L",
    "Gold prices",
    "Cash Transactions - analysis",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def column_number(name: str) -> int:
    result = 0
    for char in name:
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def column_name(number: int) -> str:
    if number < 1:
        raise ValueError(f"invalid Excel column number: {number}")
    chars: List[str] = []
    while number:
        number, remainder = divmod(number - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def split_address(address: str) -> Tuple[str, int]:
    match = CELL_RE.match(address.upper())
    if not match:
        raise ValueError(f"invalid cell address: {address}")
    return match.group(1), int(match.group(2))


def normalize_formula(formula: str, *, ignore_dollars: bool = False) -> str:
    value = formula.strip()
    if value.startswith("="):
        value = value[1:]
    # Excel's OOXML serializer decorates modern functions, LET-bound variables,
    # and Bloomberg add-in functions even though the Excel UI omits the prefixes.
    # Examples: _xlfn.LET, _xlpm.d, _xlws.FILTER, and _xll.BDP/BDH.
    value = re.sub(r"(?i)_(?:xlfn|xlpm|xlws|xll)\.", "", value)
    value = re.sub(r"\s+", "", value).upper()
    if ignore_dollars:
        value = value.replace("$", "")
    return value


def historical_fx_formula(
    row: int,
    sheet: str,
    identity_currency: str,
    currency_column: str,
    date_column: str,
) -> str:
    currency = f"${currency_column}{row}"
    date = f"${date_column}{row}"
    return (
        f'IF(OR({currency}="",{date}=""),"",IF({currency}="{identity_currency}",1,LET('
        f"d,'{sheet}'!$A$8:$A$735,"
        f"c,MATCH({currency},'{sheet}'!$B$4:$L$4,0),"
        f"r,INDEX('{sheet}'!$B$8:$L$735,0,c),"
        f"ok,(d<={date})*ISNUMBER(r),"
        "ld,LOOKUP(2,1/ok,d),"
        "lr,LOOKUP(2,1/ok,r),"
        f"IF({date}-ld<=10,lr,NA()))))"
    )


def current_fx_formula(
    row: int,
    sheet: str,
    identity_currency: str,
    currency_column: str,
) -> str:
    currency = f"${currency_column}{row}"
    return (
        f'IF({currency}="","",IF({currency}="{identity_currency}",1,LET('
        f"c,MATCH({currency},'{sheet}'!$B$4:$L$4,0),"
        f"live,INDEX('{sheet}'!$B$6:$L$6,1,c),"
        f"d,'{sheet}'!$A$8:$A$735,"
        f"r,INDEX('{sheet}'!$B$8:$L$735,0,c),"
        "ok,(d<=TODAY())*ISNUMBER(r),"
        "ld,LOOKUP(2,1/ok,d),"
        "lr,LOOKUP(2,1/ok,r),"
        "IF(ISNUMBER(live),live,IF(TODAY()-ld<=10,lr,NA())))))"
    )


def translate_shared_formula(formula: str, source: str, target: str) -> str:
    """Translate ordinary A1 references in a shared-formula follower.

    Excel stores many copied formulas once, on a shared-formula master.  This is
    sufficient for the formulas in this workbook and preserves absolute axes.
    """

    source_col, source_row = split_address(source)
    target_col, target_row = split_address(target)
    delta_col = column_number(target_col) - column_number(source_col)
    delta_row = target_row - source_row

    def replace(match: re.Match[str]) -> str:
        col_abs = match.group("colabs") == "$"
        row_abs = match.group("rowabs") == "$"
        col_num = column_number(match.group("col"))
        row_num = int(match.group("row"))
        if not col_abs:
            col_num += delta_col
        if not row_abs:
            row_num += delta_row
        if col_num < 1 or row_num < 1:
            return match.group(0)
        return (
            ("$" if col_abs else "")
            + column_name(col_num)
            + ("$" if row_abs else "")
            + str(row_num)
        )

    return A1_REF_RE.sub(replace, formula)


@dataclass(frozen=True)
class Cell:
    address: str
    row: int
    column: str
    cell_type: str
    value: Optional[str]
    formula: Optional[str]
    formula_attributes: Mapping[str, str]

    @property
    def has_formula(self) -> bool:
        return self.formula is not None

    def numeric_value(self) -> Optional[float]:
        if self.value is None or self.cell_type in {"s", "str", "inlineStr", "e", "b"}:
            return None
        try:
            result = float(self.value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None


class Sheet:
    def __init__(self, name: str, xml_root: ET.Element, shared_strings: Sequence[str]) -> None:
        self.name = name
        self.cells: Dict[str, Cell] = {}
        self.shared_masters: Dict[str, Tuple[str, str]] = {}

        for element in xml_root.findall(".//m:sheetData/m:row/m:c", NS):
            address = element.attrib.get("r", "").upper()
            if not CELL_RE.match(address):
                continue
            column, row = split_address(address)
            cell_type = element.attrib.get("t", "n")
            formula_element = element.find("m:f", NS)
            formula: Optional[str] = None
            formula_attributes: Mapping[str, str] = {}
            if formula_element is not None:
                # Empty text is meaningful for a shared-formula follower.
                formula = formula_element.text or ""
                formula_attributes = dict(formula_element.attrib)
                if (
                    formula_attributes.get("t") == "shared"
                    and formula_attributes.get("si") is not None
                    and formula
                ):
                    self.shared_masters[formula_attributes["si"]] = (address, formula)

            raw_value: Optional[str] = None
            if cell_type == "inlineStr":
                raw_value = "".join(
                    text.text or "" for text in element.findall(".//m:is//m:t", NS)
                )
            else:
                value_element = element.find("m:v", NS)
                if value_element is not None:
                    raw_value = value_element.text or ""
                    if cell_type == "s":
                        try:
                            raw_value = shared_strings[int(raw_value)]
                        except (ValueError, IndexError):
                            pass

            self.cells[address] = Cell(
                address=address,
                row=row,
                column=column,
                cell_type=cell_type,
                value=raw_value,
                formula=formula,
                formula_attributes=formula_attributes,
            )

    def cell(self, address: str) -> Cell:
        normalized = address.upper()
        column, row = split_address(normalized)
        return self.cells.get(
            normalized,
            Cell(normalized, row, column, "n", None, None, {}),
        )

    def effective_formula(self, address: str) -> Optional[str]:
        cell = self.cell(address)
        if cell.formula is None:
            return None
        if cell.formula:
            return cell.formula
        if cell.formula_attributes.get("t") != "shared":
            return ""
        shared_index = cell.formula_attributes.get("si")
        if shared_index not in self.shared_masters:
            return ""
        master_address, master_formula = self.shared_masters[shared_index]
        return translate_shared_formula(master_formula, master_address, cell.address)


class WorkbookPackage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sheet_names: List[str] = []
        self.sheets: Dict[str, Sheet] = {}
        self.defined_names: List[Tuple[str, str]] = []
        self.external_link_parts: List[str] = []
        self.external_link_relationships: List[str] = []

        with zipfile.ZipFile(path, "r") as archive:
            corrupt_part = archive.testzip()
            if corrupt_part is not None:
                raise ValueError(f"CRC failure in XLSX member: {corrupt_part}")

            members = set(archive.namelist())
            required = {"[Content_Types].xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            missing = sorted(required - members)
            if missing:
                raise ValueError(f"missing required XLSX members: {', '.join(missing)}")

            # Parsing all XML package members catches malformed-but-CRC-valid XML.
            for member in sorted(name for name in members if name.lower().endswith(".xml")):
                ET.fromstring(archive.read(member))

            shared_strings = self._read_shared_strings(archive, members)
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            relationship_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relationships = {
                rel.attrib["Id"]: rel
                for rel in relationship_root.findall("pr:Relationship", NS)
                if "Id" in rel.attrib
            }

            for rel in relationships.values():
                rel_type = rel.attrib.get("Type", "")
                target = rel.attrib.get("Target", "")
                if "externalLink" in rel_type or "externalLinks" in target:
                    self.external_link_relationships.append(
                        f"{rel.attrib.get('Id', '?')}: {rel_type} -> {target}"
                    )

            for defined_name in workbook_root.findall(".//m:definedNames/m:definedName", NS):
                self.defined_names.append(
                    (defined_name.attrib.get("name", "(unnamed)"), defined_name.text or "")
                )

            for sheet_element in workbook_root.findall(".//m:sheets/m:sheet", NS):
                name = sheet_element.attrib["name"]
                relationship_id = sheet_element.attrib.get(f"{{{REL_NS}}}id")
                if not relationship_id or relationship_id not in relationships:
                    raise ValueError(f"worksheet {name!r} has no resolvable relationship")
                target = relationships[relationship_id].attrib.get("Target", "")
                if target.startswith("/"):
                    member = target.lstrip("/")
                else:
                    member = posixpath.normpath(posixpath.join("xl", target))
                if member not in members:
                    raise ValueError(f"worksheet {name!r} is missing package member {member!r}")
                root = ET.fromstring(archive.read(member))
                self.sheet_names.append(name)
                self.sheets[name] = Sheet(name, root, shared_strings)

            self.external_link_parts = sorted(
                name for name in members if name.startswith("xl/externalLinks/")
            )

    @staticmethod
    def _read_shared_strings(archive: zipfile.ZipFile, members: Iterable[str]) -> List[str]:
        if "xl/sharedStrings.xml" not in members:
            return []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        return [
            "".join(node.text or "" for node in item.findall(".//m:t", NS))
            for item in root.findall("m:si", NS)
        ]

    def sheet(self, name: str) -> Sheet:
        if name not in self.sheets:
            raise KeyError(f"missing worksheet: {name}")
        return self.sheets[name]


class ValidationReport:
    def __init__(self) -> None:
        self.checks: List[dict] = []
        self.failures: List[str] = []
        self.warnings: List[str] = []

    def check(self, name: str, condition: bool, detail: str) -> None:
        self.checks.append({"name": name, "ok": bool(condition), "detail": detail})
        if not condition:
            self.failures.append(f"{name}: {detail}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def display_value(cell: Cell) -> str:
    return "<blank>" if cell.value is None else repr(cell.value)


def expect_text_value(
    report: ValidationReport,
    workbook: WorkbookPackage,
    sheet_name: str,
    address: str,
    expected: str,
) -> None:
    cell = workbook.sheet(sheet_name).cell(address)
    actual = cell.value
    report.check(
        f"value {sheet_name}!{address}",
        actual == expected and actual == actual.strip() if actual is not None else False,
        f"expected {expected!r}; found {display_value(cell)}",
    )


def expect_formula(
    report: ValidationReport,
    workbook: WorkbookPackage,
    sheet_name: str,
    address: str,
    expected: str,
    *,
    ignore_dollars: bool = False,
) -> None:
    sheet = workbook.sheet(sheet_name)
    formula = sheet.effective_formula(address)
    condition = formula is not None and normalize_formula(
        formula, ignore_dollars=ignore_dollars
    ) == normalize_formula(expected, ignore_dollars=ignore_dollars)
    report.check(
        f"formula {sheet_name}!{address}",
        condition,
        f"expected ={expected}; found {('=' + formula) if formula is not None else '<no formula>'}",
    )


def expect_formula_fragments(
    report: ValidationReport,
    workbook: WorkbookPackage,
    sheet_name: str,
    address: str,
    fragments: Sequence[str],
) -> None:
    sheet = workbook.sheet(sheet_name)
    formula = sheet.effective_formula(address)
    normalized = normalize_formula(formula or "", ignore_dollars=True)
    missing = [
        fragment
        for fragment in fragments
        if normalize_formula(fragment, ignore_dollars=True) not in normalized
    ]
    report.check(
        f"formula content {sheet_name}!{address}",
        formula is not None and not missing,
        f"missing fragments {missing}; found {('=' + formula) if formula is not None else '<no formula>'}",
    )


def expect_numeric(
    report: ValidationReport,
    workbook: WorkbookPackage,
    sheet_name: str,
    address: str,
) -> Optional[float]:
    cell = workbook.sheet(sheet_name).cell(address)
    number = cell.numeric_value()
    report.check(
        f"numeric cached result {sheet_name}!{address}",
        number is not None,
        f"found type={cell.cell_type!r}, value={display_value(cell)}",
    )
    return number


def is_blank(cell: Cell) -> bool:
    return cell.value is None or cell.value == ""


def is_known_noise(workbook: WorkbookPackage, sheet_name: str, cell: Cell) -> bool:
    if sheet_name in KNOWN_NOISE_SHEETS:
        return True
    if sheet_name == "Gold Transactions" and cell.row == 6:
        return True
    if sheet_name == "Equity Transactions" and cell.row == 6:
        return True
    if sheet_name == "Current Bond Positions" and cell.column == "AF":
        driver = workbook.sheet(sheet_name).cell(f"X{cell.row}").numeric_value()
        return driver == 0.0
    return False


def is_blank_template_error(workbook: WorkbookPackage, sheet_name: str, cell: Cell) -> bool:
    sheet = workbook.sheet(sheet_name)
    if sheet_name == "Bond Transactions" and cell.row >= 9:
        return is_blank(sheet.cell(f"D{cell.row}"))
    if sheet_name == "Equity Transactions" and cell.row >= 9:
        return is_blank(sheet.cell(f"D{cell.row}"))
    if sheet_name == "Gold Transactions" and cell.row >= 9:
        driver = sheet.cell(f"D{cell.row}").value
        return driver is None or driver in {"", "-"}
    return False


def compact_error_items(items: Sequence[Tuple[str, str, str]]) -> dict:
    counts_by_sheet: Dict[str, int] = {}
    grouped: Dict[str, Dict[str, List[str]]] = {}
    for sheet, address, token in items:
        counts_by_sheet[sheet] = counts_by_sheet.get(sheet, 0) + 1
        grouped.setdefault(sheet, {}).setdefault(token, []).append(address)
    return {
        "count": len(items),
        "counts_by_sheet": dict(sorted(counts_by_sheet.items())),
        "cells_by_sheet_and_error": {
            sheet: {token: addresses for token, addresses in sorted(tokens.items())}
            for sheet, tokens in sorted(grouped.items())
        },
    }


def enumerate_errors(workbook: WorkbookPackage) -> dict:
    structural: List[Tuple[str, str, str]] = []
    known_noise: List[Tuple[str, str, str]] = []
    blank_templates: List[Tuple[str, str, str]] = []
    provider_structural: List[Tuple[str, str, str]] = []
    raw_provider_markers: List[str] = []
    downstream_provider_markers: List[str] = []

    for sheet_name, sheet in workbook.sheets.items():
        for cell in sheet.cells.values():
            formula = sheet.effective_formula(cell.address) or ""
            tokens: List[str] = []
            if cell.cell_type == "e" and cell.value in STRUCTURAL_ERROR_TOKENS:
                tokens.append(cell.value)
            for token in STRUCTURAL_ERROR_TOKENS:
                if token in formula.upper() and token not in tokens:
                    tokens.append(token)

            for token in tokens:
                item = (sheet_name, cell.address, token)
                if sheet_name in RAW_PROVIDER_SHEETS:
                    provider_structural.append(item)
                elif is_known_noise(workbook, sheet_name, cell):
                    known_noise.append(item)
                elif is_blank_template_error(workbook, sheet_name, cell):
                    blank_templates.append(item)
                else:
                    structural.append(item)

            text = cell.value or ""
            if PROVIDER_MARKER_RE.search(text):
                rendered = f"{sheet_name}!{cell.address}: {text[:180]}"
                if sheet_name in RAW_PROVIDER_SHEETS:
                    raw_provider_markers.append(rendered)
                else:
                    downstream_provider_markers.append(rendered)

    return {
        "unexpected_structural_errors": compact_error_items(structural),
        "known_presentation_or_legacy_noise": compact_error_items(known_noise),
        "blank_template_errors": compact_error_items(blank_templates),
        "raw_provider_structural_errors": compact_error_items(provider_structural),
        "raw_provider_markers": {
            "count": len(raw_provider_markers),
            "examples": raw_provider_markers[:100],
        },
        "downstream_provider_markers": {
            "count": len(downstream_provider_markers),
            "examples": downstream_provider_markers[:100],
        },
    }


def validate_source_string_preservation(
    report: ValidationReport,
    source: WorkbookPackage,
    repaired: WorkbookPackage,
) -> dict:
    """Catch Excel dropping orphan ``t=str`` literals during open/save.

    The source file contains observed identifiers encoded as formula-string cells
    even though they have no formula.  Excel silently treats those cells as blank
    when it rewrites the package unless the repair restores/normalizes them.
    Trimming surrounding whitespace is an explicitly allowed repair.
    """

    checked = 0
    mismatches: List[str] = []

    def belongs_to_known_spill(sheet_name: str, cell: Cell) -> bool:
        column_index = column_number(cell.column)
        return (
            (sheet_name == "Bond Transactions" and cell.column == "D" and 51 <= cell.row <= 156)
            or (sheet_name == "Bonds analysis" and cell.column == "A" and 6 <= cell.row <= 63)
            or (
                sheet_name == "Bond prices"
                and cell.row == 4
                and column_number("C") <= column_index <= column_number("BH")
            )
            or (
                sheet_name == "Bond prices"
                and cell.column == "A"
                and 31 <= cell.row <= 89
            )
        )

    for sheet_name, source_sheet in source.sheets.items():
        if sheet_name not in repaired.sheets:
            mismatches.append(f"missing repaired worksheet: {sheet_name}")
            continue
        repaired_sheet = repaired.sheet(sheet_name)
        for source_cell in source_sheet.cells.values():
            if (
                source_cell.cell_type != "str"
                or source_cell.formula is not None
                or source_cell.value in {None, ""}
                or belongs_to_known_spill(sheet_name, source_cell)
            ):
                continue
            checked += 1
            actual = repaired_sheet.cell(source_cell.address).value
            expected = source_cell.value or ""
            if actual not in {expected, expected.strip()}:
                mismatches.append(
                    f"{sheet_name}!{source_cell.address}: source={expected!r}; repaired={actual!r}"
                )

    report.check(
        "source non-formula t=str observations preserved",
        not mismatches,
        f"checked {checked}; found {len(mismatches)} losses/changes: {mismatches[:200]}",
    )
    return {
        "checked_cells": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def validate_bond_spill_semantics(
    report: ValidationReport,
    source: WorkbookPackage,
    repaired: WorkbookPackage,
) -> dict:
    """Validate bond-ID and transpose ranges by spill meaning, not encoding."""

    def normalized(cell: Cell) -> str:
        return (cell.value or "").strip()

    source_bond_sheet = source.sheet("Bond Transactions")
    repaired_bond_sheet = repaired.sheet("Bond Transactions")
    expected_bonds = [normalized(source_bond_sheet.cell(f"D{row}")) for row in range(50, 157)]
    actual_bonds = [normalized(repaired_bond_sheet.cell(f"D{row}")) for row in range(50, 157)]

    source_sequence_valid = (
        len(expected_bonds) == 107
        and all(expected_bonds)
    )
    report.check(
        "source Bond Transactions D50:D156 defines 107 normalized IDs",
        source_sequence_valid,
        f"count={len(expected_bonds)}, blank positions="
        f"{[index + 50 for index, value in enumerate(expected_bonds) if not value]}",
    )
    bond_mismatches = [
        f"D{row}: expected={expected!r}; repaired={actual!r}"
        for row, (expected, actual) in enumerate(zip(expected_bonds, actual_bonds), start=50)
        if actual != expected
    ]
    report.check(
        "Bond Transactions D50:D156 equals source sequence after trimming",
        source_sequence_valid and not bond_mismatches,
        f"found {len(bond_mismatches)} mismatches: {bond_mismatches[:150]}",
    )

    # The canonical security order is the source Bond prices header/Bonds
    # analysis spill order.  It is not necessarily the first-seen order of the
    # 107 Bond Transactions rows.
    source_prices_sheet = source.sheet("Bond prices")
    source_price_headers = [
        normalized(source_prices_sheet.cell(f"{column_name(column)}4"))
        for column in range(column_number("B"), column_number("BH") + 1)
    ]
    source_analysis_sheet = source.sheet("Bonds analysis")
    source_analysis_values = [
        normalized(source_analysis_sheet.cell(f"A{row}")) for row in range(5, 64)
    ]
    header_ordered_unique = list(
        dict.fromkeys(value for value in source_price_headers if value)
    )
    analysis_ordered_unique = list(
        dict.fromkeys(value for value in source_analysis_values if value)
    )
    source_orders_match = header_ordered_unique == analysis_ordered_unique
    report.check(
        "source Bond prices and Bonds analysis define the same normalized order",
        source_orders_match,
        f"Bond prices={header_ordered_unique}; Bonds analysis={analysis_ordered_unique}",
    )

    ordered_unique = header_ordered_unique if source_orders_match else []
    unique_definition_valid = (
        len(ordered_unique) == 56
        and ordered_unique[-1:] == ["US500769JZ83"]
    )
    report.check(
        "canonical source bond header has expected 56-item ordered UNIQUE",
        unique_definition_valid,
        f"count={len(ordered_unique)}, last={ordered_unique[-1] if ordered_unique else None!r}",
    )

    expected_spill = ordered_unique + [""] * (59 - len(ordered_unique))
    analysis_sheet = repaired.sheet("Bonds analysis")
    analysis_spill = [normalized(analysis_sheet.cell(f"A{row}")) for row in range(5, 64)]
    prices_sheet = repaired.sheet("Bond prices")
    prices_spill = [
        normalized(prices_sheet.cell(f"{column_name(column)}4"))
        for column in range(column_number("B"), column_number("BH") + 1)
    ]

    analysis_mismatches = [
        f"A{row}: expected={expected!r}; repaired={actual!r}"
        for row, (expected, actual) in enumerate(zip(expected_spill, analysis_spill), start=5)
        if expected != actual
    ]
    prices_mismatches = [
        f"{column_name(column)}4: expected={expected!r}; repaired={actual!r}"
        for column, (expected, actual) in enumerate(
            zip(expected_spill, prices_spill), start=column_number("B")
        )
        if expected != actual
    ]
    report.check(
        "Bonds analysis A5:A63 equals contiguous ordered-UNIQUE spill",
        unique_definition_valid and not analysis_mismatches,
        f"found {len(analysis_mismatches)} mismatches: {analysis_mismatches[:100]}",
    )
    report.check(
        "Bond prices B4:BH4 equals contiguous ordered-UNIQUE spill",
        unique_definition_valid and not prices_mismatches,
        f"found {len(prices_mismatches)} mismatches: {prices_mismatches[:100]}",
    )

    # A30 transposes the row-4 header spill down column A.  Its first element
    # corresponds to the blank/zero row label in A4, then A31:A86 must mirror
    # the 56 populated headers and the final three follower slots must be empty.
    transpose_formula = prices_sheet.effective_formula("A30")
    report.check(
        "Bond prices A30 retains the row-4 TRANSPOSE master",
        (
            transpose_formula is not None
            and "TRANSPOSE(4:4)" in normalize_formula(transpose_formula, ignore_dollars=True)
        ),
        f"found {('=' + transpose_formula) if transpose_formula is not None else '<no formula>'}",
    )
    transpose_anchor = normalized(prices_sheet.cell("A30"))
    report.check(
        "Bond prices A30 transpose anchor cache is blank or zero",
        transpose_anchor in {"", "0"},
        f"found {display_value(prices_sheet.cell('A30'))}",
    )
    transpose_values = [
        normalized(prices_sheet.cell(f"A{row}")) for row in range(31, 87)
    ]
    transpose_mismatches = [
        f"A{row}: expected={expected!r}; repaired={actual!r}"
        for row, (expected, actual) in enumerate(
            zip(prices_spill[:56], transpose_values), start=31
        )
        if expected != actual
    ]
    report.check(
        "Bond prices A31:A86 transposes B4:BE4 in order",
        not transpose_mismatches,
        f"found {len(transpose_mismatches)} mismatches: {transpose_mismatches[:100]}",
    )
    transpose_tail = {
        f"A{row}": normalized(prices_sheet.cell(f"A{row}")) for row in range(87, 90)
    }
    invalid_transpose_tail = {
        address: value for address, value in transpose_tail.items() if value not in {"", "0"}
    }
    report.check(
        "Bond prices A87:A89 transpose tail is blank or zero",
        not invalid_transpose_tail,
        f"invalid values: {invalid_transpose_tail}",
    )

    return {
        "source_bond_count": len(expected_bonds),
        "ordered_unique_count": len(ordered_unique),
        "ordered_unique_last": ordered_unique[-1] if ordered_unique else None,
        "bond_transaction_mismatches": bond_mismatches,
        "bonds_analysis_mismatches": analysis_mismatches,
        "bond_prices_mismatches": prices_mismatches,
        "bond_prices_transpose_mismatches": transpose_mismatches,
        "bond_prices_transpose_tail": transpose_tail,
    }


def validate_external_links(report: ValidationReport, workbook: WorkbookPackage) -> None:
    report.check(
        "no external-link package parts",
        not workbook.external_link_parts,
        f"found: {workbook.external_link_parts}",
    )
    report.check(
        "no external-link workbook relationships",
        not workbook.external_link_relationships,
        f"found: {workbook.external_link_relationships}",
    )

    bracket_formulas: List[str] = []
    for sheet_name, sheet in workbook.sheets.items():
        for cell in sheet.cells.values():
            formula = sheet.effective_formula(cell.address)
            if formula is not None and "[" in formula:
                bracket_formulas.append(f"{sheet_name}!{cell.address}: ={formula}")
    for name, formula in workbook.defined_names:
        if "[" in formula:
            bracket_formulas.append(f"defined name {name}: ={formula}")
    report.check(
        "no formula or defined-name '[' references",
        not bracket_formulas,
        f"found {len(bracket_formulas)}: {bracket_formulas[:50]}",
    )


def validate_exact_repairs(report: ValidationReport, workbook: WorkbookPackage) -> None:
    # IDs that were visually valid but contained leading/trailing whitespace.
    transaction_ids = {
        "G87": "US594918BY93",
        "G88": "US594918BR43",
        "G92": "US594918BR43",
        "G111": "C6L SP Equity",
        "G122": "SG7J60932174",
        "G174": "SG1W45939194",
        "G216": "DE0008430026",
    }
    bond_ids = {
        "D74": "US594918BY93",
        "D75": "US594918BR43",
        "D77": "US594918BR43",
        "D95": "SG7J60932174",
    }
    for address, expected in transaction_ids.items():
        expect_text_value(report, workbook, "Transactions List", address, expected)
    for address, expected in bond_ids.items():
        expect_text_value(report, workbook, "Bond Transactions", address, expected)

    equity_formulas = {
        "G11": "'Transactions List'!I111",
        "G12": "'Transactions List'!I127",
        "G14": "'Transactions List'!I129",
        "G17": "'Transactions List'!I174",
        "G18": "'Transactions List'!I175",
        "A19": "'Transactions List'!A184",
        "I19": "'Transactions List'!L184+'Transactions List'!M184",
    }
    for address, expected in equity_formulas.items():
        expect_formula(report, workbook, "Equity Transactions", address, expected)

    expect_formula(report, workbook, "Transactions List", "Q241", "$F241/ABS($F242)")
    expect_formula(report, workbook, "Transactions List", "Q242", "1")
    expect_formula(
        report,
        workbook,
        "Transactions List",
        "Q245",
        historical_fx_formula(245, "Exchange rate - base USD", "USD", "E", "A"),
    )
    expect_formula(
        report,
        workbook,
        "Transactions List",
        "U231",
        current_fx_formula(231, "Exchange rate - base USD", "USD", "E"),
    )
    expect_formula(
        report,
        workbook,
        "Transactions List",
        "V231",
        'IF(NOT(ISNUMBER($F231)),"",$F231/$U231)',
    )
    expect_formula(
        report,
        workbook,
        "Transactions List",
        "Z226",
        historical_fx_formula(226, "Exchange rate - base SGD", "SGD", "E", "A"),
    )
    expect_formula(
        report,
        workbook,
        "Bond Transactions",
        "BD141",
        historical_fx_formula(141, "Exchange rate - base SGD", "SGD", "S", "A"),
    )
    expect_formula_fragments(
        report,
        workbook,
        "Transactions List",
        "F223",
        (
            'AND(B223="Bond",C223="Matured")',
            "H223*I223/100",
            'AND(B223="Bond",C223="Buy")',
            "-((H223*I223/100)+J223)",
            'AND(B223="Bond",C223="Coupon Received")',
            'AND(B223="Equity",C223="Buy")',
            'AND(B223="Gold",C223="Sell")',
        ),
    )
    expect_formula(
        report,
        workbook,
        "BS P&L",
        "G30",
        'SUMIF(\'Transactions List\'!C:C,"Dividend received",\'Transactions List\'!R:R)',
    )
    expect_formula(
        report,
        workbook,
        "Cash Transactions - analysis",
        "J64",
        'IF(OR(D60="",D60="-"),"",BDP("EUR"&D60&" CURNCY","PX_LAST"))',
    )
    expect_formula_fragments(
        report,
        workbook,
        "Gold prices",
        "D4",
        ("FILTER", "'Gold Transactions'!D9:D5000", '<>""', '<>"-"', "UNIQUE", "TRANSPOSE"),
    )

    # These five rates are intentional manual overrides and must not be converted
    # to provider formulas while rebuilding the rest of column Q.
    manual_rates = {
        "Q9": 31.505,
        "Q39": 1.2854800170450504,
        "Q42": 1.2749099722100894,
        "Q45": 1.2788739915022145,
        "Q49": 0.8368000000000001,
    }
    transaction_sheet = workbook.sheet("Transactions List")
    for address, expected in manual_rates.items():
        cell = transaction_sheet.cell(address)
        actual = cell.numeric_value()
        condition = (
            not cell.has_formula
            and actual is not None
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        )
        report.check(
            f"preserved manual FX rate Transactions List!{address}",
            condition,
            f"expected non-formula {expected!r}; found formula={cell.formula!r}, value={display_value(cell)}",
        )


def validate_transactions_chain(report: ValidationReport, workbook: WorkbookPackage) -> dict:
    sheet = workbook.sheet("Transactions List")
    active_rows: List[int] = []
    failures: List[str] = []
    pasted_text: List[str] = []
    formula_mismatches: List[str] = []

    for row in range(2, 1001):
        # Require a date plus transaction-identifying data.  Do not use F being
        # numeric as the active-row predicate: a broken F formula is exactly the
        # kind of upstream fault this chain validation must expose.
        identifying_cells = ("D", "E", "F", "G")
        if not is_blank(sheet.cell(f"A{row}")) and any(
            not is_blank(sheet.cell(f"{column}{row}")) for column in identifying_cells
        ):
            active_rows.append(row)
            expected_formulas = {
                "R": f'IF(NOT(ISNUMBER($F{row})),"",$F{row}/$Q{row})',
                "S": f'IF($D{row}="","",SUMIF($D$2:$D{row},$D{row},$R$2:$R{row}))',
                "T": f'IF(NOT(ISNUMBER($F{row})),"",SUM($R$2:$R{row}))',
                "U": current_fx_formula(row, "Exchange rate - base USD", "USD", "E"),
                "V": f'IF(NOT(ISNUMBER($F{row})),"",$F{row}/$U{row})',
                "W": f'IF($D{row}="","",SUMIF($D$2:$D{row},$D{row},$V$2:$V{row}))',
                "X": f'IF(NOT(ISNUMBER($F{row})),"",SUM($V$2:$V{row}))',
            }
            for column in ("R", "S", "T", "U", "V", "W", "X"):
                address = f"{column}{row}"
                cell = sheet.cell(address)
                formula = sheet.effective_formula(address)
                if cell.cell_type in {"s", "str", "inlineStr"} and formula is None:
                    pasted_text.append(f"{address}: {display_value(cell)}")
                if formula is None or cell.numeric_value() is None:
                    failures.append(
                        f"{address}: formula={'yes' if formula is not None else 'no'}, "
                        f"type={cell.cell_type!r}, value={display_value(cell)}"
                    )
                elif normalize_formula(formula) != normalize_formula(expected_formulas[column]):
                    formula_mismatches.append(
                        f"{address}: expected ={expected_formulas[column]}; found ={formula}"
                    )

    report.check(
        "Transactions List active row boundary",
        bool(active_rows) and active_rows[-1] == 246,
        f"active rows={len(active_rows)}, last={active_rows[-1] if active_rows else None}; expected last=246",
    )
    report.check(
        "no pasted display text in Transactions List R:X active rows",
        not pasted_text,
        f"found {len(pasted_text)}: {pasted_text[:100]}",
    )
    report.check(
        "Transactions List R:X active formulas have numeric cached results",
        not failures,
        f"found {len(failures)}: {failures[:150]}",
    )
    report.check(
        "Transactions List R:X active formulas match repaired formula families",
        not formula_mismatches,
        f"found {len(formula_mismatches)}: {formula_mismatches[:100]}",
    )
    return {
        "active_row_count": len(active_rows),
        "first_active_row": active_rows[0] if active_rows else None,
        "last_active_row": active_rows[-1] if active_rows else None,
        "pasted_text_cells": pasted_text,
        "non_formula_or_nonnumeric_cells": failures,
        "formula_mismatches": formula_mismatches,
    }


def validate_maturity_formulas(report: ValidationReport, workbook: WorkbookPackage) -> dict:
    sheet = workbook.sheet("Bonds maturity and cpn timeline")
    failures: List[str] = []

    month_anchor = sheet.cell("U9")
    month_text = month_anchor.value or ""
    report.check(
        "maturity U9 month spill anchor is populated text",
        (
            month_anchor.formula is not None
            and month_anchor.cell_type in {"s", "str", "inlineStr"}
            and bool(month_text.strip())
            and not month_text.startswith("#")
        ),
        f"found type={month_anchor.cell_type!r}, value={display_value(month_anchor)}, "
        f"formula={sheet.effective_formula('U9')!r}",
    )

    for row in range(9, 101):
        address = f"X{row}"
        formula = sheet.effective_formula(address)
        normalized = normalize_formula(formula or "", ignore_dollars=True)
        row_ref = f"U{row}"
        conditions = (
            formula is not None,
            "SUMIFS(F1:F1000,A1:A1000" in normalized,
            normalized.count("A1:A1000") >= 2,
            row_ref in normalized,
            f"YEAR({row_ref})" in normalized,
            f"MONTH({row_ref})" in normalized,
            f"EOMONTH({row_ref},0)" in normalized,
            "F1:F999" not in normalized,
            "A1:A999" not in normalized,
        )
        if not all(conditions):
            failures.append(
                f"{address}: {('=' + formula) if formula is not None else '<no formula>'}"
            )

    report.check(
        "maturity X9:X100 SUMIFS ranges align at row 1000",
        not failures,
        f"found {len(failures)} mismatches: {failures[:100]}",
    )
    return {"checked_cells": 92, "mismatches": failures}


def validate_critical_results(report: ValidationReport, workbook: WorkbookPackage) -> dict:
    critical_cells = (
        ("Transactions List", "U231"),
        ("Transactions List", "V231"),
        ("Transactions List", "Q245"),
        ("Transactions List", "Z226"),
        ("Bond Transactions", "BD141"),
        ("Bond Transactions", "BG141"),
        ("BS P&L", "G26"),
        ("BS P&L", "G30"),
        ("BS P&L", "G49"),
        ("BS P&L", "D33"),
        ("Bonds maturity and cpn timeline", "X9"),
    )
    values: Dict[str, Optional[float]] = {}
    for sheet_name, address in critical_cells:
        values[f"{sheet_name}!{address}"] = expect_numeric(
            report, workbook, sheet_name, address
        )

    pnl_check = values.get("BS P&L!D33")
    if pnl_check is not None and not math.isclose(pnl_check, 0.0, abs_tol=0.01):
        # D33's purpose is to expose a residual reconciliation difference.  The
        # repair order required a numeric result, not an inferred rewrite of
        # ambiguous transfer classifications, so retain it as a visible warning.
        report.warn(f"BS P&L!D33 remains non-zero after recalculation: {pnl_check}")
    return values


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="original untouched XLSX")
    parser.add_argument("--repaired", required=True, type=Path, help="repaired/recalculated XLSX")
    parser.add_argument(
        "--expected-source-sha256",
        required=True,
        help="SHA-256 captured from the source before repair (64 hexadecimal characters)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    report = ValidationReport()
    output: dict = {
        "validator": "validate_portfolio_repair.py",
        "read_only": True,
        "source": str(args.source.resolve()),
        "repaired": str(args.repaired.resolve()),
    }

    try:
        expected_hash = args.expected_source_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError("--expected-source-sha256 must contain exactly 64 hexadecimal characters")
        if not args.source.is_file():
            raise FileNotFoundError(f"source workbook does not exist: {args.source}")
        if not args.repaired.is_file():
            raise FileNotFoundError(f"repaired workbook does not exist: {args.repaired}")

        source_path = args.source.resolve()
        repaired_path = args.repaired.resolve()
        report.check(
            "source and repaired paths are distinct",
            source_path != repaired_path,
            f"source={source_path}; repaired={repaired_path}",
        )

        source_hash = sha256_file(source_path)
        repaired_hash = sha256_file(repaired_path)
        output["source_sha256"] = source_hash
        output["expected_source_sha256"] = expected_hash
        output["repaired_sha256"] = repaired_hash
        report.check(
            "source SHA-256 unchanged",
            source_hash == expected_hash,
            f"expected={expected_hash}; actual={source_hash}",
        )
        report.check(
            "repaired workbook differs from source",
            repaired_hash != source_hash,
            f"source={source_hash}; repaired={repaired_hash}",
        )

        # Construction verifies ZIP CRCs, required OOXML parts, every XML part,
        # workbook relationships, and all worksheet XML.
        source_workbook = WorkbookPackage(source_path)
        report.check("source XLSX package opens and parses", True, "ZIP CRC and OOXML parse passed")
        workbook = WorkbookPackage(repaired_path)
        report.check("repaired XLSX package opens and parses", True, "ZIP CRC and OOXML parse passed")
        missing_sheets = sorted(REQUIRED_SHEETS - set(workbook.sheet_names))
        report.check(
            "required worksheets are present",
            not missing_sheets,
            f"missing: {missing_sheets}",
        )

        if not missing_sheets:
            output["source_string_preservation"] = validate_source_string_preservation(
                report, source_workbook, workbook
            )
            output["bond_spill_semantics"] = validate_bond_spill_semantics(
                report, source_workbook, workbook
            )
            validate_external_links(report, workbook)
            validate_exact_repairs(report, workbook)
            output["transactions_chain"] = validate_transactions_chain(report, workbook)
            output["maturity_formulas"] = validate_maturity_formulas(report, workbook)
            output["critical_cached_values"] = validate_critical_results(report, workbook)
            output["error_inventory"] = enumerate_errors(workbook)
            unexpected_count = output["error_inventory"]["unexpected_structural_errors"]["count"]
            report.check(
                "no unexpected structural formula errors",
                unexpected_count == 0,
                f"found {unexpected_count}; see error_inventory.unexpected_structural_errors",
            )

        source_hash_after_validation = sha256_file(source_path)
        output["source_sha256_after_validation"] = source_hash_after_validation
        report.check(
            "source SHA-256 stable throughout validation",
            source_hash_after_validation == source_hash == expected_hash,
            f"before={source_hash}; after={source_hash_after_validation}; expected={expected_hash}",
        )

    except Exception as exc:  # Produce a machine-readable failure even for malformed XLSX.
        report.failures.append(f"validator exception: {type(exc).__name__}: {exc}")

    output["checks"] = report.checks
    output["warnings"] = report.warnings
    output["failures"] = report.failures
    output["status"] = "PASS" if not report.failures else "FAIL"
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not report.failures else 1


if __name__ == "__main__":
    sys.exit(main())
