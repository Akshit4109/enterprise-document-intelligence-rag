from typing import Dict, Optional
from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.openai import OpenAILLMProvider
from app.llm.gemini import GeminiLLMProvider


class LLMProviderFactory:
    """
    Factory registry for instantiating and caching LLM Providers.
    """

    _instances: Dict[str, BaseLLMProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider_type: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> BaseLLMProvider:
        p_type = (provider_type or settings.LLM_PROVIDER).lower()

        cache_key = f"{p_type}_{model_name}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]

        if p_type == "mock":
            provider = MockLLMProvider(model_name=model_name or "mock-llm-v1")
        elif p_type == "openai":
            provider = OpenAILLMProvider(model_name=model_name)
        elif p_type == "gemini":
            provider = GeminiLLMProvider(model_name=model_name)
        else:
            raise ValueError(f"Unsupported LLM provider: '{p_type}'. Options: 'mock', 'openai', 'gemini'")

        cls._instances[cache_key] = provider
        return provider


def get_llm_provider() -> BaseLLMProvider:
    """Dependency helper to resolve the active LLM provider."""
    return LLMProviderFactory.get_provider()
