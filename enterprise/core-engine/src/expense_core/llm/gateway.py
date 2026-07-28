"""Model-agnostic LLM gateway (SCOPING §2, §11).

The engine depends on this Protocol, never on a concrete SDK. Production wires in
AzureFoundryProvider; tests and offline dev use LocalEchoProvider. Swapping models is
a provider/config change — the tools never know which model answered.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class LLMGateway(Protocol):
    """Minimal surface the tools need: a deterministic, low-temperature completion."""

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
        """Pinned model identifier, recorded in the audit log for reproducibility."""
        ...
