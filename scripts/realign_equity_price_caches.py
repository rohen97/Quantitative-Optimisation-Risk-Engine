#!/usr/bin/env python3
"""Realign the ten current Equity prices caches from a trusted checkpoint.

This focused OOXML helper copies only cached cell type/value metadata from
``Equity prices!B7:K7`` in a source checkpoint to the same formula cells in a
repaired workbook.  ``A7`` is included automatically only when both workbooks
contain the same nonempty formula there.  Header identity, formula semantics,
styles, and every non-target cell are validated before publication.

The default mode is a dry run.  ``--apply`` creates a same-volume atomic backup
and atomically replaces only the repaired target.  Excel is never automated or
opened by this script.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Reuse the adjacent audited ZIP/XML, locking, hash, integrity, backup, and
# atomic-publication primitives.  Importing it does not execute its CLI.
import restore_formula_caches as xlsx  # noqa: E402


SHEET_NAME = "Equity prices"
HEADER_ROW = 4
PRICE_ROW = 7
PRICE_COLUMNS = tuple("BCDEFGHIJK")
DATE_ANCHOR = "A7"
EXPECTED_HEADERS = (
    "WOLF GR EQUITY",
    "C6L SP Equity",
    "SCI SP EQUITY",
    "CLI SP EQUITY",
    "SATS SP EQUITY",
    "CLAR SP EQUITY",
    "STTF SP EQUITY",
    "SAN FP EQUITY",
    "MUV2 GY EQUITY",
    "BMW GR EQUITY",
)


@dataclass(frozen=True)
class CacheTarget:
    reference: str
    header: str | None
    source_type: str | None
    source_value: str
    target_value_before: str | None


@dataclass
class RealignStats:
    formula_cells_targeted: int = 0
    source_values_present: int = 0
    type_changes: int = 0
    changed_cells: int = 0
    date_anchor_included: bool = False
    date_anchor_skip_reason: str | None = None


def _shared_strings(package: xlsx.Package) -> tuple[str, ...]:
    part_name = "xl/sharedStrings.xml"
    if part_name not in package.entries:
        return ()
    root = xlsx._parse_xml(package.entries[part_name], part_name).root
    values: list[str] = []
    for element in root:
        if xlsx._local_name(element.tag) != "si":
            continue
        values.append(
            "".join(
                descendant.text or ""
                for descendant in element.iter()
                if xlsx._local_name(descendant.tag) == "t"
            )
        )
    return tuple(values)


def _cell_text(
    cell: Any | None,
    shared_strings: tuple[str, ...],
    *,
    label: str,
) -> str | None:
    if cell is None:
        return None
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            descendant.text or ""
            for descendant in cell.iter()
            if xlsx._local_name(descendant.tag) == "t"
        )
    value = xlsx._value_child(cell)
    if value is None:
        return None
    text = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(text)]
        except (ValueError, IndexError) as exc:
            raise xlsx.CacheRestoreError(
                f"Invalid shared-string index at {label}: {text!r}"
            ) from exc
    if cell_type == "e":
        raise xlsx.CacheRestoreError(
            f"Cannot use Excel error cache as text at {label}: {text!r}"
        )
    return text


def _worksheet_cells(
    package: xlsx.Package,
) -> tuple[str, Any, dict[str, Any]]:
    sheet_parts = xlsx._sheet_part_map(package.entries)
    if SHEET_NAME not in sheet_parts:
        raise xlsx.CacheRestoreError(f"Worksheet is missing: {SHEET_NAME}")
    part_name = sheet_parts[SHEET_NAME]
    document = xlsx._parse_xml(package.entries[part_name], part_name)
    cells = xlsx._cell_index(document.root, SHEET_NAME)
    return part_name, document, cells


def _formula_text(cell: Any, *, label: str) -> str:
    formula = xlsx._formula_child(cell)
    if formula is None or not (formula.text or "").strip():
        raise xlsx.CacheRestoreError(
            f"Expected a nonempty formula cell at {label}"
        )
    return (formula.text or "").strip()


def _cached_text(cell: Any) -> str | None:
    value = xlsx._value_child(cell)
    return None if value is None else value.text or ""


def _require_numeric_source_cache(cell: Any, *, label: str) -> str:
    if cell.attrib.get("t") in {"s", "str", "inlineStr", "e", "b"}:
        raise xlsx.CacheRestoreError(
            f"Source cache is not numeric at {label}: type={cell.attrib.get('t')!r}"
        )
    text = _cached_text(cell)
    if text is None:
        raise xlsx.CacheRestoreError(f"Source cache is absent at {label}")
    try:
        numeric = float(text)
    except ValueError as exc:
        raise xlsx.CacheRestoreError(
            f"Source cache is not numeric at {label}: {text!r}"
        ) from exc
    if not math.isfinite(numeric):
        raise xlsx.CacheRestoreError(
            f"Source cache is not finite at {label}: {text!r}"
        )
    return text


def _assert_headers_identical(
    source: xlsx.Package,
    repaired: xlsx.Package,
    source_cells: dict[str, Any],
    repaired_cells: dict[str, Any],
) -> tuple[str, ...]:
    source_strings = _shared_strings(source)
    repaired_strings = _shared_strings(repaired)
    source_headers: list[str] = []
    repaired_headers: list[str] = []
    for column in PRICE_COLUMNS:
        reference = f"{column}{HEADER_ROW}"
        source_header = _cell_text(
            source_cells.get(reference),
            source_strings,
            label=f"source {SHEET_NAME}!{reference}",
        )
        repaired_header = _cell_text(
            repaired_cells.get(reference),
            repaired_strings,
            label=f"repaired {SHEET_NAME}!{reference}",
        )
        if source_header is None or repaired_header is None:
            raise xlsx.CacheRestoreError(
                f"Blank equity header at {SHEET_NAME}!{reference}"
            )
        if source_header != repaired_header:
            raise xlsx.CacheRestoreError(
                f"Header identity mismatch at {SHEET_NAME}!{reference}: "
                f"source={source_header!r}, repaired={repaired_header!r}"
            )
        source_headers.append(source_header)
        repaired_headers.append(repaired_header)

    headers = tuple(source_headers)
    if headers != EXPECTED_HEADERS:
        raise xlsx.CacheRestoreError(
            "Unexpected Equity prices B4:K4 header order: " + repr(headers)
        )
    if len(set(headers)) != len(headers):
        raise xlsx.CacheRestoreError("Equity prices B4:K4 contains duplicate headers")
    if tuple(repaired_headers) != headers:
        raise xlsx.CacheRestoreError("Internal header identity validation failed")
    return headers


def _assert_cache_formula_compatible(
    source_cell: Any,
    repaired_cell: Any,
    *,
    label: str,
) -> None:
    source_formula = _formula_text(source_cell, label=f"source {label}")
    repaired_formula = _formula_text(repaired_cell, label=f"repaired {label}")
    if source_formula != repaired_formula:
        raise xlsx.CacheRestoreError(
            f"Formula text mismatch at {label}; refusing to transfer its cache"
        )
    if source_cell.attrib.get("s") != repaired_cell.attrib.get("s"):
        raise xlsx.CacheRestoreError(
            f"Style mismatch at {label}; refusing to transfer its cache"
        )


def _validate_target_caches(
    source: xlsx.Package,
    after_entries: dict[str, bytes],
    references: tuple[str, ...],
) -> None:
    source_part, _, source_cells = _worksheet_cells(source)
    del source_part
    after_package = xlsx.Package(infos=(), entries=after_entries, comment=b"")
    _, _, after_cells = _worksheet_cells(after_package)
    mismatches: list[str] = []
    for reference in references:
        source_cell = source_cells.get(reference)
        after_cell = after_cells.get(reference)
        if source_cell is None or after_cell is None:
            mismatches.append(reference)
            continue
        if (
            source_cell.attrib.get("t") != after_cell.attrib.get("t")
            or xlsx._cached_value_payload(source_cell)
            != xlsx._cached_value_payload(after_cell)
        ):
            mismatches.append(reference)
    if mismatches:
        raise xlsx.CacheRestoreError(
            "Equity price caches do not match the checkpoint at: "
            + ", ".join(mismatches)
        )


def _build_modified_entries(
    source: xlsx.Package,
    repaired: xlsx.Package,
) -> tuple[dict[str, bytes], tuple[str, ...], tuple[str, ...], list[CacheTarget], RealignStats]:
    source_part, _, source_cells = _worksheet_cells(source)
    repaired_part, repaired_document, repaired_cells = _worksheet_cells(repaired)
    del source_part
    headers = _assert_headers_identical(
        source, repaired, source_cells, repaired_cells
    )

    references: list[str] = []
    targets: list[CacheTarget] = []
    stats = RealignStats()

    for column, header in zip(PRICE_COLUMNS, headers):
        reference = f"{column}{PRICE_ROW}"
        source_cell = source_cells.get(reference)
        repaired_cell = repaired_cells.get(reference)
        if source_cell is None or repaired_cell is None:
            raise xlsx.CacheRestoreError(
                f"Required cache cell is missing: {SHEET_NAME}!{reference}"
            )
        _assert_cache_formula_compatible(
            source_cell, repaired_cell, label=f"{SHEET_NAME}!{reference}"
        )
        source_value = _require_numeric_source_cache(
            source_cell, label=f"source {SHEET_NAME}!{reference}"
        )
        target_value_before = _cached_text(repaired_cell)
        changed, type_changed, has_value = xlsx._copy_cached_type_and_value(
            source_cell, repaired_cell
        )
        references.append(reference)
        targets.append(
            CacheTarget(
                reference=reference,
                header=header,
                source_type=source_cell.attrib.get("t"),
                source_value=source_value,
                target_value_before=target_value_before,
            )
        )
        stats.formula_cells_targeted += 1
        stats.source_values_present += int(has_value)
        stats.type_changes += int(type_changed)
        stats.changed_cells += int(changed)

    source_date = source_cells.get(DATE_ANCHOR)
    repaired_date = repaired_cells.get(DATE_ANCHOR)
    if source_date is None or repaired_date is None:
        stats.date_anchor_skip_reason = "A7 is absent in one workbook"
    else:
        source_date_formula = xlsx._formula_child(source_date)
        repaired_date_formula = xlsx._formula_child(repaired_date)
        source_formula_text = (
            "" if source_date_formula is None else (source_date_formula.text or "").strip()
        )
        repaired_formula_text = (
            "" if repaired_date_formula is None else (repaired_date_formula.text or "").strip()
        )
        if not source_formula_text or source_formula_text != repaired_formula_text:
            stats.date_anchor_skip_reason = "A7 formulas are absent or differ"
        elif source_date.attrib.get("s") != repaired_date.attrib.get("s"):
            stats.date_anchor_skip_reason = "A7 styles differ"
        else:
            source_value = _require_numeric_source_cache(
                source_date, label=f"source {SHEET_NAME}!{DATE_ANCHOR}"
            )
            target_value_before = _cached_text(repaired_date)
            changed, type_changed, has_value = xlsx._copy_cached_type_and_value(
                source_date, repaired_date
            )
            references.append(DATE_ANCHOR)
            targets.append(
                CacheTarget(
                    reference=DATE_ANCHOR,
                    header=None,
                    source_type=source_date.attrib.get("t"),
                    source_value=source_value,
                    target_value_before=target_value_before,
                )
            )
            stats.date_anchor_included = True
            stats.formula_cells_targeted += 1
            stats.source_values_present += int(has_value)
            stats.type_changes += int(type_changed)
            stats.changed_cells += int(changed)

    modified_entries = dict(repaired.entries)
    if stats.changed_cells:
        modified_entries[repaired_part] = xlsx._serialize_xml(repaired_document)

    targeted_keys = {(SHEET_NAME, reference) for reference in references}
    xlsx._validate_repaired_integrity(
        repaired.entries, modified_entries, targeted_keys
    )
    _validate_target_caches(source, modified_entries, tuple(references))
    return modified_entries, headers, tuple(references), targets, stats


def _default_backup_path(repaired: Path) -> Path:
    return repaired.with_name(f"{repaired.stem}.pre-equity-cache-realign.xlsx")


def _print_report(
    *,
    mode: str,
    source: Path,
    repaired: Path,
    backup: Path,
    source_hash: str,
    repaired_hash_before: str,
    repaired_hash_after: str | None,
    headers: tuple[str, ...],
    references: tuple[str, ...],
    targets: list[CacheTarget],
    stats: RealignStats,
    backup_created: bool,
) -> None:
    print(f"Mode: {mode}")
    print(f"Checkpoint source (read-only): {source}")
    print(f"Repaired target: {repaired}")
    print(
        f"Atomic backup: {backup} "
        f"({'created' if backup_created else 'planned/not created'})"
    )
    print(f"Source SHA-256: {source_hash}")
    print(f"Repaired SHA-256 before: {repaired_hash_before}")
    if repaired_hash_after is not None:
        print(f"Repaired SHA-256 after: {repaired_hash_after}")
    print(f"Validated header order ({len(headers)}): {headers!r}")
    print(f"Target cache references: {', '.join(references)}")
    for target in targets:
        label = target.reference if target.header is None else f"{target.reference} {target.header!r}"
        print(
            f"{label}: target_before={target.target_value_before!r}; "
            f"checkpoint={target.source_value!r}; type={target.source_type!r}"
        )
    print(f"Formula cache cells targeted: {stats.formula_cells_targeted}")
    print(f"Source numeric caches present: {stats.source_values_present}")
    print(f"Cell type changes: {stats.type_changes}")
    print(f"Changed target cache cells: {stats.changed_cells}")
    print(f"A7 date anchor included: {stats.date_anchor_included}")
    if stats.date_anchor_skip_reason:
        print(f"A7 date anchor skip reason: {stats.date_anchor_skip_reason}")
    print("Header/formula/style/non-target invariants: passed")
    if mode == "dry-run":
        print("Dry run complete: no files were changed.")
    elif stats.changed_cells:
        print("Apply complete: backup and repaired target were atomically published.")
    else:
        print("Apply complete: caches were already aligned; no files were changed.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy only Equity prices B7:K7 cached t/v metadata from a trusted "
            "checkpoint into a repaired XLSX. A7 is included only when its "
            "formula and style agree. The default is a non-writing dry run."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Trusted pre-cache-restore XLSX checkpoint; never written",
    )
    parser.add_argument(
        "--repaired",
        required=True,
        help="Repaired target XLSX; modified in place only with --apply",
    )
    parser.add_argument(
        "--backup",
        help=(
            "New same-volume .xlsx backup path. Defaults to "
            "<repaired stem>.pre-equity-cache-realign.xlsx"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate in memory without writing (default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Create an atomic backup and atomically replace the repaired target",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    temp_path: Path | None = None
    try:
        source = xlsx._resolve_workbook(args.source, "Checkpoint source")
        repaired = xlsx._resolve_workbook(args.repaired, "Repaired target")
        xlsx._assert_distinct_files(source, repaired)
        backup_text = args.backup or str(_default_backup_path(repaired))
        backup = xlsx._resolve_backup_path(backup_text, repaired)
        xlsx._assert_workbook_files_closed(source, repaired)

        source_hash = xlsx._sha256(source)
        repaired_hash_before = xlsx._sha256(repaired)
        source_package = xlsx._read_package(source)
        repaired_package = xlsx._read_package(repaired)
        modified_entries, headers, references, targets, stats = _build_modified_entries(
            source_package, repaired_package
        )

        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Checkpoint source changed during validation")
        if xlsx._sha256(repaired) != repaired_hash_before:
            raise xlsx.CacheRestoreError("Repaired target changed during validation")

        if not args.apply:
            xlsx._assert_workbook_files_closed(source, repaired)
            if xlsx._sha256(source) != source_hash:
                raise xlsx.CacheRestoreError("Checkpoint changed during dry run")
            if xlsx._sha256(repaired) != repaired_hash_before:
                raise xlsx.CacheRestoreError("Repaired target changed during dry run")
            _print_report(
                mode="dry-run",
                source=source,
                repaired=repaired,
                backup=backup,
                source_hash=source_hash,
                repaired_hash_before=repaired_hash_before,
                repaired_hash_after=None,
                headers=headers,
                references=references,
                targets=targets,
                stats=stats,
                backup_created=False,
            )
            return 0

        if not stats.changed_cells:
            _print_report(
                mode="apply",
                source=source,
                repaired=repaired,
                backup=backup,
                source_hash=source_hash,
                repaired_hash_before=repaired_hash_before,
                repaired_hash_after=repaired_hash_before,
                headers=headers,
                references=references,
                targets=targets,
                stats=stats,
                backup_created=False,
            )
            return 0

        temp_path = xlsx._write_temp_package(
            repaired_package, modified_entries, repaired
        )
        temp_package = xlsx._read_package(temp_path)
        if temp_package.entries != modified_entries:
            raise xlsx.CacheRestoreError(
                "Temporary XLSX differs after ZIP serialization"
            )
        targeted_keys = {(SHEET_NAME, reference) for reference in references}
        xlsx._validate_repaired_integrity(
            repaired_package.entries, temp_package.entries, targeted_keys
        )
        _validate_target_caches(source_package, temp_package.entries, references)

        xlsx._assert_workbook_files_closed(source, repaired)
        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Checkpoint changed before apply")
        if xlsx._sha256(repaired) != repaired_hash_before:
            raise xlsx.CacheRestoreError("Repaired target changed before apply")
        try:
            xlsx._create_atomic_backup(repaired, backup, repaired_hash_before)
            os.replace(temp_path, repaired)
        except OSError as exc:
            raise xlsx.CacheRestoreError(
                f"Atomic backup/replace failed; any published backup is at "
                f"{backup}: {exc}"
            ) from exc
        temp_path = None

        final_package = xlsx._read_package(repaired)
        if final_package.entries != modified_entries:
            raise xlsx.CacheRestoreError(
                "Final target differs from the validated temporary package"
            )
        xlsx._validate_repaired_integrity(
            repaired_package.entries, final_package.entries, targeted_keys
        )
        _validate_target_caches(source_package, final_package.entries, references)
        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Checkpoint source changed")
        if xlsx._sha256(backup) != repaired_hash_before:
            raise xlsx.CacheRestoreError("Atomic backup hash is incorrect")

        repaired_hash_after = xlsx._sha256(repaired)
        _print_report(
            mode="apply",
            source=source,
            repaired=repaired,
            backup=backup,
            source_hash=source_hash,
            repaired_hash_before=repaired_hash_before,
            repaired_hash_after=repaired_hash_after,
            headers=headers,
            references=references,
            targets=targets,
            stats=stats,
            backup_created=True,
        )
        return 0
    except xlsx.CacheRestoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
