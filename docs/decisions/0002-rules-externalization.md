# 0002: 业务规则外置到 rules.json

- **Status**: Accepted
- **Date**: 2026-08-11
- **Deciders**: @ronnieliu

## Context

LLM 行为受 prompt 影响很大。如果业务规则(过滤逻辑、字段偏好、输出格式、行业合规约束)写在 Python 字符串里:
- 改规则要改代码、重新部署、重启服务
- 不同行业/客户要 fork 代码分支
- 测试 prompt 改动 vs 代码改动混在一起

业务规则**本质是配置**,不是代码,应该和数据源路径、LLM key 一样外置。

## Decision

业务规则统一在 `web/rules.json`,**改它即可改 LLM 行为,不动 Python 代码**。结构分四区:

| 区 | 内容 | 例子 |
|---|---|---|
| `filters` | 数据过滤的前置规则(度量值统一、转岗不排除等),有 priority | 度量值过滤、离职转岗不排除 |
| `field_preferences` | 字段语义提示(primary/secondary/ignore) | 学术接受度 = primary;医院 = ignore |
| `output_style` | 数字格式(全局 + 列特定覆盖) | decimal_places=2;金额列千分位 |
| `calculation_rules` | 指标计算公式(同比/达成/环比) | 同比 = (cur-prev)/prev |
| `industry_specific` | 行业背景与合规约束 | 医药代表管理办法 2026.8.1 |

服务端启动时读入,注入到 LLM 的 system prompt(由 `web/server.py` 负责组装)。**改完 rules.json 需重启 server 生效**(无热加载)。

**不要做的事**(AGENTS.md 第 64-66 行):
- 不要把业务规则硬编码到 Python 字符串里
- 不要把业务规则塞进图表模板或前端代码

## Consequences

**正面:**
- 改业务规则不用改代码、不用走 PR review
- 不同客户/行业可以维护各自的 rules.json(通过 `RULES_PATH` 环境变量切换)
- rules.json 是单一事实源,prompt 模板可以保持稳定
- 团队里非工程师(业务方)也能改规则

**负面/成本:**
- JSON 没类型检查,改错 key 会导致 silent failure(启动会校验,但加新字段要小心)
- 优先级体系(high/medium/low)比较粗糙,复杂条件没法表达
- 热加载不做,改完必须重启——但这避免了一致性问题

## References

- 提交: `b7d475d` 2026-08-11 (初始提交)
- 文件: `web/rules.json`(完整结构)
- 服务组装: `web/server.py` 中加载 rules 并拼入 prompt 的相关函数
- 约定: `AGENTS.md` 第 38-47 行(业务规则外置)+ 第 64-66 行(不要做的事)