"""LLM provider abstraction. The LLM is used ONLY for language: extracting facts from a question,
reading rules out of policy text, and phrasing the final answer. Decisions are made elsewhere.

Providers (LLM_PROVIDER): ollama (free, local) | openai_compat (Groq/OpenRouter free tiers) | mock
"""
import json
import re
from typing import AsyncIterator

import httpx

from .config import settings


class LLMError(Exception):
    pass


def provider_name() -> str:
    return settings.llm_provider


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("The language model returned an unreadable response.")


async def chat_json(system: str, user: str) -> dict:
    p = settings.llm_provider
    if p == "mock":
        raise LLMError("mock provider has no language model")
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as c:
            if p == "ollama":
                r = await c.post(f"{settings.ollama_url}/api/chat", json={
                    "model": settings.ollama_model, "stream": False, "format": "json",
                    "keep_alive": "30m", "options": {"temperature": 0, "num_ctx": 4096},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                r.raise_for_status()
                return _extract_json(r.json()["message"]["content"])
            r = await c.post(f"{settings.openai_base_url}/chat/completions",
                             headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                             json={"model": settings.openai_model, "temperature": 0,
                                   "response_format": {"type": "json_object"},
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}]})
            r.raise_for_status()
            return _extract_json(r.json()["choices"][0]["message"]["content"])
    except LLMError:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise LLMError(f"The language model is unavailable ({type(e).__name__}).") from e


async def stream_text(system: str, user: str, fallback: str = "") -> AsyncIterator[str]:
    p = settings.llm_provider
    if p == "mock":
        for w in re.findall(r"\S+\s*", fallback):
            yield w
        return
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as c:
            if p == "ollama":
                async with c.stream("POST", f"{settings.ollama_url}/api/chat", json={
                        "model": settings.ollama_model, "stream": True, "keep_alive": "30m",
                        "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 320},
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": user}]}) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        d = json.loads(line)
                        if d.get("message", {}).get("content"):
                            yield d["message"]["content"]
                        if d.get("done"):
                            break
            else:
                async with c.stream("POST", f"{settings.openai_base_url}/chat/completions",
                                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                                    json={"model": settings.openai_model, "stream": True, "temperature": 0.2,
                                          "max_tokens": 400,
                                          "messages": [{"role": "system", "content": system},
                                                       {"role": "user", "content": user}]}) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.startswith("data:") or line.strip().endswith("[DONE]"):
                            continue
                        d = json.loads(line[5:])
                        delta = d["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise LLMError(f"The language model is unavailable ({type(e).__name__}).") from e


async def health() -> dict:
    p = settings.llm_provider
    if p == "mock":
        return {"provider": p, "ok": True}
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            if p == "ollama":
                r = await c.get(f"{settings.ollama_url}/api/tags")
                names = [m["name"] for m in r.json().get("models", [])]
                return {"provider": p, "model": settings.ollama_model,
                        "ok": any(n.startswith(settings.ollama_model.split(":")[0]) for n in names)}
            return {"provider": p, "model": settings.openai_model, "ok": bool(settings.openai_api_key)}
    except Exception:
        return {"provider": p, "ok": False}


async def warmup() -> None:
    """Load the model into memory at startup so the first real question isn't slow. Failures are ignored."""
    if settings.llm_provider != "ollama":
        return
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as c:
            await c.post(f"{settings.ollama_url}/api/chat", json={
                "model": settings.ollama_model, "stream": False, "keep_alive": "30m",
                "messages": [{"role": "user", "content": "hi"}], "options": {"num_predict": 1}})
    except Exception:
        pass
