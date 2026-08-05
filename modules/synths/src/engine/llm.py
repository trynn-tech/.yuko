#!/usr/bin/env python3
# modules/synths/src/engine/llm.py

import json
import httpx

from rich.console import Console 

console = Console() 

class LocalInferenceEngine:
    """Raw streaming inference client for local OpenAI-compatible / Ollama endpoints."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8081/v1/chat/completions",
        model_name: str = "gpt-5",
        timeout: float = 120.0,
    ):
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout = timeout

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
            }
            if is_openai_schema
            else {
                "model": self.model_name,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": True,
                "options": {"temperature": 0.2, "num_ctx": 16384},
            }
        )

        console.print(f"\n[cyan]=^-.-^= Synthesizing via {self.model_name}...[/cyan]\n")

        try:
            with httpx.stream("POST", self.endpoint, json=payload, timeout=self.timeout) as response:
                if response.status_code != 200:
                    console.print(f"[red]Error ({response.status_code}):[/red] {response.read().decode('utf-8')}")
                    return ""

                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    # Decode OpenAI or Ollama token format
                    token = self._extract_token(line, is_openai_schema)
                    if token:
                        full_response.append(token)
                        console.print(token, end="")

            console.print("\n")
            return "".join(full_response)

        except Exception as e:
            console.print(f"[red]Inference failed:[/red] {e}")
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
