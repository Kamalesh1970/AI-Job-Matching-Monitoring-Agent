"""
Abstract base class interface for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """
    Abstract interface for LLM providers generating structured output.
    Allows swapping OpenAI with other providers in the future without modifying services.
    """

    @abstractmethod
    def generate_structured(
        self, prompt: str, system_prompt: str, response_model: Type[T]
    ) -> T:
        """
        Generates a structured object matching response_model using the LLM.

        Args:
            prompt: User prompt containing resume, job description, and match context.
            system_prompt: System prompt with strict instructions and factual constraints.
            response_model: Pydantic model class to validate and parse response into.

        Returns:
            An instance of response_model populated with LLM generation results.

        Raises:
            Exception: If provider call fails, times out, or fails validation.
        """
        pass
