import re
from typing import Dict, Optional
from app.llm.base import BaseLLMProvider, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM Provider for deterministic testing without external API calls or token costs.
    Synthesizes concise grounded answers citing verified sources [1], [2] without boilerplate repetitive preambles.
    """

    def __init__(self, model_name: str = "mock-llm-v1"):
        self._model_name = model_name
        self.custom_response: Optional[str] = None
        self.simulate_failure: bool = False

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = 1000,
    ) -> LLMResponse:
        if self.simulate_failure:
            raise RuntimeError("Simulated LLM API rate limit / timeout error.")

        if self.custom_response is not None:
            return LLMResponse(
                content=self.custom_response,
                model=self._model_name,
                token_usage={
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(self.custom_response.split()),
                    "total_tokens": len(prompt.split()) + len(self.custom_response.split()),
                },
            )

        # Extract context passages marked as [1], [2], etc. from prompt
        context_blocks = re.findall(r"(\[\d+\].*?)(?=\[\d+\]|==============================|CURRENT USER QUESTION:|$)", prompt, re.DOTALL)

        if not context_blocks:
            content = "Based on the provided documents, I could not find sufficient information to answer this question."
        else:
            # Construct a concise, natural grounded answer citing the source numbers directly
            sentences = []
            for i, block in enumerate(context_blocks, start=1):
                clean_block = " ".join(block.split())
                # Extract the core text after Header/Content: if present
                if "Content:" in clean_block:
                    core_content = clean_block.split("Content:", 1)[1].strip()
                else:
                    core_content = clean_block
                snippet = core_content[:140].rstrip(".")
                sentences.append(f"{snippet} [{i}].")

            content = " ".join(sentences)

        return LLMResponse(
            content=content,
            model=self._model_name,
            token_usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(content.split()),
                "total_tokens": len(prompt.split()) + len(content.split()),
            },
        )
