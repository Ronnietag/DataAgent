# 0001: 沙箱安全基线

- **Status**: Accepted
- **Date**: 2026-08-11
- **Deciders**: @ronnieliu

## Context

DataAgent 让 LLM 生成 pandas 代码并在服务端执行——这意味着**LLM 输出的字符串会被 `exec()`**。如果没有强约束,LLM 可以:

- 通过 `__import__('os').system('rm -rf /')` 执行任意命令
- 通过 `open('/etc/passwd')` 读敏感文件
- 通过 `__class__.__mro__` 反射链逃出沙箱
- 通过 `pd.read_csv('http://evil.com/...')` 触发网络 IO
- 返回巨型 DataFrame(几十万行)导致 OOM

常规 `eval` 不够——AST 层 + runtime 层都需要约束。

## Decision

建立**双层防御**:

**AST 静态检查层**(代码生成到 `exec` 之间):
- 禁 `__dunder__` 访问(反射链,如 `__class__`、`__bases__`、`__subclasses__`)
- 禁 `import` 语句(代码内不能 import 模块)
- 禁文件 IO 与网络 IO 函数白名单外的调用(`read_*` / `to_*` 系列统一禁)

**Runtime 层**:
- `builtins` 白名单(只暴露必要内建:`len`、`range`、`int`、`float`、`str`、`list`、`dict`、`set`、`print` 等)
- 模块白名单:`pandas`、`numpy`、`math`、`collections`、`datetime`、`re`;其它 import 抛 `ImportError`
- 沙箱上下文只注入 `df`(当前数据)与 `pd`
- 结果行数上限 `MAX_RESULT_ROWS = 100_000`,超过抛 `ValueError`

**任何新增能力前先评估逃逸风险**(AGENTS.md 第 55 行)。

## Consequences

**正面:**
- LLM 生成的"危险代码"在到达 exec 之前被静态拦下
- 即使 AST 漏判,runtime 白名单也能兜住大部分逃逸
- 数据规模爆炸有硬上限,服务不会 OOM

**负面/成本:**
- 实现需要在 CLI(data_agent.py)与 Web(server.py)各维护一份,两处必须保持同步
- 严格白名单意味着 LLM 不能 import 用户想要的库(如 sklearn、scipy),需要权衡
- AST 黑名单可能被新模式绕过,要持续加 test_sandbox.py 用例覆盖

## References

- 提交: `b7d475d` 2026-08-11 (初始提交)
- 文件: `data_agent.py:59-160`, `web/server.py:1221-1309`
- 测试: `tests/test_sandbox.py`
- 约定: `AGENTS.md` 第 51-55 行