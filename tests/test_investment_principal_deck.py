from pathlib import Path

import pytest
from pptx import Presentation

from src.reporting.investment_principal_deck import (
    build_investment_principal_deck,
    load_deck_evidence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deck_evidence_uses_resolved_portfolio() -> None:
    evidence = load_deck_evidence(REPO_ROOT)

    assert len(evidence.holdings) == 20
    assert evidence.holdings['final_weight'].sum() == pytest.approx(1.0)
    assert (evidence.trades['trade_action'] == 'Buy').sum() == 19
    assert evidence.approval_status == 'CONDITIONALLY_APPROVED'
    assert evidence.governance_score == 80.0


def test_deck_builds_with_expected_sections(tmp_path: Path) -> None:
    result = build_investment_principal_deck(
        REPO_ROOT, tmp_path
    )
    presentation = Presentation(result.pptx_path)
    text = '\n'.join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if hasattr(shape, 'text')
    )

    assert result.slide_count == 18
    assert len(presentation.slides) == 18
    assert 'Approve a controlled live pilot' in text
    assert 'Alpha and overfitting' in text
    assert 'Equities to establish' in text
    assert result.report_path.exists()
    assert result.manifest_path.exists()
    assert all(path.exists() for path in result.plot_paths)
