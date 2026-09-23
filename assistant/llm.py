"""Minimal client for a local Ollama server, with an on-disk response cache."""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

CACHE_DIR = Path(os.environ.get("LLM_CACHE_DIR", ".cache/llm"))


@dataclass
class Reply:
    content: str
    prompt_tokens: int
    output_tokens: int
    seconds: float
    cached: bool


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: float = 120.0, use_cache: bool = True):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.use_cache = use_cache

    @classmethod
    def from_env(cls) -> "OllamaClient":
        return cls(
            url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),
        )

    def _key(self, messages) -> str:
        blob = json.dumps({"model": self.model, "messages": messages}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def chat(self, messages: list[dict]) -> Reply:
        key = self._key(messages)
        path = CACHE_DIR / f"{key}.json"
        if self.use_cache and path.exists():
            data = json.loads(path.read_text())
            return Reply(data["content"], data["prompt_tokens"], data["output_tokens"], 0.0, True)

        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        started = time.perf_counter()
        try:
            r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
            r.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(f"cannot reach ollama at {self.url}") from exc
        data = r.json()
        reply = Reply(
            content=data["message"]["content"],
            prompt_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            seconds=time.perf_counter() - started,
            cached=False,
        )
        if self.use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"content": reply.content, "prompt_tokens": reply.prompt_tokens,
                                        "output_tokens": reply.output_tokens}))
        return reply
