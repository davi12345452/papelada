"""Model clients. Every provider is reached through an OpenAI-compatible chat endpoint.

Models are named "<provider>:<model id>", e.g. "openrouter:openai/gpt-4o" or
"google:gemini-2.5-flash-lite".
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "google": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GOOGLE_API_KEY"),
}

RETRY_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass
class Completion:
    text: str | None
    latency_s: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None  # only when the provider reports it (OpenRouter does)
    error: str | None = None


def complete(model: str, system: str, prompt: str, image: Path, timeout: float = 180, retries: int = 3) -> Completion:
    provider, _, model_id = model.partition(":")
    if provider not in PROVIDERS or not model_id:
        raise ValueError(f"Model must be '<provider>:<id>' with provider in {sorted(PROVIDERS)}: {model!r}")
    url, key_env = PROVIDERS[provider]
    key = os.environ.get(key_env)
    if not key:
        raise RuntimeError(f"{key_env} is not set")

    mime = "image/png" if image.suffix == ".png" else "image/jpeg"
    data_url = f"data:{mime};base64,{base64.b64encode(image.read_bytes()).decode()}"
    body = {
        "model": model_id,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
    }
    if provider == "openrouter":
        body["usage"] = {"include": True}

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    started = time.monotonic()
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUS and attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            detail = e.read().decode(errors="replace")[:500]
            return Completion(None, time.monotonic() - started, error=f"HTTP {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            return Completion(None, time.monotonic() - started, error=str(e))

    latency = time.monotonic() - started
    usage = payload.get("usage") or {}
    choices = payload.get("choices") or []
    text = choices[0].get("message", {}).get("content") if choices else None
    return Completion(
        text=text,
        latency_s=latency,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        cost_usd=usage.get("cost"),
        error=None if text else f"empty response: {json.dumps(payload)[:500]}",
    )
