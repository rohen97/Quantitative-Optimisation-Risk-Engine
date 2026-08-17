"""Realign cached Bond prices values after normalized IDs collapse columns.

This is a focused, standard-library OOXML helper.  It derives the canonical
56-bond order from the normalized ordered-unique headers in untouched source
``Bond prices!B4:BH4``.  It then maps each ID back to its best source header
(preferring an exact header to a whitespace variant) and copies only cached
cell type/value metadata into formula cells in ``Bond prices!B5:BE16`` of the
repaired workbook.  It also restores the matching ``A16`` date cache so an
older validated BDP snapshot is not relabelled as today's observation.

The repaired workbook is changed only with ``--apply``.  Omitting a mode flag,
or passing ``--dry-run``, performs all mapping and integrity checks without
writing.  Unrelated Excel instances are left alone; the repaired target itself
must have no owner file and must allow exclusive read/write access.

Examples::

    python scripts/realign_bond_price_caches.py \
        --source "C:\\path\\Portfolio Tracker_original.xlsx" \
        --repaired "artifacts\\Portfolio Tracker_REPAIRED.xlsx"

    python scripts/realign_bond_price_caches.py \
        --source "C:\\path\\Portfolio Tracker_original.xlsx" \
        --repaired "artifacts\\Portfolio Tracker_REPAIRED.xlsx" \
        --apply
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# The adjacent helper contains the audited standard-library ZIP/XML, locking,
# hashing, atomic-backup, and cell-integrity primitives.  Importing it does not
# execute its CLI because that entry point is protected by __main__.
import restore_formula_caches as xlsx  # noqa: E402


BOND_PRICES_SHEET = "Bond prices"
EXPECTED_BOND_IDS = 56
SOURCE_HEADER_FIRST_COLUMN = 2  # B
SOURCE_HEADER_LAST_COLUMN = 60  # BH
SOURCE_HEADER_ROW = 4
DESTINATION_FIRST_COLUMN = 2  # B
DESTINATION_LAST_COLUMN = 57  # BE
DESTINATION_FIRST_ROW = 5
DESTINATION_LAST_ROW = 16


@dataclass(frozen=True)
class HeaderMapping:
    ordinal: int
    bond_id: str
    destination_column: str
    source_column: str
    source_header: str
    match_kind: str
    candidate_count: int


@dataclass(frozen=True)
class CacheTarget:
    bond_id: str
    source_reference: str
    destination_reference: str


@dataclass
class RealignStats:
    formula_cells_targeted: int = 0
    nonformula_cells_preserved: int = 0
    source_values_present: int = 0
    source_values_absent: int = 0
    type_changes: int = 0
    changed_cells: int = 0


def _column_name(number: int) -> str:
    if number < 1:
        raise xlsx.CacheRestoreError(f"Invalid Excel column number: {number}")
    characters: list[str] = []
    while number:
        number, remainder = divmod(number - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


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
            index = int(text)
            return shared_strings[index]
        except (ValueError, IndexError) as exc:
            raise xlsx.CacheRestoreError(
                f"Invalid shared-string index at {label}: {text!r}"
            ) from exc
    if cell_type == "e":
        raise xlsx.CacheRestoreError(
            f"Cannot use Excel error cache as an identifier at {label}: {text!r}"
        )
    return text


def _normalized_identifier(value: str | None) -> str:
    return "" if value is None else value.strip()


def _worksheet_cells(
    package: xlsx.Package, sheet_name: str
) -> tuple[str, dict[str, Any]]:
    sheet_parts = xlsx._sheet_part_map(package.entries)
    if sheet_name not in sheet_parts:
        raise xlsx.CacheRestoreError(f"Worksheet is missing: {sheet_name}")
    part_name = sheet_parts[sheet_name]
    root = xlsx._parse_xml(package.entries[part_name], part_name).root
    return part_name, xlsx._cell_index(root, sheet_name)


def _ordered_source_header_ids(source: xlsx.Package) -> list[str]:
    """Return normalized header IDs in first-position order.

    Whitespace-distinct source headers can represent the same bond.  The first
    position determines destination order, while `_map_source_headers` later
    chooses the exact canonical header as the cache source when one exists.
    """

    _, cells = _worksheet_cells(source, BOND_PRICES_SHEET)
    shared_strings = _shared_strings(source)
    ordered: list[str] = []
    seen: set[str] = set()
    blank_columns: list[str] = []

    for column_number in range(
        SOURCE_HEADER_FIRST_COLUMN, SOURCE_HEADER_LAST_COLUMN + 1
    ):
        column = _column_name(column_number)
        identifier = _normalized_identifier(
            _cell_text(
                cells.get(f"{column}{SOURCE_HEADER_ROW}"),
                shared_strings,
                label=f"{BOND_PRICES_SHEET}!{column}{SOURCE_HEADER_ROW}",
            )
        )
        if not identifier:
            blank_columns.append(column)
            continue
        if identifier not in seen:
            seen.add(identifier)
            ordered.append(identifier)

    if blank_columns:
        raise xlsx.CacheRestoreError(
            f"Source {BOND_PRICES_SHEET}!B4:BH4 has blank cached headers at: "
            + ", ".join(blank_columns)
        )
    if len(ordered) != EXPECTED_BOND_IDS:
        raise xlsx.CacheRestoreError(
            f"Expected {EXPECTED_BOND_IDS} normalized ordered-unique IDs from "
            f"{BOND_PRICES_SHEET}!B4:BH4, found {len(ordered)}"
        )
    return ordered


def _map_source_headers(
    source: xlsx.Package, ordered_ids: list[str]
) -> list[HeaderMapping]:
    _, cells = _worksheet_cells(source, BOND_PRICES_SHEET)
    shared_strings = _shared_strings(source)
    candidates: dict[str, list[tuple[int, str]]] = {}
    for column_number in range(
        SOURCE_HEADER_FIRST_COLUMN, SOURCE_HEADER_LAST_COLUMN + 1
    ):
        column = _column_name(column_number)
        raw_header = _cell_text(
            cells.get(f"{column}{SOURCE_HEADER_ROW}"),
            shared_strings,
            label=f"{BOND_PRICES_SHEET}!{column}{SOURCE_HEADER_ROW}",
        )
        normalized = _normalized_identifier(raw_header)
        if not normalized:
            continue
        candidates.setdefault(normalized, []).append(
            (column_number, raw_header if raw_header is not None else "")
        )

    mappings: list[HeaderMapping] = []
    for ordinal, bond_id in enumerate(ordered_ids, start=1):
        options = candidates.get(bond_id, [])
        if not options:
            raise xlsx.CacheRestoreError(
                f"No source {BOND_PRICES_SHEET} header in B4:BH4 maps to {bond_id!r}"
            )
        exact = [option for option in options if option[1] == bond_id]
        if len(exact) > 1:
            columns = ", ".join(_column_name(option[0]) for option in exact)
            raise xlsx.CacheRestoreError(
                f"Multiple exact canonical headers map to {bond_id!r}: {columns}"
            )
        if exact:
            selected = exact[0]
            match_kind = "exact"
        else:
            if len(options) > 1:
                columns = ", ".join(_column_name(option[0]) for option in options)
                raise xlsx.CacheRestoreError(
                    f"Ambiguous whitespace-only source headers map to {bond_id!r}: "
                    f"{columns}"
                )
            selected = options[0]
            match_kind = "trimmed"

        destination_number = DESTINATION_FIRST_COLUMN + ordinal - 1
        mappings.append(
            HeaderMapping(
                ordinal=ordinal,
                bond_id=bond_id,
                destination_column=_column_name(destination_number),
                source_column=_column_name(selected[0]),
                source_header=selected[1],
                match_kind=match_kind,
                candidate_count=len(options),
            )
        )

    if len(mappings) != EXPECTED_BOND_IDS:
        raise xlsx.CacheRestoreError(
            f"Expected {EXPECTED_BOND_IDS} header mappings, built {len(mappings)}"
        )
    if mappings[-1].destination_column != _column_name(DESTINATION_LAST_COLUMN):
        raise xlsx.CacheRestoreError(
            "Destination mapping does not end at Bond prices column BE"
        )
    source_columns = [mapping.source_column for mapping in mappings]
    if len(source_columns) != len(set(source_columns)):
        raise xlsx.CacheRestoreError("A source header column was mapped more than once")
    return mappings


def _build_realign_entries(
    source: xlsx.Package,
    repaired: xlsx.Package,
    mappings: list[HeaderMapping],
) -> tuple[dict[str, bytes], list[CacheTarget], RealignStats]:
    source_parts = xlsx._sheet_part_map(source.entries)
    repaired_parts = xlsx._sheet_part_map(repaired.entries)
    if BOND_PRICES_SHEET not in source_parts or BOND_PRICES_SHEET not in repaired_parts:
        raise xlsx.CacheRestoreError(f"Worksheet is missing: {BOND_PRICES_SHEET}")

    source_part = source_parts[BOND_PRICES_SHEET]
    repaired_part = repaired_parts[BOND_PRICES_SHEET]
    source_document = xlsx._parse_xml(source.entries[source_part], source_part)
    repaired_document = xlsx._parse_xml(repaired.entries[repaired_part], repaired_part)
    source_cells = xlsx._cell_index(source_document.root, BOND_PRICES_SHEET)
    repaired_cells = xlsx._cell_index(repaired_document.root, BOND_PRICES_SHEET)
    targets: list[CacheTarget] = []
    stats = RealignStats()

    for mapping in mappings:
        for row in range(DESTINATION_FIRST_ROW, DESTINATION_LAST_ROW + 1):
            destination_reference = f"{mapping.destination_column}{row}"
            repaired_cell = repaired_cells.get(destination_reference)
            if repaired_cell is None or xlsx._formula_child(repaired_cell) is None:
                stats.nonformula_cells_preserved += 1
                continue
            source_reference = f"{mapping.source_column}{row}"
            source_cell = source_cells.get(source_reference)
            if source_cell is None:
                raise xlsx.CacheRestoreError(
                    f"Mapped source cache cell is missing: "
                    f"{BOND_PRICES_SHEET}!{source_reference}"
                )
            changed, type_changed, has_value = xlsx._copy_cached_type_and_value(
                source_cell, repaired_cell
            )
            stats.formula_cells_targeted += 1
            stats.changed_cells += int(changed)
            stats.type_changes += int(type_changed)
            stats.source_values_present += int(has_value)
            stats.source_values_absent += int(not has_value)
            targets.append(
                CacheTarget(
                    bond_id=mapping.bond_id,
                    source_reference=source_reference,
                    destination_reference=destination_reference,
                )
            )

    # The source price observations in row 16 were cached on the date carried
    # by A16. Keep that formula cache with the observations; recalculating only
    # TODAY() while Bloomberg is unavailable would misdate the preserved data.
    source_date_cell = source_cells.get("A16")
    repaired_date_cell = repaired_cells.get("A16")
    if (
        source_date_cell is None
        or repaired_date_cell is None
        or xlsx._formula_child(source_date_cell) is None
        or xlsx._formula_child(repaired_date_cell) is None
    ):
        raise xlsx.CacheRestoreError(
            f"Expected formula date anchors at {BOND_PRICES_SHEET}!A16"
        )
    changed, type_changed, has_value = xlsx._copy_cached_type_and_value(
        source_date_cell, repaired_date_cell
    )
    stats.formula_cells_targeted += 1
    stats.changed_cells += int(changed)
    stats.type_changes += int(type_changed)
    stats.source_values_present += int(has_value)
    stats.source_values_absent += int(not has_value)
    targets.append(
        CacheTarget(
            bond_id="<current-price-as-of-date>",
            source_reference="A16",
            destination_reference="A16",
        )
    )

    modified_entries = dict(repaired.entries)
    if stats.changed_cells:
        modified_entries[repaired_part] = xlsx._serialize_xml(repaired_document)

    targeted_keys = {
        (BOND_PRICES_SHEET, target.destination_reference) for target in targets
    }
    xlsx._validate_repaired_integrity(
        repaired.entries, modified_entries, targeted_keys
    )
    _validate_mapped_caches(source, modified_entries, targets)
    return modified_entries, targets, stats


def _validate_mapped_caches(
    source: xlsx.Package,
    after_entries: dict[str, bytes],
    targets: list[CacheTarget],
) -> None:
    source_parts = xlsx._sheet_part_map(source.entries)
    after_parts = xlsx._sheet_part_map(after_entries)
    source_part = source_parts[BOND_PRICES_SHEET]
    after_part = after_parts[BOND_PRICES_SHEET]
    source_root = xlsx._parse_xml(source.entries[source_part], source_part).root
    after_root = xlsx._parse_xml(after_entries[after_part], after_part).root
    source_cells = xlsx._cell_index(source_root, BOND_PRICES_SHEET)
    after_cells = xlsx._cell_index(after_root, BOND_PRICES_SHEET)
    mismatches: list[str] = []
    for target in targets:
        source_cell = source_cells.get(target.source_reference)
        after_cell = after_cells.get(target.destination_reference)
        if source_cell is None or after_cell is None:
            mismatches.append(target.destination_reference)
            continue
        if (
            source_cell.attrib.get("t") != after_cell.attrib.get("t")
            or xlsx._cached_value_payload(source_cell)
            != xlsx._cached_value_payload(after_cell)
        ):
            mismatches.append(target.destination_reference)
    if mismatches:
        raise xlsx.CacheRestoreError(
            "Mapped Bond prices caches do not match source at: "
            + ", ".join(mismatches[:12])
        )


def _assert_target_unlocked(repaired: Path) -> None:
    owner_file = repaired.with_name(f"~${repaired.name}")
    if owner_file.exists():
        raise xlsx.CacheRestoreError(
            f"Excel owner/lock file exists for repaired target: {owner_file}"
        )
    xlsx._assert_exclusive_windows_access(repaired, writable=True)


def _default_backup_path(repaired: Path) -> Path:
    return repaired.with_name(
        f"{repaired.stem}.pre-bond-cache-realign-source-order.xlsx"
    )


def _print_report(
    *,
    mode: str,
    source: Path,
    repaired: Path,
    backup: Path,
    source_hash: str,
    repaired_hash_before: str,
    repaired_hash_after: str | None,
    mappings: list[HeaderMapping],
    targets: list[CacheTarget],
    stats: RealignStats,
    backup_created: bool,
) -> None:
    print(f"Mode: {mode}")
    print(f"Source (read-only): {source}")
    print(f"Repaired target: {repaired}")
    print(
        f"Atomic backup: {backup} "
        f"({'created' if backup_created else 'planned/not created'})"
    )
    print(f"Source SHA-256: {source_hash}")
    print(f"Repaired SHA-256 before: {repaired_hash_before}")
    if repaired_hash_after is not None:
        print(f"Repaired SHA-256 after: {repaired_hash_after}")
    print(f"Ordered normalized unique source headers: {len(mappings)}")
    print(f"Header mappings: {len(mappings)}")
    for mapping in mappings:
        print(
            f"{mapping.ordinal:02d} {mapping.bond_id!r}: "
            f"source {mapping.source_column} -> destination "
            f"{mapping.destination_column}; match={mapping.match_kind}; "
            f"normalized_candidates={mapping.candidate_count}; "
            f"source_header={mapping.source_header!r}"
        )
    print(f"Formula cache cells mapped: {len(targets)}")
    print(f"Formula cells targeted: {stats.formula_cells_targeted}")
    print(f"Non-formula cells preserved: {stats.nonformula_cells_preserved}")
    print(f"Source cache values present: {stats.source_values_present}")
    print(f"Source cache values absent: {stats.source_values_absent}")
    print(f"Cell type changes: {stats.type_changes}")
    print(f"Changed target cache cells: {stats.changed_cells}")
    print("Formula/style/non-formula/row-4 spill invariants: passed")
    if mode == "dry-run":
        print("Dry run complete: no files were changed.")
    elif stats.changed_cells:
        print("Apply complete: backup and repaired target were atomically published.")
    else:
        print("Apply complete: caches were already aligned; no files were changed.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Realign Bond prices formula caches from an untouched source after "
            "whitespace-normalized source headers collapse duplicate columns."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Untouched original XLSX; read and hash-checked but never written",
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
            "<repaired stem>.pre-bond-cache-realign-source-order.xlsx"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Map and validate without writing (default)",
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
        source = xlsx._resolve_workbook(args.source, "Source")
        repaired = xlsx._resolve_workbook(args.repaired, "Repaired")
        xlsx._assert_distinct_files(source, repaired)
        backup_text = args.backup or str(_default_backup_path(repaired))
        backup = xlsx._resolve_backup_path(backup_text, repaired)
        _assert_target_unlocked(repaired)

        source_hash = xlsx._sha256(source)
        repaired_hash_before = xlsx._sha256(repaired)
        source_package = xlsx._read_package(source)
        repaired_package = xlsx._read_package(repaired)
        ordered_ids = _ordered_source_header_ids(source_package)
        mappings = _map_source_headers(source_package, ordered_ids)
        modified_entries, targets, stats = _build_realign_entries(
            source_package, repaired_package, mappings
        )

        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Source workbook changed during validation")
        if xlsx._sha256(repaired) != repaired_hash_before:
            raise xlsx.CacheRestoreError("Repaired target changed during validation")

        if not args.apply:
            _assert_target_unlocked(repaired)
            if xlsx._sha256(source) != source_hash:
                raise xlsx.CacheRestoreError("Source workbook changed during dry run")
            if xlsx._sha256(repaired) != repaired_hash_before:
                raise xlsx.CacheRestoreError(
                    "Repaired target changed during dry run"
                )
            _print_report(
                mode="dry-run",
                source=source,
                repaired=repaired,
                backup=backup,
                source_hash=source_hash,
                repaired_hash_before=repaired_hash_before,
                repaired_hash_after=None,
                mappings=mappings,
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
                mappings=mappings,
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
                "Temporary XLSX payload differs after ZIP serialization"
            )
        targeted_keys = {
            (BOND_PRICES_SHEET, target.destination_reference) for target in targets
        }
        xlsx._validate_repaired_integrity(
            repaired_package.entries, temp_package.entries, targeted_keys
        )
        _validate_mapped_caches(source_package, temp_package.entries, targets)

        _assert_target_unlocked(repaired)
        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Source workbook changed before apply")
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
                "Final repaired XLSX differs from the validated temporary package"
            )
        xlsx._validate_repaired_integrity(
            repaired_package.entries, final_package.entries, targeted_keys
        )
        _validate_mapped_caches(source_package, final_package.entries, targets)
        if xlsx._sha256(source) != source_hash:
            raise xlsx.CacheRestoreError("Untouched source workbook changed")
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
            mappings=mappings,
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
