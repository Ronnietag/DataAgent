"""图表类型归一化 + x/y 轴校验回归测试"""
import server


def test_normalize_chart_type_aliases():
    assert server._normalize_chart_type("bar") == "bar"
    assert server._normalize_chart_type("柱状图") == "bar"
    assert server._normalize_chart_type("横向柱状图") == "horizontal_bar"
    assert server._normalize_chart_type("折线图") == "line"
    assert server._normalize_chart_type("饼图") == "pie"
    assert server._normalize_chart_type("scatter") == "scatter"
    assert server._normalize_chart_type("line_chart") == "line"


def test_normalize_chart_type_invalid():
    assert server._normalize_chart_type("3d") is None
    assert server._normalize_chart_type("") is None
    assert server._normalize_chart_type(None) is None
    assert server._normalize_chart_type(123) is None


_COLS = ["name", "val", "rate"]
_PREVIEW = [["a", "1", "0.5"], ["b", "2", "0.9"]]


def test_pick_axes_swaps_reversed_x_y():
    x, y = server._pick_chart_axes({"x": "val", "y": "name"}, _COLS, _PREVIEW)
    assert (x, y) == ("name", "val")


def test_pick_axes_keeps_valid():
    x, y = server._pick_chart_axes({"x": "name", "y": "val"}, _COLS, _PREVIEW)
    assert (x, y) == ("name", "val")


def test_pick_axes_y_falls_back_to_rate_column():
    x, y = server._pick_chart_axes({"x": "name", "y": "bad_col"}, _COLS, _PREVIEW)
    assert y == "rate"
    assert x == "name"


def test_pick_axes_scatter_needs_two_numeric():
    x, y = server._pick_chart_axes({"x": "name", "y": "val"}, _COLS, _PREVIEW, ctype="scatter")
    assert x in ("val", "rate")
    assert x != y
    assert y in ("val", "rate")


def test_is_numeric_col_tolerates_formatting():
    rows = [["1,234", "12.5%", ""], ["5", "3.3%", ""]]
    assert server._is_numeric_col(rows, 0)
    assert server._is_numeric_col(rows, 1)
    assert not server._is_numeric_col(rows, 2)


def test_is_numeric_col_rejects_text():
    rows = [["abc", "x"], ["def", "y"]]
    assert not server._is_numeric_col(rows, 0)
