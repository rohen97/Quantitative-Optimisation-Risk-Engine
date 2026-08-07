from __future__ import annotations

import pandas as pd


HORIZON_MONTHS = {'3M': 3, '6M': 6, '9M': 9, '12M': 12}


def add_realisation_dates(forecasts: pd.DataFrame) -> pd.DataFrame:
    required = {'security_id', 'forecast_date', 'horizon'}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f'Missing forecast alignment columns: {sorted(missing)}')
    result = forecasts.copy()
    result['forecast_date'] = pd.to_datetime(result['forecast_date'], errors='raise')
    invalid = set(result['horizon'].dropna().unique()).difference(HORIZON_MONTHS)
    if invalid:
        raise ValueError(f'Unsupported horizons: {sorted(invalid)}')
    result['realisation_date'] = result.apply(
        lambda row: row['forecast_date']
        + pd.DateOffset(months=HORIZON_MONTHS[row['horizon']]),
        axis=1,
    )
    return result


def _align_keyed_outcomes(
    forecasts: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    left = forecasts.copy()
    right = outcomes.copy()
    left['as_of_date'] = pd.to_datetime(left['as_of_date'])
    right['as_of_date'] = pd.to_datetime(right['as_of_date'])
    keys = ['security_id', 'as_of_date']
    if 'horizon' in left and 'horizon' in right:
        left['horizon'] = left['horizon'].astype(str).str.upper()
        right['horizon'] = right['horizon'].astype(str).str.upper()
        keys.append('horizon')
    elif 'horizon_months' in left and 'horizon_months' in right:
        keys.append('horizon_months')
    realised_column = (
        'realised_return' if 'realised_return' in right else 'return'
    )
    outcome_columns = [
        column
        for column in (
            *keys,
            realised_column,
            'target_date',
            'outcome_date',
            'end_trade_date',
        )
        if column in right
    ]
    right = right[outcome_columns].drop_duplicates(keys, keep='last')
    if realised_column != 'realised_return':
        right = right.rename(columns={realised_column: 'realised_return'})
    return left.merge(right, on=keys, how='left', validate='many_to_one')


def align_forecasts_with_outcomes(
    forecasts: pd.DataFrame,
    outcomes: pd.DataFrame,
    horizon_months: int,
    maximum_days_after_target: int = 7,
) -> pd.DataFrame:
    required_forecast = {'security_id', 'as_of_date'}
    if not required_forecast.issubset(forecasts):
        raise ValueError('Forecasts are missing alignment columns.')
    if {'security_id', 'as_of_date'}.issubset(outcomes):
        aligned = _align_keyed_outcomes(forecasts, outcomes)
        aligned['horizon_months'] = horizon_months
        return aligned
    required_outcome = {'security_id', 'date', 'return'}
    if not required_outcome.issubset(outcomes):
        raise ValueError('Outcomes are missing alignment columns.')
    left = forecasts.copy()
    left['as_of_date'] = pd.to_datetime(left['as_of_date'])
    left['target_date'] = left['as_of_date'] + pd.DateOffset(months=horizon_months)
    rows: list[pd.DataFrame] = []
    right = outcomes.copy()
    right['date'] = pd.to_datetime(right['date'])
    for security_id, group in left.groupby('security_id', sort=False):
        observed = right.loc[
            right['security_id'].astype(str).eq(str(security_id))
        ].sort_values('date')
        if observed.empty:
            rows.append(group.assign(realised_return=float('nan')))
            continue
        matched = pd.merge_asof(
            group.sort_values('target_date'),
            observed[['date', 'return']],
            left_on='target_date',
            right_on='date',
            direction='forward',
            tolerance=pd.Timedelta(days=maximum_days_after_target),
        ).rename(columns={'return': 'realised_return', 'date': 'outcome_date'})
        rows.append(matched)
    aligned = pd.concat(rows, ignore_index=True) if rows else left
    aligned['horizon_months'] = horizon_months
    return aligned


def validate_chronology(
    splits: pd.DataFrame,
    purge_days: int = 0,
    embargo_days: int = 0,
) -> pd.DataFrame:
    required = {'train_end', 'validation_start', 'validation_end', 'test_start'}
    if not required.issubset(splits):
        raise ValueError(
            f'Missing chronology columns: {sorted(required.difference(splits.columns))}'
        )
    rows = []
    for index, row in splits.iterrows():
        train_end = pd.Timestamp(row['train_end'])
        validation_start = pd.Timestamp(row['validation_start'])
        validation_end = pd.Timestamp(row['validation_end'])
        test_start = pd.Timestamp(row['test_start'])
        purge_ok = validation_start > train_end + pd.Timedelta(days=purge_days)
        embargo_ok = test_start > validation_end + pd.Timedelta(days=embargo_days)
        rows.append(
            {
                'window': index,
                'purge_ok': purge_ok,
                'embargo_ok': embargo_ok,
                'chronology_ok': purge_ok and embargo_ok,
            }
        )
    return pd.DataFrame(rows)
