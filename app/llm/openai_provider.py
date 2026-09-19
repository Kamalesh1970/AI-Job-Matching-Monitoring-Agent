"""
OpenAI API LLM Provider implementation using the official OpenAI Python SDK.
Uses structured output with Pydantic parsing, bounded retries, and privacy-preserving error handling.
"""

import time
from typing import Type, TypeVar
from pydantic import BaseModel

from app.config import Config
from app.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """
    OpenAI Provider implementing structured output generation.
    """

    def __init__(self, config: Config):
        self.config = config
        self.model = config.openai_model or "gpt-5.6-luna"
        self.temperature = config.llm_temperature
        self.api_key = config.openai_api_key

        if not config.llm_enabled:
            self.client = None
        else:
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY is not configured or empty.")
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)

    def generate_structured(
        self, prompt: str, system_prompt: str, response_model: Type[T]
    ) -> T:
        """
        Calls OpenAI API with structured output parsing and bounded retries.
        """
        if not self.config.llm_enabled or not self.client:
            raise RuntimeError("LLM is disabled or OpenAI client is not initialized.")

        max_retries = 3
        backoff_delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                # Use beta.chat.completions.parse for structured output deserialization
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    response_format=response_model,
                )

                parsed = response.choices[0].message.parsed
                if parsed is None:
                    # Fallback check if response content exists
                    content = response.choices[0].message.content
                    if not content or not content.strip():
                        raise ValueError("OpenAI returned an empty response.")
                    parsed = response_model.model_validate_json(content)

                return parsed

            except Exception as exc:
                exc_type = type(exc).__name__
                exc_str = str(exc)

                # Do not retry authentication or permission errors
                if "AuthenticationError" in exc_type or "401" in exc_str or "403" in exc_str:
                    raise RuntimeError("OpenAI API authentication failure.") from exc

                # Retry transient errors up to max_retries
                if attempt < max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    raise RuntimeError(f"OpenAI API call failed after {max_retries} attempts: {exc_type}") from exc

        raise RuntimeError("OpenAI API call failed.")
