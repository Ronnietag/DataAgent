"""Lieflat 风格图表的公共骨架与工具。

数据契约与模板渲染逻辑来自 vendor/lieflat-charts
(templates/basics-gallery.html, PolyForm Noncommercial 1.0.0, 内部非商业使用)。
"""

import math
import json

# ---------- 公共常量 ----------
PAPER = "#F0EFEB"
INK = "#1C1C1A"
MUTED = "#8F8E88"
FAINT = "#C6C5BF"
GRID = "#DEDDD6"

# ---------- 单位换算工具 ----------

def unit_for(values, max_units):
    """计算每格代表多少单位,保证格子数不超过 max_units"""
    mx = max(values) if values else 0
    if mx <= max_units:
        return 1
    return math.ceil(mx / max_units)


def counts_for(values, unit):
    """数值转格子数(v=0 -> 0, v>0 至少 1 格)"""
    return [0 if v <= 0 else max(1, round(v / unit)) for v in values]


def _js(obj) -> str:
    """Python 值转 JS 数组/对象字面量(中文不转义)"""
    return json.dumps(obj, ensure_ascii=False)


def _fmt(v) -> str:
    """数值格式化为 JS 用字符串(整数不带小数点,避免 38.0)"""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


# ---------- 公共 CSS / helpers JS ----------

_CSS = """\
:root{--bg:#F0EFEB;--ink:#1C1C1A;--muted:#8F8E88;--faint:#C6C5BF;--grid:#DEDDD6}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%}
body{background:var(--bg);font-family:'Inter','PingFang SC','Microsoft YaHei',sans-serif;color:var(--ink);
  padding:18px;-webkit-font-smoothing:antialiased}
.grid2{display:grid;grid-template-columns:1fr;gap:22px;max-width:1100px;margin:0 auto}
.card{background:var(--bg);border-radius:24px;padding:22px 22px 16px}
h2{font-weight:700;font-size:16.5px;letter-spacing:-.02em;margin-bottom:3px;line-height:1.35}
.sub{font-size:11.5px;color:var(--muted);margin-bottom:12px;line-height:1.6}
.src{font-size:9.5px;color:var(--faint);margin-top:8px;letter-spacing:.08em;font-weight:500}
svg{width:100%;max-height:330px;display:block;margin:0 auto}
svg text{font-family:'Inter','PingFang SC','Microsoft YaHei',sans-serif}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .5s cubic-bezier(.2,.7,.3,1.3) both}
@keyframes pop{from{transform:scale(0)}to{transform:none}}
.fade{animation:fade .9s ease both}
@keyframes fade{from{opacity:0}}
.draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1s cubic-bezier(.4,0,.2,1) both}
@keyframes draw{to{stroke-dashoffset:0}}
"""

_HELPERS = """\
const INK='#1C1C1A',PAPER='#F0EFEB',MUTED='#8F8E88',GRID='#DEDDD6';
const NS='http://www.w3.org/2000/svg';
const el=(p,t,a)=>{const n=document.createElementNS(NS,t);for(const k in a)n.setAttribute(k,a[k]);p.appendChild(n);return n};
const txt=(p,a,s)=>{const n=el(p,'text',a);n.textContent=s;return n};
const tip=(n,s)=>{const t=document.createElementNS(NS,'title');t.textContent=s;n.appendChild(t)};
const rnd=(i,k)=>Math.abs(((i*73856093)^(k*19349663))%1000)/1000;
const D2R=Math.PI/180;
const pol=(cx,cy,r,deg)=>[cx+r*Math.cos(deg*D2R),cy+r*Math.sin(deg*D2R)];
const obsReveal=(id,fn)=>{
  const n=document.getElementById(id);
  const go=()=>{n.innerHTML='';fn(n)};
  const io=new IntersectionObserver(es=>{if(es[0].isIntersecting){go();io.disconnect()}},{threshold:.3});
  io.observe(n);
  n.style.cursor='pointer';
  n.addEventListener('click',go);
};
"""

_FONT_LINK = """\
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
"""


def page(title: str, sub: str, src: str, render_js: str, svg_id: str = "ch") -> str:
    """组装单文件 HTML(内联全部 CSS/JS)"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
{_FONT_LINK}
<style>
{_CSS}
</style>
</head>
<body>
<div class="grid2">
  <div class="card">
    <h2>{title}</h2>
    <div class="sub">{sub}</div>
    <svg id="{svg_id}" viewBox="0 0 400 320" preserveAspectRatio="xMidYMid meet"></svg>
    <div class="src">{src}</div>
  </div>
</div>
<script>
{_HELPERS}
{render_js}
</script>
</body>
</html>"""
