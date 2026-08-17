"""Restore selected XLSX formula caches from an untouched workbook.

This helper operates directly on the OOXML ZIP package.  It copies only the
cached cell type (the ``c/@t`` attribute) and cached value (the ``c/v``
element) from an untouched source workbook into a repaired copy.  Formula
nodes, styles, and every non-formula repaired cell are verified unchanged.

The repaired workbook is modified in place only with ``--apply``.  ``--dry-run``
performs the complete merge and validation in memory without writing a file;
omitting both mode flags also defaults to a dry run.

Examples::

    python scripts/restore_formula_caches.py \
        --source "C:\\path\\Portfolio Tracker_original.xlsx" \
        --repaired "artifacts\\Portfolio Tracker_REPAIRED.xlsx" \
        --dry-run

    python scripts/restore_formula_caches.py \
        --source "C:\\path\\Portfolio Tracker_original.xlsx" \
        --repaired "artifacts\\Portfolio Tracker_REPAIRED.xlsx" \
        --apply

The command leaves unrelated Excel processes alone.  It fails closed if either
target workbook has an Excel owner/lock file or cannot be opened exclusively,
and it repeats hash and lock checks immediately before replacement.  It never
writes to the source path.
"""

from __future__ import annotations

import argparse
import copy
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import hashlib
import io
import os
from pathlib import Path
import posixpath
import re
import shutil
import stat
import sys
import tempfile
from typing import Any, Iterable
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr
import zipfile


WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELS_PART = "xl/_rels/workbook.xml.rels"
PRICE_SHEETS = frozenset({"Bond prices", "Equity prices", "Gold prices"})
GUARD_WRAPPED_SHEETS = PRICE_SHEETS | {
    "Current Equity Positions",
    "Exited Equity Positions",
    "Equity Analysis",
}
SGD_SHEET = "Exchange rate - base SGD"
USD_SHEET = "Exchange rate - base USD"
REQUIRED_SHEETS = GUARD_WRAPPED_SHEETS | {SGD_SHEET, USD_SHEET}
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
CELL_REFERENCE_RE = re.compile(r"^([A-Za-z]{1,3})([1-9][0-9]*)$")


class CacheRestoreError(RuntimeError):
    """Raised when a safety or workbook-integrity invariant fails."""


@dataclass(frozen=True)
class Package:
    infos: tuple[zipfile.ZipInfo, ...]
    entries: dict[str, bytes]
    comment: bytes


@dataclass
class XmlDocument:
    root: ET.Element
    leading_bytes: bytes
    root_namespaces: tuple[tuple[str, str], ...]


@dataclass
class SheetStats:
    selected_formula_cells: int = 0
    cache_values_copied: int = 0
    absent_cache_values_copied: int = 0
    changed_cells: int = 0
    type_changes: int = 0
    empty_formula_followers_skipped: int = 0
    repaired_only_formulas_skipped: int = 0
    source_empty_formulas_skipped: int = 0
    source_only_formula_cells: int = 0


@dataclass
class MergeReport:
    sheets: dict[str, SheetStats] = field(default_factory=dict)
    targeted_cells: set[tuple[str, str]] = field(default_factory=set)
    old_calc_properties: dict[str, str | None] = field(default_factory=dict)
    replacement_parts: int = 0


@dataclass(frozen=True)
class CellState:
    is_formula: bool
    formula: Any
    style: str | None
    full_cell: Any
    non_cache_cell: Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_workbook(path_text: str, role: str) -> Path:
    path = Path(path_text).expanduser().resolve(strict=True)
    if path.is_symlink():
        raise CacheRestoreError(f"{role} workbook must not be a symlink: {path}")
    if not path.is_file():
        raise CacheRestoreError(f"{role} workbook is not a regular file: {path}")
    if path.suffix.casefold() != ".xlsx":
        raise CacheRestoreError(f"{role} workbook must be an .xlsx file: {path}")
    return path


def _assert_distinct_files(source: Path, repaired: Path) -> None:
    if source == repaired or os.path.samefile(source, repaired):
        raise CacheRestoreError(
            "Source and repaired workbook resolve to the same file; refusing to write"
        )


def _assert_exclusive_windows_access(path: Path, *, writable: bool) -> None:
    if os.name != "nt":
        raise CacheRestoreError("Exclusive workbook safety checks require Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    generic_read = 0x80000000
    generic_write = 0x40000000
    open_existing = 3
    file_attribute_normal = 0x80
    desired_access = generic_read | (generic_write if writable else 0)
    handle = create_file(
        str(path),
        desired_access,
        0,  # No sharing: fail if any process has the workbook open.
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error_code = ctypes.get_last_error()
        action = "read/write" if writable else "read"
        raise CacheRestoreError(
            f"Cannot obtain exclusive {action} access to {path} "
            f"(Windows error {error_code}: {ctypes.FormatError(error_code).strip()})"
        )
    try:
        pass
    finally:
        close_handle(handle)


def _assert_workbook_files_closed(source: Path, repaired: Path) -> None:
    for path in (source, repaired):
        owner_file = path.with_name(f"~${path.name}")
        if owner_file.exists():
            raise CacheRestoreError(
                f"Excel owner/lock file still exists for {path}: {owner_file}"
            )
    _assert_exclusive_windows_access(source, writable=False)
    _assert_exclusive_windows_access(repaired, writable=True)


def _read_package(path: Path) -> Package:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = tuple(archive.infolist())
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise CacheRestoreError(f"ZIP contains duplicate part names: {path}")
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise CacheRestoreError(
                    f"Workbook expands to {total_size:,} bytes, above the "
                    f"{MAX_UNCOMPRESSED_BYTES:,}-byte safety limit: {path}"
                )
            entries = {info.filename: archive.read(info) for info in infos}
            comment = archive.comment
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, CacheRestoreError):
            raise
        raise CacheRestoreError(f"Cannot read XLSX package {path}: {exc}") from exc

    for required_part in (WORKBOOK_PART, WORKBOOK_RELS_PART):
        if required_part not in entries:
            raise CacheRestoreError(
                f"Required OOXML part {required_part!r} is missing from {path}"
            )
    return Package(infos=infos, entries=entries, comment=comment)


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _root_namespace_declarations(data: bytes) -> tuple[tuple[str, str], ...]:
    declarations: list[tuple[str, str]] = []
    try:
        iterator = ET.iterparse(io.BytesIO(data), events=("start-ns", "start"))
        for event, value in iterator:
            if event == "start-ns":
                prefix, uri = value
                declarations.append((prefix or "", uri))
            else:
                break
    except ET.ParseError as exc:
        raise CacheRestoreError(f"Invalid OOXML XML: {exc}") from exc
    return tuple(declarations)


def _leading_xml_bytes(data: bytes) -> bytes:
    match = re.match(
        rb"(?:\xef\xbb\xbf)?\s*(?:<\?xml\s+[^?]*\?>\s*)?",
        data,
        flags=re.DOTALL,
    )
    return match.group(0) if match else b""


def _parse_xml(data: bytes, part_name: str) -> XmlDocument:
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise CacheRestoreError(f"DTD/entity declarations are not allowed in {part_name}")
    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        root = ET.fromstring(data, parser=parser)
    except ET.ParseError as exc:
        raise CacheRestoreError(f"Invalid XML in {part_name}: {exc}") from exc
    return XmlDocument(
        root=root,
        leading_bytes=_leading_xml_bytes(data),
        root_namespaces=_root_namespace_declarations(data),
    )


def _ensure_root_namespaces(
    serialized_root: bytes, declarations: Iterable[tuple[str, str]]
) -> bytes:
    tag_end = serialized_root.find(b">")
    if tag_end < 0:
        raise CacheRestoreError("Serialized XML root has no closing angle bracket")
    start_tag = serialized_root[: tag_end + 1]
    additions: list[bytes] = []
    for prefix, uri in declarations:
        if prefix == "xml":
            continue
        attribute = "xmlns" if not prefix else f"xmlns:{prefix}"
        pattern = rb"\s" + re.escape(attribute.encode("utf-8")) + rb"\s*="
        if re.search(pattern, start_tag):
            continue
        additions.append(f" {attribute}={quoteattr(uri)}".encode("utf-8"))
    if not additions:
        return serialized_root
    return serialized_root[:tag_end] + b"".join(additions) + serialized_root[tag_end:]


def _serialize_xml(document: XmlDocument) -> bytes:
    for prefix, uri in document.root_namespaces:
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            # Reserved auto-generated prefixes are still emitted with a valid
            # namespace by ElementTree; original declarations are re-added below.
            pass
    serialized = ET.tostring(
        document.root,
        encoding="utf-8",
        short_empty_elements=True,
    )
    serialized = _ensure_root_namespaces(serialized, document.root_namespaces)
    return document.leading_bytes + serialized


def _relationship_id(element: ET.Element) -> str | None:
    for name, value in element.attrib.items():
        if _local_name(name).casefold() == "id":
            return value
    return None


def _resolve_relationship_target(target: str) -> str:
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(WORKBOOK_PART), target)
        )
    if resolved == ".." or resolved.startswith("../"):
        raise CacheRestoreError(f"Unsafe workbook relationship target: {target!r}")
    return resolved


def _sheet_part_map(entries: dict[str, bytes]) -> dict[str, str]:
    workbook = _parse_xml(entries[WORKBOOK_PART], WORKBOOK_PART).root
    relationships = _parse_xml(
        entries[WORKBOOK_RELS_PART], WORKBOOK_RELS_PART
    ).root
    relation_map: dict[str, tuple[str, str]] = {}
    for relation in relationships.iter():
        if _local_name(relation.tag) != "Relationship":
            continue
        relation_id = relation.attrib.get("Id")
        target = relation.attrib.get("Target")
        relation_type = relation.attrib.get("Type", "")
        if relation_id and target:
            relation_map[relation_id] = (target, relation_type)

    result: dict[str, str] = {}
    for sheet in workbook.iter():
        if _local_name(sheet.tag) != "sheet":
            continue
        name = sheet.attrib.get("name")
        relation_id = _relationship_id(sheet)
        if not name or not relation_id or relation_id not in relation_map:
            raise CacheRestoreError("Workbook contains an unresolved sheet relationship")
        target, relation_type = relation_map[relation_id]
        if not relation_type.rstrip("/").endswith("/worksheet"):
            continue
        if name in result:
            raise CacheRestoreError(f"Workbook contains duplicate sheet name {name!r}")
        part_name = _resolve_relationship_target(target)
        if part_name not in entries:
            raise CacheRestoreError(
                f"Worksheet part {part_name!r} for {name!r} is missing"
            )
        result[name] = part_name
    return result


def _formula_child(cell: ET.Element) -> ET.Element | None:
    formulas = [child for child in cell if _local_name(child.tag) == "f"]
    if len(formulas) > 1:
        raise CacheRestoreError(
            f"Cell {cell.attrib.get('r', '<unknown>')} contains multiple formula nodes"
        )
    return formulas[0] if formulas else None


def _is_cache_formula(formula: ET.Element | None) -> bool:
    """Return true for a real formula/master, not an empty spill follower.

    Excel can materialize dynamic-array followers as ``<f ca="1"/>`` even
    though those cells have no independent formula in the untouched workbook.
    Formula text identifies an ordinary/master formula; ``ref`` identifies a
    range master even if its text is empty.  Empty shared/spill followers are
    deliberately excluded and left structurally untouched.
    """

    if formula is None:
        return False
    if (formula.text or "").strip():
        return True
    return bool(formula.attrib.get("ref"))


def _value_child(cell: ET.Element) -> ET.Element | None:
    values = [child for child in cell if _local_name(child.tag) == "v"]
    if len(values) > 1:
        raise CacheRestoreError(
            f"Cell {cell.attrib.get('r', '<unknown>')} contains multiple cached values"
        )
    return values[0] if values else None


def _cell_index(root: ET.Element, sheet_name: str) -> dict[str, ET.Element]:
    cells: dict[str, ET.Element] = {}
    for cell in root.iter():
        if _local_name(cell.tag) != "c":
            continue
        reference = cell.attrib.get("r")
        if not reference:
            raise CacheRestoreError(f"A cell on {sheet_name!r} has no reference")
        if reference in cells:
            raise CacheRestoreError(
                f"Worksheet {sheet_name!r} contains duplicate cell {reference}"
            )
        cells[reference] = cell
    return cells


def _cell_coordinates(reference: str) -> tuple[str, int]:
    match = CELL_REFERENCE_RE.fullmatch(reference)
    if not match:
        raise CacheRestoreError(f"Unsupported cell reference: {reference!r}")
    return match.group(1).upper(), int(match.group(2))


def _is_in_restore_scope(sheet_name: str, reference: str) -> bool:
    if sheet_name in GUARD_WRAPPED_SHEETS:
        return True
    column, row = _cell_coordinates(reference)
    if sheet_name == SGD_SHEET:
        return row <= 555
    if sheet_name == USD_SHEET:
        if column == "K" and 8 <= row <= 30:
            return False
        return row <= 597
    return False


def _canonical_element(element: ET.Element) -> Any:
    tag = element.tag if isinstance(element.tag, str) else repr(element.tag)
    return (
        tag,
        tuple(sorted(element.attrib.items())),
        element.text or "",
        tuple(_canonical_element(child) for child in element),
    )


def _canonical_non_cache_cell(cell: ET.Element) -> Any:
    tag = cell.tag if isinstance(cell.tag, str) else repr(cell.tag)
    attributes = tuple(
        sorted((name, value) for name, value in cell.attrib.items() if name != "t")
    )
    children = tuple(
        _canonical_element(child)
        for child in cell
        if _local_name(child.tag) != "v"
    )
    return (tag, attributes, cell.text or "", children)


def _workbook_cell_states(entries: dict[str, bytes]) -> dict[tuple[str, str], CellState]:
    states: dict[tuple[str, str], CellState] = {}
    for sheet_name, part_name in _sheet_part_map(entries).items():
        root = _parse_xml(entries[part_name], part_name).root
        for reference, cell in _cell_index(root, sheet_name).items():
            formula = _formula_child(cell)
            key = (sheet_name, reference)
            states[key] = CellState(
                is_formula=formula is not None,
                formula=_canonical_element(formula) if formula is not None else None,
                style=cell.attrib.get("s"),
                full_cell=_canonical_element(cell),
                non_cache_cell=_canonical_non_cache_cell(cell),
            )
    return states


def _copy_cached_type_and_value(
    source_cell: ET.Element, repaired_cell: ET.Element
) -> tuple[bool, bool, bool]:
    source_type = source_cell.attrib.get("t")
    repaired_type = repaired_cell.attrib.get("t")
    source_value = _value_child(source_cell)
    repaired_value = _value_child(repaired_cell)
    before_cache = (
        repaired_type,
        _canonical_element(repaired_value) if repaired_value is not None else None,
    )

    if source_type is None:
        repaired_cell.attrib.pop("t", None)
    else:
        repaired_cell.attrib["t"] = source_type

    if source_value is None:
        if repaired_value is not None:
            repaired_cell.remove(repaired_value)
    else:
        cell_namespace = ""
        if isinstance(repaired_cell.tag, str) and repaired_cell.tag.startswith("{"):
            cell_namespace = repaired_cell.tag.split("}", 1)[0] + "}"
        replacement_value = ET.Element(
            f"{cell_namespace}v", dict(source_value.attrib)
        )
        replacement_value.text = source_value.text
        for child in source_value:
            replacement_value.append(copy.deepcopy(child))

        if repaired_value is not None:
            child_index = list(repaired_cell).index(repaired_value)
            replacement_value.tail = repaired_value.tail
            repaired_cell.remove(repaired_value)
            repaired_cell.insert(child_index, replacement_value)
        else:
            formula = _formula_child(repaired_cell)
            if formula is None:
                raise CacheRestoreError("Attempted to cache a non-formula cell")
            child_index = list(repaired_cell).index(formula) + 1
            repaired_cell.insert(child_index, replacement_value)

    after_value = _value_child(repaired_cell)
    after_cache = (
        repaired_cell.attrib.get("t"),
        _canonical_element(after_value) if after_value is not None else None,
    )
    return (
        before_cache != after_cache,
        source_type != repaired_type,
        source_value is not None,
    )


def _cached_value_payload(cell: ET.Element) -> Any:
    value = _value_child(cell)
    if value is None:
        return None
    return (
        tuple(sorted(value.attrib.items())),
        value.text or "",
        tuple(_canonical_element(child) for child in value),
    )


def _validate_target_caches_match_source(
    source_entries: dict[str, bytes],
    after_entries: dict[str, bytes],
    targeted_cells: set[tuple[str, str]],
) -> None:
    source_parts = _sheet_part_map(source_entries)
    after_parts = _sheet_part_map(after_entries)
    source_cells_by_sheet: dict[str, dict[str, ET.Element]] = {}
    after_cells_by_sheet: dict[str, dict[str, ET.Element]] = {}
    mismatches: list[str] = []
    for sheet_name, reference in sorted(targeted_cells):
        if sheet_name not in source_cells_by_sheet:
            source_root = _parse_xml(
                source_entries[source_parts[sheet_name]], source_parts[sheet_name]
            ).root
            after_root = _parse_xml(
                after_entries[after_parts[sheet_name]], after_parts[sheet_name]
            ).root
            source_cells_by_sheet[sheet_name] = _cell_index(source_root, sheet_name)
            after_cells_by_sheet[sheet_name] = _cell_index(after_root, sheet_name)
        source_cell = source_cells_by_sheet[sheet_name].get(reference)
        after_cell = after_cells_by_sheet[sheet_name].get(reference)
        if source_cell is None or after_cell is None:
            mismatches.append(f"{sheet_name}!{reference}")
            continue
        if (
            source_cell.attrib.get("t") != after_cell.attrib.get("t")
            or _cached_value_payload(source_cell) != _cached_value_payload(after_cell)
        ):
            mismatches.append(f"{sheet_name}!{reference}")
    if mismatches:
        raise CacheRestoreError(
            "Restored cache differs from source at: " + ", ".join(mismatches[:12])
        )


def _merge_sheet_caches(
    source: Package,
    repaired: Package,
) -> tuple[dict[str, bytes], MergeReport]:
    source_sheets = _sheet_part_map(source.entries)
    repaired_sheets = _sheet_part_map(repaired.entries)
    missing_source = sorted(REQUIRED_SHEETS - source_sheets.keys())
    missing_repaired = sorted(REQUIRED_SHEETS - repaired_sheets.keys())
    if missing_source or missing_repaired:
        raise CacheRestoreError(
            "Required worksheet missing; "
            f"source={missing_source or 'none'}, repaired={missing_repaired or 'none'}"
        )

    replacements: dict[str, bytes] = {}
    report = MergeReport()
    for sheet_name in sorted(REQUIRED_SHEETS):
        source_part = source_sheets[sheet_name]
        repaired_part = repaired_sheets[sheet_name]
        source_document = _parse_xml(source.entries[source_part], source_part)
        repaired_document = _parse_xml(repaired.entries[repaired_part], repaired_part)
        source_cells = _cell_index(source_document.root, sheet_name)
        repaired_cells = _cell_index(repaired_document.root, sheet_name)
        stats = SheetStats()
        report.sheets[sheet_name] = stats

        for reference, repaired_cell in repaired_cells.items():
            repaired_formula = _formula_child(repaired_cell)
            if repaired_formula is None or not _is_in_restore_scope(sheet_name, reference):
                continue
            if not _is_cache_formula(repaired_formula):
                stats.empty_formula_followers_skipped += 1
                continue
            source_cell = source_cells.get(reference)
            if source_cell is None:
                stats.repaired_only_formulas_skipped += 1
                continue
            source_formula = _formula_child(source_cell)
            if source_formula is None:
                stats.repaired_only_formulas_skipped += 1
                continue
            if not _is_cache_formula(source_formula):
                stats.source_empty_formulas_skipped += 1
                continue
            stats.selected_formula_cells += 1
            report.targeted_cells.add((sheet_name, reference))
            changed, type_changed, has_value = _copy_cached_type_and_value(
                source_cell, repaired_cell
            )
            stats.changed_cells += int(changed)
            stats.type_changes += int(type_changed)
            if has_value:
                stats.cache_values_copied += 1
            else:
                stats.absent_cache_values_copied += 1

        for reference, source_cell in source_cells.items():
            if (
                _is_cache_formula(_formula_child(source_cell))
                and _is_in_restore_scope(sheet_name, reference)
                and (
                    reference not in repaired_cells
                    or not _is_cache_formula(_formula_child(repaired_cells[reference]))
                )
            ):
                stats.source_only_formula_cells += 1

        if stats.changed_cells:
            replacements[repaired_part] = _serialize_xml(repaired_document)

    return replacements, report


def _find_start_tag(data: bytes, local_name: bytes) -> tuple[int, int] | None:
    pattern = re.compile(
        rb"<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?"
        + re.escape(local_name)
        + rb"(?=[\s/>])"
    )
    matches = list(pattern.finditer(data))
    if not matches:
        return None
    if len(matches) > 1:
        raise CacheRestoreError(
            f"Workbook XML contains multiple {local_name.decode('ascii')} elements"
        )
    start = matches[0].start()
    quote: int | None = None
    for index in range(matches[0].end(), len(data)):
        byte = data[index]
        if quote is None and byte in (ord("'"), ord('"')):
            quote = byte
        elif quote is not None and byte == quote:
            quote = None
        elif quote is None and byte == ord(">"):
            return start, index + 1
    raise CacheRestoreError(
        f"Unterminated {local_name.decode('ascii')} start tag in workbook XML"
    )


def _set_start_tag_attribute(tag: bytes, name: bytes, value: bytes) -> bytes:
    pattern = re.compile(
        rb"\s"
        + re.escape(name)
        + rb"\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
        flags=re.DOTALL,
    )
    match = pattern.search(tag)
    if match:
        return tag[: match.start("value")] + value + tag[match.end("value") :]
    closing_index = tag.rfind(b"/>")
    if closing_index < 0:
        closing_index = tag.rfind(b">")
    if closing_index < 0:
        raise CacheRestoreError("Malformed XML start tag")
    return (
        tag[:closing_index]
        + b" "
        + name
        + b'="'
        + value
        + b'"'
        + tag[closing_index:]
    )


def _calc_properties(workbook_xml: bytes) -> dict[str, str | None]:
    root = _parse_xml(workbook_xml, WORKBOOK_PART).root
    calc_nodes = [node for node in root.iter() if _local_name(node.tag) == "calcPr"]
    if len(calc_nodes) > 1:
        raise CacheRestoreError("Workbook contains multiple calcPr nodes")
    if not calc_nodes:
        return {
            "calcMode": None,
            "forceFullCalc": None,
            "fullCalcOnLoad": None,
        }
    node = calc_nodes[0]
    return {
        "calcMode": node.attrib.get("calcMode"),
        "forceFullCalc": node.attrib.get("forceFullCalc"),
        "fullCalcOnLoad": node.attrib.get("fullCalcOnLoad"),
    }


def _set_manual_calc_properties(workbook_xml: bytes) -> tuple[bytes, dict[str, str | None]]:
    old_properties = _calc_properties(workbook_xml)
    bounds = _find_start_tag(workbook_xml, b"calcPr")
    if bounds is None:
        closing = re.search(
            rb"</(?P<prefix>[A-Za-z_][A-Za-z0-9_.-]*:)?workbook\s*>",
            workbook_xml,
        )
        if closing is None:
            raise CacheRestoreError("Cannot find closing workbook tag")
        prefix = closing.group("prefix") or b""
        node = (
            b"<"
            + prefix
            + b'calcPr calcMode="manual" forceFullCalc="0" '
            + b'fullCalcOnLoad="0"/>'
        )
        updated = workbook_xml[: closing.start()] + node + workbook_xml[closing.start() :]
    else:
        start, end = bounds
        tag = workbook_xml[start:end]
        tag = _set_start_tag_attribute(tag, b"calcMode", b"manual")
        tag = _set_start_tag_attribute(tag, b"forceFullCalc", b"0")
        tag = _set_start_tag_attribute(tag, b"fullCalcOnLoad", b"0")
        updated = workbook_xml[:start] + tag + workbook_xml[end:]

    expected = {
        "calcMode": "manual",
        "forceFullCalc": "0",
        "fullCalcOnLoad": "0",
    }
    if _calc_properties(updated) != expected:
        raise CacheRestoreError("Failed to set the requested workbook calculation flags")
    return updated, old_properties


def _validate_repaired_integrity(
    before_entries: dict[str, bytes],
    after_entries: dict[str, bytes],
    targeted_cells: set[tuple[str, str]],
) -> None:
    before = _workbook_cell_states(before_entries)
    after = _workbook_cell_states(after_entries)
    if before.keys() != after.keys():
        removed = sorted(before.keys() - after.keys())[:10]
        added = sorted(after.keys() - before.keys())[:10]
        raise CacheRestoreError(
            f"Cell set changed during cache merge; removed={removed}, added={added}"
        )

    formula_changes: list[str] = []
    style_changes: list[str] = []
    non_formula_changes: list[str] = []
    unexpected_formula_cell_changes: list[str] = []
    targeted_non_cache_changes: list[str] = []
    for key, before_state in before.items():
        after_state = after[key]
        label = f"{key[0]}!{key[1]}"
        if (
            before_state.is_formula != after_state.is_formula
            or before_state.formula != after_state.formula
        ):
            formula_changes.append(label)
        if before_state.style != after_state.style:
            style_changes.append(label)
        if not before_state.is_formula:
            if before_state.full_cell != after_state.full_cell:
                non_formula_changes.append(label)
        elif key in targeted_cells:
            if before_state.non_cache_cell != after_state.non_cache_cell:
                targeted_non_cache_changes.append(label)
        elif before_state.full_cell != after_state.full_cell:
            unexpected_formula_cell_changes.append(label)

    failures = {
        "formula text/metadata": formula_changes,
        "style": style_changes,
        "non-formula cell": non_formula_changes,
        "non-cache portion of targeted formula cell": targeted_non_cache_changes,
        "untargeted formula cell": unexpected_formula_cell_changes,
    }
    messages = []
    for category, labels in failures.items():
        if labels:
            messages.append(f"{category}: {', '.join(labels[:10])}")
    if messages:
        raise CacheRestoreError(
            "Repaired workbook integrity verification failed; " + "; ".join(messages)
        )


def _build_modified_entries(
    source: Package, repaired: Package
) -> tuple[dict[str, bytes], MergeReport]:
    replacements, report = _merge_sheet_caches(source, repaired)
    workbook_xml, old_properties = _set_manual_calc_properties(
        repaired.entries[WORKBOOK_PART]
    )
    report.old_calc_properties = old_properties
    if workbook_xml != repaired.entries[WORKBOOK_PART]:
        replacements[WORKBOOK_PART] = workbook_xml
    report.replacement_parts = len(replacements)

    modified_entries = dict(repaired.entries)
    modified_entries.update(replacements)
    _validate_repaired_integrity(
        repaired.entries, modified_entries, report.targeted_cells
    )
    _validate_target_caches_match_source(
        source.entries, modified_entries, report.targeted_cells
    )
    expected_calc = {
        "calcMode": "manual",
        "forceFullCalc": "0",
        "fullCalcOnLoad": "0",
    }
    if _calc_properties(modified_entries[WORKBOOK_PART]) != expected_calc:
        raise CacheRestoreError("Calculation properties failed final in-memory validation")
    return modified_entries, report


def _write_temp_package(
    repaired: Package,
    modified_entries: dict[str, bytes],
    destination: Path,
) -> Path:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.restore-cache-",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", allowZip64=True) as archive:
            archive.comment = repaired.comment
            for info in repaired.infos:
                archive.writestr(info, modified_entries[info.filename])
        destination_mode = stat.S_IMODE(destination.stat().st_mode)
        os.chmod(temp_path, destination_mode)
        with temp_path.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _resolve_backup_path(path_text: str | None, repaired: Path) -> Path:
    if path_text:
        backup = Path(path_text).expanduser().resolve(strict=False)
    else:
        backup = repaired.with_name(f"{repaired.stem}.pre-cache-restore.xlsx")
    if backup == repaired or os.path.exists(backup) and os.path.samefile(backup, repaired):
        raise CacheRestoreError("Backup path resolves to the repaired workbook")
    if backup.suffix.casefold() != ".xlsx":
        raise CacheRestoreError(f"Backup path must end in .xlsx: {backup}")
    if not backup.parent.is_dir():
        raise CacheRestoreError(f"Backup directory does not exist: {backup.parent}")
    if backup.exists() or backup.is_symlink():
        raise CacheRestoreError(
            f"Backup path already exists; choose a new --backup path: {backup}"
        )
    if os.stat(backup.parent).st_dev != os.stat(repaired.parent).st_dev:
        raise CacheRestoreError(
            "Backup must be on the same volume as the repaired workbook"
        )
    return backup


def _create_atomic_backup(
    repaired: Path, backup: Path, expected_hash: str
) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{backup.name}.building-",
        suffix=".tmp",
        dir=backup.parent,
    )
    os.close(descriptor)
    temp_backup = Path(temp_name)
    published = False
    try:
        shutil.copyfile(repaired, temp_backup)
        os.chmod(temp_backup, stat.S_IMODE(repaired.stat().st_mode))
        with temp_backup.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        if _sha256(temp_backup) != expected_hash:
            raise CacheRestoreError("Pre-restore backup hash does not match repaired input")
        # On Windows os.rename is atomic and refuses to overwrite an existing
        # destination, so a concurrent process cannot replace an older backup.
        os.rename(temp_backup, backup)
        published = True
        if _sha256(backup) != expected_hash:
            raise CacheRestoreError("Published pre-restore backup failed hash validation")
    finally:
        if not published:
            temp_backup.unlink(missing_ok=True)


def _validate_temp_package(
    temp_path: Path,
    repaired: Package,
    modified_entries: dict[str, bytes],
    targeted_cells: set[tuple[str, str]],
) -> Package:
    temp_package = _read_package(temp_path)
    if tuple(info.filename for info in temp_package.infos) != tuple(
        info.filename for info in repaired.infos
    ):
        raise CacheRestoreError("Temporary XLSX changed ZIP part ordering or membership")
    for part_name, expected_data in modified_entries.items():
        if temp_package.entries.get(part_name) != expected_data:
            raise CacheRestoreError(
                f"Temporary XLSX part differs after ZIP write: {part_name}"
            )
    _validate_repaired_integrity(
        repaired.entries, temp_package.entries, targeted_cells
    )
    expected_calc = {
        "calcMode": "manual",
        "forceFullCalc": "0",
        "fullCalcOnLoad": "0",
    }
    if _calc_properties(temp_package.entries[WORKBOOK_PART]) != expected_calc:
        raise CacheRestoreError("Temporary XLSX has incorrect calculation properties")
    return temp_package


def _print_report(
    *,
    mode: str,
    source: Path,
    repaired: Path,
    source_hash: str,
    repaired_hash_before: str,
    repaired_hash_after: str | None,
    backup: Path,
    report: MergeReport,
) -> None:
    print(f"Mode: {mode}")
    print(f"Source (read-only): {source}")
    print(f"Repaired copy: {repaired}")
    print(f"Pre-restore backup: {backup}")
    print(f"Source SHA-256: {source_hash}")
    print(f"Repaired SHA-256 before: {repaired_hash_before}")
    if repaired_hash_after is not None:
        print(f"Repaired SHA-256 after: {repaired_hash_after}")
    print(
        "calcPr before: "
        + ", ".join(
            f"{name}={value!r}"
            for name, value in report.old_calc_properties.items()
        )
    )
    print("calcPr after: calcMode='manual', forceFullCalc='0', fullCalcOnLoad='0'")
    for sheet_name in sorted(report.sheets):
        stats = report.sheets[sheet_name]
        print(
            f"{sheet_name}: selected={stats.selected_formula_cells}, "
            f"cached_values={stats.cache_values_copied}, "
            f"absent_values={stats.absent_cache_values_copied}, "
            f"changed={stats.changed_cells}, type_changes={stats.type_changes}, "
            f"empty_spill_followers_skipped={stats.empty_formula_followers_skipped}, "
            f"repaired_only_formulas_skipped={stats.repaired_only_formulas_skipped}, "
            f"source_empty_formulas_skipped={stats.source_empty_formulas_skipped}, "
            f"source_only_formulas_preserved={stats.source_only_formula_cells}"
        )
    print(f"OOXML parts replaced: {report.replacement_parts}")
    if mode == "dry-run":
        print("Dry run complete: no files were changed.")
    else:
        print("Apply complete: the repaired copy was atomically replaced.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore selected formula caches from an untouched XLSX into a "
            "repaired copy without changing formulas, styles, or non-formula cells."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Untouched original XLSX; opened read-only and never replaced",
    )
    parser.add_argument(
        "--repaired",
        required=True,
        help="Repaired XLSX copy; modified in place only with --apply",
    )
    parser.add_argument(
        "--backup",
        help=(
            "New same-volume .xlsx backup path. Defaults to "
            "<repaired stem>.pre-cache-restore.xlsx and must not already exist"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the merge in memory without writing (default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Atomically replace the repaired copy after all validation passes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    temp_path: Path | None = None
    try:
        source = _resolve_workbook(args.source, "Source")
        repaired = _resolve_workbook(args.repaired, "Repaired")
        _assert_distinct_files(source, repaired)
        backup = _resolve_backup_path(args.backup, repaired)
        _assert_workbook_files_closed(source, repaired)

        source_hash = _sha256(source)
        repaired_hash_before = _sha256(repaired)
        source_package = _read_package(source)
        repaired_package = _read_package(repaired)
        modified_entries, report = _build_modified_entries(
            source_package, repaired_package
        )

        if _sha256(source) != source_hash:
            raise CacheRestoreError("Source workbook changed during validation")
        if _sha256(repaired) != repaired_hash_before:
            raise CacheRestoreError("Repaired workbook changed during validation")

        if not args.apply:
            _assert_workbook_files_closed(source, repaired)
            if _sha256(source) != source_hash or _sha256(repaired) != repaired_hash_before:
                raise CacheRestoreError("An input workbook changed during the dry run")
            _print_report(
                mode="dry-run",
                source=source,
                repaired=repaired,
                source_hash=source_hash,
                repaired_hash_before=repaired_hash_before,
                repaired_hash_after=None,
                backup=backup,
                report=report,
            )
            return 0

        temp_path = _write_temp_package(
            repaired_package, modified_entries, repaired
        )
        _validate_temp_package(
            temp_path,
            repaired_package,
            modified_entries,
            report.targeted_cells,
        )

        # Recheck immediately before the only destructive operation.  The
        # temporary ZIP is on the same volume, so os.replace is atomic.
        _assert_workbook_files_closed(source, repaired)
        if _sha256(source) != source_hash:
            raise CacheRestoreError("Source workbook changed before atomic replace")
        if _sha256(repaired) != repaired_hash_before:
            raise CacheRestoreError("Repaired workbook changed before atomic replace")
        try:
            _create_atomic_backup(repaired, backup, repaired_hash_before)
            os.replace(temp_path, repaired)
        except OSError as exc:
            raise CacheRestoreError(
                f"Atomic backup/replace failed; any published backup is at "
                f"{backup}: {exc}"
            ) from exc
        temp_path = None

        final_package = _read_package(repaired)
        if final_package.entries != modified_entries:
            raise CacheRestoreError(
                "Final XLSX payload differs from the fully validated temporary package"
            )
        _validate_repaired_integrity(
            repaired_package.entries,
            final_package.entries,
            report.targeted_cells,
        )
        expected_calc = {
            "calcMode": "manual",
            "forceFullCalc": "0",
            "fullCalcOnLoad": "0",
        }
        if _calc_properties(final_package.entries[WORKBOOK_PART]) != expected_calc:
            raise CacheRestoreError("Final workbook calculation flags are incorrect")
        if _sha256(source) != source_hash:
            raise CacheRestoreError("Source workbook changed unexpectedly")
        if _sha256(backup) != repaired_hash_before:
            raise CacheRestoreError("Pre-restore backup changed unexpectedly")

        repaired_hash_after = _sha256(repaired)
        _print_report(
            mode="apply",
            source=source,
            repaired=repaired,
            source_hash=source_hash,
            repaired_hash_before=repaired_hash_before,
            repaired_hash_after=repaired_hash_after,
            backup=backup,
            report=report,
        )
        return 0
    except CacheRestoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
