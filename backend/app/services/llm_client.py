"""Unified LLM Client with multi-provider failover.

Architecture:
- Primary Provider: CodeCraft OpenAI-compatible gateway with CODECRAFT_API_KEY
- Local Fallback: Ollama OpenAI-compatible endpoint for offline demos
- Optional Providers: Direct OpenAI and AgentRouter Claude
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
        self.active_provider: Literal["codecraft", "openai", "ollama", "agentrouter", "deterministic"] = "deterministic"
        self.active_model: str = "nexus_deterministic"
        self.probe_status: dict[str, dict[str, object]] = {}

    def _compatible_headers(self, key: str) -> dict[str, str]:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}

    def _provider_config(self, provider: str) -> tuple[str, str, str] | None:
        configs = {
            "codecraft": (self.settings.codecraft_base_url, self.settings.codecraft_model, self.settings.codecraft_api_key or ""),
            "openai": (self.settings.openai_base_url, self.settings.openai_model, self.settings.openai_api_key or ""),
            "ollama": (self.settings.ollama_base_url, self.settings.ollama_model, "ollama"),
        }
        config = configs.get(provider)
        if not config or (provider == "ollama" and not self.settings.ollama_enabled):
            return None
        if provider != "ollama" and not config[2]:
            return None
        return config

    async def _probe_compatible(self, provider: str) -> tuple[bool, int, str]:
        config = self._provider_config(provider)
        if not config:
            return False, 0, f"{provider.title()} is not configured"
        base_url, model, key = config
        payload = {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=self._compatible_headers(key))
            if response.status_code == 200:
                return True, 200, "OK"
            try:
                message = response.json().get("error", {}).get("message", response.text[:100])
            except Exception:
                message = response.text[:100]
            return False, response.status_code, message
        except Exception as exc:
            return False, 0, str(exc)

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
        return await self._probe_compatible("openai")

    async def probe_codecraft(self) -> tuple[bool, int, str]:
        """Test the requested CodeCraft OpenAI-compatible gateway."""
        return await self._probe_compatible("codecraft")

    async def probe_ollama(self) -> tuple[bool, int, str]:
        """Test the local Ollama OpenAI-compatible endpoint."""
        return await self._probe_compatible("ollama")

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
        """Select CodeCraft, then Ollama, then optional cloud providers."""
        print("=" * 70)
        print("[NexusAI Startup Probe] Checking AI model health...")

        # 1. Probe CodeCraft first so the requested model is the primary path.
        codecraft_ok, codecraft_code, codecraft_msg = await self.probe_codecraft()
        msg_cc = codecraft_msg.encode("ascii", errors="replace").decode("ascii")
        print(f"  [1] CodeCraft ({self.settings.codecraft_model}) -> {'200 OK' if codecraft_ok else f'HTTP {codecraft_code}'}: {msg_cc[:60]}")

        # 2. Probe Direct OpenAI
        openai_ok, openai_code, openai_msg = await self.probe_openai()
        self.probe_status["openai"] = {
            "model": self.settings.openai_model,
            "status_code": openai_code,
            "ok": openai_ok,
            "message": openai_msg,
        }
        status_tag = "200 OK" if openai_ok else f"HTTP {openai_code}"
        msg_oa = openai_msg.encode("ascii", errors="replace").decode("ascii")
        print(f"  [2] Direct OpenAI ({self.settings.openai_model}) -> {status_tag}: {msg_oa[:60]}")

        # 3. Probe local Ollama before the remote secondary provider.
        ollama_ok, ollama_code, ollama_msg = await self.probe_ollama()
        self.probe_status["ollama"] = {"model": self.settings.ollama_model, "status_code": ollama_code, "ok": ollama_ok, "message": ollama_msg}
        msg_ol = ollama_msg.encode("ascii", errors="replace").decode("ascii")
        print(f"  [3] Ollama ({self.settings.ollama_model}) -> {'200 OK' if ollama_ok else f'HTTP {ollama_code}'}: {msg_ol[:60]}")

        # 4. Probe AgentRouter Claude
        ar_ok, ar_code, ar_msg = await self.probe_agentrouter()
        self.probe_status["agentrouter"] = {
            "model": self.settings.agentrouter_model,
            "status_code": ar_code,
            "ok": ar_ok,
            "message": ar_msg,
        }
        status_tag_ar = "200 OK" if ar_ok else f"HTTP {ar_code}"
        msg_ar = ar_msg.encode("ascii", errors="replace").decode("ascii")
        print(f"  [4] AgentRouter Claude ({self.settings.agentrouter_model}) -> {status_tag_ar}: {msg_ar[:60]}")

        # Selection logic
        if codecraft_ok:
            self.active_provider = "codecraft"
            self.active_model = self.settings.codecraft_model
            print(f"  >>> DEFAULT MODEL SELECTED: CodeCraft ({self.active_model}) [ACTIVE]")
        elif ollama_ok:
            self.active_provider = "ollama"
            self.active_model = self.settings.ollama_model
            print(f"  >>> DEFAULT MODEL SELECTED: Ollama ({self.active_model}) [ACTIVE - LOCAL FALLBACK]")
        elif openai_ok:
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

    async def _generate_compatible(
        self,
        instructions: str,
        input_text: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider: str = "openai",
    ) -> str:
        config = self._provider_config(provider)
        if not config:
            raise RuntimeError(f"{provider.title()} is not configured")
        base_url, model, key = config
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=self._compatible_headers(key))
            if resp.status_code != 200:
                raise RuntimeError(f"{provider.title()} HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _generate_openai(self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048) -> str:
        return await self._generate_compatible(instructions, input_text, temperature, max_tokens, "openai")

    async def generate(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> tuple[str, str]:
        """Generate response with automatic provider failover. Returns (text, source_provider)."""
        providers = [self.active_provider, "ollama", "codecraft", "openai", "agentrouter"]
        seen = set()
        failures = []
        for provider in providers:
            if provider in seen or provider == "deterministic":
                continue
            seen.add(provider)
            try:
                if provider == "agentrouter":
                    text = await self._generate_agentrouter(instructions, input_text, temperature, max_tokens)
                else:
                    text = await self._generate_compatible(instructions, input_text, temperature, max_tokens, provider)
                self._mark_active(provider)
                return text, provider
            except Exception as exc:
                failures.append(f"{provider}: {exc}")
                logger.warning("%s generation failed: %s", provider, exc)
        raise RuntimeError("All configured LLM providers failed: " + " | ".join(failures))

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

    async def _stream_compatible(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048, provider: str = "openai"
    ) -> AsyncIterator[str]:
        config = self._provider_config(provider)
        if not config:
            raise RuntimeError(f"{provider.title()} is not configured")
        base_url, model, key = config
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", f"{base_url.rstrip('/')}/chat/completions", headers=self._compatible_headers(key), json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise RuntimeError(f"{provider.title()} stream HTTP {response.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")
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

    async def _stream_openai(self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048) -> AsyncIterator[str]:
        async for token in self._stream_compatible(instructions, input_text, temperature, max_tokens, "openai"):
            yield token

    def _mark_active(self, provider: str) -> None:
        """Keep health/architecture responses aligned with runtime failover."""
        self.active_provider = provider  # type: ignore[assignment]
        if provider == "codecraft":
            self.active_model = self.settings.codecraft_model
        elif provider == "ollama":
            self.active_model = self.settings.ollama_model
        elif provider == "openai":
            self.active_model = self.settings.openai_model
        elif provider == "agentrouter":
            self.active_model = self.settings.agentrouter_model

    async def stream(
        self, instructions: str, input_text: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """Stream response with provider failover."""
        providers = [self.active_provider, "ollama", "codecraft", "openai", "agentrouter"]
        seen = set()
        failures = []
        for provider in providers:
            if provider in seen or provider == "deterministic":
                continue
            seen.add(provider)
            try:
                stream = self._stream_agentrouter(instructions, input_text, temperature, max_tokens) if provider == "agentrouter" else self._stream_compatible(instructions, input_text, temperature, max_tokens, provider)
                async for token in stream:
                    yield token
                self._mark_active(provider)
                return
            except Exception as exc:
                failures.append(f"{provider}: {exc}")
                logger.warning("%s streaming failed: %s", provider, exc)
        raise RuntimeError("All configured streaming providers failed: " + " | ".join(failures))

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
