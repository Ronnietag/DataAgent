# 0006: 图表默认配色改为 Wire · 编辑部红

- **Status**: Accepted
- **Date**: 2026-08-14
- **Deciders**: @ronnieliu

## Context

DataAgent 用 Lieflat 风格的图表模板(单文件 HTML + SVG + IntersectionObserver 懒加载)。原来的默认配色是**纯灰阶 Mono**:

- 灰阶承载全部数据
- 没有"主角"——所有元素颜色一致
- 用户(尤其非工程师)看图表时,目光没有着力点

Lieflat 官方仓库提供的 `color-presets.js` 里有**Wire · 编辑部红**预设——灰阶为主,荧光橙 `#F5572F` 点睛。这套配色:
- 与本项目数据特征贴合(医药 SFE 报告偏严肃)
- 主角规则清晰(每张图只一个 HERO)
- 不是 ECharts 时代的"彩色堆叠",而是"灰阶叙事 + 一点橙"

## Decision

调色板对齐官方 `color-presets.js` 的 Wire 预设:

| 角色 | 色值 | 用途 |
|---|---|---|
| `PAPER` | `#F0F0EE` | BG 纸 |
| `INK` | `#1F1E1C` | TXT 墨 |
| `HERO` | `#F5572F` | 荧光橙——**每张图只给一个元素** |
| `DATA` | `#22211F` | 数据墨(主数据) |
| `DATA2` | `#8F8E86` | 次级数据 / 减项 |
| `FAINTDATA` | `#C0BFB7` | 淡数据(前值 / 浅档) |
| `LAB` | `rgba(31,30,28,.72)` | 行名标签 |
| `FAINT` | `rgba(31,30,28,.32)` | 来源行 / 辅助刻度 |
| `GRID` | `rgba(31,30,28,.16)` | 网格 / 发丝线 |
| `FLOOR` | `rgba(31,30,28,.24)` | 底部刻度 / 未上墨 |
| `TRACK` | `rgba(31,30,28,.12)` | 轨道线 |
| `BEAD` | `#8F8E86` | 串珠 |

**主角上色规则**(每张图只一个 HERO):

| 图型 | 主角(橙) |
|---|---|
| F1 竖柱 | 最大值那根柱 |
| F2 折线 / F3 面积 | 峰值点 + 峰值发丝 |
| F4 环形 | 最大扇区 |
| F5 横向排名 | 第一名那行 |
| F6 分组柱 | 现值(B)数值标签 |
| F7 堆叠 | 最底层段 |
| F9 瀑布 | NET 合计柱 |
| F11 进度表盘 | 当前值指针圆 |
| F12 哑铃 | 现值实心圆 |

**彩色加墨规则**: 数据线宽 ×1.8、透明度地板 .85。

## Consequences

**正面:**
- 图表视觉层级清晰——用户的眼睛知道往哪看
- 灰阶承载数据 → 数量感不被颜色干扰
- 与 Lieflat 官方保持一致,后续升级/借鉴方便

**负面/成本:**
- 单图型主角逻辑是手写的(如 F5 `MAXIDX` 行用 HERO),新增图型时要复制这个模式
- 一些场景可能需要"两个并列主角"(如 A/B 测试)——当前规则不允许,需要 override
- 颜色绑定在 JS 模板字符串里,改主题要重写 `_HELPERS` + 各图型 JS

## References

- 提交: `d5891fb` 2026-08-14
- 文件: `web/chart_templates/_base.py`(调色板 + CSS + `_HELPERS` JS 常量)
- 文件: `web/chart_templates/basics.py`(各图型 wire 改造)
- 上游: Lieflat `color-presets.js` 的 wire 预设
- 文档: `README.md` 图表模板库章节