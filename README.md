# DataAgent

自然语言驱动数据分析 agent —— **数据源启动时指定,多轮对话支持,带 AI 洞察 + 自动图表 + 自动报告**。

## 📌 最近更新(2026-08-14)

**Lieflat 图表模板库(替换 ECharts)**
- 引入 lieflat-charts 模板库(`vendor/lieflat-charts` + `web/chart_templates/`),支持 **10 种图型**:柱状 / 折线 / 面积 / 环形占比 / 横向排名 / 分组对比 / 堆叠 / 瀑布 / 进度表盘 / 哑铃对比
- `/api/chart` 改为 **LLM 图型选型 + 服务端渲染单文件 HTML**,前端 `<iframe sandbox>` 展示,移除 ECharts CDN 与前端 option 构建
- 图表数值统一 2 位小数(对齐 `rules.json` 全局 `decimal_places=2`);前端表格对未匹配特殊规则的纯数值列(学术接受度/指数等)同样 2 位小数展示

### 2026-08-11

**界面重设计(v2)**
- 全新设计系统:中性灰底 `#f7f7f8` + 白卡 + 单靛蓝强调色 `#4f46e5`,去掉渐变/炫技风格
- 全部 emoji 图标替换为内联 SVG 图标(lucide 风格 stroke 1.8)
- 移除 Tailwind CDN,改为自建 CSS 设计系统(去 CDN 依赖,更易内网部署)
- 消息区 880px 居中、圆角发送按钮、输入容器聚焦态、统一表单控件样式
- 约束:所有 `id` / `class` 钩子 / `data-*` 绑定与 JS 逻辑零改动,功能全部保留

**功能修复与加固**
- 增长率口径修复:LLM 输出小数比率(0.99=99%),前端统一 ×100 显示 `%`
- 沙箱加固:AST 白名单检查 + 受限 builtins + 结果行数上限,防止绕过沙箱
- 图表修复:`x/y` 列放反检测与自动纠正(数值列/类别列判定,保留 LLM 列选择意图)
- 稳定性:同步 LLM 调用改 `run_in_threadpool`、会话惰性清理、memory 读写加 `RLock`、markdown 渲染白名单 sanitize

## 🎯 业务规则外置(`web/rules.json`)

业务规则不再硬编码到 prompt —— **修改 `rules.json` 即可改变 LLM 行为**。

### 规则文件结构
```json
{
  "filters": [
    {
      "name": "度量值过滤",
      "description": "用 学术接受度/同期_学术接受度 累加时,务必先用 df['度量值'] == '学术接受度' 过滤",
      "type": "prepend",
      "priority": "high"
    }
  ],
  "field_preferences": {
    "primary_metrics": ["学术接受度", "同期_学术接受度"],
    "secondary_metrics": ["接受度指数"],
    "ignore_columns": ["医院ID", "区县", "市"]
  },
  "industry_specific": {
    "current_industry": "医药 SFE",
    "compliance_constraints": ["《医药代表管理办法》2026.8.1 施行"]
  }
}
```

### priority 标记
- `high` — 必做,LLM 必须遵守
- `medium` — 重要,默认遵守
- `low` — 建议遵守

> 前端"配置"面板中以 高(必做)/中(默认)/低(建议) 展示,与 rules.json 的 `priority` 字段一一对应

### 列特定格式规则(`output_style.format_rules`)
针对特定列覆盖全局格式,例如"学术接受度 保留 2 位小数":
```json
{
  "output_style": {
    "number_format": "rate_pct",
    "decimal_places": 2,
    "thousand_separator": true,
    "format_rules": [
      {
        "name": "金额列",
        "apply_to_columns": ["销售额", "学术接受度"],
        "decimal_places": 2,
        "thousand_separator": true,
        "multiplier": 1,
        "description": "数值类列:千分位 + 2 位小数"
      }
    ]
  }
}
```

**字段说明**:`apply_to_columns` 作用的列 / `decimal_places` 小数位 / `multiplier` 倍数(如 1=原值、100=百分数) / `prefix`+`suffix` 前后缀 / `thousand_separator` 千分位。

> ⚠️ 注意:`format_rules` 目前作为**提示词约束**喂给 LLM(输出数据时尽量遵守),并在**前端/图表展示时统一按 2 位小数兜底格式化**;它不是数据层的强约束,若 LLM 输出超长小数,展示端会截断到配置小数位。

### 用法
```bash
# 编辑 web/rules.json 加新规则
vim web/rules.json

# 重启 server,新规则自动生效
./web/start.sh
```

也可指定自定义路径:`export RULES_PATH=/path/to/your-rules.json`

## 三种数据源

### 1. Excel 文件(最简)
```bash
export DATA_SOURCE=/path/to/your-data.xlsx
export DATA_SOURCE_SHEET=0             # 可选,默认 0
export DATA_SOURCE_LABEL="2026 Q1 SFE"  # 可选,显示在前端
./web/start.sh
```

### 2. SQL Server(生产推荐 ✅)
```bash
# 装 ODBC driver(macOS)
brew install msodbcsql17

# 启动
export DATA_SOURCE_SQL='mssql+pyodbc://sa:YourStrong@Passw0rd@localhost:1433/SFE_DB?driver=ODBC+Driver+17+for+SQL+Server'
export DATA_SOURCE_SQL_QUERY='SELECT * FROM dbo.sfe_data_2026q1'
export DATA_SOURCE_SQL_LABEL='SFE 2026 Q1 数据库'
./web/start.sh
```

> **预定义 SQL 查询** 会启动时跑,把结果加载到内存。LLM 后续基于 DataFrame 工作,不会直接接触数据库。安全 + 简单。

### 3. SQLite / PostgreSQL(开发/测试)
```bash
# SQLite
export DATA_SOURCE_SQL='sqlite:////absolute/path/to/test.db'
export DATA_SOURCE_SQL_QUERY='SELECT * FROM sfe_data'

# PostgreSQL
export DATA_SOURCE_SQL='postgresql+psycopg2://user:pass@localhost:5432/db'
export DATA_SOURCE_SQL_QUERY='SELECT * FROM public.sfe_data'
```

> **优先级**:`DATA_SOURCE_SQL` > `DATA_SOURCE`(同时设置时 SQL 优先)

## LLM 配置(任选一个)
```bash
# minimax(默认)
export MINIMAX_API_KEY=sk-cp-xxx
export LLM_BASE_URL=https://api.minimaxi.com/v1
export LLM_MODEL=MiniMax-M3

# DeepSeek
export DEEPSEEK_API_KEY=sk-xxx
export LLM_BASE_URL=https://api.deepseek.com/v1
export LLM_MODEL=deepseek-chat

# OpenAI
export OPENAI_API_KEY=sk-xxx
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4
```

## 启动
```bash
# 浏览器访问
open http://localhost:8765
```

## 核心功能

| 功能 | 触发 | 响应时间 |
|---|---|---|
| 提问分析 | 每次输入框发送 | 30-40s |
| **多轮对话** | 上下文保留 5 轮历史 | 自动 |
| **AI 洞察 + 后续问题建议** | 手动点按钮 | +8s |
| **自动图表** | 手动点按钮 | +4-8s |
| **单条分析报告** | 手动点按钮 | +56s |
| **会话总结报告** | 顶部按钮(基于整段对话) | +46s |
| **智能数据格式化** | 自动 | - |
| 继续提问 | 点建议问题按钮 / 输入新问题 | 30-40s |
| 清空对话 | 顶部清空按钮 | 立即 |

## 智能数据格式化(前端自动)

| 字段类型 | 例子 | 输出 |
|---|---|---|
| **增长率/同比/占比/份额** | `125.45`(倍) | `12,545.00%` |
| **销量/金额/数量/同期/本期/上期/cur/prev/sum** | `26.02` | `26.02` |
| **员工编号/ID/代码** | `3972` | `3972` |
| **其他纯数值**(学术接受度/指数/评分等) | `0.9466` | `0.95`(2 位小数,整数保持整数) |
| **其他**(姓名/大区/产品等) | `周庆` | 保持原样 |

> 数值统一 2 位小数,与 `rules.json` 的 `output_style.decimal_places` 一致。图表中的数值由后端 `_build_chart_payload` 统一 `round(,2)`,表格由前端 `formatCell` 格式化。

## 架构

```
数据源(Excel / SQL Server / SQLite / PostgreSQL)
   + 业务规则(rules.json)
        ↓
   启动时加载到内存
        ↓
   FastAPI server
   ┌────────────────────────────────────────┐
   │ /api/health   /api/preview             │
   │ /api/analyze  SSE 流式分析             │
   │ /api/analyze_detail 单独触发 AI 洞察   │
   │ /api/chart    选 Lieflat 图型 + 渲染单文件 HTML │
   │ /api/report   单条分析报告(markdown)   │
   │ /api/report_session 会话总结报告       │
   │ /api/session/clear  清空对话          │
   └────────────────────────────────────────┘
        ↓
   浏览器
   ┌────────────────────────────────────────┐
   │  数据源状态  │   对话区                 │
   │              │   用户消息(右)            │
   │              │   AI 消息(左)             │
   │              │   · 代码(可折叠)          │
   │              │   · 数据表格              │
   │              │   · 图表(Lieflat 模板)     │
   │              │   · 洞察 + 建议          │
   │              │   · 单条报告(markdown)    │
   └────────────────────────────────────────┘
```

## 核心模块

### LLM 调用
- OpenAI 兼容协议(DeepSeek / minimax / OpenAI 都支持)
- 通过环境变量配置
- 通用 `_clean_think()` 去掉 thinking 模式残留

### 业务规则(`web/rules.json`)
- 启动时加载,自动注入到 system prompt
- 三类规则:filters(必做) / field_preferences(字段偏好) / industry_specific(行业背景)
- 修改文件 + 重启即可生效,不用改代码

### 沙箱安全
- **白名单 builtins**:只暴露安全的 Python 内建函数
- **白名单 import**:只允许 `pandas / numpy / math / collections / datetime / re`
- **隔离 globals**:LLM 代码看不到宿主的任何变量
- **nlargest monkey-patch**:自动处理 `pd.NA` 引起的 dtype object 报错
- **inf → NaN 兜底**:避免 `nlargest` 把 inf 排前

### LLM 错误重试
- 最多 2 次重试
- 错误信息回传给 LLM,要求输出**完整代码**

### 多轮对话
- Server 内存管理 session(最多 5 轮历史 + result_summary)
- 每次 LLM 调用都带历史 messages

### 图表模板库(`web/chart_templates/`)
- 基于 lieflat-charts 风格(源码在 `vendor/lieflat-charts/`,PolyForm Noncommercial 1.0.0,内部非商业使用)
- **10 种图型**:F1 柱状 / F2 折线 / F3 面积 / F4 环形占比 / F5 横向排名 / F6 分组对比 / F7 堆叠 / F9 瀑布 / F11 进度表盘 / F12 哑铃对比
- 流程:`/api/chart` → LLM 从 10 种图型选型(`CHART_PROMPT` 约束)→ `_build_chart_payload` 按图型契约提取 x/y/y2/y3 列并校验兜底 → `render_chart` 渲染单文件 HTML(内联 CSS/JS,含 IntersectionObserver 懒加载动画)→ 前端 `<iframe sandbox="allow-scripts allow-same-origin" srcdoc>` 展示
- 数值统一保留 2 位小数(`fmt_val` round),避免图表显示长小数
- **扩展新图型**:在 `web/chart_templates/basics.py` 加渲染函数 + 在 `__init__.py` 注册到 `REGISTRY` 和 `TEMPLATE_META`,并在 `_TEMPLATE_ALIASES`(server.py)添加别名

## 项目结构

```
DataAgent/
├── data_agent.py              # CLI 核心(可选)
├── web/
│   ├── server.py              # FastAPI 后端
│   ├── rules.json             # 业务规则(可编辑)
│   ├── chart_templates/       # Lieflat 图表模板库(F1-F12 渲染函数 + 统一入口)
│   ├── static/
│   │   └── index.html         # 单文件前端(原生 JS + 自建 CSS + marked.js CDN,图表 iframe 渲染)
│   ├── uploads/               # 旧版上传目录(已废弃)
│   └── start.sh               # 启动脚本
├── vendor/
│   └── lieflat-charts/        # lieflat 图表源码(模板/许可证/说明,仅供模板库参考)
├── output/                    # CSV 输出 + 报告样本
├── tests/                     # pytest 回归测试(模板渲染 + 选型 + payload)
├── requirements.txt
└── README.md
```

## 限制 & 下一步

- 当前数据全量加载到内存,大数据量(> 100万行)需 SQL 预过滤
- 没有 SQL 审计日志(所有 SQL 都是启动时预定义的,不是 LLM 生成)
- 没有数据脱敏(医药合规场景需要)
- 没有持久化历史会话(刷新页面就丢)

## 路线图(已完成 ✅ / 待做 📋)

- ✅ CLI demo
- ✅ Web 界面
- ✅ 固定数据源(启动时加载)
- ✅ 多轮对话
- ✅ AI 洞察 + 后续问题建议
- ✅ 自动图表(Lieflat 模板库,10 种图型)
- ✅ SQL Server 接入(预定义查询模式)
- ✅ JSON 业务规则外置
- ✅ 数据格式智能优化
- ✅ 自动生成报告(单条 + 会话总结)
- ✅ 智能数据格式化(千分位 / 百分数)
- 📋 数据脱敏(医药合规)
- 📋 Docker Compose 一键起
- 📋 PDF 导出
- 📋 持久化历史会话(pgvector)
- 📋 LLM 动态生成 SQL(支持任意查询)
