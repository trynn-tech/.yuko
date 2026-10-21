#!/usr/bin/env python3
# modules/synths/src/engine/llm.py

import json
import logging
import os
from typing import Optional
import httpx
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


class LocalInferenceEngine:
    """Inference client supporting streaming and synchronous passes for OpenAI-compatible / Ollama backends."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 120.0,
        max_tokens: int = 2048,
    ):
        self.endpoint = endpoint or os.getenv(
            "LLM_ENDPOINT", "http://localhost:8081/v1/chat/completions"
        )
        self.model_name = model_name or os.getenv("LLM_MODEL", "gpt-5")
        self.timeout = timeout
        self.max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Executes a synthesis pass and returns the raw accumulated response string."""
        return self.generate_stream(system_prompt, user_prompt)

    def generate_stream(self, system_prompt: str, user_prompt: str) -> str:
        """Streams tokens directly to stdout and returns the raw accumulated string."""
        full_response = []
        is_openai_schema = "/v1/" in self.endpoint

        payload = (
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": True,
                "temperature": 0.2,
                "max_tokens": self.max_tokens,
                "stop": ["<|im_end|>", "<|endoftext|>"],
            }
            if is_openai_schema
            else {
                "model": self.model_name,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": True,
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 16384,
                    "num_predict": self.max_tokens,
                },
            }
        )

        console.print(f"\n[cyan]=^-.-^= Synthesizing via {self.model_name}...[/cyan]\n")
        try:
            with httpx.stream(
                "POST", self.endpoint, json=payload, timeout=self.timeout
            ) as response:
                if response.status_code != 200:
                    console.print(
                        f"[red]Error ({response.status_code}):[/red] {response.read().decode('utf-8')}"
                    )
                    return ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    token = self._extract_token(line, is_openai_schema)
                    if token:
                        full_response.append(token)
                        console.print(token, end="")
            console.print("\n")
            return "".join(full_response)
        except Exception as e:
            console.print(f"[red]Inference failed against {self.endpoint}:[/red] {e}")
            logger.error("Inference request failed against %s: %s", self.endpoint, e)
            return ""

    @staticmethod
    def _extract_token(line: str, is_openai: bool) -> str:
        try:
            if is_openai:
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        return ""
                    data = json.loads(data_str)
                    return data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            else:
                data = json.loads(line)
                return data.get("response", "")
        except json.JSONDecodeError:
            pass
        return ""


# Class alias for backward compatibility across engine modules
LLMClient = LocalInferenceEngine
