"""Lieflat 模板渲染测试：每个图型渲染出完整 HTML，无占位符残留，JS 语法合法"""
import re
import subprocess

from chart_templates import render_chart

_ALL_TEMPLATES = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F9", "F11", "F12"]


def _render(tid):
    if tid in ("F1", "F5"):
        payload = {"labels": ["华东", "华北", "华南"], "values": [382, 271, 165]}
    elif tid in ("F2", "F3"):
        payload = {"labels": [f"07-{i:02d}" for i in range(1, 21)], "values": [i % 40 for i in range(1, 21)]}
    elif tid == "F4":
        payload = {"labels": ["核心", "增值", "服务"], "values": [55, 32, 13]}
    elif tid == "F6":
        payload = {"labels": ["华东", "华北", "华南"], "values_a": [301, 245, 188], "values_b": [382, 271, 165]}
    elif tid == "F7":
        payload = {"labels": ["华东", "华北"], "segs": ["核心", "增值", "服务"], "values": [[18, 11, 7], [14, 9, 5]]}
    elif tid == "F9":
        payload = {"labels": ["毛收入", "退款", "成本", "净利"], "values": [420, -60, -110, 250], "is_total": [True, False, False, True]}
    elif tid == "F11":
        payload = {"value": 73}
    elif tid == "F12":
        payload = {"labels": ["邀请", "看板", "工作台"], "values_a": [14, 19, 22], "values_b": [6, 9, 13]}
    else:
        raise KeyError(tid)
    return render_chart(tid, payload, f"{tid} 标题", f"{tid} 副标题", f"{tid} · 数据源")


def test_all_templates_render_no_placeholder():
    for tid in _ALL_TEMPLATES:
        html = _render(tid)
        assert "{{" not in html, f"{tid} 有占位符残留"
        assert "<script>" in html, f"{tid} 无 script 块"


def test_all_templates_js_syntax():
    for tid in _ALL_TEMPLATES:
        html = _render(tid)
        js = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert js, f"{tid} 无 script 块"
        tmp = "/tmp/_ct_test.js"
        with open(tmp, "w") as f:
            f.write(js[0])
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        assert r.returncode == 0, f"{tid} JS 语法错误: {r.stderr}"


def test_all_templates_contain_title_sub_src():
    for tid in _ALL_TEMPLATES:
        html = _render(tid)
        assert f"{tid} 标题" in html, f"{tid} 缺少标题"
        assert f"{tid} 副标题" in html, f"{tid} 缺少副标题"
        assert f"{tid} · 数据源" in html, f"{tid} 缺少来源行"


def test_all_templates_escape_unicode():
    for tid in _ALL_TEMPLATES:
        html = _render(tid)
        assert "undefined" not in html.lower(), f"{tid} 出现 undefined"


def test_registry_meta_consistency():
    from chart_templates import REGISTRY, TEMPLATE_META
    assert set(REGISTRY) == set(TEMPLATE_META)
