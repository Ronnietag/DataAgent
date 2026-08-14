"""图型归一化 + 列校验 + payload 构造回归测试"""
import server


def test_normalize_template_aliases():
    assert server._normalize_template("F1") == "F1"
    assert server._normalize_template("bar") == "F1"
    assert server._normalize_template("柱状图") == "F1"
    assert server._normalize_template("横向柱状图") == "F5"
    assert server._normalize_template("折线图") == "F2"
    assert server._normalize_template("面积图") == "F3"
    assert server._normalize_template("饼图") == "F4"
    assert server._normalize_template("F12") == "F12"
    assert server._normalize_template("dumbbell") == "F12"
    assert server._normalize_template("F9") == "F9"


def test_normalize_template_invalid():
    assert server._normalize_template("F13") is None
    assert server._normalize_template("") is None
    assert server._normalize_template(None) is None
    assert server._normalize_template(123) is None


_COLS = ["name", "val", "rate"]
_PREVIEW = [["a", "1", "0.5"], ["b", "2", "0.9"]]


def test_pick_cols_swaps_reversed_x_y():
    out = server._pick_chart_cols({"template": "F1", "x": "val", "y": "name"}, _COLS, _PREVIEW)
    assert (out["x"], out["y"]) == ("name", "val")


def test_pick_cols_keeps_valid():
    out = server._pick_chart_cols({"template": "F1", "x": "name", "y": "val"}, _COLS, _PREVIEW)
    assert (out["x"], out["y"]) == ("name", "val")


def test_pick_cols_y_falls_back_to_rate_column():
    out = server._pick_chart_cols({"template": "F1", "x": "name", "y": "bad_col"}, _COLS, _PREVIEW)
    assert out["y"] == "rate"
    assert out["x"] == "name"


def test_pick_cols_F12_needs_second_numeric():
    out = server._pick_chart_cols({"template": "F12", "x": "name", "y": "val"}, _COLS, _PREVIEW)
    assert out["y2"] == "rate"
    assert out["y"] == "val"


def test_pick_cols_F7_picks_three_numeric():
    out = server._pick_chart_cols({"template": "F7", "x": "name", "y": "val", "y2": "rate"}, _COLS, _PREVIEW)
    assert out["y2"] == "rate"


def test_pick_cols_F11_ignores_x():
    out = server._pick_chart_cols({"template": "F11", "x": "val", "y": "val"}, _COLS, _PREVIEW)
    assert out["x"] == "val"
    assert out["y"] == "val"


def test_is_numeric_col_tolerates_formatting():
    rows = [["1,234", "12.5%", ""], ["5", "3.3%", ""]]
    assert server._is_numeric_col(rows, 0)
    assert server._is_numeric_col(rows, 1)
    assert not server._is_numeric_col(rows, 2)


def test_is_numeric_col_rejects_text():
    rows = [["abc", "x"], ["def", "y"]]
    assert not server._is_numeric_col(rows, 0)


# ---------- payload 构造 ----------
_RESULT = {
    "columns": ["大区", "接受度", "接受度指数", "格子数"],
    "rows": [
        ["华东", 0.42, 0.87, 1200],
        ["华北", 0.35, 0.9, 800],
        ["华南", 0.2, 0.75, 600],
    ],
}


def test_to_float_formats():
    assert server._to_float("1,234") == 1234.0
    assert server._to_float("12.5%") == 12.5
    assert server._to_float("－3") == -3.0
    assert server._to_float(None) == 0.0
    assert server._to_float("abc") == 0.0


def test_payload_F1():
    p = server._build_chart_payload({"template": "F1", "x": "大区", "y": "接受度"}, _RESULT)
    assert p["labels"] == ["华东", "华北", "华南"]
    assert p["values"] == [0.42, 0.35, 0.2]
    assert p["y_label"] == "接受度"


def test_payload_rounds_to_2_decimals():
    rd = {"columns": ["单元", "学术接受度"], "rows": [["甲", 0.9466], ["乙", 0.9177], ["丙", 0.8805]]}
    p = server._build_chart_payload({"template": "F5", "x": "单元", "y": "学术接受度"}, rd)
    assert p["values"] == [0.95, 0.92, 0.88]


def test_payload_rounds_F6_2_decimals():
    rd = {"columns": ["单元", "今年", "去年"], "rows": [["甲", 0.9466, 0.8855], ["乙", 0.9177, 0.8611]]}
    p = server._build_chart_payload({"template": "F6", "x": "单元", "y": "今年", "y2": "去年"}, rd)
    assert p["values_b"] == [0.95, 0.92]
    assert p["values_a"] == [0.89, 0.86]


def test_payload_F6_uses_y2_as_before():
    p = server._build_chart_payload({"template": "F6", "x": "大区", "y": "接受度", "y2": "接受度指数"}, _RESULT)
    assert p["values_a"] == [0.87, 0.9, 0.75]
    assert p["values_b"] == [0.42, 0.35, 0.2]


def test_payload_F7_stacks_columns():
    p = server._build_chart_payload({"template": "F7", "x": "大区", "y": "接受度", "y2": "接受度指数"}, _RESULT)
    assert p["segs"] == ["接受度", "接受度指数"]
    assert len(p["values"]) == 3
    assert len(p["values"][0]) == 2


def test_payload_F4_rejects_zero_sum():
    r = {"columns": ["a", "v"], "rows": [["x", 0], ["y", 0]]}
    assert server._build_chart_payload({"template": "F4", "x": "a", "y": "v"}, r) is None


def test_payload_F9_marks_first_last_total():
    r = {"columns": ["a", "v"], "rows": [["gross", 42], ["refunds", -6], ["net", 36]]}
    p = server._build_chart_payload({"template": "F9", "x": "a", "y": "v"}, r)
    assert p["is_total"] == [True, False, True]
    assert p["values"] == [42, -6, 36]


def test_payload_F9_too_short():
    r = {"columns": ["a", "v"], "rows": [["gross", 42], ["net", 36]]}
    assert server._build_chart_payload({"template": "F9", "x": "a", "y": "v"}, r) is None


def test_payload_F11_single_value():
    r = {"columns": ["a", "v"], "rows": [["完成率", 73]]}
    p = server._build_chart_payload({"template": "F11", "x": "a", "y": "v"}, r)
    assert p["value"] == 73


def test_payload_truncates_to_max_rows():
    rows = [[str(i), str(i * 10)] for i in range(20)]
    r = {"columns": ["a", "v"], "rows": rows}
    p = server._build_chart_payload({"template": "F5", "x": "a", "y": "v"}, r)
    assert len(p["values"]) == 8
