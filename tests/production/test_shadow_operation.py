from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.repository.duckdb_repository import DuckDBRepository
from src.production.shadow_operation import (
    completed_shadow_cycle_count,
    evaluate_pending_shadow_cycles,
    record_shadow_cycle,
    write_shadow_report,
)


def _repository(tmp_path: Path) -> DuckDBRepository:
    repository = DuckDBRepository(tmp_path / 'shadow.duckdb')
    repository.execute_sql_file(
        Path('sql/migrations/014_create_model_shadow_operation_tables.sql')
    )
    with repository.connection() as connection:
        connection.execute(
            '''
            CREATE TABLE prices_daily (
                security_id VARCHAR,
                trade_date DATE,
                close_price DOUBLE,
                adjusted_close DOUBLE,
                source VARCHAR,
                retrieved_at TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            INSERT INTO prices_daily VALUES
                ('A', '2026-01-31', 100, 100, 'yfinance', '2026-01-31'),
                ('B', '2026-01-31', 200, 200, 'yfinance', '2026-01-31'),
                ('A', '2026-02-28', 110, 110, 'yfinance', '2026-02-28'),
                ('B', '2026-02-28', 180, 180, 'yfinance', '2026-02-28')
            '''
        )
    return repository


def test_shadow_cycle_is_immutable_and_evaluated_only_after_due_date(tmp_path):
    repository = _repository(tmp_path)
    selected = pd.DataFrame(
        {'security_id': ['A'], 'target_weight': [1.0], 'currency': ['USD']}
    )
    equal = pd.DataFrame(
        {
            'security_id': ['A', 'B'],
            'target_weight': [0.5, 0.5],
            'currency': ['USD', 'USD'],
        }
    )
    portfolios = {'selected_final': selected, 'equal_weight_eligible': equal}

    cycle_id = record_shadow_cycle(
        repository,
        portfolios,
        as_of_date=pd.Timestamp('2026-01-31'),
        recorded_at=pd.Timestamp('2026-01-31 12:00:00'),
        model_version='test-version',
    )
    assert evaluate_pending_shadow_cycles(
        repository,
        evaluation_as_of=pd.Timestamp('2026-02-15'),
    ) == 0
    assert evaluate_pending_shadow_cycles(
        repository,
        evaluation_as_of=pd.Timestamp('2026-03-01'),
    ) == 1
    assert completed_shadow_cycle_count(repository, '2026-01-01') == 1

    cycle = repository.query(
        'SELECT * FROM model_shadow_cycles WHERE cycle_id = ?', [cycle_id]
    ).iloc[0]
    assert cycle['evaluation_status'] == 'completed'
    assert cycle['active_return_vs_equal_weight'] == pytest.approx(0.10)
    assert record_shadow_cycle(
        repository,
        portfolios,
        as_of_date=pd.Timestamp('2026-01-31'),
        recorded_at=pd.Timestamp('2026-01-31 12:00:00'),
        model_version='test-version',
    ) == cycle_id

    changed_challenger = {
        'selected_final': selected,
        'equal_weight_eligible': pd.DataFrame(
            {
                'security_id': ['A', 'B'],
                'target_weight': [0.6, 0.4],
                'currency': ['USD', 'USD'],
            }
        ),
    }
    with pytest.raises(RuntimeError, match='already frozen'):
        record_shadow_cycle(
            repository,
            changed_challenger,
            as_of_date=pd.Timestamp('2026-01-31'),
            recorded_at=pd.Timestamp('2026-01-31 12:00:00'),
            model_version='test-version',
        )

    changed = {
        'selected_final': equal,
        'equal_weight_eligible': equal,
    }
    with pytest.raises(RuntimeError, match='already frozen'):
        record_shadow_cycle(
            repository,
            changed,
            as_of_date=pd.Timestamp('2026-01-31'),
            recorded_at=pd.Timestamp('2026-01-31 12:00:00'),
            model_version='test-version',
        )

    csv_path, json_path = write_shadow_report(repository, tmp_path / 'report')
    assert csv_path.exists()
    assert json_path.exists()
    bundle_hash = repository.query(
        'SELECT portfolio_bundle_hash FROM model_shadow_cycles WHERE cycle_id = ?',
        [cycle_id],
    ).iloc[0]['portfolio_bundle_hash']
    assert isinstance(bundle_hash, str) and len(bundle_hash) == 64
