from pathlib import Path


SENSITIVE_KEYS = {
    'ALPACA_API_KEY_ID',
    'ALPACA_API_SECRET_KEY',
    'EODHD_API_TOKEN',
    'FINNHUB_API_KEY',
    'FRED_API_KEY',
    'ITICK_API_TOKEN',
    'TICKDB_API_KEY',
}


def test_tracked_environment_example_contains_no_credentials():
    values = {}
    for raw_line in Path('.env.example').read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()

    assert SENSITIVE_KEYS.issubset(values)
    assert {key: values[key] for key in SENSITIVE_KEYS if values[key]} == {}
