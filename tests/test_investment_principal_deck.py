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


def _presentation_text(presentation: Presentation) -> str:
    chunks: list[str] = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if getattr(shape, 'has_text_frame', False):
                chunks.append(shape.text)
            if getattr(shape, 'has_table', False):
                chunks.extend(
                    cell.text
                    for row in shape.table.rows
                    for cell in row.cells
                )
    return '\n'.join(chunks)


def test_deck_evidence_uses_resolved_portfolio() -> None:
    evidence = load_deck_evidence(REPO_ROOT)

    cash = evidence.holdings.loc[
        evidence.holdings['ticker'].isin(['CASH', 'CASH.USD'])
    ]
    equities = evidence.holdings.drop(index=cash.index)

    assert evidence.holdings['final_weight'].sum() == pytest.approx(1.0)
    assert 0.0 <= cash['final_weight'].sum() <= 0.25 + 1.0e-12
    assert not equities.empty
    assert equities['final_weight'].max() <= 0.05 + 1.0e-12
    assert set(evidence.trades['ticker']) == set(evidence.holdings['ticker'])
    assert (evidence.trades['trade_action'] == 'Buy').any()
    assert evidence.approval_status == 'CONDITIONALLY_APPROVED'
    assert evidence.governance_score == pytest.approx(
        evidence.scorecard['score'].sum()
    )
    assert evidence.governance_score >= 80.0
    assert evidence.pit_coverage['coverage']['delisting_events'] > 0
    production = evidence.production_pit.set_index('dataset')
    assert int(production.loc['fundamental_vintages', 'rows']) > 0
    assert set(evidence.risk_backtest['status']) == {'PASS'}
    wolf = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    assert wolf['annualised_turnover'] <= 1.5
    assert wolf['annualised_cost_drag'] <= 0.015


def test_deck_builds_with_expected_sections(tmp_path: Path) -> None:
    evidence = load_deck_evidence(REPO_ROOT)
    result = build_investment_principal_deck(
        REPO_ROOT, tmp_path
    )
    presentation = Presentation(result.pptx_path)
    text = _presentation_text(presentation)

    assert result.slide_count == 18
    assert len(presentation.slides) == 18
    assert 'Approve a controlled live pilot' in text
    assert 'Alpha and overfitting' in text
    assert 'Equities to establish' in text
    assert 'Risk calibration now passes' in text
    wolf = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    paired_p_value = float(
        evidence.benchmark_significance.loc[
            evidence.benchmark_significance['strategy'].eq('wolf_cvar'),
            'p_value',
        ].iloc[0]
    )
    delistings = int(evidence.pit_coverage['coverage']['delisting_events'])
    production = evidence.production_pit.set_index('dataset')
    fundamental_vintages = int(
        production.loc['fundamental_vintages', 'rows']
    )
    assert f'{delistings:,}' in text
    assert f'{fundamental_vintages:,}' in text
    assert f'{float(wolf.annualised_turnover):.2f}x' in text
    assert f'{float(wolf.annualised_cost_drag):.2%}' in text
    assert f'p={paired_p_value:.3f}' in text
    assert f'{evidence.governance_score:g} / 100' in text
    assert result.report_path.exists()
    assert result.manifest_path.exists()
    assert all(path.exists() for path in result.plot_paths)
    report = result.report_path.read_text(encoding='utf-8')
    cash_mask = evidence.holdings['ticker'].isin(['CASH', 'CASH.USD'])
    equity_count = int((~cash_mask).sum())
    trade_counts = evidence.trades['trade_action'].value_counts()
    assert f'{equity_count} equities capped at' in report
    assert (
        f"{int(trade_counts.get('Buy', 0))} buys and "
        f"{int(trade_counts.get('Reduce', 0))} reductions"
    ) in report
    assert f'(p={paired_p_value:.3f})' in report


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
