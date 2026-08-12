"""沙箱安全与代码执行回归测试"""
import pandas as pd
import pytest

import server


def test_validate_forbids_dunder_attribute():
    with pytest.raises(ValueError, match="双下划线"):
        server._validate_llm_code("result = df.__class__")


def test_validate_forbids_import_statement():
    with pytest.raises(ValueError, match="import"):
        server._validate_llm_code("import os\nresult = df")


def test_validate_forbids_file_io():
    with pytest.raises(ValueError, match="read_"):
        server._validate_llm_code("result = pd.read_csv('/tmp/x.csv')")


def test_validate_forbids_to_io():
    with pytest.raises(ValueError, match="IO"):
        server._validate_llm_code("result = df.to_csv('/tmp/x.csv')")


def test_validate_ok_on_normal_code():
    server._validate_llm_code("result = df.head(5)")


def test_sandbox_runs_simple_query():
    df = pd.DataFrame({"name": ["a", "b", "c"], "val": [1.0, 2.0, 3.0]})
    res = server.run_sandboxed("result = df.head(2)", df)
    assert isinstance(res, pd.DataFrame)
    assert len(res) == 2


def test_sandbox_guarded_import():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(Exception):
        server.run_sandboxed("import os\nresult = df", df)


def test_sandbox_nlargest_with_object_na():
    df = pd.DataFrame({
        "name": ["x", "y", "z", "w"],
        "val": pd.Series(["10", "30", "20", "1"], dtype=object),
    })
    res = server.run_sandboxed("result = df.nlargest(2, 'val')", df)
    assert len(res) == 2
    assert list(res["name"]) == ["y", "z"]


def test_sandbox_inf_converted_to_nan():
    df = pd.DataFrame({"a": [1.0, 2.0]})
    res = server.run_sandboxed("result = pd.DataFrame({'x': [1.0, float('inf')]})", df)
    assert res["x"].isna().sum() == 1


def test_sandbox_enforces_result_row_limit():
    df = pd.DataFrame({"a": range(server.MAX_RESULT_ROWS + 1)})
    with pytest.raises(ValueError, match="上限"):
        server.run_sandboxed("result = df", df)


def test_sandbox_rejects_non_dataframe():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(TypeError, match="DataFrame"):
        server.run_sandboxed("result = [1, 2, 3]", df)


def test_sandbox_auto_wraps_result():
    df = pd.DataFrame({"a": [1, 2, 3]})
    res = server.run_sandboxed("df.sort_values('a', ascending=False)", df)
    assert isinstance(res, pd.DataFrame)
    assert res["a"].tolist() == [3, 2, 1]


def test_sandbox_auto_wrap_ignores_kwarg_equals():
    # 回归:最后一行含 `ascending=False` 这种参数赋值时,仍要自动包装成 result
    df = pd.DataFrame({"a": [3, 1, 2]})
    res = server.run_sandboxed("df.sort_values('a', ascending=False)", df)
    assert res["a"].tolist() == [3, 2, 1]
