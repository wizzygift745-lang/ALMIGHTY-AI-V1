"""TEMPORARY PROVIDER LAYER — read carefully.

This module exists ONLY so external models can be plugged in *temporarily*
during early development/experimentation/fallback, per the ALMIGHTY AI
charter. It is architecturally isolated:

  * the orchestrator calls it through the same EngineResult contract;
  * it is disabled unless the admin setting `allow_external_providers=on`;
  * credentials live exclusively in server-side environment variables —
    they are never shipped to the browser;
  * deleting this file changes nothing else in the codebase.

LONG-TERM TARGET:  User -> ALMIGHTY AI -> ALMIGHTY models -> ALMIGHTY infra.
"""
import os
from dataclasses import dataclass


@dataclass
class ProviderResult:
    path: str
    media_type: str


class ProviderAdapter:
    """Contract every temporary external provider must implement."""
    name = "abstract"

    def configured(self) -> bool:
        return False

    def generate_image(self, prompt: str, **params) -> ProviderResult:
        raise NotImplementedError

    def generate_video(self, prompt: str, **params) -> ProviderResult:
        raise NotImplementedError


class OpenAICompatibleAdapter(ProviderAdapter):
    """Example adapter for an OpenAI-compatible endpoint (disabled stub)."""
    name = "openai-compatible"

    def configured(self) -> bool:
        return bool(os.environ.get("ALMIGHTY_EXT_BASE_URL") and os.environ.get("ALMIGHTY_EXT_KEY"))

    def generate_image(self, prompt: str, **params) -> ProviderResult:
        raise NotImplementedError(
            "Temporary provider not implemented in MVP. Use ALMIGHTY engines.")


_REGISTRY = {"openai-compatible": OpenAICompatibleAdapter()}


def active_provider() -> ProviderAdapter | None:
    """Return a configured temporary provider, or None (the normal case)."""
    from .. import db
    if db.setting("allow_external_providers", "off") != "on":
        return None
    for adapter in _REGISTRY.values():
        if adapter.configured():
            return adapter
    return None
