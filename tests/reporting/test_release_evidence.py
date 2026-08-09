import pandas as pd
import pytest

from src.reporting.release_evidence import build_universe_summary


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
