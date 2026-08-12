"""字段语义字典构建与格式化回归测试"""
import pandas as pd

import server


def test_column_semantics_types():
    df = pd.DataFrame({
        "数值": [float(i) for i in range(15)],
        "文本": [f"t{i}" for i in range(15)],
        "枚举": ["A", "B", "C"] * 5,
        "日期": pd.date_range("2026-01-01", periods=15),
    })
    sem = server._build_column_semantics(df)
    assert sem["数值"]["类型"] == "数值"
    assert sem["文本"]["类型"] == "文本"
    assert "示例" in sem["文本"]
    assert "取值" in sem["枚举"]
    assert sem["日期"]["类型"] == "日期"


def test_column_semantics_enum_when_few_unique():
    df = pd.DataFrame({"度量值": ["学术接受度", "接受度指数", "学术接受度"]})
    sem = server._build_column_semantics(df)
    assert sem["度量值"]["取值"] == ["学术接受度", "接受度指数"]


def test_column_semantics_marks_missing():
    df = pd.DataFrame({"x": [1.0, None, None, None, None]})
    sem = server._build_column_semantics(df)
    assert "缺失" in sem["x"]


def test_format_column_dict_lines():
    sem = {
        "a": {"类型": "数值"},
        "b": {"类型": "文本", "示例": ["x", "y"]},
        "c": {"类型": "文本", "取值": ["P", "Q"]},
    }
    txt = server._format_column_dict(sem)
    assert "a: 数值" in txt
    assert "b: 文本" in txt
    assert "c: 文本 枚举" in txt
    assert "P" in txt and "Q" in txt
