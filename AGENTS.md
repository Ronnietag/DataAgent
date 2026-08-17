# DataAgent 项目指南

自然语言驱动数据分析 agent：中文问题 → LLM 生成 pandas 代码 → 受限沙箱执行 → 输出 DataFrame，前端带 AI 洞察 + 自动图表 + 自动报告。

## 常用命令

```bash
# 启动 Web 服务（自动加载 .env，端口 8765）
./web/start.sh

# 运行测试（pytest，tests/ 下，conftest 已把 web/ 加入 sys.path）
python3.11 -m pytest tests/

# 单测一个文件
python3.11 -m pytest tests/test_sandbox.py -q

# CLI 直连模式（不启动 web）
python3 data_agent.py <excel路径> "<中文问题>"
# 跳过 LLM，验证沙箱链路
python3 data_agent.py <excel路径> --dry-run
```

环境要求：`/opt/homebrew/bin/python3.11`（start.sh 固定用它）。依赖见 `requirements.txt`（pandas/fastapi/uvicorn/sqlalchemy/pyodbc/openpyxl）。

## 架构

```
数据源(Excel / SQL Server / SQLite / PostgreSQL) + 业务规则(rules.json)
   → 启动时加载到内存 DataFrame
   → FastAPI server (web/server.py)
   → 前端 (web/static)
```

- **数据源优先级**：`DATA_SOURCE_SQL` > `DATA_SOURCE`，SQL 查询启动时跑一次，之后 LLM 只基于内存 DataFrame 工作
- **API 端点**：`/api/health` `/api/preview` `/api/analyze`(SSE 流式) `/api/analyze_detail` `/api/chart` `/api/report` `/api/report_session`
- **图表**：Lieflat 模板库（`vendor/lieflat-charts` + `web/chart_templates/`），LLM 选图型 + 服务端渲染单文件 HTML，前端 `<iframe sandbox>` 展示，无 ECharts CDN

## 业务规则外置（关键）

规则在 `web/rules.json`，**改它即可改 LLM 行为，不要硬编码到 prompt**。结构：

- `filters`：前置规则，含 `priority`（high=必做 / medium=重要 / low=建议）
- `field_preferences`：`primary_metrics`/`secondary_metrics` 核心指标，`ignore_columns` 忽略列
- `output_style`：数字格式（全局 `decimal_places=2`、`format_rules` 针对特定列覆盖）
- `industry_specific`：行业合规约束

改完 rules.json **需重启 server** 生效。

## 硬性编码约定（改代码必须遵守）

1. **沙箱安全是红线**（`data_agent.py` + `web/server.py`）：
   - LLM 生成代码必须过 AST 白名单检查：禁 `__dunder__` 反射、禁 `import`、禁文件/网络 IO（`read_*`/`to_*` 全禁）
   - 沙箱 builtins 白名单 + 受限模块（pandas/numpy/math/collections/datetime/re）
   - 结果行数上限 `MAX_RESULT_ROWS = 100_000`
   - 任何新暴露给 LLM 的能力都要先评估逃逸风险
2. **数值口径**：
   - 增长率/同比/占比/份额：LLM 输出**小数比率**（0.99=99%），**绝不乘 100**，前端 ×100 显示 `%`
   - 数值统一 2 位小数（对齐 rules.json `decimal_places=2`），图表 `round(,2)`，表格前端 `formatCell`
3. **中文**：全项目中文，代码注释、UI、报告均用中文
4. **前端约束**：改样式可以，但所有 `id`/`class` 钩子/`data-*` 绑定与 JS 逻辑不能动（历史约束）

## 决策记录 (`docs/decisions/`)

项目的关键"为什么"沉淀在 [docs/decisions/](docs/decisions/),每条决策对应一个 ADR 文件:

- [ADR-0001](docs/decisions/0001-sandbox-security-baseline.md) 沙箱安全基线（AST + runtime 双层防御）
- [ADR-0002](docs/decisions/0002-rules-externalization.md) 业务规则外置到 `web/rules.json`
- [ADR-0003](docs/decisions/0003-numeric-format-decimal-rate.md) 数值口径（LLM 输出小数比率，前端 ×100 显示 %）
- [ADR-0004](docs/decisions/0004-excel-load-cap.md) Excel 加载上限 `nrows=200_000`
- [ADR-0005](docs/decisions/0005-single-file-frontend.md) 单 HTML 前端 + 内部分块标记
- [ADR-0006](docs/decisions/0006-wire-editorial-red-color.md) 图表默认配色 Wire · 编辑部红

引入/修改架构原则时,**新建或更新一条 ADR**(模板见 `docs/decisions/README.md`),不要只留在 commit message 里。

## 不要做的事

- 不要给 LLM 沙箱外直接执行任意代码的能力
- 不要在 prompt 里硬编码业务规则（改 rules.json）
- 不要改动 `vendor/` 下第三方库文件
- 不要提交 `.env`（含真实密钥，已在 .gitignore）
- `output/`、`deck/`、`web/user_memory.json` 是运行时产物，已 gitignore

## 测试

`tests/` 用 pytest，覆盖：沙箱安全（test_sandbox.py）、prompt 模板（test_prompt.py）、列格式（test_columns.py）、图表模板与 payload（test_chart.py / test_chart_templates.py）。

改沙箱或图表链路后必须跑 `python3.11 -m pytest tests/` 全绿才算完成。