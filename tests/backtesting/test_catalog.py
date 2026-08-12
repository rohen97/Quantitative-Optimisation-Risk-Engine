from src.backtesting.portfolio_catalog import fallback_yfinance_symbol


def test_fallback_yfinance_symbol_maps_supported_exchanges() -> None:
    assert fallback_yfinance_symbol('AAPL.US') == 'AAPL'
    assert fallback_yfinance_symbol('000333.SHE') == '000333.SZ'
    assert fallback_yfinance_symbol('601398.SHG') == '601398.SS'
    assert fallback_yfinance_symbol('ALV.XETRA') == 'ALV.DE'
    assert fallback_yfinance_symbol('NESN.SW') == 'NESN.SW'


def test_fallback_yfinance_symbol_preserves_unknown_suffix() -> None:
    assert fallback_yfinance_symbol('ABC.UNKNOWN') == 'ABC.UNKNOWN'
