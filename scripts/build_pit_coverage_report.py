from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository


DATASETS = (
    ("fundamental_vintages", "security_id", "fiscal_period_end", "available_from"),
    ("corporate_action_vintages", "security_id", "ex_date", "available_from"),
    ("market_cap_vintages", "security_id", "as_of_date", "available_from"),
    ("identifier_vintages", "security_id", "effective_from", "available_from"),
    ("macro_release_vintages", "series_id", "observation_date", "available_from"),
    ("sentiment_vintages", "security_id", "published_at", "available_from"),
    ("decision_snapshot_manifests", "model_run_id", "as_of_date", "available_from"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an aggregate, publishable PIT coverage report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/outputs/production_pit_coverage.md"),
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path("reports/outputs/production_pit_coverage.csv"),
    )
    return parser.parse_args()


def _coverage(repository: DuckDBRepository) -> pd.DataFrame:
    rows = []
    for table, entity, observation, availability in DATASETS:
        result = repository.query(
            f"""
            SELECT
                COUNT(1) AS row_count,
                COUNT(DISTINCT {entity}) AS entity_count,
                MIN({observation}) AS earliest_observation,
                MAX({observation}) AS latest_observation,
                MIN({availability}) AS earliest_available_from,
                MAX({availability}) AS latest_available_from
            FROM {table}
            """
        ).iloc[0]
        rows.append({"dataset": table, **result.to_dict()})
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame) -> str:
    display = frame.astype(object).where(pd.notna(frame), "")
    for column in display.columns:
        if column.endswith("observation") or column.endswith("available_from"):
            display[column] = display[column].astype(str).str.slice(0, 19)
    headers = [str(column) for column in display.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repository = DuckDBRepository(load_data_config().duckdb_path, read_only=True)
    coverage = _coverage(repository)
    universe = repository.query(
        """
        SELECT COUNT(1) AS securities
        FROM securities
        WHERE instrument_type = 'Equity'
          AND listing_status = 'Active'
          AND region IN ('Mainland China', 'Hong Kong')
        """
    ).iloc[0, 0]
    mapped_universe = repository.query(
        """
        SELECT COUNT(DISTINCT s.security_id) AS securities
        FROM securities s
        JOIN security_identifiers i USING (security_id)
        WHERE s.instrument_type = 'Equity'
          AND s.listing_status = 'Active'
          AND s.region IN ('Mainland China', 'Hong Kong')
          AND i.identifier_type = 'bloomberg_ticker'
        """
    ).iloc[0, 0]
    fundamental = repository.query(
        """
        SELECT fiscal_period_type, available_from,
               COUNT(1) AS row_count,
               COUNT(DISTINCT security_id) AS entity_count
        FROM fundamental_vintages
        GROUP BY 1, 2
        ORDER BY 2, 1
        """
    )
    macro = repository.query(
        """
        SELECT series_id, COUNT(1) AS row_count,
               COUNT(DISTINCT observation_date) AS observation_count,
               MIN(observation_date) AS earliest_observation,
               MAX(observation_date) AS latest_observation
        FROM macro_release_vintages
        GROUP BY 1
        ORDER BY 1
        """
    )
    generated = pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Production Point-in-Time Coverage",
        "",
        f"Generated: {generated}",
        "",
        "This report contains aggregate coverage only. Licensed Bloomberg observations remain in the ignored local DuckDB and are not published.",
        "",
        f"Active Mainland China and Hong Kong inventory: **{int(universe):,} securities**; canonical Bloomberg-mapped target: **{int(mapped_universe):,}**.",
        "",
        "## Dataset Coverage",
        "",
        _markdown_table(coverage),
        "",
        "## Fundamental Snapshots",
        "",
        _markdown_table(fundamental) if not fundamental.empty else "No Bloomberg database-as-of fundamentals have been stored.",
        "",
        "## Macro Series",
        "",
        _markdown_table(macro) if not macro.empty else "No macro vintages have been stored.",
        "",
        "## Evidence Grades",
        "",
        "- Bloomberg fundamentals: genuine `FUNDAMENTAL_DATABASE_DATE` snapshots. Each row is usable only from its database-as-of date.",
        "- FRED GDP, real GDP, CPI, core CPI, unemployment and monthly Fed funds: ALFRED release/revision vintages.",
        "- Daily rates, curves, FX, VIX and market credit spreads: non-revising observations available on the observation date.",
        "- Bloomberg market cap/free float: dated historical observations, not reconstructed from today's shares.",
        "- Corporate actions: event-time reconstruction using declaration dates; later vendor corrections are not yet separately versioned.",
        "- Identifier mappings: current retrieval snapshots only. Historical effective-date mappings remain incomplete.",
        "- Decision archives: retrospective cryptographic registration of existing walk-forward artifacts; availability is the archive timestamp, not the original rebalance date.",
        "",
        "## Open Production Gaps",
        "",
        "- Complete monthly Bloomberg fundamental snapshots from July 2018 onward. The current session stopped at Bloomberg's daily data capacity and is safely resumable.",
        "- Historical constituent/delisted-security membership and historical ticker/ISIN mappings for a survivorship-clean 1997 universe.",
        "- Timestamped entity-mapped news and immutable sentiment vintages. No production sentiment rows are currently present.",
        "- Genuine pre-1997 China/Hong Kong fundamentals are not established by the current entitlements; the 1997 test remains reconstructed rather than fully genuine PIT.",
        "",
        "## DRL Decision",
        "",
        "The production DRL challenger uses five Stable-Baselines3 PPO seeds over a chronological regional panel. All validation information ratios are currently negative, so the validation guard selects the constrained baseline optimiser with a 0% DRL live blend.",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(args.csv_output, index=False)
    print(f"Wrote {args.output} and {args.csv_output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
