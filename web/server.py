"""
DataAgent Web 后端 - FastAPI
数据源启动时指定 + 多轮对话支持 + 内存里管理 session
"""
import ast
import os
import re
import json
import time
import uuid
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional, List, Dict

import requests
import pandas as pd
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# ============================================================
# 业务规则(从 JSON 文件加载,启动时注入到 system prompt)
# ============================================================
RULES_PATH = Path(os.environ.get("RULES_PATH", str(BASE_DIR / "rules.json")))
_business_rules: dict = {}

# ============================================================
# 用户习惯记忆(自动学习 + 手动管理)
# ============================================================
MEMORY_PATH = Path(os.environ.get("MEMORY_PATH", str(BASE_DIR / "user_memory.json")))
_user_memory: dict = {"habits": []}


def load_business_rules():
    """加载业务规则 JSON,失败用空 dict"""
    global _business_rules
    try:
        if RULES_PATH.exists():
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                _business_rules = json.load(f)
            print(f"   业务规则:{RULES_PATH} ({len(_business_rules.get('filters', []))} 条过滤规则)")
        else:
            print(f"   ⚠️  业务规则文件不存在:{RULES_PATH}")
            _business_rules = {}
    except Exception as e:
        print(f"   ❌ 加载业务规则失败:{e}")
        _business_rules = {}


def build_rules_prompt() -> str:
    """把业务规则转成 system prompt 的一部分"""
    if not _business_rules:
        return ""

    parts = ["\n\n## 业务规则(必须遵守)"]

    # filters
    for f in _business_rules.get('filters', []):
        name = f.get('name', '')
        desc = f.get('description', '')
        pri = f.get('priority', 'medium')
        pri_mark = "🔴" if pri == 'high' else "🟡" if pri == 'medium' else "🟢"
        parts.append(f"\n{pri_mark} **{name}**:\n{desc}")

    # field preferences
    fp = _business_rules.get('field_preferences', {})
    if fp:
        parts.append("\n## 字段偏好")
        if fp.get('primary_metrics'):
            parts.append(f"\n核心指标(优先使用):{', '.join(fp['primary_metrics'])}")
        if fp.get('secondary_metrics'):
            parts.append(f"\n次要指标:{', '.join(fp['secondary_metrics'])}")
        if fp.get('ignore_columns'):
            parts.append(f"\n可忽略字段(噪音):{', '.join(fp['ignore_columns'])}")

    # calculation rules(指标计算公式)
    cr = _business_rules.get('calculation_rules', {})
    if cr and isinstance(cr, dict) and cr.get('rules'):
        parts.append("\n## 指标计算规则(用以下公式,不要自己瞎编)")
        for r in cr['rules']:
            name = r.get('name', '')
            formula = r.get('formula', '')
            desc = r.get('description', '')
            pri = r.get('priority', 'medium')
            cat = r.get('category', '')
            pri_mark = "🔴" if pri == 'high' else "🟡" if pri == 'medium' else "🟢"
            cat_str = f"[{cat}]" if cat else ""
            parts.append(f"\n{pri_mark} {cat_str} **{name}** = `{formula}`\n  {desc}")

    # output style(全局 + format_rules 列表)
    out = _business_rules.get('output_style', {})
    if out:
        parts.append("\n## 输出格式")
        parts.append(f"\n全局默认:百分数={out.get('number_format', 'rate_pct')}, 小数={out.get('decimal_places', 2)}, 千分位={out.get('thousand_separator', True)}, 中文列名={out.get('use_chinese_labels', True)}")
        # format_rules 列表
        fmt_rules = out.get('format_rules', [])
        if fmt_rules:
            parts.append("\n针对特定列的格式覆盖:")
            for fr in fmt_rules:
                cols = ', '.join(fr.get('apply_to_columns', []))
                prefix = fr.get('prefix', '') or ''
                suffix = fr.get('suffix', '') or ''
                mult = fr.get('multiplier', 1)
                dec = fr.get('decimal_places', out.get('decimal_places', 2))
                thou = fr.get('thousand_separator', out.get('thousand_separator', True))
                desc = fr.get('description', '')
                parts.append(f"- **{fr.get('name', '')}**({cols}):小数={dec}, 千分位={thou}, 倍数={mult}, 前缀='{prefix}', 后缀='{suffix}'"
                             + (f" — {desc}" if desc else ""))

    # industry
    ind = _business_rules.get('industry_specific', {})
    if ind:
        parts.append("\n## 行业背景")
        if ind.get('current_industry'):
            parts.append(f"\n行业:{ind['current_industry']}")
        if ind.get('business_objective'):
            parts.append(f"\n业务目标:{ind['business_objective']}")
        if ind.get('compliance_constraints'):
            parts.append(f"\n合规约束:{'; '.join(ind['compliance_constraints'])}")

    return "\n".join(parts)


# ============================================================
# 用户习惯记忆(自动学习用户偏好)
# ============================================================
MEMORY_IO_LOCK = threading.RLock()  # 串行化 memory 文件读写,防并发覆盖(RLock 允许嵌套,admin_save 内部会调 load_user_memory)


def load_user_memory() -> dict:
    """加载用户习惯记忆,失败用空 dict(每次 LLM 调用都重读,支持热更新)"""
    global _user_memory
    try:
        with MEMORY_IO_LOCK:
            if MEMORY_PATH.exists():
                with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                    _user_memory = json.load(f)
                if not isinstance(_user_memory, dict):
                    _user_memory = {"habits": []}
                if "habits" not in _user_memory or not isinstance(_user_memory["habits"], list):
                    _user_memory["habits"] = []
            else:
                _user_memory = {"habits": []}
    except Exception as e:
        print(f"   ⚠️  加载用户记忆失败:{e}")
        _user_memory = {"habits": []}
    return _user_memory


def _rules_field_names() -> set:
    """扁平化 rules.json 的字段名(用于冲突检测)"""
    if not _business_rules:
        return set()
    names = set()
    # 顶层(忽略 _ 开头的注释字段)
    for k in _business_rules.keys():
        if not k.startswith("_"):
            names.add(k)
    # 嵌套 sections
    for section in ("output_style", "field_preferences", "industry_specific", "calculation_rules"):
        for k in _business_rules.get(section, {}).keys():
            if not k.startswith("_"):
                names.add(k)
                names.add(f"preferred_{k}")
    return names


def _detect_rule_conflicts(habits: list) -> set:
    """返回与 rules.json 字段冲突的 habit key 集合(这些会被屏蔽,不进入 prompt)"""
    rule_fields = _rules_field_names()
    if not rule_fields:
        return set()
    conflicts = set()
    for h in habits:
        key = h.get("key", "")
        if not key:
            continue
        # 直接同名
        if key in rule_fields:
            conflicts.add(key)
            continue
        # 常见变体:preferred_xxx / xxx_format / xxx_preference
        for candidate in (key.replace("preferred_", ""), f"preferred_{key}"):
            if candidate in rule_fields:
                conflicts.add(key)
                break
    return conflicts


def build_memory_prompt(min_confidence: float = 0.5) -> str:
    """把用户习惯转成 system prompt 的一部分(只注入置信度达标的)

    核心规则:管理员业务规则(## 业务规则)优先级永远 > 本节(## 用户习惯记忆)。
    两者冲突时,以业务规则为准。冲突的 habit 会被自动屏蔽,不进入 prompt。
    """
    # 重新读盘(支持热更新)
    mem = load_user_memory()
    all_habits = [h for h in mem.get("habits", []) if h.get("confidence", 0) >= min_confidence]
    if not all_habits:
        return ""

    # 检测冲突,屏蔽掉与 rules.json 字段重名的
    conflicts = _detect_rule_conflicts(all_habits)
    habits = [h for h in all_habits if h.get("key") not in conflicts]

    if conflicts:
        print(f"   ⚠️ 以下习惯与业务规则字段冲突,已被屏蔽(优先级:rules > memory):{sorted(conflicts)}")

    if not habits:
        return ""

    parts = ["\n\n## 用户习惯记忆(基于历史对话自动学习,置信度 ≥ 0.5)"]
    parts.append("⚠️ **核心规则:本节的优先级永远低于上面的「业务规则」段。如果两者冲突,以业务规则为准,本节内容忽略。**")
    parts.append("用户过往对话体现出的偏好,你应该主动遵循:")
    for h in habits:
        key = h.get("key", "")
        val = h.get("value", "")
        cat = h.get("category", "general")
        desc = h.get("description", "")
        conf = h.get("confidence", 0)
        parts.append(f"- [{cat}] {key}: {val} (置信度 {conf:.2f}{' · ' + desc if desc else ''})")

    prompt = "\n".join(parts)
    # 调试:首次注入时打印(避免每条都打)
    if not hasattr(build_memory_prompt, "_last_count") or build_memory_prompt._last_count != len(habits):
        print(f"   🧠 Memory 注入:共 {len(habits)} 条习惯进入 SYSTEM_PROMPT"
              + (f"(屏蔽 {len(conflicts)} 条与规则冲突)" if conflicts else ""))
        build_memory_prompt._last_count = len(habits)
    return prompt

# ============================================================
# 数据源(启动时加载到内存)
# 优先级:DATA_SOURCE_SQL(数据库) > DATA_SOURCE(Excel 文件)
# ============================================================
DATA_SOURCE_PATH = os.environ.get("DATA_SOURCE", "")
DATA_SOURCE_SHEET = os.environ.get("DATA_SOURCE_SHEET", "0")
DATA_SOURCE_LABEL = os.environ.get("DATA_SOURCE_LABEL", "默认数据源")

# SQL Server / 数据库配置
DATA_SOURCE_SQL = os.environ.get("DATA_SOURCE_SQL", "")  # SQLAlchemy 格式的连接字符串
DATA_SOURCE_SQL_QUERY = os.environ.get("DATA_SOURCE_SQL_QUERY", "SELECT * FROM dbo.your_table")  # 预定义查询
DATA_SOURCE_SQL_LABEL = os.environ.get("DATA_SOURCE_SQL_LABEL", DATA_SOURCE_LABEL)

_global_df: Optional[pd.DataFrame] = None
_global_meta: dict = {}

# 字段语义字典(启动时扫描一次,注入 prompt 帮 LLM 理解列含义)
_column_semantics: dict = {}

_DATE_SHAPE_RE = re.compile(r"^\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?")

def _looks_like_date(values) -> bool:
    """轻量判断样本是否像日期(正则预判,避免 pd.to_datetime 的 dateutil 慢解析)"""
    vals = [str(v) for v in list(values)[:5] if str(v).strip()]
    if not vals:
        return False
    hits = sum(1 for v in vals if _DATE_SHAPE_RE.match(v))
    return hits >= max(1, len(vals) // 2)

def _build_column_semantics(df: pd.DataFrame, max_enum: int = 12) -> dict:
    """为每列生成语义注解(类型/枚举值/示例/缺失率)。

    - 数值列:标注"数值"
    - 枚举列(唯一值 ≤ max_enum):列出全部取值(如"度量值"列的指标枚举)
    - 文本列:给 3 个示例值
    - 日期列:标注"日期"
    供 LLM 首轮就理解列含义,减少字段误解导致的报错重试。
    """
    sem: dict = {}
    for col in df.columns:
        s = df[col]
        entry: dict = {}
        na_pct = float(s.isna().mean())
        if na_pct > 0.05:
            entry["缺失"] = f"{na_pct:.0%}"

        if pd.api.types.is_bool_dtype(s):
            entry["类型"] = "布尔"
        elif pd.api.types.is_numeric_dtype(s):
            entry["类型"] = "数值"
        else:
            sample = s.dropna().head(10)
            if len(sample) > 0 and _looks_like_date(sample):
                entry["类型"] = "日期"
            else:
                entry["类型"] = "文本"
            if entry["类型"] == "文本":
                # 先采样判断基数,避免每列都全量 unique(60 列 × 9 万行会拖慢启动)
                sample_uniq = [str(u) for u in s.dropna().head(2000).unique()]
                if len(sample_uniq) > max_enum:
                    entry["示例"] = sample_uniq[:3]
                elif sample_uniq:
                    full_uniq = [str(u) for u in s.dropna().unique()]
                    if len(full_uniq) <= max_enum:
                        entry["取值"] = full_uniq
                    else:
                        entry["示例"] = full_uniq[:3]
        sem[str(col)] = entry
    return sem


def _format_column_dict(sem: dict) -> str:
    """把字段语义字典格式化成 prompt 段落(紧凑单行/列)"""
    lines = []
    for col, info in sem.items():
        t = info.get("类型", "?")
        if "取值" in info:
            lines.append(f"- {col}: {t} 枚举[{', '.join(info['取值'])}]")
        elif "示例" in info:
            lines.append(f"- {col}: {t}(如 {'、'.join(info['示例'])})")
        elif "缺失" in info:
            lines.append(f"- {col}: {t}(缺失 {info['缺失']})")
        else:
            lines.append(f"- {col}: {t}")
    return "\n".join(lines)

def load_data_source():
    global _global_df, _global_meta

    # 优先:SQL Server / 其他数据库
    if DATA_SOURCE_SQL:
        try:
            from sqlalchemy import create_engine
            engine = create_engine(DATA_SOURCE_SQL)
            # 测试连接
            with engine.connect() as conn:
                conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            # 跑预定义查询(用户应该自己写带 WHERE/LIMIT 的查询控制数据量)
            _global_df = pd.read_sql_query(DATA_SOURCE_SQL_QUERY, engine)
            # 提取数据库信息(从 URL 解析)
            db_type = DATA_SOURCE_SQL.split("://")[0] if "://" in DATA_SOURCE_SQL else "unknown"
            # 解析连接信息(隐藏密码)
            url_safe = DATA_SOURCE_SQL
            if "@" in url_safe:
                # mssql+pyodbc://user:pass@host:port/db
                host_part = url_safe.split("@", 1)[1]
            else:
                # sqlite:////path/to/db  或  postgresql://host/db
                host_part = url_safe.split("://", 1)[1]
            _global_meta = {
                "type": f"sql:{db_type}",
                "label": DATA_SOURCE_SQL_LABEL,
                "connection": host_part,  # 隐藏密码
                "query": DATA_SOURCE_SQL_QUERY[:200],
                "rows": int(_global_df.shape[0]),
                "columns": int(_global_df.shape[1]),
                "column_list": list(_global_df.columns),
            }
            _column_semantics = _build_column_semantics(_global_df)
            print(f"   数据库:{db_type} @ {host_part}")
            return
        except Exception as e:
            print(f"❌ SQL 数据源加载失败:{e}")
            raise

    # 备选:Excel 文件
    if DATA_SOURCE_PATH and Path(DATA_SOURCE_PATH).exists():
        sheet = DATA_SOURCE_SHEET
        try:
            sheet = int(sheet)
        except ValueError:
            pass
        _global_df = pd.read_excel(DATA_SOURCE_PATH, sheet_name=sheet, nrows=200000)
        _global_meta = {
            "type": "excel",
            "label": DATA_SOURCE_LABEL,
            "path": DATA_SOURCE_PATH,
            "sheet": sheet,
            "filename": Path(DATA_SOURCE_PATH).name,
            "rows": int(_global_df.shape[0]),
            "columns": int(_global_df.shape[1]),
            "column_list": list(_global_df.columns),
        }
        _column_semantics = _build_column_semantics(_global_df)
        return

    raise RuntimeError(
        "未指定数据源。请设置环境变量:\n"
        "  Excel:export DATA_SOURCE=/path/to/data.xlsx\n"
        "  数据库:export DATA_SOURCE_SQL='mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server'\n"
        "         export DATA_SOURCE_SQL_QUERY='SELECT * FROM dbo.your_table'\n"
    )


# ============================================================
# Session 管理(内存)
# ============================================================
sessions: Dict[str, List[dict]] = {}  # session_id -> messages
sessions_lock = threading.Lock()
SESSION_IDLE_TTL_SECONDS = 2 * 3600  # session 空闲 2 小时自动清理
_session_last_active: Dict[str, float] = {}

MAX_HISTORY_TURNS = 5  # 最多保留 5 轮历史(10 条 messages)


def _evict_stale_sessions():
    """惰性清理:删除超过 TTL 未活动的 session(须在持有 sessions_lock 时调用)"""
    now = time.time()
    stale = [sid for sid, ts in _session_last_active.items() if now - ts > SESSION_IDLE_TTL_SECONDS]
    for sid in stale:
        sessions.pop(sid, None)
        _session_last_active.pop(sid, None)


def get_or_create_session(session_id: Optional[str]) -> tuple:
    with sessions_lock:
        _evict_stale_sessions()
        if not session_id or session_id not in sessions:
            session_id = uuid.uuid4().hex[:8]
            sessions[session_id] = []
        _session_last_active[session_id] = time.time()
        return session_id, sessions[session_id]


def add_to_session(session_id: str, role: str, content: str):
    with sessions_lock:
        if session_id in sessions:
            _session_last_active[session_id] = time.time()
            sessions[session_id].append({"role": role, "content": content})
            # 限制长度
            if len(sessions[session_id]) > MAX_HISTORY_TURNS * 2:
                sessions[session_id] = sessions[session_id][-MAX_HISTORY_TURNS * 2:]


def get_session(session_id: str) -> List[dict]:
    with sessions_lock:
        if session_id in sessions:
            _session_last_active[session_id] = time.time()
        return list(sessions.get(session_id, []))


def append_session_data(session_id: str, role: str, content: str, extras: dict = None):
    """在 session 里追加消息,可选附加 result/code/insight 等元数据"""
    with sessions_lock:
        if session_id not in sessions:
            sessions[session_id] = []
        _session_last_active[session_id] = time.time()
        msg = {"role": role, "content": content}
        if extras:
            msg.update(extras)
        sessions[session_id].append(msg)
        # 限制长度(只按 messages 数量限制,extras 不占位)
        if len(sessions[session_id]) > MAX_HISTORY_TURNS * 2:
            sessions[session_id] = sessions[session_id][-MAX_HISTORY_TURNS * 2:]


# ============================================================
# LLM
# ============================================================
LLM_API_KEY = os.environ.get("MINIMAX_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.minimaxi.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "MiniMax-M3")

SYSTEM_PROMPT_BASE = """你是数据分析代码生成器。给定 Excel 字段列表和用户问题(可能含历史对话),只输出可执行的 pandas 代码。

硬性规则:
1. 只输出 ```python ... ``` 代码块,不要解释文字
2. 数据已经在变量 df 里(已经是 pandas DataFrame)
3. 最终结果必须赋值给 result,且必须是 DataFrame
4. 不要 print,不要 import(pandas 已通过 pd 暴露)
5. 涉及"增长率/同比/占比/份额"用公式:(cur - prev) / prev,处理除零。结果一律输出**小数比率**(0.99 表示 99%、5.0 表示 500%),**绝不要乘以 100**;比率列命名用"增长率"或含 rate/pct 的英文名
6. 涉及"top N"用 .head(N) 或 .nlargest(N, ...)
7. 数值列若含 pd.NA,需用 pd.to_numeric(col, errors='coerce') 强转
8. 用 .copy() 避免 SettingWithCopyWarning
9. 不要写 if df / if result 这种 DataFrame 真值判断
10. 用户可能说"再加个条件""换成大区"等——根据历史对话理解新需求的完整含义
"""

def build_system_prompt() -> str:
    """动态拼装 SYSTEM_PROMPT(每次调用重新读 memory,支持热更新)"""
    return SYSTEM_PROMPT_BASE + build_rules_prompt() + build_memory_prompt()


def _compact_history_for_llm(history: List[dict]) -> List[dict]:
    """压缩历史消息再传给 LLM,控制 prompt 体积、加速首 token 输出:
    - user 消息原样保留(多轮"再加个条件"依赖原文)
    - assistant 消息只保留结果摘要(行数/列/前几行预览),省略完整代码块
    """
    out: List[dict] = []
    for h in history:
        if h["role"] not in ("user", "assistant"):
            continue
        if h["role"] == "user":
            out.append({"role": "user", "content": h.get("content", "")})
            continue
        rs = h.get("result_summary")
        if rs and isinstance(rs, dict):
            preview = rs.get("preview") or []
            compact = (
                f"[上一轮已完成分析,代码略]\n"
                f"结果:{rs.get('row_count', '?')} 行 × {len(rs.get('columns', []))} 列\n"
                f"列:{', '.join(rs.get('columns', []))}\n"
                f"数据预览:{json.dumps([row[:10] for row in preview[:5]], ensure_ascii=False)}"
            )
        else:
            compact = str(h.get("content", ""))[:500]
        out.append({"role": "assistant", "content": compact})
    return out


def call_llm_with_history(history: List[dict], current_prompt: str) -> str:
    """调用 LLM,带历史对话"""
    if not LLM_API_KEY:
        raise RuntimeError("未配置 API key")

    # 构造 messages:[system, ...history, current_user]
    messages = [{"role": "system", "content": build_system_prompt()}]
    # history 里如果有 system 跳过,只保留 user/assistant;assistant 消息做压缩
    for h in _compact_history_for_llm(history):
        messages.append(h)
    messages.append({"role": "user", "content": current_prompt})

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000,
        },
        timeout=180,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return _clean_think(raw)


def _clean_think(content: str) -> str:
    """去掉 LLM thinking 模式的 <think>...</think> 块"""
    import re
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


# ============================================================
# 用户习惯提取(每次分析后跑一次,轻量 LLM 调用)
# ============================================================
EXTRACT_HABITS_PROMPT = """你是用户偏好观察员。基于以下单次对话,判断是否体现出**稳定、可复用的用户偏好**。

【用户问题】
{question}

【回答摘要】
{answer_summary}

【已有记忆】
{existing_memory}

只输出严格的 JSON,不要其他文字。如果本次对话**没有体现新偏好**,返回空数组:
{{"new_habits": []}}

如果体现了新偏好(只提取**强信号**——重复出现 2 次以上、或用户明确表达过),输出:
{{"new_habits": [
  {{
    "key": "英文键名(类似 preferred_chart_for_topn)",
    "value": "具体值(中文或英文都行)",
    "category": "chart | filter | metric | format | domain | style",
    "description": "一句话中文描述这个偏好",
    "confidence": 0.5-0.9(首次 0.5,重复/明确表达可 0.7-0.9),
    "evidence": "本次对话中体现该偏好的具体证据(1 句话)"
  }}
]}}

判断准则:
- ✅ 强信号(写):"我习惯看柱状图" / 第 3 次问 top10 都要"按增长率排序" / 反复只问川渝大区
- ❌ 弱信号(不写):单次提问、临时性需求、宽泛的"看下数据"、bug 报告
- ❌ 不要写:具体业务数据(销售额=12345)、单次查询条件
- key 要 stable,同类型偏好复用同一个 key(如所有"图表类型"偏好都用 chart_xxx 开头)
- value 要具体可执行,不要"看情况"
- confidence 不要超过 0.9(记忆需要持续验证)"""


def call_llm_extract_habits(question: str, answer_summary: str, existing_memory: dict) -> list:
    """从单次对话抽取用户偏好。失败返回空 list(不影响主流程)"""
    if not LLM_API_KEY:
        return []

    # 简化已有记忆的展示(只列 key + value)
    existing_str = "\n".join(
        f"- {h.get('key', '')}: {h.get('value', '')} (置信度 {h.get('confidence', 0):.2f})"
        for h in existing_memory.get("habits", [])
    ) or "(空)"

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "user", "content": EXTRACT_HABITS_PROMPT.format(
                        question=question[:500],
                        answer_summary=answer_summary[:500],
                        existing_memory=existing_str,
                    )},
                ],
                "temperature": 0.0,  # 提取任务要稳定
                "max_tokens": 800,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = _clean_think(resp.json()["choices"][0]["message"]["content"])
        data = json.loads(raw)
        new_habits = data.get("new_habits", [])
        if not isinstance(new_habits, list):
            return []
        # 字段校验 + 截断
        valid = []
        for h in new_habits[:5]:  # 一次最多 5 条
            if not isinstance(h, dict) or "key" not in h or "value" not in h:
                continue
            valid.append({
                "key": str(h["key"])[:80],
                "value": str(h["value"])[:200],
                "category": str(h.get("category", "general"))[:30],
                "description": str(h.get("description", ""))[:300],
                "confidence": max(0.0, min(0.9, float(h.get("confidence", 0.5)))),
                "evidence": str(h.get("evidence", ""))[:200],
            })
        return valid
    except Exception as e:
        print(f"   ⚠️ 习惯提取失败(忽略):{e}")
        return []


def merge_habits_into_memory(new_habits: list) -> int:
    """把新习惯合并到 memory 文件。同 key 累加置信度,新 key 添加。返回合并条数。"""
    if not new_habits:
        return 0

    # 全程持锁:读->合并->写 三段原子化,防止与 admin 保存并发导致覆盖
    with MEMORY_IO_LOCK:
        # 读最新文件(防止与最近一次 UI 改动冲突)
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                mem = json.load(f)
        except Exception:
            mem = {"_version": "1.0", "habits": []}

        if not isinstance(mem.get("habits"), list):
            mem["habits"] = []

        now = datetime.now().isoformat(timespec="seconds")
        merged = 0
        for nh in new_habits:
            key = nh["key"]
            # 同 key 找现有
            existing = next((h for h in mem["habits"] if h.get("key") == key), None)
            if existing:
                # 累加置信度,封顶 0.95(允许手动改超过)
                old_conf = float(existing.get("confidence", 0.5))
                new_conf = nh["confidence"]
                # 移动加权:旧 * 0.7 + 新 * 0.3,让稳定偏好更稳
                blended = old_conf * 0.7 + new_conf * 0.3
                existing["confidence"] = min(0.95, max(blended, new_conf))
                existing["evidence_count"] = existing.get("evidence_count", 1) + 1
                existing["updated_at"] = now
                # 更新 value(如果新的更具体)
                if len(str(nh["value"])) > len(str(existing.get("value", ""))):
                    existing["value"] = nh["value"]
                # 累积 evidence(最近 3 条)
                evidences = existing.get("recent_evidences", [])
                evidences.append(nh.get("evidence", ""))
                existing["recent_evidences"] = evidences[-3:]
                existing["description"] = nh.get("description", existing.get("description", ""))
            else:
                mem["habits"].append({
                    "key": key,
                    "value": nh["value"],
                    "category": nh["category"],
                    "description": nh["description"],
                    "confidence": nh["confidence"],
                    "evidence_count": 1,
                    "source": "auto",
                    "learned_from": nh.get("evidence", ""),
                    "recent_evidences": [nh.get("evidence", "")],
                    "created_at": now,
                    "updated_at": now,
                })
            merged += 1

        # 写回
        try:
            with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump(mem, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ❌ 写记忆文件失败:{e}")
            return 0
    return merged


# ============================================================
# 用户习惯提取:后台异步 + 冷却(避免每次提问都触发一次 LLM 调用)
# ============================================================
HABIT_EXTRACT_COOLDOWN = 90  # 秒,同一 session 冷却期内不再重复提取
_habit_extract_last: Dict[str, float] = {}


def _should_run_habit_extract(session_id: str) -> bool:
    now = time.time()
    if now - _habit_extract_last.get(session_id, 0) < HABIT_EXTRACT_COOLDOWN:
        return False
    _habit_extract_last[session_id] = now
    return True


async def _extract_habits_async(question: str, answer_summary: str) -> None:
    """后台抽取用户习惯(独立于主响应流,失败仅打日志,不阻塞/不影响响应)"""
    try:
        existing = load_user_memory()
        extracted = await run_in_threadpool(call_llm_extract_habits, question, answer_summary, existing)
        if extracted:
            merged = merge_habits_into_memory(extracted)
            print(f"   🧠 自动学习:抽到 {len(extracted)} 条偏好,合并 {merged} 条")
        else:
            print(f"   🧠 自动学习:本次无新偏好(单次为弱信号,需重复/明确表达)")
    except Exception as e:
        print(f"   ⚠️ 习惯提取异常(忽略):{e}")


ANALYSIS_PROMPT = """你是数据分析助手。给定用户问题、执行的代码、结果摘要,生成业务洞察和后续问题建议。

只输出严格的 JSON,不要其他文字:
{"insight": "1-2 句业务洞察(基于结果数据,具体到数字,中文)", "suggestions": ["问题1", "问题2", "问题3"]}

要求:
- insight 必须基于结果数据,引用具体数字(如"top10 中 G-东蒙大区占 5 席"、"增长率均超 30x")
- suggestions 是用户可能想继续问的具体问题(中文,3 个,与本次结果直接相关,不是泛泛而谈)
"""


CHART_PROMPT = """你是图表配置生成器。给定用户问题、结果数据(列名 + 前 8 行),选择最合适的图表类型并配置。

支持的图表类型:
- "bar" : 柱状图(分类对比,如代表 vs 数值)
- "line" : 折线图(时间趋势)
- "pie" : 饼图(占比,只用于 < 8 个分类)
- "scatter" : 散点图(两列数值关系)
- "horizontal_bar" : 横向柱状图(类目名长时)

只输出严格的 JSON,不要其他文字:
{"type": "bar", "title": "图表标题", "x": "X 轴列名", "y": "Y 轴列名", "x_label": "X 轴标题(可选)", "y_label": "Y 轴标题(可选)"}

判断规则:
- 有时间/日期/月份列 + 数值:用 line
- 类目(如代表/大区/产品) + 数值:用 bar
- 占比类问题 + 分类 < 8:用 pie
- 两个数值列相关:用 scatter
- 类目名长(如代表姓名):用 horizontal_bar
"""


REPORT_PROMPT = """你是数据分析师,负责基于用户的分析问题和数据结果,撰写一份**专业、结构化的中文分析报告**。

报告要求:
1. **结构清晰**:严格按以下章节组织
   - # 报告标题(基于用户问题)
   - ## 1. 分析概述(用 1-2 段说明背景、目标、范围)
   - ## 2. 数据概览(用 markdown 表格展示结果数据,前 20 行)
   - ## 3. 关键发现(3-5 个具体洞察,每个洞察要有数据支撑,引用具体数字)
   - ## 4. 详细分析(可选,如果数据有突出模式就展开)
   - ## 5. 结论与建议(2-3 条 actionable 建议,中文)
   - ## 附录(数据明细链接,如果有)

2. **基于数据**:每个结论必须引用具体数字(行数、增长率、占比等),不要泛泛而谈
3. **简洁专业**:像 SFE 报告给老板看的样子,不要 LLM 那种"作为一个 AI"的废话
4. **格式规范**:
   - 标题用 #/##
   - 列表用 - 
   - 表格用 markdown 表格
   - 关键数字用 **加粗**

5. **不要**:
   - 不要说"根据以上数据"
   - 不要加免责声明
   - 不要问"还有什么需要分析吗"
   - 报告最后直接结束

只输出 markdown 报告内容,不要其他文字。"""


def call_llm_report(context: dict) -> str:
    """LLM 生成结构化分析报告"""
    insight_block = ""
    if context.get('insight'):
        insight_block = f"\n【已生成的 AI 洞察】\n{context['insight']}\n"

    user_prompt = f"""【用户原始问题】
{context['question']}

【数据概览】
共 {context['row_count']} 行 × {context['columns_count']} 列
列名:{', '.join(context['columns'])}

【结果数据(完整,如果超过 30 行只展示前 30 行)】
{chr(10).join(['| ' + ' | '.join(context['columns']) + ' |' for _ in range(1)] + [''])}
{chr(10).join(['| ' + ' | '.join(str(v) for v in row) + ' |' for row in context['rows'][:30]])}
{insight_block}

请基于以上数据,撰写一份完整的中文分析报告(markdown 格式)。"""

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": REPORT_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return _clean_think(resp.json()["choices"][0]["message"]["content"])


SESSION_REPORT_PROMPT = """你是数据分析师,负责基于用户**整段对话**中的所有分析,撰写一份**综合性的中文总结报告**。

报告要求:
1. **结构清晰**:
   - # 报告标题(基于对话主题)
   - ## 1. 对话概述(用户本次对话分析的几个问题,大概方向)
   - ## 2. 分析清单(按对话顺序,每个问题一段,包含:问题、数据概要、关键数字)
   - ## 3. 跨分析洞察(综合多个分析的关联、趋势、共同模式)
   - ## 4. 总结与建议(2-3 条 actionable 建议)

2. **基于真实数据**:每个分析必须引用具体数字(行数、增长率、代表名等),不要泛泛而谈
3. **跨分析洞察是重点**:不只是把单条分析拼起来,要发现"多个分析之间的关联"
4. **格式规范**:markdown 标题/列表/表格
5. **不要**说"根据以上对话"、问"还有什么需要"等 LLM 套话

只输出 markdown 报告内容,不要其他文字。"""


def call_llm_session_report(items: list) -> str:
    """LLM 生成综合会话报告"""
    # items: [{question, code, result_summary, insight?}, ...]
    sections = []
    for i, item in enumerate(items, 1):
        sec = f"""### 分析 {i}:{item.get('question', '?')}
- **数据**:{item.get('row_count', 0)} 行 × {len(item.get('columns', []))} 列
- **列名**:{', '.join(item.get('columns', [])[:8])}
- **预览(前 5 行)**:
"""
        for row in item.get('preview', [])[:5]:
            sec += f"  - {row}\n"
        if item.get('insight'):
            sec += f"- **AI 洞察**:{item['insight']}\n"
        sections.append(sec)

    user_prompt = f"""用户本次对话共做了 {len(items)} 个分析。请基于以下所有分析,撰写一份**综合性总结报告**。

{chr(10).join(sections)}

要求:
- 在"分析清单"中保留每个分析的关键数据
- 在"跨分析洞察"中重点发现多个分析之间的关联(例如:多个 top10 都集中在某大区、某产品,反映同一业务模式)
- 报告长度 1500-3000 字
"""

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SESSION_REPORT_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return _clean_think(resp.json()["choices"][0]["message"]["content"])


_CHART_TYPE_ALIASES = {
    "bar": "bar", "column": "bar", "bar_chart": "bar", "barchart": "bar", "柱状图": "bar",
    "horizontal_bar": "horizontal_bar", "horizontal": "horizontal_bar", "hbar": "horizontal_bar",
    "h_bar": "horizontal_bar", "横向": "horizontal_bar", "横向柱状图": "horizontal_bar",
    "line": "line", "line_chart": "line", "折线图": "line", "trend": "line",
    "pie": "pie", "pie_chart": "pie", "donut": "pie", "饼图": "pie",
    "scatter": "scatter", "散点图": "scatter", "point": "scatter",
}


def _normalize_chart_type(t) -> str:
    """把 LLM 输出的图表类型别名归一化,非法返回 None"""
    if not isinstance(t, str):
        return None
    key = t.strip().lower().replace(" ", "_")
    return _CHART_TYPE_ALIASES.get(key)


def _is_numeric_col(rows: list, idx: int, sample: int = 20) -> bool:
    """判断某列是否为数值列(基于前 sample 行,容忍千分位逗号/百分号/空串)"""
    rows = rows[:sample]
    if not rows:
        return False
    hits = 0
    for row in rows:
        v = row[idx] if idx < len(row) else None
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        if isinstance(v, (int, float)):
            hits += 1
            continue
        if isinstance(v, str):
            s = v.strip().replace(",", "").replace("%", "").replace("－", "-")
            try:
                float(s)
                hits += 1
            except ValueError:
                pass
    return hits >= max(1, len(rows) // 2)


def _pick_chart_axes(cfg: dict, columns: list, preview: list, ctype: str = "bar") -> tuple:
    """校验并兜底 x/y 列名。规则:
    - y 必须是数值列(优先率/占比类)
    - 非 scatter 时 x 必须是类别列(防 LLM 把数值列当 x,如 x/y 放反时自动纠正)
    - scatter 需要两个不同的数值列
    """
    x, y = cfg.get("x", ""), cfg.get("y", "")
    num_cols = [c for c in columns if _is_numeric_col(preview, columns.index(c))]
    cat_cols = [c for c in columns if c not in num_cols]

    # LLM 把 x/y 整体放反(数值列当 x、文本列当 y)时先交换,保留 LLM 的列选择意图
    if x in num_cols and y not in num_cols:
        x, y = y, x

    if y not in num_cols:
        y = (next((c for c in num_cols if re.search(r"率|占比|份额|rate|ratio|pct|growth", c, re.I)), None)
             or (num_cols[0] if num_cols else columns[-1]))

    if ctype == "scatter":
        if x not in num_cols or x == y:
            x = next((c for c in num_cols if c != y), None) or x
    else:
        if x not in cat_cols or x == y:
            x = (cat_cols[0] if cat_cols
                 else next((c for c in num_cols if c != y), None) or columns[0])
    return x, y


def call_llm_chart(context: dict) -> dict:
    """LLM 选图表类型 + 配置(返回前做类型归一化 + x/y 列名校验,防止 LLM 输出不合法配置)"""
    user_prompt = f"""【用户问题】
{context['question']}

【列名】
{context['columns']}

【前 8 行数据】
{json.dumps(context['preview'], ensure_ascii=False, indent=2)}

请选择最合适的图表类型并输出配置。x 必须是上述列名中的**原样一个**,y 必须是数值列列名(含增长率/占比的列优先)。"""

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": CHART_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = _clean_think(resp.json()["choices"][0]["message"]["content"])
    cfg = {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                cfg = parsed
        except json.JSONDecodeError:
            pass
    ctype = _normalize_chart_type(cfg.get("type")) or "bar"
    x, y = _pick_chart_axes(cfg, context["columns"], context.get("preview", []), ctype)
    return {
        "type": ctype,
        "title": str(cfg.get("title") or context.get("question", ""))[:80],
        "x": x,
        "y": y,
        "x_label": str(cfg.get("x_label") or ""),
        "y_label": str(cfg.get("y_label") or ""),
    }


def call_llm_analysis(context: dict) -> dict:
    """LLM 分析结果 + 建议后续问题"""
    user_prompt = f"""【用户问题】
{context['question']}

【结果概览】
- 行数:{context.get('row_count', 0)}
- 列:{context.get('columns', [])}
- 前 8 行数据:{json.dumps(context.get('preview', []), ensure_ascii=False, indent=2)}

请基于结果数据生成业务洞察和后续问题建议。"""

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = _clean_think(resp.json()["choices"][0]["message"]["content"])
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if "insight" in data and "suggestions" in data:
                return data
        except json.JSONDecodeError:
            pass
    # fallback
    return {"insight": raw[:300] if raw else "(无洞察)", "suggestions": []}


# ============================================================
# 沙箱(同前)
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
    import builtins as _bi
    safe_bi = {k: getattr(_bi, k) for k in SAFE_BUILTINS if hasattr(_bi, k)}
    real_import = _bi.__import__
    def guarded_import(name, *a, **kw):
        root = name.split(".")[0]
        if root not in ALLOWED_MODULES:
            raise ImportError(f"模块 {root!r} 不在白名单,禁止导入")
        return real_import(name, *a, **kw)
    safe_bi["__import__"] = guarded_import

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

    lines = code.rstrip().split("\n")
    last = lines[-1].strip()
    # 最后一行若不是 `result = ...` 赋值,则把它的结果赋给 result。
    # 不能只看行内是否含 "="——`ascending=False` 这类参数赋值会被误判。
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", last) if last else None
    if last and not (m and m.group(1) == "result") and not last.startswith("print"):
        lines[-1] = f"result = {last}"
        code = "\n".join(lines)

    # AST 静态检查(拦截反射链与 IO,再 exec)
    _validate_llm_code(code)

    exec(code, sandbox, local_ns)
    result = local_ns.get("result")
    if result is None:
        result = sandbox.get("result")
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"代码未返回 DataFrame,实际是 {type(result).__name__}")
    if len(result) > MAX_RESULT_ROWS:
        raise ValueError(f"结果行数 {len(result):,} 超过安全上限 {MAX_RESULT_ROWS:,}")

    for col in result.columns:
        if result[col].dtype == object:
            try:
                converted = pd.to_numeric(result[col], errors="coerce")
                if converted.notna().sum() >= result[col].notna().sum() * 0.8:
                    result[col] = converted
            except Exception:
                pass

    # 兜底:把所有 inf/-inf 转 NaN(避免 nlargest 把 inf 排前)
    result = result.replace([float('inf'), float('-inf')], pd.NA)
    # 同步清除包含 NaN 的行(避免呈现 NaN 增长率)
    return result


# ============================================================
# FastAPI
# ============================================================
app = FastAPI(title="DataAgent Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup():
    load_business_rules()
    load_data_source()
    print(f"📊 数据源:{_global_meta.get('filename')} ({_global_meta.get('rows'):,} 行 × {_global_meta.get('columns')} 列)")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL,
        "data_source": _global_meta,
    }


@app.get("/api/preview")
async def preview():
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")
    df = _global_df.head(50)
    return {
        "meta": _global_meta,
        "columns": list(df.columns),
        "rows": df.fillna("").astype(str).values.tolist(),
    }


@app.post("/api/analyze")
async def analyze(
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
    with_analysis: Optional[str] = Form(None),  # "true" 才做 analysis 阶段
):
    """SSE 流式分析,支持多轮对话。with_analysis=true 时才做 AI 洞察(快路径)"""
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")

    session_id, history = get_or_create_session(session_id)
    do_analysis = (with_analysis == "true")

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'event': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'event': 'start', 'question': question}, ensure_ascii=False)}\n\n"

            # 把用户问题存到 session
            add_to_session(session_id, "user", question)

            # 构造 current prompt(带数据源元信息)
            column_hint = _format_column_dict(_column_semantics) or json.dumps(_global_meta.get('column_list', []), ensure_ascii=False)
            current_prompt = f"""【数据源】
{_global_meta.get('label', _global_meta.get('filename'))}({_global_meta.get('rows'):,} 行 × {_global_meta.get('columns')} 列)

【字段字典】(列名 → 类型/取值/示例,写代码前先读这里理解列含义)
{column_hint}

【数据提示】
- 如果字段列表里有"度量值"列,该列决定了每一行属于哪种指标(可能有多种,例如"学术接受度"和"接受度指数"),用"学术接受度"和"同期_学术接受度"做累加时,务必先用 df['度量值'] == '学术接受度' 过滤,避免不同度量值被错误累加
- "NEW代表"列里包含"(离职)"或"(转岗)"后缀的代表**不要排除**,这些数据本身就是有效的历史学术活动记录(在岗时做的),除非用户明确说"排除离职/转岗"
- "同期"列基本都是小数(如 0.05、1.5),增长率巨大是正常的(新产品铺货场景)
- 所有比率/增长率/占比类列**一律输出小数比率**(0.99=99%、5.0=500%),**不要乘以 100**,前端会自动转成百分数显示

【当前问题】
{question}

请生成 pandas 代码,把最终 DataFrame 赋值给 result。只输出 python 代码块。"""

            # LLM 调用(带历史)
            max_retries = 2
            last_error = None
            for attempt in range(max_retries + 1):
                if attempt == 0:
                    raw = await run_in_threadpool(call_llm_with_history, history[:-1], current_prompt)  # 去掉刚加的 user
                else:
                    yield f"data: {json.dumps({'event': 'retry', 'attempt': attempt, 'last_error': last_error[:200]}, ensure_ascii=False)}\n\n"
                    raw = await run_in_threadpool(call_llm_with_history, history, f"""上一次代码报错了,请重新输出**完整代码**。

【错误】
{last_error[:300]}

【当前问题】
{question}

【字段】
{_format_column_dict(_column_semantics) or json.dumps(_global_meta.get('column_list', []), ensure_ascii=False)}

输出完整 python 代码块。""")

                m = re.search(r"```python\s*\n(.*?)```", raw, re.DOTALL)
                code = m.group(1).strip() if m else raw.strip()

                if attempt == 0:
                    yield f"data: {json.dumps({'event': 'code', 'code': code}, ensure_ascii=False)}\n\n"

                try:
                    result = run_sandboxed(code, _global_df)
                    break
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    if attempt == max_retries:
                        yield f"data: {json.dumps({'event': 'error', 'message': last_error}, ensure_ascii=False)}\n\n"
                        return

            # 把代码和结果存到 session(供后续会话总结报告用)
            append_session_data(session_id, "assistant", f"```python\n{code}\n```", {
                "result_summary": {
                    "row_count": len(result),
                    "columns": list(result.columns),
                    "preview": result.head(5).fillna("").astype(str).values.tolist(),
                }
            })

            result_dict = {
                "columns": list(result.columns),
                "rows": result.fillna("").astype(str).values.tolist()[:100],
                "row_count": len(result),
            }
            yield f"data: {json.dumps({'event': 'result', 'data': result_dict, 'code': code, 'question': question}, ensure_ascii=False)}\n\n"

            # 后台异步抽取用户习惯(独立于响应流,带冷却;失败忽略,不拖慢 done 事件)
            if _should_run_habit_extract(session_id):
                answer_summary = f"行数={len(result)}, 列={list(result.columns)}, 前 3 行={result.head(3).fillna('').astype(str).values.tolist()}"
                asyncio.create_task(_extract_habits_async(question, answer_summary))

            if do_analysis:
                # 第二轮 LLM:分析结果 + 建议后续问题
                yield f"data: {json.dumps({'event': 'analyzing'}, ensure_ascii=False)}\n\n"
                try:
                    analysis = await run_in_threadpool(call_llm_analysis, {
                        "question": question,
                        "code": code,
                        "row_count": len(result),
                        "columns": list(result.columns),
                        "preview": result.head(8).fillna("").astype(str).values.tolist(),
                    })
                except Exception as e:
                    analysis = {"insight": f"(分析失败:{e})", "suggestions": []}

                yield f"data: {json.dumps({'event': 'analysis', 'data': analysis}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': f'{type(e).__name__}: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/analyze_detail")
async def analyze_detail(
    question: str = Form(...),
    code: str = Form(...),
    result_json: str = Form(...),  # 前端传来的 result JSON
    session_id: Optional[str] = Form(None),
):
    """单独触发 analysis 阶段(用于"获取 AI 洞察"按钮)"""
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")

    try:
        result_data = json.loads(result_json)
        analysis = await run_in_threadpool(call_llm_analysis, {
            "question": question,
            "code": code,
            "row_count": result_data.get("row_count", 0),
            "columns": result_data.get("columns", []),
            "preview": result_data.get("rows", [])[:8],
        })
    except Exception as e:
        analysis = {"insight": f"(分析失败:{e})", "suggestions": []}

    # 把 insight 存到 session
    if session_id:
        add_to_session(session_id, "assistant", f"[insight] {analysis.get('insight', '')}")

    return analysis


@app.post("/api/chart")
async def chart(
    question: str = Form(...),
    result_json: str = Form(...),
):
    """根据 result 数据生成图表配置(LLM 选类型,前端用 ECharts 渲染)"""
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")

    try:
        result_data = json.loads(result_json)
        chart_cfg = await run_in_threadpool(call_llm_chart, {
            "question": question,
            "columns": result_data.get("columns", []),
            "preview": result_data.get("rows", [])[:8],
        })
    except Exception as e:
        # fallback:默认 bar
        cols = json.loads(result_json).get("columns", [])
        chart_cfg = {"type": "bar", "title": question[:30], "x": cols[0] if cols else "", "y": cols[-1] if cols else ""}

    return chart_cfg


@app.post("/api/report")
async def report(
    question: str = Form(...),
    result_json: str = Form(...),
    insight: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    """根据 result + 可选 insight 生成结构化 markdown 报告"""
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")

    try:
        result_data = json.loads(result_json)
        report_md = await run_in_threadpool(call_llm_report, {
            "question": question,
            "row_count": result_data.get("row_count", 0),
            "columns_count": len(result_data.get("columns", [])),
            "columns": result_data.get("columns", []),
            "rows": result_data.get("rows", []),
            "insight": insight or "",
        })
    except Exception as e:
        raise HTTPException(500, f"生成报告失败:{e}")

    # 把报告存到 session
    if session_id:
        add_to_session(session_id, "assistant", f"[report]\n{report_md[:500]}...")

    # 保存到 output 目录(供后续导出)
    import uuid
    output_dir = BASE_DIR.parent / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / f"report_{uuid.uuid4().hex[:6]}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return {"report": report_md, "path": str(report_path)}


@app.post("/api/report_session")
async def report_session(session_id: str = Form(...)):
    """基于 session 里所有的分析结果,生成综合性总结报告"""
    if _global_df is None:
        raise HTTPException(500, "数据源未加载")

    history = get_session(session_id)
    if not history:
        raise HTTPException(400, "session 为空")

    # 收集所有 (question, result_summary) 对
    items = []
    last_question = None
    for msg in history:
        if msg['role'] == 'user':
            last_question = msg.get('content', '')
        elif msg['role'] == 'assistant' and msg.get('result_summary'):
            items.append({
                'question': last_question,
                'row_count': msg['result_summary'].get('row_count', 0),
                'columns': msg['result_summary'].get('columns', []),
                'preview': msg['result_summary'].get('preview', []),
                'insight': msg.get('insight', ''),
            })

    if not items:
        raise HTTPException(400, "本次对话还没有可总结的分析结果")

    try:
        report_md = await run_in_threadpool(call_llm_session_report, items)
    except Exception as e:
        raise HTTPException(500, f"生成会话总结失败:{e}")

    import uuid
    output_dir = BASE_DIR.parent / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / f"session_report_{uuid.uuid4().hex[:6]}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return {"report": report_md, "path": str(report_path), "item_count": len(items)}


@app.post("/api/session/clear")
async def clear_session(session_id: str = Form(...)):
    """清空指定 session 的历史"""
    with sessions_lock:
        if session_id in sessions:
            sessions[session_id] = []
            _session_last_active[session_id] = time.time()
    return {"status": "ok"}


# ============================================================
# 后台管理(业务规则读写)
# ============================================================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dataagent-admin")  # 默认 token,生产建议改

@app.get("/api/admin/rules")
async def admin_get_rules():
    """读取当前业务规则 JSON"""
    if not RULES_PATH.exists():
        raise HTTPException(404, f"规则文件不存在:{RULES_PATH}")
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"path": str(RULES_PATH), "content": content}


@app.post("/api/admin/rules")
async def admin_save_rules(
    content: str = Form(...),
    token: str = Form(...),
):
    """保存业务规则 JSON(覆盖写)"""
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "鉴权失败:token 不正确")

    # 验证 JSON 合法
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON 格式错误:{e}")

    # 写回
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    # 重新加载到内存
    load_business_rules()

    return {
        "status": "ok",
        "path": str(RULES_PATH),
        "rules_count": len(_business_rules.get('filters', [])),
        "message": "已保存,新规则立即生效(每次 LLM 调用都会重新拼装 prompt)",
    }


# ============================================================
# 后台管理(用户习惯记忆读写)
# ============================================================
@app.get("/api/admin/memory")
async def admin_get_memory():
    """读取用户习惯记忆 JSON"""
    if not MEMORY_PATH.exists():
        return {"path": str(MEMORY_PATH), "content": json.dumps({"habits": []}, ensure_ascii=False)}
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"path": str(MEMORY_PATH), "content": content}


@app.post("/api/admin/memory")
async def admin_save_memory(
    content: str = Form(...),
    token: str = Form(...),
):
    """保存用户习惯记忆 JSON(覆盖写)。修改后立即生效(下次 LLM 调用重新读)"""
    if token != ADMIN_TOKEN:
        raise HTTPException(403, "鉴权失败:token 不正确")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON 格式错误:{e}")

    # 简单的 schema 校验
    if not isinstance(parsed, dict) or not isinstance(parsed.get("habits", []), list):
        raise HTTPException(400, "habits 必须是 list")

    # 写回(持锁,防止与自动学习线程并发写)
    with MEMORY_IO_LOCK:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)

        # 立即重读到内存(下次 LLM 调用会再次读盘,这是保险)
        load_user_memory()

    return {
        "status": "ok",
        "path": str(MEMORY_PATH),
        "habits_count": len(parsed.get("habits", [])),
        "message": "已保存,下次 LLM 调用立即生效",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8765))

    print(f"🚀 DataAgent Web")
    if DATA_SOURCE_SQL:
        print(f"   数据源:SQL Server (query: {DATA_SOURCE_SQL_QUERY[:60]}...)")
    elif DATA_SOURCE_PATH:
        print(f"   数据源:Excel {DATA_SOURCE_PATH}")
    else:
        print(f"   ⚠️  未指定数据源")
    load_business_rules()
    load_user_memory()
    print(f"   LLM:{LLM_MODEL}")
    print(f"   用户记忆:{MEMORY_PATH} ({len(_user_memory.get('habits', []))} 条已学偏好)")
    print(f"   http://localhost:{port}")
    print()
    uvicorn.run(app, host="127.0.0.1", port=port)
