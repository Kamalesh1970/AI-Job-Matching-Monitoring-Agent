"""
Google Gemini API LLM Provider implementation using the official google-genai Python SDK.
Uses structured JSON schema output with Pydantic parsing, bounded retries, and privacy-preserving error handling.
"""

import time
from typing import Type, TypeVar
from pydantic import BaseModel

from app.config import Config
from app.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """
    Gemini Provider implementing structured output generation using google-genai SDK.
    """

    def __init__(self, config: Config):
        self.config = config
        self.model = config.gemini_model or "gemini-2.5-flash"
        self.temperature = config.llm_temperature
        self.api_key = config.gemini_api_key

        if not config.llm_enabled:
            self.client = None
        else:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured or empty.")
            from google import genai

            self.client = genai.Client(api_key=self.api_key)

    def generate_structured(
        self, prompt: str, system_prompt: str, response_model: Type[T]
    ) -> T:
        """
        Calls Gemini API with structured output schema parsing and bounded retries.
        """
        if not self.config.llm_enabled or not self.client:
            raise RuntimeError("LLM is disabled or Gemini client is not initialized.")

        from google.genai import types

        max_retries = 3
        backoff_delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                gen_config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    response_mime_type="application/json",
                    response_schema=response_model,
                )

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=gen_config,
                )

                if hasattr(response, "parsed") and response.parsed is not None:
                    if isinstance(response.parsed, response_model):
                        return response.parsed
                    if isinstance(response.parsed, dict):
                        return response_model.model_validate(response.parsed)

                text = getattr(response, "text", None)
                if text and text.strip():
                    cleaned = text.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    if cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    return response_model.model_validate_json(cleaned.strip())

                raise ValueError("Gemini returned empty structured output.")

            except Exception as exc:
                exc_type = type(exc).__name__
                exc_str = str(exc)
                exc_lower = exc_str.lower()

                # Do not retry authentication or permission errors
                if any(
                    kw in exc_lower or kw in exc_type.lower()
                    for kw in [
                        "authentication",
                        "401",
                        "403",
                        "api_key_invalid",
                        "unauthenticated",
                        "permissiondenied",
                        "invalid_api_key",
                        "invalid api key",
                    ]
                ):
                    raise RuntimeError("Gemini API authentication failure.") from exc

                # Bounded retries for transient errors
                if attempt < max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    raise RuntimeError(
                        f"Gemini API call failed after {max_retries} attempts: {exc_type}"
                    ) from exc

        raise RuntimeError("Gemini API call failed.")
