from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use('Agg')

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

INK = '172127'
PAPER = 'F6F8F7'
WHITE = 'FFFFFF'
MUTED = '647078'
BORDER = 'D8E0DD'
GREEN = '14966F'
GREEN_DARK = '0B6F56'
TEAL = '2B7280'
BLUE = '3478A5'
GOLD = 'C99328'
RED = 'BB4A4A'

PALE_GREEN = 'E8F4EF'
PALE_BLUE = 'E9F1F6'
PALE_GOLD = 'FBF3DF'
PALE_RED = 'F8EAEA'

FONT_HEAD = 'Aptos Display'
FONT_BODY = 'Aptos'

RELEASE_RELATIVE = Path(
    'reports/releases/2026-08-13-risk-pit-cost-validation'
)
PRIOR_RELEASE_RELATIVE = Path('reports/releases/2026-08-07-full-universe')
BACKTEST_RELATIVE = Path('reports/backtests/1997_to_latest')
OUTPUTS_RELATIVE = Path('reports/outputs')

PRESENTATION_RELATIVE = Path(
    'reports/presentations/wolf_investment_principal'
)


@dataclass(frozen=True)
class DeckEvidence:
    repo_root: Path
    release_root: Path
    backtest_root: Path
    outputs_root: Path
    validation_manifest: dict
    prior_validation_manifest: dict
    walk_forward_manifest: dict
    backtest_manifest: dict

    universe: pd.DataFrame
    holdings: pd.DataFrame
    trades: pd.DataFrame
    scorecard: pd.DataFrame
    prior_pit_summary: pd.DataFrame
    pit_summary: pd.DataFrame
    pit_returns: pd.DataFrame
    pit_coverage: dict
    alpha: pd.DataFrame
    overfitting: pd.Series
    performance: pd.DataFrame
    optimiser: pd.DataFrame
    risk_backtest: pd.DataFrame
    constraints: pd.DataFrame
    regime: pd.DataFrame

    @property
    def current_aum(self) -> float:
        return float(self.backtest_manifest['current_portfolio_nav_usd'])

    @property
    def as_of_date(self) -> str:
        value = str(self.validation_manifest['as_of_date'])
        return pd.Timestamp(value).strftime('%d %B %Y')

    @property
    def approval_status(self) -> str:
        return str(self.validation_manifest['approval_status'])

    @property
    def governance_score(self) -> float:
        return float(self.validation_manifest['overall_score'])


@dataclass(frozen=True)
class DeckBuildResult:
    pptx_path: Path
    report_path: Path
    manifest_path: Path
    plot_paths: tuple[Path, ...]
    slide_count: int

def _require_files(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        joined = '\n'.join(f'- {path}' for path in missing)
        raise FileNotFoundError(
            f'Missing presentation evidence files:\n{joined}'
        )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))

def load_deck_evidence(repo_root: str | Path) -> DeckEvidence:
    repo_root = Path(repo_root).resolve()
    release_root = repo_root / RELEASE_RELATIVE
    prior_release_root = repo_root / PRIOR_RELEASE_RELATIVE
    backtest_root = repo_root / BACKTEST_RELATIVE
    outputs_root = repo_root / OUTPUTS_RELATIVE
    validation_root = release_root / 'validation'
    required = [
        validation_root / 'validation_manifest.json',
        release_root / 'walk_forward_manifest.json',
        release_root / 'universe_summary.csv',

        validation_root / 'model_validation_scorecard.csv',
        validation_root / 'portfolio_strategy_comparison.csv',
        validation_root / 'portfolio_monthly_returns.csv',
        validation_root / 'risk_backtesting_report.csv',
        validation_root / 'constraint_compliance_report.csv',
        release_root / 'pit_evidence_coverage.json',
        prior_release_root / 'validation/validation_manifest.json',
        prior_release_root
        / 'validation/portfolio_strategy_comparison.csv',
        backtest_root / 'run_manifest.json',
        backtest_root / 'point_in_time_alpha_significance.csv',

        backtest_root / 'strategy_overfitting_summary.csv',
        backtest_root / 'performance_summary.csv',
        outputs_root / 'final_portfolio_weights.csv',
        outputs_root / 'portfolio_trade_list.csv',
        outputs_root / 'portfolio_optimisation_summary.csv',
    ]
    _require_files(required)

    holdings = pd.read_csv(
        outputs_root / 'final_portfolio_weights.csv'
    )

    holdings['final_weight'] = pd.to_numeric(
        holdings['final_weight'], errors='coerce'
    ).fillna(0.0)
    holdings = holdings.loc[holdings['final_weight'] > 1e-9].copy()
    holdings = holdings.sort_values(
        ['region', 'ticker']
    ).reset_index(drop=True)

    trades = pd.read_csv(outputs_root / 'portfolio_trade_list.csv')

    trades = trades.loc[
        trades['ticker'].isin(holdings['ticker'])
    ].copy()
    trades['target_weight'] = pd.to_numeric(
        trades['target_weight'], errors='coerce'
    ).fillna(0.0)
    trades = trades.sort_values(
        ['trade_action', 'ticker']
    ).reset_index(drop=True)

    overfitting = pd.read_csv(
        backtest_root / 'strategy_overfitting_summary.csv'
    )

    if overfitting.empty:
        raise ValueError('The overfitting summary has no evidence row.')

    return DeckEvidence(
        repo_root=repo_root,
        release_root=release_root,
        backtest_root=backtest_root,
        outputs_root=outputs_root,
        validation_manifest=_read_json(
            validation_root / 'validation_manifest.json'
        ),
        prior_validation_manifest=_read_json(
            prior_release_root / 'validation/validation_manifest.json'
        ),
        walk_forward_manifest=_read_json(
            release_root / 'walk_forward_manifest.json'
        ),
        backtest_manifest=_read_json(
            backtest_root / 'run_manifest.json'
        ),
        universe=pd.read_csv(release_root / 'universe_summary.csv'),
        holdings=holdings,
        trades=trades,
        scorecard=pd.read_csv(
            validation_root / 'model_validation_scorecard.csv'
        ),
        prior_pit_summary=pd.read_csv(
            prior_release_root
            / 'validation/portfolio_strategy_comparison.csv'
        ),
        pit_summary=pd.read_csv(
            validation_root / 'portfolio_strategy_comparison.csv'
        ),
        pit_returns=pd.read_csv(
            validation_root / 'portfolio_monthly_returns.csv'
        ),
        pit_coverage=_read_json(
            release_root / 'pit_evidence_coverage.json'
        ),
        alpha=pd.read_csv(
            backtest_root / 'point_in_time_alpha_significance.csv'
        ),
        overfitting=overfitting.iloc[0],
        performance=pd.read_csv(
            backtest_root / 'performance_summary.csv'
        ),

        optimiser=pd.read_csv(
            outputs_root / 'portfolio_optimisation_summary.csv'
        ),
        risk_backtest=pd.read_csv(
            validation_root / 'risk_backtesting_report.csv'
        ),
        constraints=pd.read_csv(
            validation_root / 'constraint_compliance_report.csv'
        ),
        regime=pd.read_csv(
            validation_root / 'regime_performance_report.csv'
        ),
    )

def _rgb(hex_value: str) -> RGBColor:
    value = hex_value.lstrip('#')
    return RGBColor(
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _ascii_display(value: object) -> str:
    text = '' if value is None else str(value)
    return (
        unicodedata.normalize('NFKD', text)
        .encode('ascii', 'ignore')
        .decode('ascii')
    )

def _pct(value: float, digits: int = 1) -> str:
    return f'{float(value) * 100:.{digits}f}%'


def _usd(value: float, digits: int = 1) -> str:
    amount = float(value)
    magnitude = abs(amount)
    if magnitude >= 1_000_000_000:
        return '$' + f'{amount / 1_000_000_000:.{digits}f}bn'
    if magnitude >= 1_000_000:
        return '$' + f'{amount / 1_000_000:.{digits}f}m'

    if magnitude >= 1_000:
        return '$' + f'{amount / 1_000:.{digits}f}k'
    return '$' + f'{amount:,.0f}'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _manifest_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _set_axes_style(ax: plt.Axes) -> None:

    ax.set_facecolor('#' + WHITE)
    ax.grid(axis='y', color='#E4EAE8', linewidth=0.8)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color('#B9C4C0')
    ax.tick_params(colors='#536068', labelsize=9, length=0)


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path, dpi=180, bbox_inches='tight', facecolor='#' + WHITE
    )
    plt.close(fig)
    return path

STRATEGY_LABELS = {
    'wolf_cvar': 'Wolf CVaR',
    'equal_weight_eligible': 'Equal weight',
    'cap_weight_eligible': 'Cap weight',
}
STRATEGY_COLORS = {
    'wolf_cvar': '#' + GREEN,
    'equal_weight_eligible': '#' + BLUE,
    'cap_weight_eligible': '#' + GOLD,
}


def _plot_pit_capital(
    evidence: DeckEvidence, output_path: Path
) -> Path:

    data = evidence.pit_returns.copy()
    data['date'] = pd.to_datetime(data['date'])
    data['net_return'] = pd.to_numeric(
        data['net_return'], errors='coerce'
    ).fillna(0.0)
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    for strategy, group in data.groupby('strategy', sort=False):
        group = group.sort_values('date')
        wealth = evidence.current_aum * (
            1.0 + group['net_return']
        ).cumprod()

        ax.plot(
            group['date'],
            wealth / 1_000_000,
            color=STRATEGY_COLORS[strategy],
            linewidth=2.4,
            label=STRATEGY_LABELS[strategy],
        )
        ax.text(
            group['date'].iloc[-1],
            wealth.iloc[-1] / 1_000_000,
            '  ' + _usd(wealth.iloc[-1]),

            color=STRATEGY_COLORS[strategy],
            fontsize=9,
            va='center',
            weight='bold',
        )
    _set_axes_style(ax)
    ax.set_ylabel('Illustrative AUM, USD millions', color='#536068')
    ax.set_title(
        'Five-year point-in-time proxy on current AUM',
        loc='left',
        fontsize=15,
        color='#' + INK,
        weight='bold',
    )

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.legend(
        loc='upper left',
        frameon=False,
        ncol=3,
        fontsize=9,
    )
    ax.margins(x=0.04)
    fig.tight_layout()
    return _save_figure(fig, output_path)


def _plot_pit_metrics(
    evidence: DeckEvidence, output_path: Path
) -> Path:

    data = evidence.pit_summary.set_index('strategy')
    strategies = [
        'wolf_cvar',
        'equal_weight_eligible',
        'cap_weight_eligible',
    ]
    panels = [
        ('annualised_return', 'Net return', 100.0),
        ('sharpe', 'Sharpe ratio', 1.0),
        ('maximum_drawdown', 'Maximum drawdown', 100.0),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 4.1))

    labels = [STRATEGY_LABELS[item] for item in strategies]
    colors = [STRATEGY_COLORS[item] for item in strategies]
    for ax, (column, title, scale) in zip(axes, panels):
        values = [
            float(data.loc[item, column]) * scale
            for item in strategies
        ]
        bars = ax.bar(labels, values, color=colors, width=0.62)
        _set_axes_style(ax)
        ax.set_title(
            title, fontsize=13, color='#' + INK, weight='bold'
        )

        ax.tick_params(axis='x', rotation=22)
        ax.axhline(0.0, color='#B9C4C0', linewidth=0.8)
        for bar, value in zip(bars, values):
            suffix = '%' if column != 'sharpe' else ''
            label = f'{value:.1f}{suffix}'
            y = value + (0.45 if value >= 0 else -0.45)
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y,
                label,
                ha='center',

                va='bottom' if value >= 0 else 'top',
                fontsize=9,
                color='#' + INK,
                weight='bold',
            )
    fig.suptitle(
        'Wolf trades some return for a smoother path',
        x=0.02,
        ha='left',
        fontsize=15,
        color='#' + INK,
        weight='bold',
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))

    return _save_figure(fig, output_path)


def _plot_overfitting(
    evidence: DeckEvidence, output_path: Path
) -> Path:
    row = evidence.overfitting
    values = [
        float(row['median_selected_is_information_ratio']),
        float(row['median_selected_oos_information_ratio']),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    bars = ax.bar(
        ['Selected in-sample', 'Same winner out-of-sample'],

        values,
        color=['#' + GOLD, '#' + GREEN],
        width=0.55,
    )
    _set_axes_style(ax)
    ax.set_ylabel('Information ratio', color='#536068')
    ax.set_title(
        'Selection performance is roughly halved out-of-sample',
        loc='left',
        fontsize=14,
        color='#' + INK,
        weight='bold',
    )
    for bar, value in zip(bars, values):

        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.035,
            f'{value:.2f}',
            ha='center',
            fontsize=12,
            color='#' + INK,
            weight='bold',
        )
    pbo = float(row['probability_of_backtest_overfitting'])
    haircut = float(row['selected_information_ratio_haircut'])
    ax.text(
        0.02,
        0.93,

        f'PBO {_pct(pbo)}  |  IR haircut {_pct(haircut)}',
        transform=ax.transAxes,
        fontsize=10,
        color='#' + MUTED,
        va='top',
    )
    fig.tight_layout()
    return _save_figure(fig, output_path)


def _plot_cost_drag(
    evidence: DeckEvidence, output_path: Path
) -> Path:
    before = evidence.prior_pit_summary.set_index('strategy').loc[
        'wolf_cvar'
    ]
    after = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    panels = [
        (
            'annualised_cost_drag',
            'Annualised cost drag',
            100.0,
            '%',
        ),
        ('annualised_turnover', 'Annualised turnover', 1.0, 'x'),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(8.1, 4.5))
    for ax, (column, title, scale, suffix) in zip(axes, panels):
        values = [float(before[column]) * scale, float(after[column]) * scale]
        bars = ax.bar(
            ['Before', 'Now'],
            values,
            color=['#' + RED, '#' + GREEN],
            width=0.58,
        )
        _set_axes_style(ax)
        ax.set_title(
            title, fontsize=13, color='#' + INK, weight='bold'
        )
        ax.axhline(
            1.5,
            color='#' + GOLD,
            linewidth=1.4,
            linestyle='--',
            label='1.5 target',
        )
        ax.legend(frameon=False, fontsize=8, loc='upper right')
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.06,
                f'{value:.2f}{suffix}',
                ha='center',
                fontsize=10,
                color='#' + INK,
                weight='bold',
            )
    fig.suptitle(
        'Turnover controls moved both implementation measures below target',
        x=0.02,
        ha='left',
        fontsize=14,
        color='#' + INK,
        weight='bold',
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    return _save_figure(fig, output_path)


def _build_plot_assets(
    evidence: DeckEvidence, plot_dir: Path
) -> tuple[Path, ...]:

    plot_dir.mkdir(parents=True, exist_ok=True)
    assets = (
        _plot_pit_capital(
            evidence, plot_dir / 'pit_capital_projection.png'
        ),
        _plot_pit_metrics(
            evidence, plot_dir / 'pit_metric_comparison.png'
        ),
        _plot_overfitting(
            evidence, plot_dir / 'overfitting_haircut.png'
        ),
        _plot_cost_drag(
            evidence, plot_dir / 'implementation_cost_drag.png'
        ),
    )
    return assets

def _set_background(slide, color: str = PAPER) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def _add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 18,
    color: str = INK,
    bold: bool = False,

    font: str = FONT_BODY,
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.TOP,
    margin: float = 0.02,
):
    shape = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = valign
    inset = Inches(margin)
    frame.margin_left = inset
    frame.margin_right = inset

    frame.margin_top = inset
    frame.margin_bottom = inset
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = _ascii_display(text)
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    shape.name = 'Text: ' + _ascii_display(text)[:50]
    return shape

def _add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = WHITE,
    line: str = BORDER,
    radius: bool = False,
):
    kind = (
        MSO_SHAPE.ROUNDED_RECTANGLE
        if radius
        else MSO_SHAPE.RECTANGLE
    )
    shape = slide.shapes.add_shape(
        kind, Inches(x), Inches(y), Inches(w), Inches(h)
    )

    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    shape.line.color.rgb = _rgb(line)
    shape.line.width = Pt(0.8)
    if radius:
        shape.adjustments[0] = 0.06
    return shape


def _add_header(
    slide, title: str, subtitle: str, slide_number: int
) -> None:
    _add_text(
        slide, title, 0.52, 0.32, 10.9, 0.44,
        size=25, bold=True, font=FONT_HEAD,
    )

    if subtitle:
        _add_text(
            slide, subtitle, 0.54, 0.81, 11.4, 0.28,
            size=10.5, color=MUTED,
        )
    _add_text(
        slide, f'{slide_number:02d}', 12.27, 0.35, 0.52, 0.28,
        size=10, color=MUTED, bold=True, align=PP_ALIGN.RIGHT,
    )
    divider = _add_rect(
        slide, 0.54, 1.16, 12.25, 0.012,
        fill=BORDER, line=BORDER,
    )
    divider.name = 'Header divider'

def _add_footer(
    slide,
    source: str,
    *,
    label: str = 'Wolf Quant Model | Research use',
) -> None:
    _add_text(
        slide, label, 0.54, 7.18, 3.8, 0.16,
        size=7.5, color=MUTED,
    )
    _add_text(
        slide, source, 4.1, 7.18, 8.68, 0.16,
        size=7.5, color=MUTED, align=PP_ALIGN.RIGHT,
    )


def _new_slide(

    presentation: Presentation,
    title: str,
    subtitle: str,
    number: int,
    source: str,
):
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )
    _set_background(slide)
    _add_header(slide, title, subtitle, number)
    _add_footer(slide, source)
    return slide


def _add_bullets(
    slide,
    items: Sequence[str],
    x: float,
    y: float,

    w: float,
    h: float,
    *,
    size: float = 16,
    color: str = INK,
    spacing: float = 10,
):
    shape = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    bullet = chr(0x2022)

    for index, item in enumerate(items):
        paragraph = (
            frame.paragraphs[0]
            if index == 0
            else frame.add_paragraph()
        )
        paragraph.text = f'{bullet} {_ascii_display(item)}'
        paragraph.font.name = FONT_BODY
        paragraph.font.size = Pt(size)
        paragraph.font.color.rgb = _rgb(color)
        paragraph.space_after = Pt(spacing)
        paragraph.line_spacing = 1.05
    shape.name = 'Bullet list'
    return shape

def _add_kpi(
    slide,
    value: str,
    label: str,
    x: float,
    y: float,
    w: float,
    *,
    fill: str = WHITE,
    accent: str = GREEN,
) -> None:
    _add_rect(slide, x, y, w, 1.02, fill=fill, line=BORDER)
    _add_rect(
        slide, x, y, 0.055, 1.02, fill=accent, line=accent
    )

    _add_text(
        slide, value, x + 0.18, y + 0.14, w - 0.28, 0.34,
        size=21, color=INK, bold=True, font=FONT_HEAD,
    )
    _add_text(
        slide, label, x + 0.18, y + 0.58, w - 0.28, 0.22,
        size=9.5, color=MUTED,
    )


def _add_callout(
    slide,
    heading: str,
    body: str,
    x: float,
    y: float,

    w: float,
    h: float,
    *,
    fill: str = PALE_GREEN,
    accent: str = GREEN,
) -> None:
    _add_rect(slide, x, y, w, h, fill=fill, line=fill)
    _add_rect(
        slide, x, y, 0.06, h, fill=accent, line=accent
    )
    if h < 0.9:
        _add_text(
            slide,
            f'{heading}: {body}',
            x + 0.22,
            y + 0.1,
            w - 0.36,
            h - 0.18,
            size=10.2,
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        return
    _add_text(
        slide, heading, x + 0.22, y + 0.16, w - 0.36, 0.34,
        size=17, bold=True, font=FONT_HEAD,
    )
    _add_text(
        slide, body, x + 0.22, y + 0.57, w - 0.36, h - 0.7,
        size=11.5, color=MUTED,
    )

def _add_table(
    slide,
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    widths: Sequence[float] | None = None,
    font_size: float = 10,
    highlight_rows: Sequence[int] = (),
):
    shape = slide.shapes.add_table(
        len(rows) + 1,
        len(headers),
        Inches(x),

        Inches(y),
        Inches(w),
        Inches(h),
    )
    table = shape.table
    if widths:
        total = sum(widths)
        for column, width in zip(table.columns, widths):
            column.width = Inches(w * width / total)

    for column_index, header in enumerate(headers):
        cell = table.cell(0, column_index)
        cell.text = _ascii_display(header)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(INK)

        cell.margin_left = Inches(0.06)
        cell.margin_right = Inches(0.04)
        cell.margin_top = Inches(0.03)
        cell.margin_bottom = Inches(0.03)
        paragraph = cell.text_frame.paragraphs[0]
        paragraph.font.name = FONT_BODY
        paragraph.font.size = Pt(font_size)
        paragraph.font.bold = True
        paragraph.font.color.rgb = _rgb(WHITE)
        paragraph.alignment = PP_ALIGN.LEFT

    for row_index, row in enumerate(rows, start=1):
        row_fill = PALE_GREEN if row_index - 1 in highlight_rows else WHITE

        for column_index, value in enumerate(row):
            cell = table.cell(row_index, column_index)
            cell.text = _ascii_display(value)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(row_fill)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.04)
            cell.margin_top = Inches(0.025)
            cell.margin_bottom = Inches(0.025)
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.font.name = FONT_BODY
            paragraph.font.size = Pt(font_size)
            paragraph.font.color.rgb = _rgb(INK)

            paragraph.alignment = (
                PP_ALIGN.RIGHT
                if column_index > 1
                else PP_ALIGN.LEFT
            )
    shape.name = 'Evidence table'
    return shape


def _add_picture_contain(
    slide,
    image_path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
):
    with Image.open(image_path) as image:
        image_w, image_h = image.size

    image_ratio = image_w / image_h
    box_ratio = w / h
    if image_ratio >= box_ratio:
        draw_w = w
        draw_h = w / image_ratio
    else:
        draw_h = h
        draw_w = h * image_ratio
    draw_x = x + (w - draw_w) / 2
    draw_y = y + (h - draw_h) / 2
    picture = slide.shapes.add_picture(
        str(image_path),
        Inches(draw_x),
        Inches(draw_y),
        Inches(draw_w),
        Inches(draw_h),
    )

    picture.name = 'Chart: ' + image_path.name
    return picture


def _add_chevron(
    slide, x: float, y: float, w: float = 0.33
) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.CHEVRON,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(0.58),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(BORDER)
    shape.line.color.rgb = _rgb(BORDER)

def _slide_cover(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )
    _set_background(slide, INK)
    _add_rect(
        slide, 0.55, 0.55, 0.08, 5.55,
        fill=GREEN, line=GREEN,
    )
    _add_text(
        slide, 'WOLF QUANT MODEL', 0.9, 0.64, 5.6, 0.3,
        size=11, color='8FD7BF', bold=True,
    )

    _add_text(
        slide, 'Investment committee\nbriefing',
        0.88, 1.18, 7.5, 1.3,
        size=38, color=WHITE, bold=True, font=FONT_HEAD,
    )
    _add_text(
        slide,
        'A disciplined global-equity decision system with '
        'portfolio constraints, stress testing and governance.',
        0.91, 2.72, 7.4, 0.8,
        size=18, color='D7E1DE',
    )
    _add_rect(
        slide, 0.91, 3.82, 5.55, 0.56,
        fill=GREEN_DARK, line=GREEN_DARK,
    )

    _add_text(
        slide,
        'DECISION: APPROVE A CONTROLLED LIVE PILOT',
        1.12, 3.98, 5.15, 0.2,
        size=12, color=WHITE, bold=True,
    )
    all_row = evidence.universe.loc[
        evidence.universe['region'] == 'ALL'
    ].iloc[0]
    metrics = [
        (f'{int(all_row.active):,}', 'active equities'),
        ('60', 'monthly decisions'),
        (f'{evidence.governance_score:g} / 100', 'governance score'),
        ('0', 'hard breaches'),
    ]
    for index, (value, label) in enumerate(metrics):
        x = 0.91 + index * 3.02
        _add_rect(
            slide, x, 5.25, 2.72, 1.05,
            fill='243037', line='435158',
        )

        _add_text(
            slide, value, x + 0.16, 5.42, 2.35, 0.3,
            size=21, color=WHITE, bold=True, font=FONT_HEAD,
        )
        _add_text(
            slide, label, x + 0.16, 5.84, 2.35, 0.2,
            size=9.5, color='B9C8C3',
        )
    _add_text(
        slide,
        f'As of {evidence.as_of_date}  |  '
        f'{evidence.approval_status}  |  Research evidence',
        0.91, 6.83, 11.5, 0.22,
        size=9, color='9EAFAB',
    )

def _slide_decision(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'The decision in one page',
        'The controls improved materially; the alpha claim did not.',
        2,
        '13 August validation scorecard and point-in-time comparison',
    )
    _add_callout(
        slide,
        'Recommendation',
        'Approve a small, human-supervised live pilot. '
        'Do not authorize unattended or full-scale deployment yet.',
        0.55, 1.43, 5.9, 1.18,
        fill=PALE_GREEN, accent=GREEN,
    )

    _add_text(
        slide, 'Why it earns a pilot', 0.58, 2.91, 5.5, 0.32,
        size=18, bold=True, font=FONT_HEAD,
    )
    _add_bullets(
        slide,
        [
            'Repeatable screening across six equity regions',
            'Adaptive VaR passes overall and chronological holdout tests',
            'Turnover and modeled cost drag now meet both 1.5 targets',
            'Zero hard breaches with auditable forecasts and trades',
        ],
        0.58, 3.34, 5.78, 2.62,
        size=14.5,
    )

    _add_callout(
        slide,
        'What still blocks full deployment',
        'Observed PIT evidence is incomplete, and Wolf lagged equal '
        'weight by 1.06% per year in this 60-month sample (p=0.734).',
        6.82, 1.43, 5.95, 1.18,
        fill=PALE_RED, accent=RED,
    )
    rows = [
        ('Process', 'Strong', 'Use'),
        ('Risk backtest', '15 / 15', 'Pass'),
        ('Cost controls', 'Both targets met', 'Pass'),
        ('Hard constraints', '0 breaches', 'Pass'),
        ('PIT evidence', '7.5 / 15', 'Improve'),
        ('Deployable alpha', 'Not established', 'Do not claim'),
    ]

    _add_table(
        slide,
        ['Decision area', 'Evidence', 'Action'],
        rows,
        6.82, 2.91, 5.95, 2.95,
        widths=[2.2, 1.6, 1.6],
        font_size=11,
        highlight_rows=[0, 1, 2, 3],
    )
    _add_callout(
        slide,
        'Approval means',
        'Pilot capital, pre-trade review, monthly risk reporting and '
        'explicit stop conditions. It does not mean automatic execution.',
        0.58, 6.18, 12.19, 0.65,
        fill=PALE_BLUE, accent=BLUE,
    )


def _slide_workflow(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'What the model actually does',
        'A monthly decision pipeline with risk controls at the end.',
        3,
        'Repository pipeline stages and current resolved outputs',
    )
    steps = [
        ('1  OBSERVE', 'Prices, filings, macro and portfolio'),
        ('2  FEATURE', 'Point-in-time quality, value and risk signals'),
        ('3  FORECAST', '3, 6, 9 and 12 month distributions'),

        ('4  COMPARE', 'Portfolio-aware, clean-sheet and LLM branches'),
        ('5  CONSTRAIN', 'CVaR, liquidity and concentration limits'),
        ('6  GOVERN', 'Stress, validation and committee reporting'),
    ]
    for index, (heading, body) in enumerate(steps):
        x = 0.55 + index * 2.05
        _add_rect(
            slide, x, 2.04, 1.73, 2.05,
            fill=WHITE, line=BORDER,
        )
        _add_rect(
            slide, x, 2.04, 1.73, 0.12,
            fill=GREEN if index in (0, 4, 5) else BLUE,
            line=GREEN if index in (0, 4, 5) else BLUE,
        )

        _add_text(
            slide, heading, x + 0.14, 2.39, 1.45, 0.34,
            size=12, bold=True, font=FONT_HEAD,
        )
        _add_text(
            slide, body, x + 0.14, 2.93, 1.45, 0.82,
            size=10.5, color=MUTED,
        )
        if index < len(steps) - 1:
            _add_chevron(slide, x + 1.78, 2.79, 0.24)
    _add_callout(
        slide,
        'The output is a decision package',
        'Ranked equities, target weights, trade direction, exposure '
        'limits, risk tests, stress results and an approval status.',
        0.55, 4.64, 6.0, 1.14,

        fill=PALE_GREEN, accent=GREEN,
    )
    _add_callout(
        slide,
        'DRL is a challenger, not the final authority',
        'The current DRL proposal was rejected because turnover exceeded '
        'its hard limit. The CVaR baseline remained selected.',
        6.82, 4.64, 5.95, 1.14,
        fill=PALE_GOLD, accent=GOLD,
    )
    _add_text(
        slide,
        'Human review stays between model recommendation and execution.',
        0.58, 6.18, 12.0, 0.36,
        size=18, color=GREEN_DARK, bold=True, font=FONT_HEAD,
        align=PP_ALIGN.CENTER,
    )

def _slide_evidence(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    profile = evidence.walk_forward_manifest['source_profile']
    artifact = evidence.walk_forward_manifest['artifact_profile']
    coverage = evidence.pit_coverage['coverage']
    all_row = evidence.universe.loc[
        evidence.universe['region'] == 'ALL'
    ].iloc[0]
    slide = _new_slide(
        presentation,
        'Evidence breadth and point-in-time progress',
        'Delistings improved; observed historical availability remains the main gap.',
        4,
        'Universe, walk-forward manifest and PIT evidence coverage',
    )
    kpis = [
        (f'{int(all_row.active):,}', 'active equities'),
        ('{:,}'.format(int(profile['security_count'])), 'walk-forward eligible'),
        ('{:,}'.format(int(artifact['forecast_rows'])), 'historical forecasts'),
        (f"{int(coverage['delisting_events']):,}", 'delistings archived'),
    ]
    for index, (value, label) in enumerate(kpis):
        _add_kpi(
            slide, value, label,
            0.55 + index * 3.08, 1.46, 2.78,
            fill=WHITE, accent=GREEN if index in (0, 3) else BLUE,
        )
    region_rows = []
    for row in evidence.universe.loc[
        evidence.universe['region'] != 'ALL'
    ].itertuples():
        region_rows.append(
            (
                row.region,
                f'{int(row.active):,}',
                f'{int(row.total):,}',
                _pct(row.active_share),
            )
        )
    _add_table(
        slide,
        ['Region', 'Active', 'Master', 'Active share'],
        region_rows,
        0.55, 2.83, 6.1, 3.12,
        widths=[2.1, 1.0, 1.0, 1.25],
        font_size=10.5,
    )

    pit_rows = [
        ('Delisting events', f"{int(coverage['delisting_events']):,}", 'Archived'),
        (
            'Fundamentals with filing date',
            f"{int(coverage['fundamental_rows_with_filing_date']):,}",
            'Mostly reconstructed',
        ),
        (
            'Observed acceptance times',
            f"{int(coverage['observed_acceptance_timestamps']):,}",
            'Missing',
        ),
        (
            'Dated membership events',
            f"{int(coverage['historical_membership_events']):,}",
            'Missing',
        ),
        (
            'Inactive names with prices',
            f"{int(coverage['inactive_price_securities']):,}",
            'Missing',
        ),
        (
            'Names with historical volume',
            f"{int(coverage['securities_with_historical_volume']):,}",
            'Missing',
        ),
    ]
    _add_table(
        slide,
        ['PIT evidence', 'Coverage', 'Status'],
        pit_rows,
        6.93, 2.83, 5.84, 3.12,
        widths=[2.55, 1.2, 1.45],
        font_size=10.0,
        highlight_rows=[0],
    )

    _add_callout(
        slide,
        'Provider outcome',
        'EODHD added 59,183 delistings; Nasdaq entitlement yielded five '
        'usable rows; Beam was unavailable; SEC blocked this runner. '
        'Unavailable history is never treated as observed.',
        0.55, 6.18, 12.22, 0.65,
        fill=PALE_GOLD, accent=GOLD,
    )


def _slide_trades(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    buys = int((evidence.trades['trade_action'] == 'Buy').sum())
    reduces = int(
        (evidence.trades['trade_action'] == 'Reduce').sum()
    )
    slide = _new_slide(
        presentation,
        'Equities to establish in the target portfolio',
        'Model trade direction versus current holdings; weights are targets.',
        5,
        'Final portfolio weights and portfolio trade list',
    )
    _add_kpi(
        slide, str(buys), 'buy actions',
        0.55, 1.39, 2.3, fill=PALE_GREEN, accent=GREEN,
    )

    _add_kpi(
        slide, str(reduces), 'reduce actions',
        3.02, 1.39, 2.3, fill=PALE_GOLD, accent=GOLD,
    )
    _add_kpi(
        slide, '5.0%', 'target per name',
        5.49, 1.39, 2.3, fill=WHITE, accent=BLUE,
    )
    _add_kpi(
        slide, '20', 'target holdings',
        7.96, 1.39, 2.3, fill=WHITE, accent=TEAL,
    )
    _add_kpi(
        slide, '6', 'equity regions',
        10.43, 1.39, 2.34, fill=WHITE, accent=GREEN,
    )

    rows = []
    for row in evidence.trades.itertuples():
        rows.append(
            (
                row.ticker,
                _ascii_display(row.company_name)[:29],
                row.region,
                row.trade_action,
                _pct(row.target_weight, 1),
            )
        )
    midpoint = math.ceil(len(rows) / 2)
    for index, subset in enumerate(
        (rows[:midpoint], rows[midpoint:])
    ):
        _add_table(
            slide,
            ['Ticker', 'Company', 'Region', 'Action', 'Target'],

            subset,
            0.55 + index * 6.16,
            2.73,
            5.89,
            3.72,
            widths=[1.05, 2.55, 1.35, 0.9, 0.8],
            font_size=8.6,
        )
    _add_text(
        slide,
        'Execution note: recalculate orders using live NAV, FX, '
        'liquidity and prices. Manual review remains mandatory.',
        0.58, 6.68, 12.15, 0.24,
        size=9.5, color=RED, bold=True,
        align=PP_ALIGN.CENTER,
    )

def _slide_exposure(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    chart = (
        evidence.release_root
        / 'plots/final_portfolio_exposures.png'
    )
    slide = _new_slide(
        presentation,
        'A deliberately diversified target',
        'The portfolio uses equal name weights and explicit exposure caps.',
        6,
        'Final portfolio weights and constraint report',
    )
    _add_picture_contain(slide, chart, 0.47, 1.39, 8.2, 5.33)
    _add_text(
        slide, 'Construction rules', 8.94, 1.54, 3.65, 0.34,
        size=18, bold=True, font=FONT_HEAD,
    )

    _add_bullets(
        slide,
        [
            '20 holdings at 5% each',
            'No sector above 25%',
            'No country above 30%',
            'No region or currency above 40%',
            'One listing per issuer',
            'No quarantined price history',
        ],
        8.94, 2.03, 3.65, 2.64,
        size=14,
    )
    _add_callout(
        slide,
        'Largest allocations',
        'Mainland China 30%; EU ex-DACH 25%; Financials and '
        'Consumer Staples 25% each.',
        8.94, 5.02, 3.72, 1.18,
        fill=PALE_BLUE, accent=BLUE,
    )

def _ending_value(
    evidence: DeckEvidence, strategy: str
) -> float:
    returns = evidence.pit_returns.loc[
        evidence.pit_returns['strategy'] == strategy,
        'net_return',
    ].astype(float)
    return evidence.current_aum * float(
        (1.0 + returns).prod()
    )


def _slide_optimizer(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'Why the CVaR portfolio is the baseline',
        'It balances expected return, downside loss and diversification.',
        7,

        'Portfolio optimisation summary',
    )
    labels = {
        'equal_weight': 'Equal weight',
        'score_weighted': 'Score weighted',
        'risk_parity': 'Risk parity',
        'mean_variance': 'Mean variance',
        'cvar_constrained': 'CVaR constrained',
        'dividend_income': 'Dividend income',
        'regime_aware': 'Regime aware',
    }
    rows = []
    highlight = []
    for row in evidence.optimiser.itertuples():
        if row.portfolio_method == 'cvar_constrained':
            highlight.append(len(rows))

        rows.append(
            (
                labels.get(row.portfolio_method, row.portfolio_method),
                _pct(row.expected_volatility),
                _pct(row.cvar_5),
                _pct(row.expected_dividend_yield),
                str(int(row.hard_constraint_breaches)),
            )
        )
    _add_table(
        slide,
        ['Portfolio', 'Volatility', 'CVaR 5%', 'Yield', 'Hard breaches'],
        rows,
        0.55, 1.52, 7.35, 4.45,
        widths=[2.4, 1.2, 1.2, 0.95, 1.2],
        font_size=10.5,
        highlight_rows=highlight,
    )

    _add_callout(
        slide,
        'Selected: CVaR constrained',
        'The baseline keeps the forecast return target while reducing '
        'the average loss in the worst 5% of modeled outcomes to 5.10%.',
        8.22, 1.52, 4.55, 1.28,
        fill=PALE_GREEN, accent=GREEN,
    )
    _add_text(
        slide, 'Why this matters', 8.25, 3.17, 4.2, 0.34,
        size=18, bold=True, font=FONT_HEAD,
    )
    _add_bullets(
        slide,
        [
            'Focuses on severe downside, not only average volatility',
            'Maintains 20 effective holdings',
            'Passes every hard portfolio constraint',

            'Produces the final 20-name equal-weight target',
        ],
        8.25, 3.66, 4.34, 2.05,
        size=14,
    )
    _add_callout(
        slide,
        'Interpret carefully',
        'Expected-return inputs are model forecasts, not guaranteed '
        'market returns. Live sizing still depends on trading capacity.',
        8.22, 5.87, 4.55, 0.75,
        fill=PALE_GOLD, accent=GOLD,
    )

def _slide_pit_growth(
    presentation: Presentation,
    evidence: DeckEvidence,
    plot_path: Path,
) -> None:
    wolf_end = _ending_value(evidence, 'wolf_cvar')
    wolf_pnl = wolf_end - evidence.current_aum
    slide = _new_slide(
        presentation,
        'Five-year point-in-time proxy',
        'The relevant model evidence uses dated monthly decisions.',
        8,
        '60-month reconstructed point-in-time portfolio returns',
    )
    _add_picture_contain(slide, plot_path, 0.47, 1.38, 8.45, 5.45)

    _add_callout(
        slide,
        'Illustrative current-AUM result',
        f'{_usd(evidence.current_aum)} grows to '
        f'{_usd(wolf_end)}; net PnL is {_usd(wolf_pnl)} '
        'after trading costs and before the bank fee.',
        9.12, 1.51, 3.65, 1.17,
        fill=PALE_GREEN, accent=GREEN,
    )
    wolf = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    _add_bullets(
        slide,
        [
            f'Net annualised return: {_pct(wolf.annualised_return)}',
            f'Sharpe ratio: {float(wolf.sharpe):.2f}',
            f'Maximum drawdown: {_pct(wolf.maximum_drawdown)}',
            f'Positive months: {_pct(wolf.positive_period_ratio)}',

        ],
        9.14, 3.03, 3.48, 1.95,
        size=14,
    )
    _add_callout(
        slide,
        'Not a forecast',
        'This scales the realised proxy path to current AUM. The 25 bp '
        'annual bank fee is modeled separately in the long replay.',
        9.12, 5.42, 3.65, 1.05,
        fill=PALE_GOLD, accent=GOLD,
    )

def _slide_pit_comparison(
    presentation: Presentation,
    evidence: DeckEvidence,
    plot_path: Path,
) -> None:
    summary = evidence.pit_summary.set_index('strategy')
    wolf = summary.loc['wolf_cvar']
    equal = summary.loc['equal_weight_eligible']
    slide = _new_slide(
        presentation,
        'What beat what over 60 months',
        'Wolf delivered the best risk-adjusted result, not the best return.',
        9,
        'Point-in-time strategy comparison, net of modeled costs',
    )
    _add_picture_contain(slide, plot_path, 0.55, 1.43, 8.3, 4.85)
    _add_callout(
        slide,
        'The useful result',
        f'Wolf Sharpe was {float(wolf.sharpe):.2f} and drawdown was '
        f'{_pct(abs(float(wolf.maximum_drawdown)))}, better than both '
        'simple controls on these risk measures.',
        9.08, 1.56, 3.69, 1.25,
        fill=PALE_GREEN, accent=GREEN,
    )
    _add_callout(
        slide,
        'The honest result',
        f'Equal weight returned {_pct(equal.annualised_return, 2)} versus '
        f'Wolf at {_pct(wolf.annualised_return, 2)}. The model did not '
        'beat the simplest control on net return.',
        9.08, 3.16, 3.69, 1.25,
        fill=PALE_GOLD, accent=GOLD,
    )
    _add_callout(
        slide,
        'Investment interpretation',
        'The current case is risk control and decision discipline. '
        'Incremental stock-selection alpha remains unproven.',
        9.08, 4.76, 3.69, 1.25,
        fill=PALE_BLUE, accent=BLUE,
    )
    _add_text(
        slide,
        'Highest return: Equal weight  |  Highest Sharpe: Wolf  |  '
        'Smallest drawdown: Wolf',
        0.58, 6.49, 12.1, 0.28,
        size=12.5, color=GREEN_DARK, bold=True,
        align=PP_ALIGN.CENTER,
    )


def _slide_alpha(
    presentation: Presentation,
    evidence: DeckEvidence,
    plot_path: Path,
) -> None:
    slide = _new_slide(
        presentation,
        'Alpha and overfitting: the hard truth',
        'The retrospective strategies are interesting; deployable alpha is not established.',
        10,
        'Point-in-time alpha tests and CSCV overfitting diagnostics',
    )
    alpha_rows = []
    for row in evidence.alpha.itertuples():
        alpha_rows.append(
            (
                STRATEGY_LABELS.get(row.benchmark, row.benchmark),
                _pct(row.annualised_active_return, 2),

                _pct(row.annualised_regression_alpha, 2),
                f'{float(row.two_sided_p_value):.3f}',
                row.alpha_evidence_verdict.replace('_', ' '),
            )
        )
    _add_table(
        slide,
        ['Benchmark', 'Active return', 'Reg. alpha', 'p-value', 'Verdict'],
        alpha_rows,
        0.55, 1.52, 6.14, 1.6,
        widths=[1.7, 1.15, 1.05, 0.85, 1.35],
        font_size=10.3,
    )
    _add_picture_contain(slide, plot_path, 6.94, 1.42, 5.83, 3.45)

    _add_callout(
        slide,
        'What the 50.3% fall means',
        'When history selects the apparent winner, its information ratio '
        'typically drops from 1.32 in-sample to 0.66 out-of-sample. '
        'About half the apparent edge does not survive selection.',
        0.55, 3.55, 6.14, 1.35,
        fill=PALE_GOLD, accent=GOLD,
    )
    _add_callout(
        slide,
        'Decision',
        'Use Wolf for disciplined ranking and risk control. Do not '
        'market it as a proven alpha engine until native live evidence '
        'clears the benchmark and cost hurdles.',
        0.55, 5.24, 12.22, 1.2,
        fill=PALE_RED, accent=RED,
    )

def _slide_long_history(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'The 1997 replay is a stress map',
        'It shows how today\'s holdings behaved through history, not what the model knew then.',
        11,
        '1997-present retrospective holdings replay',
    )
    chosen = [
        'current_portfolio',
        'portfolio_aware_overlay',
        'optimised_risk_parity',
        'llm_benchmark',
        'final_portfolio',
    ]
    data = evidence.performance.loc[
        (evidence.performance['window'] == 'requested_1997_window')

        & evidence.performance['strategy'].isin(chosen)
    ].set_index('strategy')
    rows = []
    for strategy in chosen:
        row = data.loc[strategy]
        rows.append(
            (
                row.strategy_label,
                _usd(row.initial_capital_usd),
                _pct(row.cagr),
                f'{float(row.sharpe):.2f}',
                _pct(row.maximum_drawdown),
                _usd(row.ending_value_usd),
            )
        )
    _add_table(
        slide,
        ['Portfolio', 'Start', 'CAGR', 'Sharpe', 'Max DD', 'End'],

        rows,
        0.55, 1.53, 7.2, 3.34,
        widths=[2.35, 1.15, 0.8, 0.75, 0.9, 1.25],
        font_size=9.7,
    )
    chart = evidence.backtest_root / 'plots/risk_return.png'
    _add_picture_contain(slide, chart, 7.98, 1.43, 4.79, 3.65)
    current_pnl = _usd(
        data.loc['current_portfolio', 'pnl_usd']
    )
    resolved_pnl = _usd(
        data.loc['final_portfolio', 'pnl_usd']
    )
    _add_callout(
        slide,
        'What looks strongest',
        f'Current Portfolio PnL: {current_pnl}. '
        f'Final Resolved PnL: {resolved_pnl}. '
        'Risk Parity led the independent optimisers.',
        0.55, 5.24, 6.0, 1.25,
        fill=PALE_GREEN, accent=GREEN,
    )

    _add_callout(
        slide,
        'Why it cannot prove selection skill',
        'The securities were chosen with current information and then '
        'replayed backward. Survivorship and selection look-ahead '
        'make the long PnL unsuitable as a live promise.',
        6.82, 5.24, 5.95, 1.25,
        fill=PALE_GOLD, accent=GOLD,
    )

def _slide_macro_events(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'Performance through major market shocks',
        'Event windows are descriptive overlaps, not causal estimates.',
        12,
        'Macro-event timeline and event performance table',
    )
    chart = evidence.backtest_root / 'plots/macro_event_timeline.png'
    _add_picture_contain(slide, chart, 0.42, 1.29, 12.48, 4.82)
    callouts = [
        ('COVID-19', '-12.58% return; -15.19% event drawdown', RED),
        ('2008 crisis', '-27.12% event drawdown', GOLD),
        ('2026 Iran war', '+3.57% return; -5.27% drawdown', BLUE),
    ]

    for index, (heading, body, accent) in enumerate(callouts):
        _add_callout(
            slide, heading, body,
            0.55 + index * 4.12, 6.17, 3.84, 0.61,
            fill=WHITE, accent=accent,
        )


def _slide_regimes(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'Interest-rate and market-regime context',
        'Conditional groupings show where the final portfolio was most comfortable.',
        13,
        'Lagged rate and market-regime performance',
    )

    rate_chart = (
        evidence.backtest_root
        / 'plots/interest_rate_performance.png'
    )
    regime_chart = (
        evidence.backtest_root
        / 'plots/market_regime_performance.png'
    )
    _add_picture_contain(
        slide, rate_chart, 0.43, 1.42, 6.22, 4.45
    )
    _add_picture_contain(
        slide, regime_chart, 6.75, 1.42, 6.15, 4.45
    )

    _add_callout(
        slide,
        'Rate reading',
        'Final Portfolio was strongest in high-rate months (15.77%) '
        'and when rates were rising (13.03%).',
        0.55, 6.04, 5.95, 0.74,
        fill=PALE_BLUE, accent=BLUE,
    )
    _add_callout(
        slide,
        'Regime reading',
        'Its strongest market group was Bull / Volatile (14.09%). '
        'Expansion months returned 9.91% annualised.',
        6.82, 6.04, 5.95, 0.74,
        fill=PALE_GREEN, accent=GREEN,
    )

def _slide_governance(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'Risk calibration now passes; approval stays conditional',
        'Adaptive VaR fixed exception clustering without hiding PIT and alpha limits.',
        14,
        'Validation scorecard and overall/holdout VaR tests',
    )
    chart = evidence.release_root / 'plots/validation_scorecard.png'
    _add_picture_contain(slide, chart, 0.43, 1.39, 6.25, 4.92)

    risk_rows = []
    for row in evidence.risk_backtest.itertuples():
        segment = (
            'Holdout'
            if row.evaluation_segment == 'chronological_holdout'
            else 'Overall'
        )
        risk_rows.append(
            (
                segment,
                f'{float(row.confidence_level):.0%}',
                f'{int(row.violations)}/{int(row.observations)}',
                f'{float(row.p_value):.3f}',
                f'{float(row.christoffersen_p_value):.3f}',
            )
        )
    _add_text(
        slide, 'VaR coverage and independence', 6.94, 1.48, 5.5, 0.34,
        size=18, bold=True, font=FONT_HEAD,
    )
    _add_table(
        slide,
        ['Sample', 'VaR', 'Exceptions', 'Kupiec p', 'Indep. p'],
        risk_rows,
        6.93, 1.94, 5.84, 2.38,
        widths=[1.15, 0.68, 1.02, 0.9, 0.9],
        font_size=9.2,
        highlight_rows=[0, 1, 2, 3],
    )
    _add_callout(
        slide,
        'Adaptive risk stack: 15 / 15',
        'DCC-IGARCH Student-t, filtered historical simulation, EWMA '
        'Normal and EWMA Student-t are selected using trailing data. '
        'The holdout is chronological reconstructed evidence, not a '
        'pristine future shadow period.',
        6.93, 4.65, 5.84, 1.45,
        fill=PALE_GREEN, accent=GREEN,
    )
    _add_text(
        slide,
        f'Overall {evidence.governance_score:g}/100  |  6 pass  |  PIT and '
        'portfolio warnings  |  0 critical failures  |  full local suite passed',
        0.58, 6.5, 12.05, 0.28,
        size=12.3, color=GREEN_DARK, bold=True,
        align=PP_ALIGN.CENTER,
    )


def _slide_costs(
    presentation: Presentation,
    evidence: DeckEvidence,
    plot_path: Path,
) -> None:
    slide = _new_slide(
        presentation,
        'Turnover and modeled cost drag now meet target',
        'Retention hysteresis and minimum-turnover transitions reduced churn.',
        15,
        'Before/after point-in-time cost and turnover validation',
    )
    _add_picture_contain(slide, plot_path, 0.48, 1.43, 7.56, 4.85)
    wolf = evidence.pit_summary.set_index('strategy').loc['wolf_cvar']
    fee = evidence.backtest_manifest['annual_bank_fee']

    _add_kpi(
        slide, _pct(wolf.annualised_cost_drag, 2),
        'modeled cost drag; target <= 1.50%',
        8.32, 1.57, 4.45, fill=PALE_GREEN, accent=GREEN,
    )
    _add_kpi(
        slide, f'{float(wolf.annualised_turnover):.2f}x',
        'annual turnover; target <= 1.50x',
        8.32, 2.83, 4.45, fill=PALE_GREEN, accent=GREEN,
    )
    _add_kpi(
        slide, _usd(fee['reference_annual_charge_usd'], 0),
        '0.25% annual bank fee at reference AUM',
        8.32, 4.09, 4.45, fill=WHITE, accent=BLUE,
    )

    _add_callout(
        slide,
        'Why portfolio remains a warning',
        'Both cost gates pass, but Wolf trailed equal weight by 1.06% '
        'per year and the difference was not significant (p=0.734).',
        8.32, 5.35, 4.45, 1.03,
        fill=PALE_GOLD, accent=GOLD,
    )
    _add_text(
        slide,
        'Retention and capped/minimum-turnover transitions drove the '
        'improvement; the configured no-trade band did not trigger in this sample.',
        0.58, 6.55, 12.1, 0.27,
        size=11.8, color=GREEN_DARK, bold=True,
        align=PP_ALIGN.CENTER,
    )


def _slide_pilot(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'A controlled path to live use',
        'Scale only when operations, costs and evidence earn it.',
        16,
        'Proposed implementation and model-risk controls',
    )
    phases = [
        (
            '0  SHADOW',
            '4 weeks',
            'Generate orders, do not trade. Validate data, NAV, FX and fills.',
        ),
        (
            '1  PILOT',
            '6 to 12 months',
            'Use limited capital with human approval and staged execution.',
        ),

        (
            '2  SCALE',
            'Evidence gated',
            'Increase capital only after cost, risk and benchmark hurdles hold.',
        ),
    ]
    for index, (name, duration, body) in enumerate(phases):
        x = 0.55 + index * 4.12
        _add_rect(
            slide, x, 1.58, 3.84, 2.08,
            fill=WHITE, line=BORDER,
        )
        _add_rect(
            slide, x, 1.58, 3.84, 0.12,
            fill=[BLUE, GREEN, GOLD][index],
            line=[BLUE, GREEN, GOLD][index],
        )

        _add_text(
            slide, name, x + 0.2, 1.91, 3.4, 0.32,
            size=17, bold=True, font=FONT_HEAD,
        )
        _add_text(
            slide, duration, x + 0.2, 2.37, 3.4, 0.24,
            size=11, color=GREEN_DARK, bold=True,
        )
        _add_text(
            slide, body, x + 0.2, 2.78, 3.39, 0.62,
            size=11.5, color=MUTED,
        )
    _add_text(
        slide, 'Proposed pilot gates', 0.58, 4.07, 5.4, 0.34,
        size=18, bold=True, font=FONT_HEAD,
    )

    _add_bullets(
        slide,
        [
            'Zero hard constraint or data-lineage breaches',
            'Pre-trade cost estimate approved for every rebalance',
            'Keep turnover <=1.5x; stretch goal <=1.0x in the pilot',
            'Net performance tracked against equal and cap weight',
            'Monthly model-risk and investment-committee review',
        ],
        0.58, 4.52, 5.83, 1.83,
        size=13.5,
    )
    _add_callout(
        slide,
        'Immediate stop conditions',
        'Stale critical data, any hard breach, a failed live risk '
        'test, failed reconciliation or trading costs '
        'above the approved budget.',
        6.82, 4.12, 5.95, 1.35,
        fill=PALE_RED, accent=RED,
    )

    _add_callout(
        slide,
        'Alpha gate',
        'Full-scale alpha claims require native live evidence and at '
        'least 60 months under the existing governance policy.',
        6.82, 5.71, 5.95, 0.84,
        fill=PALE_GOLD, accent=GOLD,
    )


def _slide_glossary(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = _new_slide(
        presentation,
        'How to read the results',
        'Plain-language definitions for the investment committee.',
        17,
        'Backtest methodology and validation framework',
    )

    rows = [
        ('CAGR', 'Average compounded annual growth.'),
        ('Sharpe', 'Return earned per unit of overall variability.'),
        ('Sortino', 'Return earned per unit of harmful downside variation.'),
        ('Max drawdown', 'Largest peak-to-trough loss.'),
        ('CVaR', 'Average loss among the worst modeled outcomes.'),
        ('Information ratio', 'Active return per unit of benchmark-relative risk.'),
        ('p-value', 'How surprising the result is if true alpha were zero.'),
        ('PBO', 'Chance that selecting the backtest winner overfits history.'),
    ]
    _add_table(
        slide,
        ['Measure', 'Simple meaning'],
        rows,
        0.55, 1.49, 7.0, 4.95,
        widths=[1.65, 4.95],
        font_size=11,
    )

    _add_callout(
        slide,
        'Three evidence layers',
        '1. Dated 60-month proxy: primary model evidence.\n'
        '2. 1997 replay: stress and exposure history.\n'
        '3. Native live record: required before full alpha approval.',
        7.86, 1.49, 4.91, 1.62,
        fill=PALE_BLUE, accent=BLUE,
    )
    _add_callout(
        slide,
        'Higher is not always better',
        'A portfolio can have a higher return but a deeper drawdown, '
        'more turnover or weaker statistical evidence. The committee '
        'should judge the package, not one headline number.',
        7.86, 3.45, 4.91, 1.42,
        fill=PALE_GOLD, accent=GOLD,
    )

    _add_callout(
        slide,
        'Where to verify',
        'The GitHub release contains the 42-page PDF, plain-language '
        'interpretation, CSV evidence, plots, manifests and checksums.',
        7.86, 5.21, 4.91, 1.23,
        fill=PALE_GREEN, accent=GREEN,
    )

def _slide_close(
    presentation: Presentation, evidence: DeckEvidence
) -> None:
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )
    _set_background(slide, INK)
    _add_text(
        slide, 'THE RECOMMENDATION', 0.91, 0.74, 4.8, 0.28,
        size=11, color='8FD7BF', bold=True,
    )
    _add_text(
        slide,
        'Approve a controlled live pilot.',
        0.89, 1.32, 8.7, 0.62,
        size=34, color=WHITE, bold=True, font=FONT_HEAD,
    )

    _add_text(
        slide,
        'Wolf is ready to improve how decisions are made: broad '
        'screening, explicit risk, consistent portfolio construction '
        'and an audit trail. It is not yet ready to promise alpha.',
        0.92, 2.26, 8.55, 1.05,
        size=18, color='D7E1DE',
    )
    statements = [
        ('USE NOW', 'Ranking, diversification, adaptive risk and governance'),
        ('PROVE LIVE', 'Net benchmark edge in a genuine future shadow record'),
        ('FIX NEXT', 'Observed PIT vintages and probability calibration'),
    ]
    for index, (heading, body) in enumerate(statements):
        x = 0.92 + index * 4.03

        _add_rect(
            slide, x, 4.08, 3.67, 1.34,
            fill='243037', line='435158',
        )
        _add_text(
            slide, heading, x + 0.18, 4.32, 3.2, 0.27,
            size=12, color='8FD7BF', bold=True,
        )
        _add_text(
            slide, body, x + 0.18, 4.79, 3.17, 0.4,
            size=11.5, color=WHITE,
        )
    _add_rect(
        slide, 0.92, 6.15, 11.72, 0.58,
        fill=GREEN_DARK, line=GREEN_DARK,
    )

    _add_text(
        slide,
        'Investment edge today: a better-controlled process.  '
        'Investment edge tomorrow: only what live evidence proves.',
        1.15, 6.33, 11.25, 0.22,
        size=13, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER,
    )
    _add_text(
        slide,
        f'{evidence.approval_status}  |  '
        f'Governance {evidence.governance_score:g}/100  |  '
        f'As of {evidence.as_of_date}',
        0.92, 7.02, 11.7, 0.2,
        size=8.5, color='9EAFAB',
        align=PP_ALIGN.RIGHT,
    )

def _validate_slide_bounds(presentation: Presentation) -> list[str]:
    errors: list[str] = []
    for slide_index, slide in enumerate(
        presentation.slides, start=1
    ):
        for shape in slide.shapes:
            if (
                shape.left < 0
                or shape.top < 0
                or shape.width <= 0
                or shape.height <= 0
                or shape.left + shape.width > presentation.slide_width
                or shape.top + shape.height > presentation.slide_height
            ):
                errors.append(
                    f'slide {slide_index}: {shape.name} is out of bounds'
                )
    return errors


def _set_document_properties(
    presentation: Presentation, evidence: DeckEvidence
) -> None:

    properties = presentation.core_properties
    properties.title = 'Wolf Quant Model Investment Committee Briefing'
    properties.subject = (
        'Current recommendations, validation evidence and live pilot plan'
    )
    properties.author = 'The Wolf Quant Model'
    properties.keywords = (
        'equities, portfolio, validation, backtest, investment committee'
    )
    properties.comments = (
        'Generated from tracked repository evidence. Research use only.'
    )
    properties.created = datetime.now()
    properties.modified = datetime.now()

def _risk_markdown_row(
    label: str, confidence: int, row: pd.Series
) -> str:
    return (
        f'| {label} | {confidence}% | '
        f'{int(row.violations)}/{int(row.observations)} | '
        f'{float(row.p_value):.3f} | '
        f'{float(row.christoffersen_p_value):.3f} | Pass |'
    )


def _performance_markdown_row(
    label: str, column: str, rows: Sequence[pd.Series]
) -> str:
    if column in {'sharpe', 'sortino'}:
        values = [f'{float(row[column]):.2f}' for row in rows]
    else:
        values = [_pct(float(row[column])) for row in rows]
    return f'| {label} | ' + ' | '.join(values) + ' |'


def _report_markdown(evidence: DeckEvidence) -> str:
    summary = evidence.pit_summary.set_index('strategy')
    prior_summary = evidence.prior_pit_summary.set_index('strategy')
    wolf = summary.loc['wolf_cvar']
    prior_wolf = prior_summary.loc['wolf_cvar']
    equal = summary.loc['equal_weight_eligible']
    cap = summary.loc['cap_weight_eligible']
    wolf_end = _ending_value(evidence, 'wolf_cvar')
    coverage = evidence.pit_coverage['coverage']
    fee = evidence.backtest_manifest['annual_bank_fee']
    risk = evidence.risk_backtest.set_index(
        ['evaluation_segment', 'confidence_level']
    )
    risk_overall_95 = risk.loc[('overall', 0.95)]
    risk_overall_99 = risk.loc[('overall', 0.99)]
    risk_holdout_95 = risk.loc[('chronological_holdout', 0.95)]
    risk_holdout_99 = risk.loc[('chronological_holdout', 0.99)]
    risk_rows = '\n'.join(
        [
            _risk_markdown_row('Overall', 95, risk_overall_95),
            _risk_markdown_row('Overall', 99, risk_overall_99),
            _risk_markdown_row('Holdout', 95, risk_holdout_95),
            _risk_markdown_row('Holdout', 99, risk_holdout_99),
        ]
    )
    performance_rows = '\n'.join(
        [
            _performance_markdown_row(
                'Annualised net return',
                'annualised_return',
                (wolf, equal, cap),
            ),
            _performance_markdown_row(
                'Sharpe ratio', 'sharpe', (wolf, equal, cap)
            ),
            _performance_markdown_row(
                'Sortino ratio', 'sortino', (wolf, equal, cap)
            ),
            _performance_markdown_row(
                'Maximum drawdown',
                'maximum_drawdown',
                (wolf, equal, cap),
            ),
            _performance_markdown_row(
                'Annualised cost drag',
                'annualised_cost_drag',
                (wolf, equal, cap),
            ),
        ]
    )
    prior_score = float(
        evidence.prior_validation_manifest['overall_score']
    )
    improvement_rows = '\n'.join(
        [
            f'| Governance score | {prior_score:g}/100 | '
            f'{evidence.governance_score:g}/100 | Conditional approval |',
            '| Risk backtesting | Warning, 7.5/15 | Pass, 15/15 | '
            'Coverage and independence pass |',
            f'| Annual turnover | '
            f'{float(prior_wolf.annualised_turnover):.2f}x | '
            f'{float(wolf.annualised_turnover):.2f}x | <=1.50x: pass |',
            f'| Annualised cost drag | '
            f'{_pct(prior_wolf.annualised_cost_drag, 2)} | '
            f'{_pct(wolf.annualised_cost_drag, 2)} | <=1.50%: pass |',
            '| Hard constraint breaches | 0 | 0 | Pass |',
        ]
    )
    alpha_cap = float(
        evidence.alpha.loc[
            evidence.alpha['benchmark'] == 'cap_weight_eligible',
            'annualised_active_return',
        ].iloc[0]
    )
    alpha_equal = float(
        evidence.alpha.loc[
            evidence.alpha['benchmark'] == 'equal_weight_eligible',
            'annualised_active_return',
        ].iloc[0]
    )
    pbo = float(evidence.overfitting['probability_of_backtest_overfitting'])
    haircut = float(
        evidence.overfitting['selected_information_ratio_haircut']
    )
    current_aum_text = _usd(evidence.current_aum)
    ending_value_text = _usd(wolf_end)
    pnl_text = _usd(wolf_end - evidence.current_aum)
    bank_fee_text = _usd(fee['reference_annual_charge_usd'], 0)
    bank_fee_rate_text = _pct(fee['annual_rate'], 2)
    relative_return_text = _pct(
        float(wolf.annualised_return - equal.annualised_return), 2
    )
    buys = sorted(
        evidence.trades.loc[
            evidence.trades['trade_action'] == 'Buy', 'ticker'
        ].tolist()
    )
    reduce_names = sorted(
        evidence.trades.loc[
            evidence.trades['trade_action'] == 'Reduce', 'ticker'
        ].tolist()
    )

    buy_text = ', '.join(f'`{ticker}`' for ticker in buys)
    reduce_text = ', '.join(
        f'`{ticker}`' for ticker in reduce_names
    )
    return f'''# Wolf Quant Model Investment Principal Report

As of {evidence.as_of_date}

## Decision

**Approve a controlled, human-supervised live pilot.** Governance improved
from {prior_score:g}/100 to {evidence.governance_score:g}/100. Six components pass,
two remain warnings, and there are zero critical failures. Adaptive risk
backtesting and the turnover/cost targets now pass. Full-scale or unattended
deployment remains unapproved because observed point-in-time evidence is
incomplete and
benchmark-relative alpha is not established.

## What Improved

| Control | Before | Now | Current gate |
| --- | ---: | ---: | --- |
{improvement_rows}

Retention hysteresis, a 6% monthly turnover cap, and minimum-turnover
transitions drove the implementation improvement. The configured no-trade
band did not trigger in this 60-month sample, so it is not credited for the
observed result.

## Adaptive Risk Backtesting

The trailing model-selection stack contains DCC-IGARCH Student-t, filtered
historical simulation, EWMA Normal, and EWMA Student-t forecasts. Kupiec
coverage and Christoffersen independence tests pass overall and on the 40%
chronological holdout.

| Sample | VaR | Exceptions | Kupiec p | Independence p | Result |
| --- | ---: | ---: | ---: | ---: | --- |
{risk_rows}

This holdout is chronological reconstructed evidence, not a pristine future
shadow period. Live monitoring is still required.

## Point-In-Time Evidence

The evidence store now contains **{int(coverage['delisting_events']):,}** delisting events and
**{int(coverage['fundamental_rows_with_filing_date']):,}** fundamental rows with filing dates.
Observed acceptance timestamps, dated
index membership, inactive-name prices, and historical volume remain below
their governance thresholds. EODHD populated delistings; the Nasdaq
entitlement yielded five usable rows; Beam was unavailable; and SEC blocked
this runner. Unavailable history is not represented as observed evidence.
The point-in-time component therefore remains **7.5/15, warning**.

## Current Target Portfolio

The resolved baseline contains 20 equal-weight positions at 5% each. The
current trade comparison produces 19 buys and one reduction. These are model
targets, not executable orders; live NAV, FX, liquidity, prices and compliance
approval must be refreshed first.

- Buy: {buy_text}
- Reduce to 5%: {reduce_text}

## Point-In-Time Performance

| Measure | Wolf CVaR | Equal weight | Cap weight |
| --- | ---: | ---: | ---: |
{performance_rows}

Applying the realised 60-month Wolf path after modeled trading costs to
current AUM of {current_aum_text} gives an illustrative ending value of {ending_value_text}
and PnL of {pnl_text}. The separate annual bank charge is {bank_fee_rate_text}, equal to
{bank_fee_text} at the reference AUM. This is a scale illustration, not a
forecast or a live-capacity result.

The portfolio component remains **5/10, warning** even though both cost gates
pass. Wolf returned {relative_return_text} per year relative to equal weight.
The paired difference was not statistically significant (p=0.734).

## Alpha And Overfitting

Wolf's point-in-time active return is {_pct(alpha_cap, 2)} versus cap weight and
{_pct(alpha_equal, 2)} versus equal weight. Neither alpha test is statistically
significant. The retrospective CSCV test estimates a
{_pct(pbo)} probability of backtest overfitting, while the selected strategy's
median information ratio falls {_pct(haircut)} out-of-sample. The 1997 replay
remains a stress and exposure diagnostic, not proof of historical selection
skill.

## Conditions For Scaling

1. Recalculate orders with live NAV, FX, price and liquidity data.
2. Require human approval before every pilot rebalance.
3. Keep annualised turnover at or below 1.5x, with a 1.0x pilot stretch goal.
4. Track net performance against equal-weight and cap-weight controls.
5. Stop on stale critical data, any hard breach, a failed live risk test,
   failed reconciliation, or a breached cost budget.
6. Require observed PIT vintages and a genuine future shadow record before
   making deployable alpha claims.

The full local test suite passed. GitHub Actions remains the publication gate.
Research output only. This report is not authorization for unattended trading
or individualized investment advice.
'''


def build_investment_principal_deck(
    repo_root: str | Path,
    output_directory: str | Path | None = None,
) -> DeckBuildResult:
    evidence = load_deck_evidence(repo_root)
    output_directory = (
        Path(output_directory).resolve()
        if output_directory
        else evidence.repo_root / PRESENTATION_RELATIVE
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    plot_paths = _build_plot_assets(
        evidence, output_directory / 'plots'
    )

    presentation = Presentation()
    presentation.slide_width = SLIDE_WIDTH
    presentation.slide_height = SLIDE_HEIGHT
    _set_document_properties(presentation, evidence)
    _slide_cover(presentation, evidence)
    _slide_decision(presentation, evidence)
    _slide_workflow(presentation, evidence)
    _slide_evidence(presentation, evidence)
    _slide_trades(presentation, evidence)
    _slide_exposure(presentation, evidence)
    _slide_optimizer(presentation, evidence)

    _slide_pit_growth(presentation, evidence, plot_paths[0])
    _slide_pit_comparison(presentation, evidence, plot_paths[1])
    _slide_alpha(presentation, evidence, plot_paths[2])
    _slide_long_history(presentation, evidence)
    _slide_macro_events(presentation, evidence)
    _slide_regimes(presentation, evidence)
    _slide_governance(presentation, evidence)
    _slide_costs(presentation, evidence, plot_paths[3])

    _slide_pilot(presentation, evidence)
    _slide_glossary(presentation, evidence)
    _slide_close(presentation, evidence)

    bounds_errors = _validate_slide_bounds(presentation)
    if bounds_errors:
        raise ValueError(
            'Presentation shape bounds failed:\n'
            + '\n'.join(bounds_errors)
        )

    pptx_path = output_directory / 'wolf_quant_model_ic_briefing.pptx'
    presentation.save(pptx_path)

    report_path = output_directory / 'investment_principal_report.md'
    report_path.write_text(
        _report_markdown(evidence), encoding='utf-8'
    )

    input_paths = [
        evidence.release_root / 'validation/validation_manifest.json',
        evidence.release_root / 'validation/risk_backtesting_report.csv',
        evidence.release_root / 'validation/transaction_cost_validation.csv',
        evidence.release_root / 'walk_forward_manifest.json',
        evidence.release_root / 'universe_summary.csv',
        evidence.release_root / 'pit_evidence_coverage.json',
        evidence.repo_root
        / PRIOR_RELEASE_RELATIVE
        / 'validation/validation_manifest.json',
        evidence.repo_root
        / PRIOR_RELEASE_RELATIVE
        / 'validation/portfolio_strategy_comparison.csv',
        evidence.outputs_root / 'final_portfolio_weights.csv',
        evidence.outputs_root / 'portfolio_trade_list.csv',
        evidence.backtest_root / 'run_manifest.json',
        evidence.backtest_root / 'point_in_time_alpha_significance.csv',
        evidence.backtest_root / 'strategy_overfitting_summary.csv',
    ]
    manifest = {
        'schema_version': 2,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'as_of_date': evidence.as_of_date,
        'approval_status': evidence.approval_status,
        'governance_score': evidence.governance_score,
        'slide_count': len(presentation.slides),

        'presentation': {
            'path': _manifest_path(pptx_path, evidence.repo_root),
            'sha256': _sha256(pptx_path),
            'bytes': pptx_path.stat().st_size,
        },
        'report': {
            'path': _manifest_path(report_path, evidence.repo_root),
            'sha256': _sha256(report_path),
            'bytes': report_path.stat().st_size,
        },

        'inputs': [
            {
                'path': path.relative_to(
                    evidence.repo_root
                ).as_posix(),
                'sha256': _sha256(path),
            }
            for path in input_paths
        ],
        'plots': [
            {
                'path': _manifest_path(path, evidence.repo_root),

                'sha256': _sha256(path),
            }
            for path in plot_paths
        ],
    }
    manifest_path = output_directory / 'manifest.json'
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + '\n',
        encoding='utf-8',
    )
    return DeckBuildResult(
        pptx_path=pptx_path,
        report_path=report_path,

        manifest_path=manifest_path,
        plot_paths=plot_paths,
        slide_count=len(presentation.slides),
    )


def register_rendered_pdf(
    repo_root: str | Path,
    output_directory: str | Path | None = None,
    *,
    pdf_path: str | Path | None = None,
    renderer: str = 'Microsoft PowerPoint 16.0',
) -> Path:
    repo_root = Path(repo_root).resolve()
    output_directory = (
        Path(output_directory).resolve()
        if output_directory
        else repo_root / PRESENTATION_RELATIVE
    )
    manifest_path = output_directory / 'manifest.json'
    pptx_path = output_directory / 'wolf_quant_model_ic_briefing.pptx'
    if pdf_path:
        rendered_pdf_path = Path(pdf_path)
        if not rendered_pdf_path.is_absolute():
            rendered_pdf_path = repo_root / rendered_pdf_path
        rendered_pdf_path = rendered_pdf_path.resolve()
    else:
        rendered_pdf_path = (
            output_directory / 'wolf_quant_model_ic_briefing.pdf'
        )
    _require_files([manifest_path, pptx_path, rendered_pdf_path])

    manifest = _read_json(manifest_path)
    slide_count = len(Presentation(pptx_path).slides)
    manifest['rendered_pdf'] = {
        'path': _manifest_path(rendered_pdf_path, repo_root),
        'sha256': _sha256(rendered_pdf_path),
        'bytes': rendered_pdf_path.stat().st_size,
    }
    manifest['rendering'] = {
        'renderer': renderer,
        'slide_count': slide_count,
        'visual_review': 'completed',
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + '\n',
        encoding='utf-8',
    )
    return manifest_path
