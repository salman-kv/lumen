"""LLM provider abstraction. The LLM is used ONLY for language: extracting facts from a question,
reading rules out of policy text, and phrasing the final answer. Decisions are made elsewhere.

Providers (LLM_PROVIDER): ollama (free, local) | openai_compat (Groq/OpenRouter free tiers) | mock
"""
import json
import logging
import re
from typing import AsyncIterator

import httpx

from .config import settings

log = logging.getLogger("llm")
# rate limited, model missing or deprecated, or the service is having a bad moment: worth trying the next model
RETRY_STATUS = {404, 408, 429, 500, 502, 503, 504}


class LLMError(Exception):
    pass


def provider_name() -> str:
    return settings.llm_provider


def _openai_models() -> list[str]:
    """The main model first, then the fallbacks (each model has its own rate-limit bucket on free tiers)."""
    extra = [m.strip() for m in settings.openai_fallback_models.split(",") if m.strip()]
    return [settings.openai_model] + [m for m in extra if m != settings.openai_model]


def _openai_payload(model: str, system: str, user: str, *, stream: bool = False, json_mode: bool = False) -> dict:
    body = {"model": model, "temperature": 0 if json_mode else 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if stream:
        body.update(stream=True, max_tokens=400)
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if "gpt-oss" in model:  # reasoning models: keep the thinking short; its tokens count toward the limit
        body["reasoning_effort"] = "low"
        if stream:
            body["max_tokens"] = 800
    return body


def _clean(text: str) -> str:
    """Some models write narrow no-break spaces; show ordinary spaces."""
    return text.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2009", " ")


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
            last: Exception | None = None
            for model in _openai_models():
                try:
                    r = await c.post(f"{settings.openai_base_url}/chat/completions",
                                     headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                                     json=_openai_payload(model, system, user, json_mode=True))
                    r.raise_for_status()
                    return _extract_json(_clean(r.json()["choices"][0]["message"]["content"]))
                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUS:
                        raise
                    log.warning("model %s answered %s, trying the next one", model, e.response.status_code)
                    last = e
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last = e
            raise last or LLMError("no language model configured")
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
                last: Exception | None = None
                for model in _openai_models():
                    started = False
                    try:
                        async with c.stream("POST", f"{settings.openai_base_url}/chat/completions",
                                            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                                            json=_openai_payload(model, system, user, stream=True)) as r:
                            r.raise_for_status()
                            async for line in r.aiter_lines():
                                if not line.startswith("data:") or line.strip().endswith("[DONE]"):
                                    continue
                                delta = json.loads(line[5:])["choices"][0]["delta"].get("content")
                                if delta:
                                    started = True
                                    yield _clean(delta)
                        return
                    except httpx.HTTPStatusError as e:
                        if started or e.response.status_code not in RETRY_STATUS:
                            raise
                        log.warning("model %s answered %s, trying the next one", model, e.response.status_code)
                        last = e
                    except (httpx.TimeoutException, httpx.ConnectError) as e:
                        if started:
                            raise
                        last = e
                if last:
                    raise last
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
