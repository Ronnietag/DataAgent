# 0004: Excel 数据源加载上限 nrows=200_000

- **Status**: Accepted
- **Date**: 2026-08-11
- **Deciders**: @ronnieliu

## Context

启动时把 Excel 全表读进内存 `_global_df`(见 `web/server.py:startup → load_data_source`)。如果数据源有几百万行:

- 内存爆(每行 60 列的 DataFrame ≈ 数十 MB/10万行,几百万行就 1GB+)
- 启动时间不可接受(openpyxl 慢,百万行 30 秒+)
- LLM 一次性给所有数据做分析的 prompt 也会爆 token
- 沙箱 `MAX_RESULT_ROWS = 100_000` 限制了**输出**,但不限制**输入**

实测当前数据(测试数据.xlsx)91,392 行 × 60 列,启动约 3-4 秒,内存占用 < 200MB,体验良好。

## Decision

`web/server.py:372` 加载 Excel 时硬编码上限:

```python
_global_df = pd.read_excel(DATA_SOURCE_PATH, sheet_name=sheet, nrows=200000)
```

**200_000 行**是按"启动 3-4 秒 / 内存 < 400MB / LLM prompt 可控"估的。当前 9 万行远未触及,留有 2 倍余量。

**配套**:
- 不在 LLM 端控"输入行数"——LLM 只在内存 DataFrame 上做分析,启动已过滤好
- 真要分析 > 20 万行的数据,应走 SQL 源(在数据库里预先过滤/聚合)

## Consequences

**正面:**
- 启动时间与内存占用有硬上限,服务稳定
- LLM 不会被"一次性给太多数据"卡死
- 与沙箱 `MAX_RESULT_ROWS` 配合,形成"输入 ≤ 200k → 处理 → 输出 ≤ 100k"的完整链

**负面/成本:**
- 超 200k 行的数据源静默截断,业务方可能不知道
- 没有"提前告知截断"的 UX——如果未来需要,应在 `/api/health` 暴露 `actual_rows` vs `loaded_rows`
- SQL 源没有同等限制(取决于查询);如果用户写了 `SELECT * FROM huge_table`,同样会爆

## References

- 提交: `b7d475d` 2026-08-11 (初始提交)
- 文件: `web/server.py:372`
- 数据规模基线: 当前 `测试数据.xlsx` 91,392 行 × 60 列
- 关联: ADR-0001(沙箱 `MAX_RESULT_ROWS = 100_000`)