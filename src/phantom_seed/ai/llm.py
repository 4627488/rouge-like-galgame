"""LLM factory for Gemini via LangChain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_google_genai import ChatGoogleGenerativeAI

if TYPE_CHECKING:
    from phantom_seed.config import Config


def create_llm(
    config: Config, *, temperature: float = 0.95, max_tokens: int = 8192
) -> ChatGoogleGenerativeAI:
    """Create a ChatGoogleGenerativeAI instance."""
    return ChatGoogleGenerativeAI(
        model=config.text_model,
        google_api_key=config.gemini_api_key,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
