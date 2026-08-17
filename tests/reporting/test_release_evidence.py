import pandas as pd
import pytest

from src.reporting.release_evidence import (
    _normalise_text_whitespace,
    build_universe_summary,
)
from src.utils.config import ROOT


def test_release_text_paths_are_portable(tmp_path):
    report = tmp_path / 'report.md'
    report.write_text(f'Source: {ROOT / "reports" / "outputs"}\n', encoding='utf-8')

    _normalise_text_whitespace(tmp_path)

    assert report.read_text(encoding='utf-8') == 'Source: .\\reports\\outputs\n'


def test_build_universe_summary_counts_active_and_delisted_by_region():
    universe = pd.DataFrame(
        {
            'security_id': ['A', 'B', 'C', 'D', 'D'],
            'region': ['US', 'US', 'DACH', 'DACH', 'DACH'],
            'listing_status': ['Active', 'Delisted', 'Active', 'Active', 'Active'],
        }
    )

    result = build_universe_summary(universe).set_index('region')

    assert result.loc['DACH', 'active'] == 2
    assert result.loc['US', 'delisted'] == 1
    assert result.loc['ALL', 'total'] == 4
    assert result.loc['ALL', 'active_share'] == pytest.approx(0.75)


def test_build_universe_summary_requires_stable_security_identifiers():
    with pytest.raises(ValueError, match='security_id'):
        build_universe_summary(
            pd.DataFrame({'region': ['US'], 'listing_status': ['Active']})
        )
