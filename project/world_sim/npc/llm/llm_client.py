"""LLM provider interface + one generic OpenAI-compatible HTTP provider.

- The simulation is never coupled to a specific provider; it talks to the
  abstract ``LLMProvider.generate(request)``.
- Provider configuration comes exclusively from environment variables
  (``NPC_LLM_API_URL``, ``NPC_LLM_API_KEY``, ``NPC_LLM_MODEL``,
  ``NPC_LLM_TIMEOUT``). API keys are never persisted, written to config,
  included in snapshots, or sent to Unity.
- ``LLMExecutor`` runs provider calls on a worker thread so the simulation
  tick is never blocked on network latency.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional


class LLMError(Exception):
    """Provider-level failure (network, timeout, malformed response)."""


@dataclass
class LLMRequest:
    system: str
    user: str
    temperature: float = 0.7
    max_tokens: int = 150
    model: Optional[str] = None
    topic: Optional[str] = None
    fingerprint: str = ""


class LLMProvider:
    """Abstract provider. Subclasses implement ``generate``."""

    def available(self) -> bool:
        return True

    def generate(self, request: LLMRequest) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """Generic OpenAI-compatible chat-completions HTTP provider.

    Environment variables (never hardcoded):
      NPC_LLM_API_URL   required endpoint, e.g.
                        https://api.openai.com/v1/chat/completions or
                        http://localhost:11434/v1/chat/completions (Ollama)
      NPC_LLM_API_KEY   optional bearer token (empty allowed for local Ollama)
      NPC_LLM_MODEL     optional model override
      NPC_LLM_TIMEOUT   optional timeout seconds (default 10)
    """

    def __init__(self, url=None, api_key=None, model=None, timeout=None):
        self.url = url if url is not None else os.environ.get("NPC_LLM_API_URL", "")
        self.api_key = (
            api_key if api_key is not None else os.environ.get("NPC_LLM_API_KEY", "")
        )
        self.model = model if model is not None else os.environ.get("NPC_LLM_MODEL", "")
        if timeout is None:
            timeout = os.environ.get("NPC_LLM_TIMEOUT", "10")
        self.timeout = float(timeout)

    def available(self) -> bool:
        return bool(self.url)

    def generate(self, request: LLMRequest) -> str:
        if not self.url:
            raise LLMError("no LLM endpoint configured (set NPC_LLM_API_URL)")
        body = {
            "model": request.model or self.model or "",
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        data = json.dumps(body).encode("utf-8")
        try:
            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMError(f"provider http {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError(f"provider network error: {exc}") from exc
        except ValueError as exc:
            raise LLMError("provider returned non-JSON") from exc
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("provider response missing choices[0].message.content") from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMError("provider content is not text")
        return text


class StaticProvider(LLMProvider):
    """Deterministic stub for tests/audits. Returns fixed JSON or raises."""

    def __init__(self, json_text=None, error=None, delay=0.0):
        self._json = json_text
        self._error = error
        self._delay = delay

    def available(self) -> bool:
        return self._error is None

    def generate(self, request: LLMRequest) -> str:
        import time

        if self._error is not None:
            raise self._error
        if self._delay:
            time.sleep(self._delay)
        if self._json is not None:
            return self._json
        return json.dumps(
            {
                "dialogue": f"A deterministic stub reply about {request.topic or 'life'}.",
                "emotion": "content",
                "topic": request.topic or "greeting",
                "follow_up": None,
            }
        )


class LLMExecutor:
    """Worker-thread executor so LLM calls never block the simulation tick."""

    def __init__(self, provider: LLMProvider, max_workers: int = 1):
        self._provider = provider
        self._shutdown = False
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, max_workers), thread_name_prefix="npc_llm"
        )

    @property
    def provider(self):
        return self._provider

    def submit(self, fn, *args):
        if self._shutdown:
            fut = Future()
            fut.set_exception(LLMError("executor shut down"))
            return fut
        try:
            return self._pool.submit(fn, *args)
        except RuntimeError:
            fut = Future()
            fut.set_exception(LLMError("executor shut down"))
            return fut

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._pool.shutdown(wait=False, cancel_futures=True)