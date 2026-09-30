import os
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse


class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider (gemini-1.5-flash, gemini-1.5-pro).
    Reads API key securely from environment variables.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        self._model_name = model_name or settings.GEMINI_MODEL_NAME

        if not self.api_key:
            raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY in environment or .env file.")

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent?key={self.api_key}"

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Gemini API Error ({response.status_code}): {response.text}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini API returned no candidates.")

            content = candidates[0]["content"]["parts"][0]["text"]
            usage_metadata = data.get("usageMetadata", {})

            return LLMResponse(
                content=content,
                model=self._model_name,
                token_usage={
                    "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                    "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                    "total_tokens": usage_metadata.get("totalTokenCount", 0),
                },
                raw_response=data,
            )
