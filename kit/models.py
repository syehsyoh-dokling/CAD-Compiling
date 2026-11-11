"""Swappable chat models. Everything model-specific lives here; the rest of the kit only calls .chat().

Providers (set in models.json):
    anthropic       Claude via the official SDK (ANTHROPIC_API_KEY). Streams, adaptive thinking.
    openai_compat   any OpenAI-compatible endpoint: OpenAI, NVIDIA NIM, OpenRouter, vLLM, Ollama, LM Studio, ...
Scripted solvers (golden / noop / replay) need no model and are defined in solvers.py.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path


class ChatModel:
    name: str = "model"
    vision: bool = False

    def chat(self, system: str, messages: list[dict], images: list[Path] | None = None) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}]; images are attached to the first user turn."""
        raise NotImplementedError


class AnthropicModel(ChatModel):
    def __init__(self, model: str = "claude-opus-5-5", max_tokens: int = 32000, vision: bool = True,
                 api_key_env: str = "ANTHROPIC_API_KEY", **_: object):
        import anthropic

        self.client = anthropic.Anthropic(api_key=os.environ.get(api_key_env))
        self.model, self.max_tokens, self.vision, self.name = model, max_tokens, vision, model

    def chat(self, system, messages, images=None):
        msgs = [dict(m) for m in messages]
        if images and self.vision:
            blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _b64(p)}} for p in images]
            msgs[0] = {"role": "user", "content": blocks + [{"type": "text", "text": msgs[0]["content"]}]}
        with self.client.messages.stream(model=self.model, max_tokens=self.max_tokens, system=system,
                                         thinking={"type": "adaptive"}, messages=msgs) as stream:
            msg = stream.get_final_message()
        return "".join(b.text for b in msg.content if b.type == "text")


class OpenAICompatModel(ChatModel):
    def __init__(self, model: str, base_url: str | None = None, api_key_env: str | None = "OPENAI_API_KEY",
                 max_tokens: int = 8192, temperature: float = 0.2, vision: bool = False, **_: object):
        from openai import OpenAI

        key = os.environ.get(api_key_env, "") if api_key_env else "not-needed"
        self.client = OpenAI(base_url=base_url, api_key=key or "not-needed")
        self.model, self.max_tokens, self.temperature, self.vision, self.name = model, max_tokens, temperature, vision, model

    def chat(self, system, messages, images=None):
        msgs = [{"role": "system", "content": system}] + [dict(m) for m in messages]
        if images and self.vision:
            parts = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(p)}"}} for p in images]
            msgs[1] = {"role": "user", "content": parts + [{"type": "text", "text": msgs[1]["content"]}]}
        r = self.client.chat.completions.create(model=self.model, messages=msgs, max_tokens=self.max_tokens,
                                                temperature=self.temperature)
        return r.choices[0].message.content or ""


PROVIDERS = {"anthropic": AnthropicModel, "openai_compat": OpenAICompatModel}


def make_chat_model(cfg: dict) -> ChatModel:
    cfg = dict(cfg)
    provider = cfg.pop("provider")
    cfg.pop("note", None)
    if provider not in PROVIDERS:
        raise ValueError(f"unknown chat provider {provider!r}; use one of {sorted(PROVIDERS)}")
    return PROVIDERS[provider](**cfg)


def _b64(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()
