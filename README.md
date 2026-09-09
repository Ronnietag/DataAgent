# DataAgent

**中文问数据，30 秒出答案。**

自然语言驱动的数据分析 Agent —— 你用中文提问，它自动写 pandas 代码、执行分析、生成图表和报告。不用写 SQL，不用等数据组排期。

> 医药 SFE 团队实测：业务代表自己问"川渝大区各代表增长率 top10"，30 秒拿到结果，不用再排队等 2 天。

---

## 效果演示

```
你: 学术接受度增长率 top10 的代表有哪些？
AI: [自动写代码] → [执行分析] → [返回表格] → [生成图表] → [AI 洞察 + 后续问题建议]
```

**核心体验**：提问 → 等 30 秒 → 拿到完整分析（表格 + 图表 + 洞察 + 报告），全程零代码。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置（任选一个 LLM）
export MINIMAX_API_KEY=sk-xxx    # 或 DEEPSEEK_API_KEY / OPENAI_API_KEY

# 3. 指定数据源
export DATA_SOURCE=/path/to/your-data.xlsx

# 4. 启动
./web/start.sh

# 5. 浏览器打开
open http://localhost:8765
```

---

## 核心能力

| 能力 | 说明 |
|---|---|
| **中文提问** | 直接用业务语言提问，不用写 SQL 或代码 |
| **多轮对话** | 上下文自动保留 5 轮，支持追问和细化 |
| **AI 洞察** | 自动发现数据异常、趋势、关键结论 |
| **自动图表** | 10 种专业图表（柱状/折线/环形/瀑布/哑铃...），一键生成 |
| **自动报告** | 单条分析报告 + 会话总结报告，Markdown 格式 |
| **智能格式化** | 增长率自动转百分比、千分位分隔、小数位统一 |
| **业务规则外置** | 改 `rules.json` 就能改变 AI 行为，不用改代码 |

---

## 数据源支持

| 数据源 | 配置方式 |
|---|---|
| **Excel** | `export DATA_SOURCE=/path/to/data.xlsx` |
| **SQL Server** | `export DATA_SOURCE_SQL='mssql+pyodbc://...'` |
| **SQLite** | `export DATA_SOURCE_SQL='sqlite:////path/to/db'` |
| **PostgreSQL** | `export DATA_SOURCE_SQL='postgresql+psycopg2://...'` |

> SQL 模式：启动时执行预定义查询，结果加载到内存。LLM 只操作 DataFrame，不直接接触数据库。

---

## 业务规则引擎

改 `web/rules.json` 就能控制 AI 分析行为，不用改代码：

```json
{
  "filters": [
    {
      "name": "度量值过滤",
      "description": "用学术接受度累加时，务必先过滤度量值",
      "priority": "high"        // high=必做 / medium=重要 / low=建议
    }
  ],
  "field_preferences": {
    "primary_metrics": ["学术接受度", "同期_学术接受度"],
    "ignore_columns": ["医院ID", "区县"]
  },
  "output_style": {
    "decimal_places": 2,
    "thousand_separator": true
  }
}
```

---

## 架构

```
数据源(Excel / SQL) + 业务规则(rules.json)
        ↓ 启动时加载到内存
   FastAPI Server (Python 3.11)
   ├── /api/analyze    SSE 流式分析
   ├── /api/chart      图表选型 + 渲染
   ├── /api/report     分析报告
   └── /api/preview    数据预览
        ↓
   浏览器 (单文件前端)
   ├── 对话区（多轮）
   ├── 数据表格（智能格式化）
   ├── 图表（Lieflat 模板库）
   ├── AI 洞察 + 建议
   └── 分析报告
```

**安全设计**：LLM 生成的代码必须通过 AST 白名单检查 + 受限沙箱执行，禁止文件/网络操作。

---

## 图表模板库

基于 [Lieflat Charts](vendor/lieflat-charts/) 风格，支持 10 种专业图表：

| 图型 | 用途 | 说明 |
|---|---|---|
| F1 柱状 | 对比 | 最大值用荧光橙高亮 |
| F2 折线 | 趋势 | 峰值点用发丝线标注 |
| F3 面积 | 趋势对比 | 双面积叠加 |
| F4 环形占比 | 构成 | 最大扇区橙色突出 |
| F5 横向排名 | 排名 | TOP 行橙色 |
| F6 分组对比 | 对比 | 每组最大值橙色 |
| F7 堆叠 | 构成 | 底层段橙色 |
| F9 瀑布 | 变化 | NET 合计橙色 |
| F11 进度表盘 | KPI | 当前值橙色指针 |
| F12 哑铃对比 | 差异 | 现值圆橙色 |

**配色规则**：灰阶承载全部数据，荧光橙 `#F5572F` 只标每张图一个主角元素。

---

## LLM 配置

支持所有 OpenAI 兼容 API：

```bash
# MiniMax（默认）
export MINIMAX_API_KEY=sk-xxx
export LLM_MODEL=MiniMax-M3

# DeepSeek
export DEEPSEEK_API_KEY=sk-xxx
export LLM_MODEL=deepseek-chat

# OpenAI
export OPENAI_API_KEY=sk-xxx
export LLM_MODEL=gpt-4
```

---

## 项目结构

```
DataAgent/
├── web/
│   ├── server.py              # FastAPI 后端
│   ├── rules.json             # 业务规则（可编辑）
│   ├── chart_templates/       # Lieflat 图表模板库
│   ├── static/index.html      # 单文件前端
│   └── start.sh               # 启动脚本
├── data_agent.py              # CLI 核心
├── vendor/lieflat-charts/     # 图表源码参考
├── tests/                     # 回归测试
├── docs/decisions/            # 架构决策记录（ADR）
└── requirements.txt
```

---

## 技术亮点

- **零 CDN 依赖**：前端自建 CSS 设计系统，适合内网部署
- **沙箱安全**：AST 白名单 + 受限 builtins + 隔离 globals，防止代码注入
- **错误自愈**：LLM 代码报错自动重试 2 次，错误信息回传重写
- **单文件前端**：一个 HTML 包含全部逻辑，`<iframe sandbox>` 渲染图表
- **业务规则外置**：改 JSON 即改 AI 行为，支持前端可视化编辑

---

## 路线图

- [x] CLI demo
- [x] Web 界面 + 多轮对话
- [x] AI 洞察 + 自动图表 + 自动报告
- [x] SQL Server 接入
- [x] 业务规则外置
- [x] Lieflat 图表模板库（10 种图型）
- [ ] 数据脱敏（医药合规）
- [ ] Docker Compose 一键部署
- [ ] PDF 导出
- [ ] 持久化历史会话（pgvector）
- [ ] LLM 动态生成 SQL

---

## License

MIT
