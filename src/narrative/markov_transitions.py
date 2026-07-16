from __future__ import annotations

import pandas as pd


def build_markov_transitions(distances_with_states: pd.DataFrame, window_days: int = 180) -> pd.DataFrame:
    """Build first-order and second-order Markov transition probabilities over narrative states."""
    if distances_with_states.empty or "narrative_state" not in distances_with_states.columns:
        return pd.DataFrame()
    rows = []
    for (security_id, ticker), group in distances_with_states.sort_values("publication_timestamp").groupby(["security_id", "ticker"]):
        states = group["narrative_state"].tolist()
        first_counts: dict[tuple[str, str], int] = {}
        for left, right in zip(states, states[1:]):
            first_counts[(left, right)] = first_counts.get((left, right), 0) + 1
        totals: dict[str, int] = {}
        for left, _ in first_counts:
            totals[left] = totals.get(left, 0) + first_counts[(left, _)]
        for (left, right), count in first_counts.items():
            rows.append(
                {
                    "security_id": security_id,
                    "ticker": ticker,
                    "transition_order": 1,
                    "from_state": left,
                    "intermediate_state": "",
                    "to_state": right,
                    "transition_probability": count / max(totals.get(left, count), 1),
                    "transition_count": count,
                    "window_days": window_days,
                }
            )
        second_counts: dict[tuple[str, str, str], int] = {}
        for first, middle, last in zip(states, states[1:], states[2:]):
            second_counts[(first, middle, last)] = second_counts.get((first, middle, last), 0) + 1
        for (first, middle, last), count in second_counts.items():
            denom = sum(value for key, value in second_counts.items() if key[0] == first and key[1] == middle)
            rows.append(
                {
                    "security_id": security_id,
                    "ticker": ticker,
                    "transition_order": 2,
                    "from_state": first,
                    "intermediate_state": middle,
                    "to_state": last,
                    "transition_probability": count / max(denom, 1),
                    "transition_count": count,
                    "window_days": window_days,
                }
            )
    return pd.DataFrame(rows)
