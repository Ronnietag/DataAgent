"""Lieflat 风格基础图型模板(F1-F7, F9, F11, F12)。

渲染逻辑源自 vendor/lieflat-charts/templates/basics-gallery.html 的对应卡内代码,
做了三处适配:
1. 数据改为参数注入(labels/values/...), 不再硬编码;
2. 值域/格子数自适应(真实数据量级远大于模板演示数据, 避免溢出画布);
3. 内部标注中文化。
"""

from ._base import page, unit_for, counts_for, _js, PAPER, INK

# ---------------------------------------------------------------
# F1 · Rung Bars 竖柱(分类比较, ≤8)
# ---------------------------------------------------------------
_F1_JS = """\
(()=>{
const L={{LABELS}},V={{VALUES}},C={{COUNTS}},STEP={{STEP}};
obsReveal('ch',s=>{
  const base=266,HW=14,step=STEP;
  const x0=i=>{const gap=Math.min(56,340/Math.max(1,L.length));return 30+i*gap};
  L.forEach((name,i)=>{
    const x=x0(i),n=C[i];
    for(let k=0;k<n;k++){
      const y=base-k*step,w=HW-1.5+rnd(k+1,i+2)*3;
      el(s,'line',{x1:x-w,y1:y,x2:x+w,y2:y,stroke:INK,'stroke-width':1,
        opacity:.5+rnd(k+2,i+4)*.5,class:'fade',style:`animation-delay:${i*.08+k*.012}s`});
      if(k%5===4)el(s,'circle',{cx:x+HW+4.5,cy:y,r:.8,fill:'#C6C5BF',
        class:'fade',style:`animation-delay:${i*.08+k*.012}s`});
    }
    const topY=base-(n-1)*step;
    const num=txt(s,{x,y:topY-10,'font-size':11,'font-weight':800,fill:INK,'text-anchor':'middle',
      class:'fade',style:`animation-delay:${.4+i*.08}s`},V[i]);
    tip(num,`${name} — ${V[i]} {{YLABEL}}`);
    txt(s,{x,y:base+18,'font-size':7.5,'font-weight':700,fill:MUTED,'text-anchor':'middle',
      'letter-spacing':'.08em',class:'fade',style:`animation-delay:${i*.08}s`},name);
  });
  el(s,'line',{x1:28,y1:base+4,x2:372,y2:base+4,stroke:GRID,'stroke-width':.8,class:'fade'});
  txt(s,{x:200,y:306,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:.9s'},'{{NOTE}}');
});
})();
"""


def render_F1(labels, values, title, sub, src, y_label="单位", note=None):
    unit = unit_for(values, 48)
    counts = counts_for(values, unit)
    step = min(5.6, 240 / max(counts, default=1))
    if note is None:
        note = f"每格 = {unit} {y_label}" + (" · 每第 5 格一个圆点" if unit == 1 else "")
    js = (_F1_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES}}", _js(values))
          .replace("{{COUNTS}}", _js(counts)).replace("{{STEP}}", _fmt(step))
          .replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F2 · Hairline Line 折线(日序列, ≤30)
# ---------------------------------------------------------------
_F2_JS = """\
(()=>{
const L={{LABELS}},V={{VALUES}},SCALE={{SCALE}},XSTEP={{XSTEP}},N={{N}};
obsReveal('ch',s=>{
  const base=262;
  const x=d=>30+d*XSTEP,map=v=>base-v*SCALE;
  for(let d=0;d<N;d++)
    el(s,'line',{x1:x(d),y1:base,x2:x(d),y2:base-7,stroke:'#CFCEC7','stroke-width':.6,
      class:'fade',style:`animation-delay:${d*.008}s`});
  el(s,'line',{x1:24,y1:base,x2:376,y2:base,stroke:GRID,'stroke-width':.8,class:'fade'});
  const vs=V;
  const top=[];
  for(const d of [...vs.keys()].sort((a,b)=>vs[b]-vs[a])){
    if(top.every(t=>Math.abs(t-d)>=Math.max(3,Math.floor(N*.12))))top.push(d);
    if(top.length===2)break;
  }
  const pts=vs.map((v,d)=>`${x(d)} ${map(v)}`).join(' L ');
  el(s,'path',{d:'M'+pts,fill:'none',stroke:INK,'stroke-width':1,pathLength:1,
    class:'draw',style:'animation-duration:1.2s'});
  vs.forEach((v,d)=>{
    const weekend=d%7===5||d%7===6,big=top.includes(d);
    const dot=el(s,'circle',{cx:x(d),cy:map(v),r:big?4.2:2.1,
      fill:weekend?PAPER:INK,stroke:INK,'stroke-width':weekend?1:0,
      class:'pop',style:`animation-delay:${.2+d*.03}s`});
    tip(dot,`${L[d]||('第 '+(d+1)+' 天')} — ${v} {{YLABEL}}`);
    if(big)txt(s,{x:x(d),y:map(v)-11,'font-size':9.5,'font-weight':800,fill:INK,'text-anchor':'middle',
      style:`paint-order:stroke;stroke:${PAPER};stroke-width:3px;animation-delay:${1+d*.01}s`,
      class:'fade'},v);
  });
  [0,Math.floor((N-1)/2),N-1].forEach(d=>
    txt(s,{x:x(d),y:base+18,'font-size':7.5,'font-weight':600,fill:MUTED,'text-anchor':d===0?'start':d===N-1?'end':'middle',
      'letter-spacing':'.1em',class:'fade'},String(L[d]||'')));
  txt(s,{x:200,y:306,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.1s'},'{{NOTE}}');
});
})();
"""


def render_F2(labels, values, title, sub, src, y_label="单位", note=None):
    n = len(values)
    mx = max(values) if values else 1
    scale = (262 - 44) / mx if mx > 0 else 0
    xstep = 346 / max(1, n - 1)
    if note is None:
        note = "空心点 = 周末 · 每点一个读数"
    js = (_F2_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES}}", _js(values))
          .replace("{{SCALE}}", _fmt(scale)).replace("{{XSTEP}}", _fmt(xstep))
          .replace("{{N}}", str(n)).replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F3 · Hairline Area 面积(30-60 天, 看形态)
# ---------------------------------------------------------------
_F3_JS = """\
(()=>{
const L={{LABELS}},V={{VALUES}},SCALE={{SCALE}},XSTEP={{XSTEP}},N={{N}};
obsReveal('ch',s=>{
  const base=262;
  const x=d=>28+d*XSTEP,map=v=>base-v*SCALE;
  el(s,'line',{x1:22,y1:base,x2:378,y2:base,stroke:GRID,'stroke-width':.8,class:'fade'});
  const vs=V;
  const peak=vs.indexOf(Math.max(...vs));
  vs.forEach((v,d)=>{
    el(s,'line',{x1:x(d),y1:base,x2:x(d),y2:map(v),
      stroke:d===peak?INK:'#8F8E88','stroke-width':d===peak?1.1:.55,
      opacity:d===peak?1:.5+rnd(d+1,7)*.45,
      class:'fade',style:`animation-delay:${d*.014}s`});
  });
  const pts=vs.map((v,d)=>`${x(d)} ${map(v)}`).join(' L ');
  el(s,'path',{d:'M'+pts,fill:'none',stroke:INK,'stroke-width':1.2,pathLength:1,
    class:'draw',style:'animation-delay:.4s;animation-duration:1.2s'});
  const pd=el(s,'circle',{cx:x(peak),cy:map(vs[peak]),r:4.2,fill:INK,
    class:'pop',style:'animation-delay:1.2s'});
  tip(pd,`${L[peak]||('第 '+(peak+1)+' 天')} — ${vs[peak]} {{YLABEL}}`);
  txt(s,{x:x(peak),y:map(vs[peak])-11,'font-size':9.5,'font-weight':800,fill:INK,'text-anchor':'middle',
    style:`paint-order:stroke;stroke:${PAPER};stroke-width:3px;animation-delay:1.3s`,
    class:'fade'},vs[peak]);
  const ticks=[0,Math.floor((N-1)/2),N-1];
  ticks.forEach(d=>
    txt(s,{x:x(d),y:base+18,'font-size':7.5,'font-weight':600,fill:MUTED,'text-anchor':d===0?'start':d===N-1?'end':'middle',
      'letter-spacing':'.1em',class:'fade'},String(L[d]||'')));
  txt(s,{x:200,y:306,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.3s'},'{{NOTE}}');
});
})();
"""


def render_F3(labels, values, title, sub, src, y_label="单位", note=None):
    n = len(values)
    mx = max(values) if values else 1
    scale = (262 - 44) / mx if mx > 0 else 0
    xstep = 350 / max(1, n - 1)
    if note is None:
        note = "每天一根发丝从底线立到峰值 · 面积由日子组成"
    js = (_F3_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES}}", _js(values))
          .replace("{{SCALE}}", _fmt(scale)).replace("{{XSTEP}}", _fmt(xstep))
          .replace("{{N}}", str(n)).replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F4 · Tick Donut 环形占比(100% 构成, ≤6)
# ---------------------------------------------------------------
_F4_JS = """\
(()=>{
const L={{LABELS}},P={{PCTS}},SH={{SHADES}},TOTAL={{TOTAL}};
obsReveal('ch',s=>{
  const cx=200,cy=148,R0=64;
  let k0=0;
  P.forEach((v,si)=>{
    for(let k=0;k<v;k++){
      const idx=k0+k,a=idx*3.6-90;
      const len=10+rnd(idx+1,si+2)*6;
      const [x1,y1]=pol(cx,cy,R0,a),[x2,y2]=pol(cx,cy,R0+len,a);
      el(s,'line',{x1,y1,x2,y2,stroke:SH[si%SH.length],'stroke-width':1,
        class:'fade',style:`animation-delay:${idx*.012}s`});
      if(idx%10===0){
        const [dx,dy]=pol(cx,cy,R0-5,a);
        el(s,'circle',{cx:dx,cy:dy,r:.8,fill:'#C6C5BF',class:'fade',style:`animation-delay:${idx*.012}s`});
      }
    }
    const mid=(k0+v/2)*3.6-90,[lx,ly]=pol(cx,cy,R0+38,mid),[gx,gy]=pol(cx,cy,R0+20,mid);
    el(s,'line',{x1:gx,y1:gy,x2:lx,y2:ly,stroke:'#C6C5BF','stroke-width':.7,
      'stroke-dasharray':'1 3',class:'fade',style:`animation-delay:${.6+si*.1}s`});
    const anchor=Math.cos(mid*D2R)>0.3?'start':Math.cos(mid*D2R)<-0.3?'end':'middle';
    const lab=txt(s,{x:lx,y:ly+3,'font-size':8,'font-weight':800,fill:SH[si%SH.length],'text-anchor':anchor,
      'letter-spacing':'.06em',style:`paint-order:stroke;stroke:${PAPER};stroke-width:3px;animation-delay:${.65+si*.1}s`,
      class:'fade'},`${L[si]} · ${v}%`);
    tip(lab,`${L[si]} — ${v}%`);
    k0+=v;
  });
  txt(s,{x:cx,y:cy-2,'font-size':22,'font-weight':800,fill:INK,'text-anchor':'middle',
    class:'fade',style:'animation-delay:.9s'},'{{TOTAL}}');
  txt(s,{x:cx,y:cy+14,'font-size':7,'font-weight':600,fill:MUTED,'text-anchor':'middle',
    'letter-spacing':'.1em',class:'fade',style:'animation-delay:.9s'},'{{CENTER}}');
  txt(s,{x:200,y:296,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.1s'},'{{NOTE}}');
});
})();
"""
_F4_SHADES = ["#1C1C1A", "#55554F", "#8F8E88", "#B0AFA9", "#C6C5BF"]


def render_F4(labels, values, title, sub, src, y_label="单位", note=None):
    total = sum(values)
    if total <= 0:
        raise ValueError("占比总和必须大于 0")
    pcts = [max(0, round(100 * v / total)) for v in values]
    pcts = _round_sum(pcts, len(values))
    total_disp = sum(pcts)
    if note is None:
        note = "一格 = 1% · 12 点钟为零 · 顺时针读 · 每第 10 格一个圆点"
    js = (_F4_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{PCTS}}", _js(pcts))
          .replace("{{SHADES}}", _js(_F4_SHADES)).replace("{{TOTAL}}", str(total_disp))
          .replace("{{CENTER}}", "一格 = 1%")
          .replace("{{NOTE}}", note))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F5 · Tick Rows 横向排名(≤8 行)
# ---------------------------------------------------------------
_F5_JS = """\
(()=>{
const L={{LABELS}},V={{VALUES}},C={{COUNTS}},GAP={{GAP}},PX={{PX}},MAXC={{MAXC}};
obsReveal('ch',s=>{
  const y0=i=>54+i*GAP,X0=100;
  L.forEach((name,i)=>{
    const y=y0(i),n=C[i];
    txt(s,{x:X0-6,y:y+3,'font-size':8,'font-weight':700,fill:'#6A6963','text-anchor':'end',
      'letter-spacing':'.08em',class:'fade',style:`animation-delay:${i*.08}s`},name);
    el(s,'line',{x1:X0,y1:y+9,x2:X0+MAXC*PX,y2:y+9,stroke:GRID,'stroke-width':.6,
      class:'fade',style:`animation-delay:${i*.08}s`});
    for(let k=0;k<n;k++){
      const x=X0+k*PX+PX/2,h=9+rnd(k+1,i+2)*6;
      el(s,'line',{x1:x,y1:y+9,x2:x,y2:y+9-h,stroke:INK,'stroke-width':.9,
        opacity:.55+rnd(k+3,i+5)*.45,class:'fade',style:`animation-delay:${i*.08+k*.012}s`});
      if(k%5===4)el(s,'circle',{cx:x,cy:y+13,r:.8,fill:'#C6C5BF',
        class:'fade',style:`animation-delay:${i*.08+k*.012}s`});
    }
    const lab=txt(s,{x:X0+n*PX+10,y:y+4,'font-size':11,'font-weight':800,fill:INK,
      class:'fade',style:`animation-delay:${.4+i*.08}s`},V[i]);
    tip(lab,`${name} — ${V[i]} {{YLABEL}}`);
  });
  txt(s,{x:200,y:308,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:.9s'},'{{NOTE}}');
});
})();
"""


def render_F5(labels, values, title, sub, src, y_label="单位", note=None):
    unit = unit_for(values, 30)
    counts = counts_for(values, unit)
    n = max(1, len(labels))
    gap = min(44, 230 / n)
    maxc = max(counts, default=1)
    px = (360 - 100) / max(1, maxc)
    if note is None:
        note = f"每格 = {unit} {y_label}" + (" · 每第 5 格一个圆点" if unit == 1 else "")
    js = (_F5_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES}}", _js(values))
          .replace("{{COUNTS}}", _js(counts)).replace("{{GAP}}", _fmt(gap))
          .replace("{{PX}}", _fmt(px)).replace("{{MAXC}}", str(maxc))
          .replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F6 · Paired Rungs 分组对比(每类 2 系列, ≤6)
# ---------------------------------------------------------------
_F6_JS = """\
(()=>{
const L={{LABELS}},A={{VALUES_A}},B={{VALUES_B}},CA={{COUNTS_A}},CB={{COUNTS_B}},STEP={{STEP}};
obsReveal('ch',s=>{
  const x0=i=>64+i*66,base=258,step=STEP,HW=10;
  L.forEach((name,i)=>{
    const was=A[i],now=B[i],xa=x0(i)-13,xb=x0(i)+13;
    for(let k=0;k<CA[i];k++){
      const y=base-k*step,w=HW-1.2+rnd(k+1,i+2)*2.4;
      el(s,'line',{x1:xa-w,y1:y,x2:xa+w,y2:y,stroke:'#B0AFA9','stroke-width':1,
        opacity:.5+rnd(k+2,i+3)*.4,class:'fade',style:`animation-delay:${i*.08+k*.01}s`});
    }
    for(let k=0;k<CB[i];k++){
      const y=base-k*step,w=HW-1.2+rnd(k+1,i+7)*2.4;
      el(s,'line',{x1:xb-w,y1:y,x2:xb+w,y2:y,stroke:INK,'stroke-width':1,
        opacity:.6+rnd(k+2,i+8)*.4,class:'fade',style:`animation-delay:${.15+i*.08+k*.01}s`});
    }
    const topB=base-(CB[i]-1)*step;
    const num=txt(s,{x:xb,y:topB-9,'font-size':10.5,'font-weight':800,fill:INK,'text-anchor':'middle',
      class:'fade',style:`animation-delay:${.5+i*.08}s`},now);
    tip(num,`${name} — ${was} → ${now} {{YLABEL}}`);
    txt(s,{x:xa,y:base-(CA[i]-1)*step-9,'font-size':8.5,'font-weight':700,fill:'#B0AFA9','text-anchor':'middle',
      class:'fade',style:`animation-delay:${.5+i*.08}s`},was);
    txt(s,{x:x0(i),y:base+18,'font-size':7.5,'font-weight':700,fill:MUTED,'text-anchor':'middle',
      'letter-spacing':'.08em',class:'fade',style:`animation-delay:${i*.08}s`},name);
  });
  el(s,'line',{x1:30,y1:base+4,x2:370,y2:base+4,stroke:GRID,'stroke-width':.8,class:'fade'});
  txt(s,{x:200,y:306,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1s'},'{{NOTE}}');
});
})();
"""


def render_F6(labels, values_a, values_b, title, sub, src, y_label="单位", note=None):
    unit = unit_for(list(values_a) + list(values_b), 40)
    ca = counts_for(values_a, unit)
    cb = counts_for(values_b, unit)
    step = min(5.4, 220 / max(ca + cb, default=1))
    if note is None:
        note = "浅档 = 前值 · 深档 = 现值 · 每格 = %s %s" % (unit, y_label)
    js = (_F6_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES_A}}", _js(values_a))
          .replace("{{VALUES_B}}", _js(values_b)).replace("{{COUNTS_A}}", _js(ca))
          .replace("{{COUNTS_B}}", _js(cb)).replace("{{STEP}}", _fmt(step))
          .replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F7 · Stacked Rungs 堆叠构成(≤4 类 × ≤3 段)
# ---------------------------------------------------------------
_F7_JS = """\
(()=>{
const L={{LABELS}},SEG={{SEGS}},V={{VALUES}},C={{COUNTS}},STEP={{STEP}};
const SHADE=['#1C1C1A','#8F8E88','#C0BFB8'];
obsReveal('ch',s=>{
  const x0=i=>72+i*76,base=262,step=STEP,HW=13;
  L.forEach((name,i)=>{
    const x=x0(i);let k0=0;
    V[i].forEach((v,si)=>{
      const n=C[i][si];
      for(let k=0;k<n;k++){
        const y=base-(k0+k+si)*step,w=HW-1.4+rnd(k+1,i*3+si+2)*2.8;
        el(s,'line',{x1:x-w,y1:y,x2:x+w,y2:y,stroke:SHADE[si],'stroke-width':1,
          opacity:.6+rnd(k+2,i+si+4)*.4,class:'fade',
          style:`animation-delay:${i*.09+(k0+k)*.012}s`});
      }
      const midY=base-(k0+n/2+si)*step;
      const lab=txt(s,{x:x+HW+7,y:midY+2.5,'font-size':8,'font-weight':800,
        fill:SHADE[si]==='#C0BFB8'?'#8F8E88':SHADE[si],class:'fade',
        style:`animation-delay:${.5+i*.09+si*.06}s`},v);
      tip(lab,`${name} ${SEG[si]} — ${v} {{YLABEL}}`);
      k0+=n;
    });
    const total=V[i].reduce((a,b)=>a+b,0);
    txt(s,{x,y:base-(k0+2)*step-8,'font-size':10.5,'font-weight':800,fill:INK,'text-anchor':'middle',
      class:'fade',style:`animation-delay:${.6+i*.09}s`},total);
    txt(s,{x,y:base+18,'font-size':7.5,'font-weight':700,fill:MUTED,'text-anchor':'middle',
      'letter-spacing':'.08em',class:'fade',style:`animation-delay:${i*.09}s`},name);
  });
  el(s,'line',{x1:36,y1:base+4,x2:364,y2:base+4,stroke:GRID,'stroke-width':.8,class:'fade'});
  txt(s,{x:200,y:306,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.1s'},'{{NOTE}}');
});
})();
"""


def render_F7(labels, seg_names, values, title, sub, src, y_label="单位", note=None):
    flat = [v for row in values for v in row]
    unit = unit_for(flat, 26)
    counts = [[max(1, round(v / unit)) if v > 0 else 0 for v in row] for row in values]
    maxc = max([c for row in counts for c in row], default=1)
    step = min(5.2, 240 / maxc)
    if note is None:
        note = f"每格 = {unit} {y_label} · 最深 = {seg_names[0] if seg_names else '第一段'}"
    js = (_F7_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{SEGS}}", _js(seg_names))
          .replace("{{VALUES}}", _js(values)).replace("{{COUNTS}}", _js(counts))
          .replace("{{STEP}}", _fmt(step)).replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F9 · Rung Waterfall 瀑布(≤6 级)
# ---------------------------------------------------------------
_F9_JS = """\
(()=>{
const L={{LABELS}},V={{VALUES}},IS={{IS}},STEP={{STEP}};
obsReveal('ch',s=>{
  const x0=i=>58+i*72,step=STEP,HW=11;
  let lv=0;const rows=[];
  L.forEach((name,i)=>{
    const v=V[i];
    if(IS[i]){
      if(i===0){rows.push([name,v,0,v]);lv=v}
      else rows.push([name,lv,0,lv]);
    }else{rows.push([name,v,lv+v,lv]);lv=lv+v}
  });
  const base=252,yOf=k=>base-k*step;
  rows.forEach(([name,v,lo,hi],i)=>{
    const x=x0(i),isTotal=IS[i],neg=v<0&&!isTotal;
    const from=isTotal?0:lo,to=isTotal?v:hi,n=Math.abs(to-from);
    for(let k=0;k<n;k++){
      const y=yOf(from+k),w=HW-1.2+rnd(k+1,i+2)*2.4;
      if(neg)el(s,'line',{x1:x-w,y1:y,x2:x+w,y2:y,stroke:'#8F8E88','stroke-width':1,
        'stroke-dasharray':'2.5 2.5',opacity:.7,class:'fade',style:`animation-delay:${i*.12+k*.014}s`});
      else el(s,'line',{x1:x-w,y1:y,x2:x+w,y2:y,stroke:INK,'stroke-width':1,
        opacity:.6+rnd(k+2,i+4)*.4,class:'fade',style:`animation-delay:${i*.12+k*.014}s`});
    }
    if(i<rows.length-1){
      const nx=x0(i+1),lvl=isTotal?v:(neg?lo:hi);
      el(s,'line',{x1:x+HW+2,y1:yOf(lvl),x2:nx-HW-2,y2:yOf(lvl),stroke:'#C6C5BF',
        'stroke-width':.7,'stroke-dasharray':'2 3',class:'fade',
        style:`animation-delay:${.3+i*.12}s`});
    }
    const topY=yOf(Math.max(from,to));
    const num=txt(s,{x,y:topY-8,'font-size':10,'font-weight':800,
      fill:neg?'#8F8E88':INK,'text-anchor':'middle',class:'fade',style:`animation-delay:${.4+i*.12}s`},
      (neg?'−':'')+Math.abs(v));
    tip(num,`${name} — ${neg?'−':''}${v} {{YLABEL}}`);
    txt(s,{x,y:base+18,'font-size':7.5,'font-weight':700,fill:MUTED,'text-anchor':'middle',
      'letter-spacing':'.08em',class:'fade',style:`animation-delay:${i*.12}s`},name);
  });
  el(s,'line',{x1:30,y1:base+4,x2:370,y2:base+4,stroke:GRID,'stroke-width':.8,class:'fade'});
  txt(s,{x:200,y:302,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.2s'},'{{NOTE}}');
});
})();
"""


def render_F9(labels, values, is_total, title, sub, src, y_label="单位", note=None):
    steps = []
    lv = 0
    for i, v in enumerate(values):
        if is_total[i]:
            steps.append(abs((lv or v) - (0 if i == 0 else lv)))
            if i == 0:
                lv = v
        else:
            steps.append(abs(v))
            lv = lv + v
    maxn = max(steps, default=1)
    step = min(5.2, 240 / maxn)
    if note is None:
        note = "实心档累加 · 虚线档扣减 · 首尾为合计"
    js = (_F9_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES}}", _js(values))
          .replace("{{IS}}", _js([bool(x) for x in is_total])).replace("{{STEP}}", _fmt(step))
          .replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F11 · Tick Gauge 进度(单值 0-100%)
# ---------------------------------------------------------------
_F11_JS = """\
(()=>{
const GOAL={{GOAL}};
obsReveal('ch',s=>{
  const cx=200,cy=190,R0=104,A0=-195,SW=210;
  for(let k=0;k<100;k++){
    const a=A0+k/100*SW,inked=k<GOAL;
    const len=inked?13+rnd(k+1,3)*6:5+rnd(k+1,7)*2.5;
    const [x1,y1]=pol(cx,cy,R0,a),[x2,y2]=pol(cx,cy,R0+len,a);
    el(s,'line',{x1,y1,x2,y2,stroke:inked?INK:'#CFCEC7','stroke-width':inked?1:.6,
      class:'fade',style:`animation-delay:${k*.012}s`});
  }
  [25,50,75,100].forEach(m=>{
    const a=A0+m/100*SW,[dx,dy]=pol(cx,cy,R0-7,a),[tx2,ty2]=pol(cx,cy,R0-19,a);
    el(s,'circle',{cx:dx,cy:dy,r:1,fill:'#B0AFA9',class:'fade',style:'animation-delay:.8s'});
    txt(s,{x:tx2,y:ty2+3,'font-size':7,'font-weight':600,fill:'#C6C5BF','text-anchor':'middle',
      class:'fade',style:'animation-delay:.85s'},m);
  });
  const aT=A0+GOAL/100*SW,[ex,ey]=pol(cx,cy,R0+20,aT);
  el(s,'circle',{cx:ex,cy:ey,r:2.4,fill:INK,class:'pop',style:'animation-delay:1.1s'});
  const num=txt(s,{x:cx,y:cy-4,'font-size':34,'font-weight':800,fill:INK,'text-anchor':'middle',
    class:'fade',style:'animation-delay:1s'},GOAL+'%');
  tip(num,'{{TIP}}');
  txt(s,{x:cx,y:cy+16,'font-size':8,'font-weight':600,fill:MUTED,'text-anchor':'middle',
    'letter-spacing':'.1em',class:'fade',style:'animation-delay:1.05s'},'{{REMAIN}}');
  txt(s,{x:200,y:300,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1.2s'},'{{NOTE}}');
});
})();
"""


def render_F11(value, title, sub, src, goal=100, y_label="", note=None):
    goal = max(0, min(100, goal))
    goal = int(round(goal))
    remain = max(0, 100 - goal)
    if note is None:
        note = "一格 = 目标的 1% · 上墨 = 已完成"
    tip_text = f"{goal}% · 还差 {remain}%"
    js = (_F11_JS
          .replace("{{GOAL}}", str(goal)).replace("{{TIP}}", tip_text)
          .replace("{{REMAIN}}", f"{remain} 未完成").replace("{{NOTE}}", note))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# F12 · Dumbbell Queue 哑铃对比(前后对比, ≤6)
# ---------------------------------------------------------------
_F12_JS = """\
(()=>{
const L={{LABELS}},A={{VALUES_A}},B={{VALUES_B}},CA={{COUNTS_A}},CB={{COUNTS_B}},
      MINV={{MIN}},MAXV={{MAX}},GAP={{GAP}},UNIT={{UNIT}};
obsReveal('ch',s=>{
  const y0=i=>54+i*GAP,X0=118,X1=364;
  const span=Math.max(1,MAXV-MINV),mapX=v=>X0+(v-MINV)/span*(X1-X0);
  L.forEach((name,i)=>{
    const y=y0(i),was=A[i],now=B[i],xa=mapX(was),xb=mapX(now);
    txt(s,{x:108,y:y+3,'font-size':7.5,'font-weight':700,fill:'#6A6963','text-anchor':'end',
      'letter-spacing':'.06em',class:'fade',style:`animation-delay:${i*.08}s`},name);
    el(s,'line',{x1:X0-6,y1:y,x2:X1+6,y2:y,stroke:'#E3E2DB','stroke-width':.7,
      class:'fade',style:`animation-delay:${i*.08}s`});
    const n=Math.max(0,Math.round(Math.abs(was-now)/Math.max(1,UNIT)));
    for(let k=0;k<n;k++){
      const t=(k+.5)/n,x=xb+t*(xa-xb),yy=y+(rnd(k+1,i+3)-.5)*2.6;
      el(s,'circle',{cx:x,cy:yy,r:1.5+rnd(k+2,i+4)*.9,fill:'#8F8E88',opacity:.85,
        class:'pop',style:`animation-delay:${.3+i*.08+k*.03}s`});
    }
    el(s,'circle',{cx:xa,cy:y,r:4.2,fill:PAPER,stroke:INK,'stroke-width':1.3,
      class:'pop',style:`animation-delay:${.2+i*.08}s`});
    const after=el(s,'circle',{cx:xb,cy:y,r:4.6,fill:INK,
      class:'pop',style:`animation-delay:${.6+i*.08}s`});
    tip(after,`${name} — ${was} → ${now} {{YLABEL}}`);
    txt(s,{x:xa+10,y:y-8,'font-size':8.5,'font-weight':700,fill:'#B0AFA9',
      class:'fade',style:`animation-delay:${.3+i*.08}s`},was);
    txt(s,{x:xb-10,y:y-8,'font-size':10,'font-weight':800,fill:INK,'text-anchor':'end',
      class:'fade',style:`animation-delay:${.7+i*.08}s`},now);
  });
  txt(s,{x:X0,y:290,'font-size':7,'font-weight':600,fill:'#C6C5BF',class:'fade'},'{{LEFT}}');
  txt(s,{x:X1,y:290,'font-size':7,'font-weight':600,fill:'#C6C5BF','text-anchor':'end',
    class:'fade'},'{{RIGHT}}');
  txt(s,{x:200,y:308,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade',style:'animation-delay:1s'},'{{NOTE}}');
});
})();
"""


def render_F12(labels, values_a, values_b, title, sub, src, y_label="单位",
               left_hint="", right_hint="", note=None):
    lo, hi = min(min(values_a), min(values_b)) if values_a else (0, 1), max(max(values_a), max(values_b)) if values_b else (0, 1)
    lo, hi = min(lo, hi), max(lo, hi)
    if lo == hi:
        hi = lo + 1
    diffs = [abs(a - b) for a, b in zip(values_a, values_b)]
    unit = unit_for(diffs, 30)
    ca = counts_for(diffs, unit)
    n = max(1, len(labels))
    gap = min(46, 240 / n)
    if note is None:
        note = "空心 = 前值 · 实心 = 现值 · 两珠之间一格 = %s %s" % (unit, y_label)
    js = (_F12_JS
          .replace("{{LABELS}}", _js(labels)).replace("{{VALUES_A}}", _js(values_a))
          .replace("{{VALUES_B}}", _js(values_b)).replace("{{COUNTS_A}}", _js(ca))
          .replace("{{COUNTS_B}}", _js(ca)).replace("{{MIN}}", _fmt(lo)).replace("{{MAX}}", _fmt(hi))
          .replace("{{GAP}}", _fmt(gap)).replace("{{UNIT}}", str(unit))
          .replace("{{NOTE}}", note).replace("{{YLABEL}}", y_label)
          .replace("{{LEFT}}", left_hint).replace("{{RIGHT}}", right_hint))
    return page(title, sub, src, js)


# ---------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------
REGISTRY = {
    "F1": render_F1,
    "F2": render_F2,
    "F3": render_F3,
    "F4": render_F4,
    "F5": render_F5,
    "F6": render_F6,
    "F7": render_F7,
    "F9": render_F9,
    "F11": render_F11,
    "F12": render_F12,
}


def _round_sum(pcts, n):
    """把四舍五入后的百分比数组凑成整 100(把误差加到最大的段上)"""
    diff = 100 - sum(pcts)
    if diff and n:
        i = pcts.index(max(pcts))
        pcts[i] += diff
    return pcts


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
