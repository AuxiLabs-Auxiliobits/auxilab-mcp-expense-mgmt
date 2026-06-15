"""Concrete LLM providers.

- LocalEchoProvider: zero-dependency, deterministic stub so the whole engine runs and
  tests pass without Azure. It does NOT attempt real reasoning — tools that use the LLM
  always pair it with a deterministic fallback, so behaviour stays sane offline.
- AzureFoundryProvider: real Azure AI Foundry access via the Azure AI Inference SDK.
  Imported lazily so `pip install expense-core` (without the [azure] extra) still works.
"""

from __future__ import annotations

from expense_core.llm.gateway import ChatMessage


class LocalEchoProvider:
    """Deterministic offline provider. Returns a fixed sentinel; callers fall back to
    their own deterministic heuristics when they see it."""

    SENTINEL = "__LOCAL_ECHO__"

    def __init__(self, model_version: str = "local-echo-0") -> None:
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


class AzureFoundryProvider:
    """Azure AI Foundry chat completion via Managed Identity (no keys in code).

    Requires the optional `[azure]` dependencies. Construct once and inject.
    """

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        *,
        api_key: str | None = None,
        api_version: str = "2024-10-21",
        credential: object | None = None,
    ) -> None:
        try:
            from openai import AzureOpenAI  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover - exercised only with extras absent
            raise RuntimeError(
                "AzureFoundryProvider needs the 'azure' extra: pip install expense-core[azure]"
            ) from e

        self._deployment = deployment
        self._model_version = deployment

        # AzureOpenAI builds the correct route ({endpoint}/openai/deployments/{model}/...),
        # which is what a Foundry/AIServices resource serves chat on. Key auth if provided,
        # else Managed Identity / az-login (needs "Cognitive Services OpenAI User").
        if api_key:
            self._client = AzureOpenAI(
                azure_endpoint=endpoint, api_key=api_key, api_version=api_version
            )
        else:
            from azure.identity import (  # noqa: PLC0415
                DefaultAzureCredential,
                get_bearer_token_provider,
            )

            token_provider = get_bearer_token_provider(
                credential or DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version=api_version,
            )

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        resp = self._client.chat.completions.create(
            model=self._deployment,
            messages=payload,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    @property
    def model_version(self) -> str:
        return self._model_version
