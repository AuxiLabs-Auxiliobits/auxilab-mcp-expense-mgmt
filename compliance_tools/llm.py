"""Optional LLM seam.

The five tools are fully functional with **no model at all** — every LLM-assisted tool
pairs the model with a deterministic fallback that produces the same shape of answer.
That is what makes this project run offline with zero credentials.

``LLMGateway`` is a structural Protocol, so bringing your own model is a matter of
passing any object with a ``complete()`` method — no subclassing, no registration, and
no provider SDK in this repository's dependency tree.

Example::

    class MyProvider:
        def complete(self, messages, *, temperature=0.0, max_tokens=1024) -> str:
            return my_client.chat(messages)

        @property
        def model_version(self) -> str:
            return "my-model-1"

    parse_receipt(text, llm=MyProvider())
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class LLMGateway(Protocol):
    """The minimal surface the tools need: one deterministic completion call."""

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Return the assistant's text. Implementations must be side-effect free."""
        ...

    @property
    def model_version(self) -> str:
        """Pinned model identifier, recorded alongside results for reproducibility."""
        ...


class OfflineProvider:
    """The default. Returns a sentinel that tells each tool to use its own
    deterministic path (regex extraction, keyword matching, templated narrative).

    This is not a "mock that pretends to work" — the deterministic paths are the
    tools' real, tested behaviour, and they are what the offline test-suite asserts on.
    """

    SENTINEL = "__OFFLINE__"

    def __init__(self, model_version: str = "offline-deterministic-1") -> None:
        self._model_version = model_version

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        return self.SENTINEL

    @property
    def model_version(self) -> str:
        return self._model_version


def is_offline(raw: str) -> bool:
    """True when a completion came from :class:`OfflineProvider`."""
    return raw == OfflineProvider.SENTINEL
