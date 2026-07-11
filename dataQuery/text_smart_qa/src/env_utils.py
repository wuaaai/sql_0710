"""
环境配置工具 — 统一从 .env 读取所有配置项，支持一键切换开发/生产环境。

一键切换:
    python switch_env.py dev      # 切换到开发环境
    python switch_env.py prod     # 切换到生产环境
    python switch_env.py show     # 显示当前使用的环境

编程切换:
    from env_utils import switch_env
    switch_env("dev")   # 或 "prod"
"""
import os
import shutil
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 项目根目录（env_utils.py 在 src/ 下，根目录在上一级）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_active_env() -> Optional[str]:
    """检测当前 .env 来自哪个环境（通过比对内容第一行）"""
    env_file = _PROJECT_ROOT / ".env"
    if not env_file.exists():
        return None
    first_line = env_file.read_text(encoding="utf-8").split("\n")[0].strip()
    for name in ("dev", "prod"):
        candidate = _PROJECT_ROOT / f".env.{name}"
        if candidate.exists():
            candidate_first = candidate.read_text(encoding="utf-8").split("\n")[0].strip()
            if first_line == candidate_first:
                return name
    return None


def switch_env(target: str) -> str:
    """
    切换到目标环境: "dev" 或 "prod"
    返回当前生效的环境名。
    """
    target = target.lower().strip()
    if target not in ("dev", "prod"):
        raise ValueError(f"不支持的环境: {target!r}，可选: dev / prod")

    source = _PROJECT_ROOT / f".env.{target}"
    dest = _PROJECT_ROOT / ".env"

    if not source.exists():
        raise FileNotFoundError(f"环境配置文件不存在: {source}")

    shutil.copy2(source, dest)
    # 重新加载环境变量（覆盖已有值）
    load_dotenv(dest, override=True)
    return target


# 启动时自动加载 .env
_load_path = _PROJECT_ROOT / ".env"
if _load_path.exists():
    load_dotenv(_load_path, override=True)
else:
    # 如果 .env 不存在，尝试从 .env.dev 复制
    dev_path = _PROJECT_ROOT / ".env.dev"
    if dev_path.exists():
        shutil.copy2(dev_path, _load_path)
        load_dotenv(_load_path, override=True)


# ============================================================
# LLM API 密钥与地址
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-Local")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:18000/v1")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")
TavilyClient_API_KEY = os.getenv("TavilyClient_API_KEY", "")

# ============================================================
# LLM 模型参数
# ============================================================
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.5"))
LLM_TRIMMER_MAX_TOKENS = int(os.getenv("LLM_TRIMMER_MAX_TOKENS", "8000"))
LLM_TOKEN_COUNTER = os.getenv("LLM_TOKEN_COUNTER", "approximate")
LLM_TRIMMER_STRATEGY = os.getenv("LLM_TRIMMER_STRATEGY", "last")

# ============================================================
# 向量数据库 (PostgreSQL pgvector)
# ============================================================
PGVECTOR_CONNECTION = os.getenv(
    "PGVECTOR_CONNECTION",
    "postgresql+psycopg2://postgres:123456@localhost:5432/postgres",
)
PGVECTOR_COLLECTION_NAME = os.getenv("PGVECTOR_COLLECTION_NAME", "parent_child_db_1024")

# ============================================================
# Embedding / Rerank 服务
# ============================================================
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "http://localhost:8991/embed")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "")
RERANK_API_URL = os.getenv("RERANK_API_URL", "http://localhost:8991/rerank")
RERANK_API_KEY = os.getenv("RERANK_API_KEY", "")
RERANK_MODEL_NAME = os.getenv("RERANK_MODEL_NAME", "")

# ============================================================
# 图片与静态资源
# ============================================================
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "http://localhost:8000/static/images/")

# ============================================================
# FastAPI 服务
# ============================================================
# ip地址目前走的是自己本机ip
SERVER_HOST = os.getenv("SERVER_HOST", "10.32.10.24")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*")

# ============================================================
# 记忆管理
# ============================================================
MEMORY_TOKEN_LIMIT = int(os.getenv("MEMORY_TOKEN_LIMIT", "13000"))
MAX_USER_MESSAGES = int(os.getenv("MAX_USER_MESSAGES", "10"))
TOKENIZER_MODEL = os.getenv("TOKENIZER_MODEL", "gpt-3.5-turbo")

# ============================================================
# 工具调用限制
# ============================================================
RAG_MAX_CALLS = int(os.getenv("RAG_MAX_CALLS", "4"))
AGENT_RUN_LIMIT = int(os.getenv("AGENT_RUN_LIMIT", "20"))

# ============================================================
# 日志
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
LOG_ROTATION = os.getenv("LOG_ROTATION", "10 MB")
LOG_RETENTION = os.getenv("LOG_RETENTION", "10 days")

# ============================================================
# 时区
# ============================================================
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
