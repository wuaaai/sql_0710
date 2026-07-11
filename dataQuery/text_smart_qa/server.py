import json
import os
import re
import sys
import time
import traceback
import uuid
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import env_utils
from src.agent.utils.log_utils import log
from src.agent.utils.memory_manager import filter_recent_user_messages, memory_manager
from src.agent.utils.tool_limiter import rag_limiter
from src.unified.chart_cache import load_chart_record
from src.unified.echarts_option_builder import build_echarts_option
from src.unified.unified_qa_service import unified_qa_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "src"))

IMAGE_STORAGE_PATH = os.path.join(BASE_DIR, "static", "images")
app = FastAPI(title="Budget Smart Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists(IMAGE_STORAGE_PATH):
    log.warning(f"图片目录不存在，正在自动创建: {IMAGE_STORAGE_PATH}")
    os.makedirs(IMAGE_STORAGE_PATH)

app.mount("/static/images", StaticFiles(directory=IMAGE_STORAGE_PATH), name="images")
log.info(f"图片服务已挂载: {env_utils.IMAGE_BASE_URL}")

_REGION_CODE_PATTERN = re.compile(r"\n{2,}(\d{6,9})\s*$")


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIRequest(BaseModel):
    model: str = "budget-assistant"
    messages: List[OpenAIMessage]
    stream: bool = False
    user: Optional[str] = "default_dify_user"
    region_code: Optional[str] = None


class ChartExportRequest(BaseModel):
    id: str


def extract_region_code(messages: list):
    """从最后一条用户消息末尾提取地区码。"""
    if not messages:
        return None, messages

    for msg in reversed(messages):
        if msg.role != "user":
            continue

        match = _REGION_CODE_PATTERN.search(msg.content)
        if not match:
            break

        code = match.group(1)
        cleaned = _REGION_CODE_PATTERN.sub("", msg.content).rstrip()
        cleaned_messages = []
        for item in messages:
            if item is msg:
                cleaned_messages.append(type(item)(role=item.role, content=cleaned))
            else:
                cleaned_messages.append(item)
        return code, cleaned_messages

    return None, messages


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "budget-assistant", "object": "model", "owned_by": "custom"},
            {"id": "rag", "object": "model", "owned_by": "custom"},
        ],
    }


@app.post("/v1/chart/export")
async def export_chart_option(request: ChartExportRequest):
    """根据用户问题读取缓存图表，并返回 Dify 可用的 ECharts option。"""
    chart_record = load_chart_record(request.id)
    if not chart_record:
        raise HTTPException(status_code=404, detail=f"未找到图表缓存，id={request.id}")

    chart = chart_record.get("chart") or {}
    if not chart.get("can_plot"):
        raise HTTPException(status_code=400, detail="chart.can_plot 为 false，当前图表不可导出。")

    try:
        option = build_echarts_option(chart)
    except Exception as exc:
        log.error(f"图表 option 生成失败: {exc}")
        log.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"图表 option 生成失败: {exc}") from exc

    return option

@app.post("/v1/chat/completions")

async def dify_openai_compatible_endpoint(request: OpenAIRequest, raw_request: Request):
    try:
        raw_body = await raw_request.json()
        conversation_id = raw_body.get("sys.conversation_id")
        user_id = raw_body.get("sys.user_id")

        print(f"\n{'=' * 60}")
        print(f"[Server] message_count: {len(request.messages)}")
        print(f"[Server] user_id: {user_id}")

        turn_id = conversation_id or str(uuid.uuid4())
        rag_limiter.reset_turn(turn_id)

        extracted_code, cleaned_messages = extract_region_code(request.messages)
        effective_region_code = request.region_code or extracted_code
        print(f"[Server] 生效 region_code: {effective_region_code!r}")

        raw_history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in cleaned_messages
        ]
        _, filtered_history, _ = filter_recent_user_messages(
            raw_history_dicts,
            token_limit=env_utils.MEMORY_TOKEN_LIMIT,
        )

        langchain_inputs = [memory_manager.dict_to_langchain(item) for item in filtered_history]

        unified_result = await unified_qa_service.answer(
            raw_history_dicts=filtered_history,
            langchain_messages=langchain_inputs,
            thread_id=turn_id,
            region_code=effective_region_code,
        )
        print("--路由--", unified_result)
        last_message = unified_result.answer
        print(f"[Server] route: {unified_result.route}, reason: {unified_result.decision.reason}")

        if not request.stream:
            extra_payload = dict(unified_result.extra or {})
            if unified_result.fiscal_result is not None:
                extra_payload["fiscal_result"] = {
                    "answer": unified_result.fiscal_result.answer,
                    "sql": unified_result.fiscal_result.sql,
                    "rows": _serialize_for_json(unified_result.fiscal_result.rows),
                    "chart": _serialize_for_json(unified_result.fiscal_result.chart),
                    "facts": _serialize_for_json(unified_result.fiscal_result.facts),
                    "summary": _serialize_for_json(unified_result.fiscal_result.summary),
                    "success": unified_result.fiscal_result.success,
                    "error": unified_result.fiscal_result.error,
                    "slot_status": unified_result.fiscal_result.slot_status,
                    "missing_slots": _serialize_for_json(unified_result.fiscal_result.missing_slots),
                    "slot_values": _serialize_for_json(unified_result.fiscal_result.slot_values),
                    "need_clarify": unified_result.fiscal_result.need_clarify,
                }

            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": last_message},
                        "finish_reason": "stop",
                    }
                ],
                "route": unified_result.route,
                "reason": unified_result.decision.reason,
                "extra": _serialize_for_json(extra_payload),
            }

        async def stream_generator():
            try:
                yield _build_stream_start(request.model)
                yield _build_stream_chunk(request.model, _build_route_tip(unified_result.route))

                for piece in _split_text_for_stream(last_message):
                    yield _build_stream_chunk(request.model, piece)

                yield _build_stream_end(request.model)
                yield "data: [DONE]\n\n"
            except Exception as exc:
                log.error(f"流式输出失败: {exc}")
                log.error(traceback.format_exc())
                yield _build_stream_chunk(request.model, f"\n\n系统异常: {exc}")
                yield _build_stream_end(request.model)
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    except Exception as exc:
        log.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))


def _build_route_tip(route: str) -> str:
    route_name_map = {
        "text_qa": "正在检索财政文档知识库，请稍候...\n\n",
        "fiscal_sql": "正在查询财政数据库，请稍候...\n\n",
        "hybrid": "正在同时查询财政数据库和财政文档，请稍候...\n\n",
        "chitchat": "正在整理回复，请稍候...\n\n",
    }
    return route_name_map.get(route, "正在处理您的问题，请稍候...\n\n")


def _build_stream_start(model_name: str) -> str:
    payload = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_stream_chunk(model_name: str, content: str) -> str:
    payload = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_stream_end(model_name: str) -> str:
    payload = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _split_text_for_stream(text: str, chunk_size: int = 80) -> List[str]:
    if not text:
        return [""]

    chunks = []
    current = ""
    for char in text:
        current += char
        if len(current) >= chunk_size or char in "\n。！；":
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def _serialize_for_json(value):
    """把 Decimal 等非 JSON 基础类型转换成可序列化值。"""
    if isinstance(value, dict):
        return {key: _serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_for_json(item) for item in value]

    class_name = value.__class__.__name__
    if class_name == "Decimal":
        return float(value)
    return value


if __name__ == "__main__":
    log.info("服务启动中...")
    print(env_utils.SERVER_HOST)
    uvicorn.run("server:app", host=env_utils.SERVER_HOST, port=env_utils.SERVER_PORT, reload=False)
