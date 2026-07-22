import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_script(script: str, timeout: int = 300) -> None:
    result = subprocess.run(
        [sys.executable, script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_drl_and_full_pipeline_scripts_run_and_write_expected_outputs():
    _run_script("scripts/run_full_pipeline.py", timeout=420)
    for script in [
        "scripts/run_drl_environment_check.py",
        "scripts/run_drl_training.py",
        "scripts/run_drl_backtest.py",
        "scripts/run_drl_explainability.py",
        "scripts/run_drl_pipeline.py",
    ]:
        _run_script(script, timeout=300)

    output_dir = REPO_ROOT / "reports" / "outputs"
    expected = [
        "drl_state_schema.csv",
        "drl_training_summary.csv",
        "drl_seed_results.csv",
        "drl_backtest_results.csv",
        "drl_benchmark_comparison.csv",
        "drl_acceptance_decision.csv",
        "drl_baseline_portfolio.csv",
        "drl_challenger_portfolio.csv",
        "drl_final_selected_weights_source.csv",
        "drl_target_weights.csv",
        "drl_trade_list.csv",
        "drl_constraint_adjustments.csv",
        "drl_reward_decomposition.csv",
        "drl_regime_agent_weights.csv",
        "drl_risk_throttle.csv",
        "drl_explanations.csv",
        "drl_feature_attributions.csv",
        "drl_asset_time_attributions.csv",
        "drl_ablation_results.csv",
        "drl_model_card.md",
        "drl_validation_report.md",
        "final_recommendations.csv",
    ]
    missing = [filename for filename in expected if not (output_dir / filename).exists()]
    assert not missing
