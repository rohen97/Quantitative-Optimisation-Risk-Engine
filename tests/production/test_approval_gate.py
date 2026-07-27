from __future__ import annotations

from src.production.approval_gate import evaluate_approval_gate


def test_approval_gate_blocks_constraint_failure():
    result = evaluate_approval_gate(True, True, True, False, True, True, True, [], [])
    assert not result.approved
    assert "Hard portfolio constraints failed." in result.critical_failures


def test_approval_gate_allows_warnings():
    result = evaluate_approval_gate(True, True, True, True, True, True, True, [], ["freshness warning"])
    assert result.approved
    assert result.status == "APPROVED_WITH_WARNINGS"
