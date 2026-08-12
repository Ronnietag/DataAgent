#!/bin/bash
# DataAgent Web 启动脚本
# 用法:./web/start.sh  (依赖环境变量,自动 source .env)

cd "$(dirname "$0")/.."

# 自动加载 .env(如果存在)
if [ -f .env ]; then
  echo "📄 加载 .env"
  set -a
  source .env
  set +a
elif [ -f .env.example ]; then
  echo "⚠️  没找到 .env,只有 .env.example 模板"
  echo "   复制一份:cp .env.example .env && 编辑填实际值"
fi

# 数据源二选一
# 1. Excel:export DATA_SOURCE=/path/to/data.xlsx
# 2. 数据库(SQL Server / SQLite / PostgreSQL 都行):export DATA_SOURCE_SQL=...

if [ -z "$DATA_SOURCE" ] && [ -z "$DATA_SOURCE_SQL" ]; then
  echo "❌ 未指定数据源"
  echo ""
  echo "用法 1:Excel 文件"
  echo "  export DATA_SOURCE=/path/to/data.xlsx"
  echo "  export DATA_SOURCE_SHEET=0  # 可选"
  echo "  export DATA_SOURCE_LABEL='2026 Q1 SFE'  # 可选,显示在前端"
  echo "  ./web/start.sh"
  echo ""
  echo "用法 2:SQL Server"
  echo "  export DATA_SOURCE_SQL='mssql+pyodbc://user:password@host:1433/db?driver=ODBC+Driver+17+for+SQL+Server'"
  echo "  export DATA_SOURCE_SQL_QUERY='SELECT * FROM dbo.sfe_data WHERE year=2026'"
  echo "  export DATA_SOURCE_SQL_LABEL='SFE 2026 数据库'"
  echo "  ./web/start.sh"
  echo ""
  echo "用法 3:SQLite(开发/测试)"
  echo "  export DATA_SOURCE_SQL='sqlite:////absolute/path/to/test.db'"
  echo "  export DATA_SOURCE_SQL_QUERY='SELECT * FROM your_table'"
  echo ""
  echo "用法 4:PostgreSQL"
  echo "  export DATA_SOURCE_SQL='postgresql+psycopg2://user:password@host:5432/db'"
  echo "  export DATA_SOURCE_SQL_QUERY='SELECT * FROM public.your_table'"
  echo ""
  exit 1
fi

if [ -z "$MINIMAX_API_KEY" ] && [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
  echo "⚠️  未配置 LLM API key"
  echo "   export MINIMAX_API_KEY=sk-xxx"
  echo ""
fi

export PORT="${PORT:-8765}"
/opt/homebrew/bin/python3.11 web/server.py
