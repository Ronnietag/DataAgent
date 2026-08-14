"""Lieflat 风格图表模板库。

统一入口 render_chart: 给定图型编号 + 数据, 输出单文件 HTML 字符串。
数据契约:
  F1  {labels, values}                     分类比较(≤8)
  F2  {labels, values}                     日序列折线(≤30)
  F3  {labels, values}                     日序列面积(30-60)
  F4  {labels, values}                     占比构成(≤6, 自动归一为百分比)
  F5  {labels, values}                     横向排名(≤8)
  F6  {labels, values_a, values_b}         前后分组对比(≤6)
  F7  {labels, segs, values:[[..]]}        堆叠构成(≤4 类 × ≤3 段)
  F9  {labels, values, is_total:[bool]}    瀑布(≤6 级, 首尾为合计)
  F11 {value}                              单值进度(0-100%)
  F12 {labels, values_a, values_b}         哑铃前后对比(≤6)
"""

from .basics import (
    REGISTRY,
    render_F1, render_F2, render_F3, render_F4, render_F5,
    render_F6, render_F7, render_F9, render_F11, render_F12,
)

__all__ = [
    "render_chart", "REGISTRY",
    "render_F1", "render_F2", "render_F3", "render_F4", "render_F5",
    "render_F6", "render_F7", "render_F9", "render_F11", "render_F12",
]

# 图型 -> 数据列需求(用于 LLM 选型与参数校验)
#   x      : 类别/时间列
#   y      : 数值列
#   y2     : 第二个数值列(对比/堆叠/哑铃)
#   y3     : 第三个数值列(堆叠)
#   single : 单值(进度)
#   max_rows: 允许的最大行数(超出截断或改用别的图)
#   desc   : 给 LLM 看的说明
TEMPLATE_META = {
    "F1": {"x": "cat", "y": "num", "max_rows": 8,
           "desc": "竖柱状(分类比较, 每格=一个单位)"},
    "F2": {"x": "date", "y": "num", "max_rows": 30,
           "desc": "发丝折线(日序列, 逐日读数)"},
    "F3": {"x": "date", "y": "num", "min_rows": 30, "max_rows": 60,
           "desc": "发丝面积(30-60 天序列, 看形态)"},
    "F4": {"x": "cat", "y": "num", "max_rows": 6,
           "desc": "环形占比(100% 构成, 段数少)"},
    "F5": {"x": "cat", "y": "num", "max_rows": 8,
           "desc": "横向排名(类目名长或排名时)"},
    "F6": {"x": "cat", "y": "num", "y2": "num", "max_rows": 6,
           "desc": "分组柱(每类两个数值列对比, 如今年 vs 去年)"},
    "F7": {"x": "cat", "y": "num", "y2": "num", "y3": "num", "max_rows": 4,
           "desc": "堆叠柱(≤4 类, 每类 ≤3 个数值段求和)"},
    "F9": {"x": "cat", "y": "num", "max_rows": 6,
           "desc": "瀑布(增减分解, 首尾为合计, 中间为加/减项)"},
    "F11": {"x": None, "y": "num", "max_rows": 1,
            "desc": "进度表盘(单值完成率 0-100%)"},
    "F12": {"x": "cat", "y": "num", "y2": "num", "max_rows": 6,
            "desc": "哑铃对比(每类前后两个数值列, 如改版前 vs 后)"},
}


def render_chart(template_id, payload: dict, title: str, sub: str, src: str) -> str:
    """按图型编号渲染, payload 见模块 docstring 的契约"""
    fn = REGISTRY.get(template_id)
    if fn is None:
        raise KeyError(f"未知图型: {template_id}")
    kwargs = {
        "title": title, "sub": sub, "src": src,
        "y_label": payload.get("y_label", "单位"),
        "note": payload.get("note"),
    }
    if template_id in ("F1", "F2", "F3", "F5"):
        kwargs.update(labels=payload["labels"], values=payload["values"])
    elif template_id == "F4":
        kwargs.update(labels=payload["labels"], values=payload["values"])
    elif template_id == "F6":
        kwargs.update(labels=payload["labels"], values_a=payload["values_a"],
                      values_b=payload["values_b"])
    elif template_id == "F7":
        kwargs.update(labels=payload["labels"], seg_names=payload["segs"],
                      values=payload["values"])
    elif template_id == "F9":
        kwargs.update(labels=payload["labels"], values=payload["values"],
                      is_total=payload["is_total"])
    elif template_id == "F11":
        kwargs.update(value=payload["value"], goal=payload.get("goal", 100))
    elif template_id == "F12":
        kwargs.update(labels=payload["labels"], values_a=payload["values_a"],
                      values_b=payload["values_b"],
                      left_hint=payload.get("left_hint", ""),
                      right_hint=payload.get("right_hint", ""))
    return fn(**kwargs)
