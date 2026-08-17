# 决策记录 (Architecture Decision Records)

本目录存放项目关键决策的"为什么"。每条决策对应一个 `NNNN-slug.md` 文件,记录当时的背景、决定、影响。

> 借鉴自 DeepSeek Harness 的 `.agents/notes/` 文化与 Michael Nygard 的 ADR 模板。

## 何时写一条新决策

**需要写**(non-trivial):
- 引入 / 修改一项架构原则(沙箱、口径、规则外置、配色等)
- 推翻或大幅修改既有决策(写一条新的 `Supersedes` 引用旧的)
- 选了一个"看起来过度"或"看起来不够"的方案(解释为什么)

**不必写**(mechanical):
- 改 typo / 修 bug / 调整样式
- 加新图型 / 新规则条目(走普通 commit)
- 文档翻译 / 重命名

## 文件命名

`NNNN-slug.md`,四 序号(如 `0001-sandbox-security-baseline.md`)。slug 用短横线连接的英文短语。

## Status 流转

| Status | 含义 |
|---|---|
| `Proposed` | 已提但未实施,等评审 |
| `Accepted` | 已实施并稳定 |
| `Superseded` | 被新决策替代(在 ADR 里写明被哪条 `Supersedes`) |
| `Deprecated` | 不再适用,但代码可能还在用(标记"将来移除") |

## 模板

```markdown
# NNNN: <标题>

- **Status**: Proposed | Accepted | Superseded | Deprecated
- **Date**: YYYY-MM-DD(决策固化日期)
- **Deciders**: @username

## Context
<背景/问题:什么场景、什么约束、什么选项被考虑过、为什么>

## Decision
<最终决定:具体规约或方案>

## Consequences

**正面:**
- ...

**负面/成本:**
- ...

## References
- 提交: <git-sha> YYYY-MM-DD
- 文件: <path:line>
```

## 引用方式

在 commit message、PR 描述、AGENTS.md、代码注释里用 `[ADR-NNNN]` 引用。