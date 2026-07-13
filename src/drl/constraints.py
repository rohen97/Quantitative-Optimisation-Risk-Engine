from __future__ import annotations


def long_only_action_valid(weights) -> bool:
    return bool((weights >= 0).all())
