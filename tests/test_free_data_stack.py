from scripts.run_free_data_stack import PHASES, _command_hash, _commands, parse_args


def test_free_data_stack_runs_fast_volume_source_before_residual_source():
    args = parse_args(["--start", "1994-01-01"])
    commands = _commands(args)

    assert PHASES.index("yfinance") < PHASES.index("akshare")
    yfinance_command, environment = commands["yfinance"]
    assert "--refresh-missing-volume" in yfinance_command
    assert environment["DATA_PRICE_PROVIDERS"] == "yfinance"
    assert int(environment["YFINANCE_LOOKBACK_DAYS"]) >= 11_900


def test_free_data_command_hash_changes_with_environment_value():
    assert _command_hash(["python", "phase.py"], {"MODE": "one"}) != (
        _command_hash(["python", "phase.py"], {"MODE": "two"})
    )
