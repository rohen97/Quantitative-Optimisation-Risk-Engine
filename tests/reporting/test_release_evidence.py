import pandas as pd
import pytest

from src.reporting.release_evidence import (
    PUBLIC_RESEARCH_OUTPUTS,
    _normalise_text_whitespace,
    _release_artifact_files,
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


def test_security_level_licensed_challenger_is_not_in_public_release() -> None:
    assert 'optimised_portfolio_regional_alpha.csv' not in PUBLIC_RESEARCH_OUTPUTS


def test_release_manifest_excludes_only_its_own_manifest(tmp_path) -> None:
    root_manifest = tmp_path / 'manifest.json'
    nested_manifest = tmp_path / 'nested' / 'manifest.json'
    nested_manifest.parent.mkdir()
    root_manifest.write_text('{}', encoding='utf-8')
    nested_manifest.write_text('{}', encoding='utf-8')

    files = _release_artifact_files(tmp_path)

    assert root_manifest not in files
    assert nested_manifest in files
