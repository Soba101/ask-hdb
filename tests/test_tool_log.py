import json

from ask_hdb import tools


def _lines(capsys):
    return [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]


def test_data_tool_logs_its_arguments(capsys):
    tools._log_call("find_sales", {"block_id": "blk_1", "since": "2025-11"}, {"sales": [{}, {}], "period": "x"})
    [line] = _lines(capsys)
    assert line == {"tool": "find_sales", "args": {"block_id": "blk_1", "since": "2025-11"},
                    "result": {"period": "x", "sales": 2}}


def test_profile_and_calculate_tools_log_only_argument_names(capsys):
    tools._log_call("ehg_amount", {"monthly_household_income": 6200, "ages": "30,30"}, {"amount": 40000})
    tools.calculate.invoke({"expression": "6200 * 12"})  # a real call goes through the same log
    first, second = _lines(capsys)
    assert first["args"] == ["ages", "monthly_household_income"]
    assert second == {"tool": "calculate", "args": ["expression"], "result": {}}
    assert "6200" not in json.dumps([first, second])


def test_tool_log_can_be_turned_off(capsys, monkeypatch):
    monkeypatch.setenv("TOOL_LOG", "0")
    tools._log_call("find_sales", {"block_id": "blk_1"}, {})
    assert _lines(capsys) == []
