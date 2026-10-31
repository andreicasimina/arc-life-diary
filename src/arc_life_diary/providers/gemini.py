"""Gemini provider implementing BaseEmbeddingModel and BaseLLMClient.

API keys are read strictly from the repository's .env file via python-dotenv.
"""

from pathlib import Path
from typing import List, Optional, Union
import dotenv
from google import genai
from google.genai import types


class ProviderAuthError(Exception):
    """Raised when provider credentials cannot be loaded from .env."""
    pass


def load_env_api_key(env_path: Union[str, Path] = ".env") -> str:
    """Loads GEMINI_API_KEY strictly from the given .env file."""
    path = Path(env_path)
    if not path.is_file():
        raise ProviderAuthError(
            f"Could not find .env file at {path.resolve()}. "
            "Please create a .env file containing GEMINI_API_KEY=your_key."
        )

    env_values = dotenv.dotenv_values(path)
    api_key = env_values.get("GEMINI_API_KEY")
    if not api_key or not str(api_key).strip():
        raise ProviderAuthError(
            f"GEMINI_API_KEY is not defined or is empty in {path.resolve()}. "
            "Please add GEMINI_API_KEY=your_key to your .env file."
        )

    return str(api_key).strip()


class GeminiEmbeddingModel:
    """Concrete embedding model using Gemini text-embedding-004 (768 dimensions)."""

    def __init__(self, api_key: Optional[str] = None, env_path: Union[str, Path] = ".env"):
        resolved_key = api_key or load_env_api_key(env_path)
        self._dimensions = 768
        self._client = genai.Client(api_key=resolved_key)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _embed(self, text: str, task_type: str) -> List[float]:
        config = types.EmbedContentConfig(task_type=task_type)
        response = self._client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=config,
        )
        return response.embedding.values

    def embed_document(self, text: str) -> List[float]:
        """Embeds a single document for ingestion with RETRIEVAL_DOCUMENT task type."""
        return self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> List[float]:
        """Embeds a user query string with RETRIEVAL_QUERY task type."""
        return self._embed(text, task_type="RETRIEVAL_QUERY")


class GeminiLLMClient:
    """Concrete LLM client using Gemini 2.5 Flash for synthesis."""

    def __init__(self, api_key: Optional[str] = None, env_path: Union[str, Path] = ".env"):
        resolved_key = api_key or load_env_api_key(env_path)
        self._client = genai.Client(api_key=resolved_key)

    def generate_synthesis(self, prompt: str, system_instruction: str) -> str:
        """Invokes gemini-2.5-flash with system instruction and context prompt."""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
        response = self._client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config,
        )
        return response.text or ""
