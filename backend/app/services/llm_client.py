"""Unified LLM Client with multi-provider failover.

Architecture:
- Primary Provider: Direct OpenAI (api.openai.com) with separate OPENAI_API_KEY
- Fallback Provider: AgentRouter Claude (agentrouter.org) with AGENTROUTER_API_KEY & Stainless/Claude headers
- Startup Health Probe: Automatically verifies 200 OK and establishes the active default model
- Runtime Failover: Seamlessly switches providers if the active model encounters quota or transient errors
"""
from __future__ import annotations

import base64
import json
import logging
from typing import AsyncIterator, Literal, Optional
import httpx

from app.config import Settings

logger = logging.getLogger("nexusai.llm")

AGENTROUTER_HEADERS = {
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "claude-code-20250219,interleaved-thinking-2025-05-14",
    "User-Agent": "claude-cli/0.2.29 (external, cli)",
    "x-app": "cli",
    "x-stainless-lang": "js",
    "x-stainless-package-version": "0.33.0",
    "x-stainless-os": "Windows",
    "x-stainless-arch": "x64",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v20.10.0",
}


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.active_provider: Literal["openai", "agentrouter", "deterministic"] = "deterministic"
        self.active_model: str = "claude-opus-4-8"
        self.probe_status: dict[str, dict[str, object]] = {}

    def _agentrouter_headers(self) -> dict[str, str]:
        key = self.settings.agentrouter_api_key or ""
        return {
            **AGENTROUTER_HEADERS,
            "Authorization": f"Bearer {key}",
            "x-api-key": key,
        }

    def _openai_headers(self) -> dict[str, str]:
        key = self.settings.openai_api_key or ""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }

    async def probe_openai(self) -> tuple[bool, int, str]:
        """Test Direct OpenAI API health."""
        if not self.settings.openai_api_key:
            return False, 0, "No OpenAI API key configured"
        url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=self._openai_headers())
                    if resp.status_code == 200:
                        return True, 200, "OK"
                    try:
                        err_msg = resp.json().get("error", {}).get("message", resp.text[:100])
                    except Exception:
                        err_msg = resp.text[:100]
                    return False, resp.status_code, err_msg
            except Exception as exc:
                if attempt == 1:
                    return False, 0, str(exc)
        return False, 0, "OpenAI probe failed after retries"

    async def probe_agentrouter(self) -> tuple[bool, int, str]:
        """Test AgentRouter Claude API health."""
        if not self.settings.agentrouter_api_key:
            return False, 0, "No AgentRouter API key configured"
        url = f"{self.settings.agentrouter_base_url.rstrip('/')}/v1/messages"
        payload = {
            "model": self.settings.agentrouter_model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}],
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload, headers=self._agentrouter_headers())
                    if resp.status_code == 200:
                        return True, 200, "OK"
                    try:
                        err_msg = resp.json().get("error", {}).get("message", resp.text[:100])
                    except Exception:
                        err_msg = resp.text[:100]
                    return False, resp.status_code, err_msg
            except Exception as exc:
                if attempt == 1:
                    return False, 0, str(exc)
        return False, 0, "AgentRouter probe failed after retries"

    async def probe_and_configure_default(self) -> str:
        """Startup health probe: test OpenAI gpt-5.4-mini, fall back to AgentRouter Claude."""
        print("=" * 70)
        print("[NexusAI Startup Probe] Checking AI model health...")

        # 1. Probe Direct OpenAI
        openai_ok, openai_code, openai_msg = await self.probe_openai()
        self.probe_status["openai"] = {
            "model": self.settings.openai_model,
            "status_code": openai_code,
            "ok": openai_ok,
            "message": openai_msg,
        }
        status_tag = "200 OK" if openai_ok else f"HTTP {openai_code}"
        print(f"  [1] Direct OpenAI ({self.settings.openai_model}) -> {status_tag}: {openai_msg[:60]}")

        # 2. Probe AgentRouter Claude
        ar_ok, ar_code, ar_msg = await self.probe_agentrouter()
        self.probe_status["agentrouter"] = {
            "model": self.settings.agentrouter_model,
            "status_code": ar_code,
            "ok": ar_ok,
            "message": ar_msg,
        }
        status_tag_ar = "200 OK" if ar_ok else f"HTTP {ar_code}"
        print(f"  [2] AgentRouter Claude ({self.settings.agentrouter_model}) -> {status_tag_ar}: {ar_msg[:60]}")

        # Selection logic
        if openai_ok:
            self.active_provider = "openai"
            self.active_model = self.settings.openai_model
            print(f"  >>> DEFAULT MODEL SELECTED: Direct OpenAI ({self.active_model}) [ACTIVE]")
        elif ar_ok:
            self.active_provider = "agentrouter"
            self.active_model = self.settings.agentrouter_model
            print(f"  >>> DEFAULT MODEL SELECTED: AgentRouter Claude ({self.active_model}) [ACTIVE - OpenAI Fallback]")
        else:
            self.active_provider = "deterministic"
            self.active_model = "nexus_deterministic"
            print("  >>> DEFAULT MODEL SELECTED: Deterministic Fallback Mode")

        print("=" * 70)
        return self.active_model

    async def _generate_agentrouter(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> str:
        url = f"{self.settings.agentrouter_base_url.rstrip('/')}/v1/messages"
        payload = {
            "model": self.settings.agentrouter_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": instructions,
            "messages": [{"role": "user", "content": input_text}],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=self._agentrouter_headers())
            if resp.status_code != 200:
                raise RuntimeError(f"AgentRouter HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
            return "\n".join(blocks).strip()

    async def _generate_openai(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> str:
        url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=self._openai_headers())
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def generate(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> tuple[str, str]:
        """Generate response with automatic provider failover. Returns (text, source_provider)."""
        # Primary attempt based on active provider
        if self.active_provider == "openai":
            try:
                text = await self._generate_openai(instructions, input_text, temperature, max_tokens)
                return text, "openai"
            except Exception as exc:
                logger.warning("Direct OpenAI generation failed: %s. Falling back to AgentRouter Claude.", exc)
                text = await self._generate_agentrouter(instructions, input_text, temperature, max_tokens)
                return text, "agentrouter"
        else:
            try:
                text = await self._generate_agentrouter(instructions, input_text, temperature, max_tokens)
                return text, "agentrouter"
            except Exception as exc:
                logger.warning("AgentRouter Claude generation failed: %s. Attempting Direct OpenAI.", exc)
                text = await self._generate_openai(instructions, input_text, temperature, max_tokens)
                return text, "openai"

    async def _stream_agentrouter(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        url = f"{self.settings.agentrouter_base_url.rstrip('/')}/v1/messages"
        payload = {
            "model": self.settings.agentrouter_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "system": instructions,
            "messages": [{"role": "user", "content": input_text}],
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, headers=self._agentrouter_headers(), json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise RuntimeError(f"AgentRouter stream HTTP {response.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    line = line.strip()
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            if event_data.get("type") == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except Exception:
                            continue

    async def _stream_openai(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, headers=self._openai_headers(), json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise RuntimeError(f"OpenAI stream HTTP {response.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    line = line.strip()
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            delta = event_data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue

    async def stream(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """Stream response with provider failover."""
        if self.active_provider == "openai":
            try:
                async for token in self._stream_openai(instructions, input_text, temperature, max_tokens):
                    yield token
                return
            except Exception as exc:
                logger.warning("OpenAI streaming failed: %s. Falling back to AgentRouter Claude.", exc)
                async for token in self._stream_agentrouter(instructions, input_text, temperature, max_tokens):
                    yield token
        else:
            try:
                async for token in self._stream_agentrouter(instructions, input_text, temperature, max_tokens):
                    yield token
                return
            except Exception as exc:
                logger.warning("AgentRouter streaming failed: %s. Falling back to Direct OpenAI.", exc)
                async for token in self._stream_openai(instructions, input_text, temperature, max_tokens):
                    yield token

    async def vision(
        self, image_bytes: bytes, filename: str, instructions: str
    ) -> str:
        """Extract information from image using multimodal Claude or OpenAI."""
        encoded = base64.b64encode(image_bytes).decode("ascii")
        # Try AgentRouter Claude vision
        try:
            url = f"{self.settings.agentrouter_base_url.rstrip('/')}/v1/messages"
            payload = {
                "model": self.settings.agentrouter_model,
                "max_tokens": 1024,
                "system": instructions,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": encoded,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"Extract operational identifiers, quantities, dates, PPAP/VDA references from {filename}.",
                            },
                        ],
                    }
                ],
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=self._agentrouter_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
                    return "\n".join(blocks).strip()
        except Exception as exc:
            logger.warning("AgentRouter Claude vision failed: %s", exc)

        # Fallback to OpenAI Vision
        try:
            url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
            payload = {
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Extract scanned document named {filename}."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                        ],
                    },
                ],
                "max_tokens": 1024,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=self._openai_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("OpenAI vision fallback failed: %s", exc)

        return ""


_llm_client_instance: Optional[LLMClient] = None


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    global _llm_client_instance
    if _llm_client_instance is None:
        if settings is None:
            from app.config import get_settings
            settings = get_settings()
        _llm_client_instance = LLMClient(settings)
    return _llm_client_instance
