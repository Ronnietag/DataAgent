"""
DataAgent Demo - 自然语言驱动 Excel 数据分析
链路:中文问题 → LLM 生成 pandas 代码 → 受限沙箱执行 → 输出 DataFrame

用法:
  export DEEPSEEK_API_KEY=sk-xxx
  python3 data_agent.py <excel_path> "<中文问题>"

  # 不调 LLM,直接用内置模板跑(验证沙箱链路)
  python3 data_agent.py <excel_path> --dry-run
"""
import ast
import os
import sys
import re
import json
import argparse
import requests
import pandas as pd

# ============================================================
# 1. LLM 调用层(OpenAI 兼容,DeepSeek / minimax / OpenAI 都行)
# ============================================================
def call_llm(system: str, user: str) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.environ.get("LLM_MODEL", "MiniMax-M3")

    if not api_key:
        raise RuntimeError(
            "未配置 API key。请设置环境变量:\n"
            "  export DEEPSEEK_API_KEY=sk-xxx   (DeepSeek)\n"
            "  export MINIMAX_API_KEY=xxx       (minimax)\n"
            "或用 --dry-run 跳过 LLM"
        )

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-Token": api_key,  # minimax 网关特殊要求
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.1,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ============================================================
# 2. 沙箱执行层(白名单 builtins + 受限 import)
# ============================================================
SAFE_BUILTINS = {
    "len", "range", "enumerate", "zip", "map", "filter", "sum", "min", "max",
    "abs", "round", "int", "float", "str", "bool", "list", "dict", "set", "tuple",
    "sorted", "print", "isinstance", "type", "True", "False", "None",
    "any", "all", "repr", "slice",
}
ALLOWED_MODULES = {"pandas", "numpy", "math", "collections", "datetime", "re"}

# LLM 代码静态检查(AST 层加固,补充 builtins 白名单)
# 拦截:双下划线属性反射链 / 文件/网络 IO / import
# 注意:只能防"意外"和常规逃逸,对抗性攻击仍需进程/Docker 隔离(P0 规划)
_FORBIDDEN_FUNCS = {
    # pandas 文件/网络/pickle RCE
    "read_csv", "read_excel", "read_pickle", "read_sql", "read_sql_query",
    "read_sql_table", "read_json", "read_hdf", "read_parquet", "read_feather",
    "read_fwf", "read_table", "read_clipboard", "read_html", "read_stata",
    "read_sas", "read_spss", "read_orc", "read_xml", "read_gbq", "read_delim",
    "to_csv", "to_excel", "to_pickle", "to_sql", "to_hdf", "to_parquet",
    "to_feather", "to_clipboard", "to_stata", "to_sas", "to_xml", "to_orc",
    "ExcelFile", "HDFStore",
    # numpy 文件 IO
    "load", "save", "savez", "savez_compressed", "fromfile", "tofile",
    "loadtxt", "savetxt", "memmap",
}
MAX_RESULT_ROWS = 100_000


def _validate_llm_code(code: str) -> None:
    """静态检查 LLM 生成的代码,发现危险模式抛错(触发 LLM 重试)"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"代码语法错误:{e}")

    for node in ast.walk(tree):
        # 1. dunder 属性访问:df.__class__ / fn.__globals__ / obj.__subclasses__ 等反射链
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"禁止访问双下划线属性:'.{node.attr}'")
        # 2. import 语句(虽然 __import__ 已被守卫,双保险)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("禁止 import 语句")
        # 3. 文件/网络 IO 函数调用
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr.startswith("read_"):
                    raise ValueError(f"禁止文件/网络读取:'.{func.attr}'")
                if func.attr in _FORBIDDEN_FUNCS:
                    raise ValueError(f"禁止文件/网络 IO:'.{func.attr}'")
            if isinstance(func, ast.Name) and func.id == "__import__":
                raise ValueError("禁止直接调用 __import__")


def run_sandboxed(code: str, df: pd.DataFrame) -> pd.DataFrame:
    """在受限环境里执行 LLM 生成的 pandas 代码,返回 result DataFrame"""
    import builtins as _bi
    safe_bi = {k: getattr(_bi, k) for k in SAFE_BUILTINS if hasattr(_bi, k)}

    real_import = _bi.__import__
    def guarded_import(name, *a, **kw):
        root = name.split(".")[0]
        if root not in ALLOWED_MODULES:
            raise ImportError(f"模块 {root!r} 不在白名单,禁止导入")
        return real_import(name, *a, **kw)
    safe_bi["__import__"] = guarded_import

    # Monkey-patch nlargest:在调用前把 object 列转 numeric,避免 pd.NA 报错
    _orig_nlargest = pd.DataFrame.nlargest
    def _safe_nlargest(self, n, columns, *args, **kwargs):
        df_copy = self.copy()
        cols = columns if isinstance(columns, list) else [columns]
        for c in cols:
            if c in df_copy.columns and df_copy[c].dtype == object:
                df_copy[c] = pd.to_numeric(df_copy[c], errors="coerce")
        return _orig_nlargest(df_copy, n, columns, *args, **kwargs)
    pd.DataFrame.nlargest = _safe_nlargest

    sandbox = {"__builtins__": safe_bi, "df": df, "pd": pd}
    local_ns: dict = {}

    # 如果代码最后一行是裸表达式(没有 =),自动包成 result = ...
    lines = code.rstrip().split("\n")
    last = lines[-1].strip()
    if last and "=" not in last and not last.startswith(("result", "print")):
        lines[-1] = f"result = {last}"
        code = "\n".join(lines)

    # AST 静态检查(拦截反射链与 IO,再 exec)
    _validate_llm_code(code)

    exec(code, sandbox, local_ns)

    result = local_ns.get("result")
    if result is None:
        # 容错:在 sandbox 里查 result
        result = sandbox.get("result")
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"代码未返回 DataFrame,实际是 {type(result).__name__}")
    if len(result) > MAX_RESULT_ROWS:
        raise ValueError(f"结果行数 {len(result):,} 超过安全上限 {MAX_RESULT_ROWS:,}")

    # 兜底:把 result 里含 pd.NA 的 object 列强转 numeric(避免 nlargest/sort 报错)
    for col in result.columns:
        if result[col].dtype == object:
            try:
                converted = pd.to_numeric(result[col], errors="coerce")
                # 只有当转换后非空值数量 >= 原非空数量时,才接受转换
                if converted.notna().sum() >= result[col].notna().sum() * 0.8:
                    result[col] = converted
            except Exception:
                pass
    return result


# ============================================================
# 3. LLM Prompt 模板
# ============================================================
SYSTEM_PROMPT = """你是数据分析代码生成器。给定 Excel 字段列表和用户问题,只输出可执行的 pandas 代码。

硬性规则:
1. 只输出 ```python ... ``` 代码块,不要解释文字
2. 数据已经在变量 df 里(已经是 pandas DataFrame)
3. 最终结果必须赋值给 result,且必须是 DataFrame
4. 不要 print,不要 import(pandas 已通过 pd 暴露)
5. 涉及"增长率/同比/占比/份额"用公式:(cur - prev) / prev,处理除零。结果一律输出**小数比率**(0.99 表示 99%),**绝不要乘以 100**
6. 涉及"top N"用 .head(N) 或 .nlargest(N, ...)
7. **数值列若含 pd.NA,需用 pd.to_numeric(col, errors='coerce') 强转,避免 nlargest 报错**
8. 用 .copy() 避免 SettingWithCopyWarning
"""

USER_PROMPT_TEMPLATE = """【Excel 字段列表】
{columns}

【数据样例(前 2 行,字段顺序对应)】
{sample}

【用户问题】
{question}

请生成 pandas 代码,把最终 DataFrame 赋值给 result。
"""


# ============================================================
# 4. 内置模板(dry-run 模式,验证沙箱链路)
# ============================================================
DRY_RUN_CODE = """\
# 排除离职/转岗代表
mask = ~df['代表'].fillna('').str.contains('离职|转岗', regex=True)
df = df[mask].copy()

# 按"代表员工编号+产品"聚合学术接受度(本期/同期)
agg = df.groupby(['代表员工编号', '代表', '大区', '地区', '产品'], as_index=False).agg(
    prev=('同期_学术接受度', 'sum'),
    cur=('学术接受度', 'sum'),
)

# 只保留可算增长率的(同期>0)
agg = agg[agg['prev'] > 0].copy()
agg['growth_pct'] = ((agg['cur'] - agg['prev']) / agg['prev']).round(4)

result = agg.nlargest(10, 'growth_pct')[
    ['代表', '代表员工编号', '大区', '地区', '产品', 'prev', 'cur', 'growth_pct']
].reset_index(drop=True)
"""


# ============================================================
# 5. 主流程
# ============================================================
def main():
    p = argparse.ArgumentParser(description="自然语言驱动 Excel 分析")
    p.add_argument("excel", nargs="?", help="Excel 文件路径")
    p.add_argument("question", nargs="?", help="中文问题,如'找 top10 增长代表'")
    p.add_argument("--sheet", default=0, help="Sheet 名或索引,默认 0")
    p.add_argument("--rows", type=int, default=200000, help="最大读取行数")
    p.add_argument("--dry-run", action="store_true", help="跳过 LLM,使用内置模板")
    p.add_argument("--save", default=None, help="把结果 DataFrame 保存为 CSV")
    args = p.parse_args()

    if not args.excel:
        p.print_help()
        sys.exit(1)

    # 加载 Excel
    print(f"📂 读取 Excel: {args.excel}")
    if args.sheet in (0, "0") or isinstance(args.sheet, int):
        df = pd.read_excel(args.excel, sheet_name=args.sheet, nrows=args.rows)
    else:
        df = pd.read_excel(args.excel, sheet_name=args.sheet, nrows=args.rows)

    print(f"   形状: {df.shape[0]} 行 × {df.shape[1]} 列")
    cols = list(df.columns)

    # 决定代码来源
    if args.dry_run:
        print("🔧 模式: --dry-run(用内置模板)")
        code = DRY_RUN_CODE
    else:
        if not args.question:
            print("❌ 非 dry-run 模式必须提供问题参数")
            sys.exit(1)
        print(f"🤖 调用 LLM 生成代码...")
        sample = df.head(2).values.tolist()
        user_prompt = USER_PROMPT_TEMPLATE.format(
            columns=json.dumps(cols, ensure_ascii=False, indent=2),
            sample=json.dumps(sample, ensure_ascii=False, indent=2, default=str),
            question=args.question,
        )
        raw = call_llm(SYSTEM_PROMPT, user_prompt)
        # 提取 ```python ... ``` 块
        m = re.search(r"```python\s*\n(.*?)```", raw, re.DOTALL)
        code = m.group(1).strip() if m else raw.strip()

    print(f"\n{'='*60}\n📝 生成的代码:\n{'='*60}\n{code}\n{'='*60}\n")

    # 沙箱执行
    print("⚙️  沙箱执行...")
    try:
        result = run_sandboxed(code, df)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)

    # 展示
    print(f"\n{'='*60}\n✅ 结果({len(result)} 行):\n{'='*60}")
    with pd.option_context("display.max_rows", 30, "display.max_columns", 20, "display.width", 200):
        print(result.to_string())

    if args.save:
        result.to_csv(args.save, index=False, encoding="utf-8-sig")
        print(f"\n💾 已保存: {args.save}")


if __name__ == "__main__":
    main()
