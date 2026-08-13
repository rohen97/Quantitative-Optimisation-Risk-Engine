import json
from pathlib import Path

import pytest
from pptx import Presentation

from src.reporting.investment_principal_deck import (
    build_investment_principal_deck,
    load_deck_evidence,
    register_rendered_pdf,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deck_evidence_uses_resolved_portfolio() -> None:
    evidence = load_deck_evidence(REPO_ROOT)

    assert len(evidence.holdings) == 20
    assert evidence.holdings['final_weight'].sum() == pytest.approx(1.0)
    assert (evidence.trades['trade_action'] == 'Buy').sum() == 19
    assert evidence.approval_status == 'CONDITIONALLY_APPROVED'
    assert evidence.governance_score == 87.5
    assert evidence.pit_coverage['coverage']['delisting_events'] == 59183
    assert set(evidence.risk_backtest['status']) == {'PASS'}
    wolf = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    assert wolf['annualised_turnover'] <= 1.5
    assert wolf['annualised_cost_drag'] <= 0.015


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
    assert 'Risk calibration now passes' in text
    assert '59,183' in text
    assert '1.33x' in text
    assert '87.5 / 100' in text
    assert result.report_path.exists()
    assert result.manifest_path.exists()
    assert all(path.exists() for path in result.plot_paths)


def test_register_rendered_pdf_accepts_versioned_path(
    tmp_path: Path,
) -> None:
    result = build_investment_principal_deck(REPO_ROOT, tmp_path)
    pdf_path = tmp_path / 'wolf_quant_model_ic_briefing_versioned.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n%%EOF\n')

    manifest_path = register_rendered_pdf(
        REPO_ROOT,
        tmp_path,
        pdf_path=pdf_path,
        renderer='test renderer',
    )
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    assert result.slide_count == 18
    assert manifest['rendered_pdf']['path'] == str(pdf_path)
    assert manifest['rendering']['renderer'] == 'test renderer'
    assert manifest['rendering']['visual_review'] == 'completed'
