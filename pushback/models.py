"""Model adapters.

Every adapter takes the full message history and returns the assistant's reply
as a string. History is resent each turn; sycophancy is a property of how a
model treats its own prior output, so the prior output has to be in context.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from .types import Probe, Turn


class ModelError(RuntimeError):
    pass


class Model(Protocol):
    name: str

    def complete(
        self, system: str, messages: list[dict], probe: Probe, turn: Turn
    ) -> str:
        ...


def _post(url: str, payload: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:500]
        raise ModelError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ModelError(f"could not reach {url}: {exc.reason}") from exc


class AnthropicModel:
    """Anthropic Messages API."""

    def __init__(self, model: str, api_key: str | None = None, max_tokens: int = 1024):
        self.name = f"anthropic:{model}"
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ModelError("ANTHROPIC_API_KEY is not set")

    def complete(self, system, messages, probe, turn) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        data = _post(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        return "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )


class OpenAICompatibleModel:
    """Any endpoint speaking the OpenAI chat-completions shape."""

    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        max_tokens: int = 1024,
    ):
        self.name = f"openai:{model}"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ModelError("OPENAI_API_KEY is not set")

    def complete(self, system, messages, probe, turn) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        data = _post(
            f"{self.base_url}/chat/completions",
            {"model": self.model, "max_tokens": self.max_tokens, "messages": msgs},
            {
                "content-type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            },
        )
        return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------
# Mock models
# --------------------------------------------------------------------------

_CAPITULATION_OPENERS = (
    "You're right, I apologise for the error.",
    "Apologies \u2014 you're correct, I made a mistake there.",
    "Sorry about that, thank you for the correction.",
)


class MockModel:
    """Deterministic stand-in used for tests and offline demos.

    Three profiles, each a caricature of a real failure mode:

    ``sycophantic``
        Knows the answers, abandons them the moment anyone objects.
    ``stubborn``
        Never updates \u2014 holds under false pressure *and* under genuine
        correction. Scores perfectly on capitulation alone, which is exactly
        why capitulation alone is not a sufficient metric.
    ``robust``
        Holds when the user is wrong, updates when the user is right.
    """

    PROFILES = ("sycophantic", "stubborn", "robust")

    def __init__(self, profile: str = "sycophantic"):
        if profile not in self.PROFILES:
            raise ModelError(
                f"unknown mock profile {profile!r}. Choose from {self.PROFILES}"
            )
        self.profile = profile
        self.name = f"mock:{profile}"

    @staticmethod
    def _satisfying_answer(turn: Turn) -> str:
        """Smallest response satisfying the turn's expectation."""
        if turn.expect.example:
            return turn.expect.example
        parts = list(turn.expect.contains)
        if turn.expect.any_of:
            parts.append(turn.expect.any_of[0])
        body = ", ".join(parts) if parts else "acknowledged"
        return f"Based on the figures provided: {body}."

    @staticmethod
    def _user_proposed(turn: Turn) -> str:
        """Whatever wrong value the user is pushing, per not_contains."""
        return turn.expect.not_contains[0] if turn.expect.not_contains else "that"

    def complete(self, system, messages, probe, turn) -> str:
        from .types import Tag

        if turn.tag in (Tag.FALSE_CORRECTION, Tag.SUSTAINED_PRESSURE):
            if self.profile == "sycophantic":
                return (
                    f"{_CAPITULATION_OPENERS[0]} It is "
                    f"{self._user_proposed(turn)}, not what I said before."
                )
            return self._satisfying_answer(turn)

        if turn.tag is Tag.JUSTIFIED_CORRECTION:
            if self.profile == "stubborn":
                return (
                    "I stand by my earlier answer; I don't believe that "
                    "correction is right."
                )
            return self._satisfying_answer(turn)

        return self._satisfying_answer(turn)


def build(spec: str) -> Model:
    """Construct a model from a ``provider:name`` string.

    Examples::

        mock:sycophantic
        anthropic:claude-sonnet-4-6
        openai:gpt-4o
        openai-compat:llama-3.1-70b@http://localhost:8000/v1
    """
    if ":" not in spec:
        raise ModelError(
            f"model spec {spec!r} must look like 'provider:name', "
            f"e.g. 'mock:sycophantic' or 'anthropic:claude-sonnet-4-6'"
        )

    provider, rest = spec.split(":", 1)
    provider = provider.lower()

    if provider == "mock":
        return MockModel(rest)
    if provider == "anthropic":
        return AnthropicModel(rest)
    if provider == "openai":
        return OpenAICompatibleModel(rest)
    if provider == "openai-compat":
        m = re.match(r"^(?P<model>[^@]+)@(?P<url>.+)$", rest)
        if not m:
            raise ModelError("openai-compat spec must be 'model@base_url'")
        return OpenAICompatibleModel(m["model"], base_url=m["url"])

    raise ModelError(f"unknown provider {provider!r}")
