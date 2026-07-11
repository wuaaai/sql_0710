"""大模型调用封装模块。"""

from __future__ import annotations

import json
from typing import Any, Dict

import requests

from config import LLMConfig


class DeepSeekClient:
    """对外提供简单的文本生成和 JSON 提取能力。"""

    def __init__(self, config: LLMConfig):
        """保存大模型连接配置。"""
        self._config = config

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """发送一次聊天请求，并返回模型生成的纯文本。"""
        if not self._config.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured.")

        response = requests.post(
            f"{self._config.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._config.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """发送一次聊天请求，并把模型输出解析成 JSON。"""
        raw_text = self.chat(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1)
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text.replace("json", "", 1).strip()
        return json.loads(raw_text)
