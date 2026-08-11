# DataAgent

自然语言驱动数据分析 agent —— **数据源启动时指定,多轮对话支持,带 AI 洞察 + 自动图表 + 自动报告**。

## 📌 最近更新(2026-08-11)

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
| **其他**(姓名/大区/产品等) | `周庆` | 保持原样 |

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
   │ /api/chart    自动选图表类型 + 配置    │
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
   │              │   · 图表(ECharts)         │
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

## 项目结构

```
DataAgent/
├── data_agent.py              # CLI 核心(可选)
├── web/
│   ├── server.py              # FastAPI 后端
│   ├── rules.json             # 业务规则(可编辑)
│   ├── static/
│   │   └── index.html         # 单文件前端(原生 JS + 自建 CSS + ECharts + marked.js CDN)
│   ├── uploads/               # 旧版上传目录(已废弃)
│   └── start.sh               # 启动脚本
├── output/                    # CSV 输出 + 报告样本
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
- ✅ 自动图表(ECharts)
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
