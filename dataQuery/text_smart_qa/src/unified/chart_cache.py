from __future__ import annotations

import hashlib
import json

import redis
from redis.exceptions import RedisError


REDIS_HOST = "10.32.10.24"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_CHART_KEY_PREFIX = "smartqa:chart:"
REDIS_CHART_TTL_SECONDS = 60 * 60 * 24


def get_redis_client():
    """创建 Redis 客户端。"""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        protocol=2,
    )


def build_chart_redis_key(question: str) -> str:
    """根据用户原问题生成 Redis key。"""
    normalized = (question or "").strip()
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return f"{REDIS_CHART_KEY_PREFIX}{digest}"


def save_chart_record(question: str, chart: dict) -> None:
    """把图表配置按用户原问题写入 Redis。"""
    if not question:
        return

    payload = {
        "id": question,
        "chart": chart or {},
    }
    client = get_redis_client()
    client.setex(
        build_chart_redis_key(question),
        REDIS_CHART_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False),
    )


def load_chart_record(question: str) -> dict | None:
    """根据用户原问题从 Redis 读取图表配置。"""
    if not question:
        return None

    client = get_redis_client()
    raw_text = client.get(build_chart_redis_key(question))
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except Exception:
        return None


def save_chart_record_safe(question: str, chart: dict) -> tuple[bool, str]:
    """安全写入 Redis。

    返回:
    - bool: 是否写入成功
    - str: 失败时的错误信息
    """
    try:
        save_chart_record(question, chart)
        return True, ""
    except RedisError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)
