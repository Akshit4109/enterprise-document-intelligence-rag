from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Standard response object returned by all LLM providers."""
    content: str = Field(description="Generated text response from the model")
    model: str = Field(description="Identifier of the model used")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Prompt, completion, and total tokens used")
    raw_response: Optional[Dict[str, Any]] = Field(default=None, description="Raw vendor response object if available")


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    Decouples RAG business logic from specific proprietary APIs (OpenAI, Gemini, Anthropic, local vLLM).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = 1000,
    ) -> LLMResponse:
        """
        Generates text completion based on prompt and optional system instructions.
        """
        pass
