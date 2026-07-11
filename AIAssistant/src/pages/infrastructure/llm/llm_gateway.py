"""大模型网关。

统一封装 LLM 调用，提供与 dataQuery DeepSeekClient 兼容的接口，
供 UnifiedIntentExtractor 等业务模块使用。

支持 OpenAI 兼容 API 格式（DeepSeek / 本地模型等）。
"""

import json
from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass
class LlmConfig:
    """LLM 连接配置。"""

    api_key: str = ""
    """API 密钥。"""

    base_url: str = "https://api.deepseek.com/v1"
    """API 基础地址，兼容 OpenAI 格式。"""

    model: str = "deepseek-chat"
    """模型名称。"""

    timeout_seconds: int = 90
    """请求超时秒数。"""


class LlmGateway:
    """大模型网关。

    封装 OpenAI 兼容的 LLM 调用，提供 chat_json 接口。
    与 dataQuery 的 DeepSeekClient 接口兼容，
    可直接作为 UnifiedIntentExtractor 的 llm_client 使用。
    """

    def __init__(self, config: LlmConfig):
        """初始化网关。

        Args:
            config: LLM 连接配置
        """
        self._config = config

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """发送一次聊天请求，返回模型生成的纯文本。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 采样温度，默认 0.2

        Returns:
            模型输出的文本

        Raises:
            ValueError: API key 未配置时抛出
            requests.HTTPError: API 调用失败时抛出
        """
        if not self._config.api_key:
            raise ValueError("LLM API key 未配置")

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
        """发送聊天请求，将模型输出解析为 JSON dict。

        UnifiedIntentExtractor 依赖此接口获取结构化意图提取结果。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            模型输出的 JSON dict

        Raises:
            json.JSONDecodeError: 模型输出不是合法 JSON 时抛出
        """
        raw_text = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text.replace("json", "", 1).strip()
        return json.loads(raw_text)
