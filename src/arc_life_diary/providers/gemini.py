"""Gemini provider implementing BaseEmbeddingModel and BaseLLMClient.

API keys are read from environment variables or .env file via python-dotenv.
"""

import os
from pathlib import Path
from typing import List, Optional, Union
import dotenv
from google import genai
from google.genai import types


class ProviderAuthError(Exception):
    """Raised when provider credentials cannot be loaded from environment or .env."""
    pass


def load_env_api_key(env_path: Union[str, Path] = ".env") -> str:
    """Populates os.environ from .env (if present) and resolves GEMINI_API_KEY from environment."""
    dotenv.load_dotenv(dotenv_path=env_path, override=False)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not str(api_key).strip():
        raise ProviderAuthError(
            "GEMINI_API_KEY is not set in environment or .env file. "
            "Please export GEMINI_API_KEY or define it in your .env file."
        )
    return str(api_key).strip()


def default_http_options() -> types.HttpOptions:
    """Returns HttpOptions configured with automatic retries for rate limits and server errors."""
    return types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=5,
            http_status_codes=[408, 429, 500, 502, 503, 504],
            initial_delay=10.0,
            max_delay=60.0,
            exp_base=2.0,
            jitter=1.0,
        )
    )


def create_gemini_client(
    api_key: Optional[str] = None,
    env_path: Union[str, Path] = ".env",
    http_options: Optional[types.HttpOptions] = None,
) -> genai.Client:
    """Constructs a shared genai.Client.

    Populates os.environ with .env upfront (override=False) and relies on
    standard environment resolution or explicit api_key.
    """
    dotenv.load_dotenv(dotenv_path=env_path, override=False)
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not resolved_key or not str(resolved_key).strip():
        raise ProviderAuthError(
            "GEMINI_API_KEY is not set in environment or .env file. "
            "Please export GEMINI_API_KEY or define it in your .env file."
        )
    opts = http_options if http_options is not None else default_http_options()
    return genai.Client(api_key=resolved_key.strip(), http_options=opts)


class GeminiEmbeddingModel:
    """Concrete embedding model using Gemini gemini-embedding-001 (768 dimensions)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        env_path: Union[str, Path] = ".env",
        http_options: Optional[types.HttpOptions] = None,
        client: Optional[genai.Client] = None,
    ):
        self._dimensions = 768
        self._model_name = "gemini-embedding-001"
        if client is not None:
            self._client = client
        else:
            self._client = create_gemini_client(
                api_key=api_key,
                env_path=env_path,
                http_options=http_options,
            )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _embed(self, text: str, task_type: str) -> List[float]:
        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self._dimensions,
        )
        response = self._client.models.embed_content(
            model=self._model_name,
            contents=text,
            config=config,
        )
        return list(response.embeddings[0].values)

    def embed_document(self, text: str) -> List[float]:
        """Embeds a single document for ingestion with RETRIEVAL_DOCUMENT task type."""
        return self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_documents(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Embeds multiple documents in batches for efficient ingestion."""
        if not texts:
            return []

        results: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            config = types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self._dimensions,
            )
            response = self._client.models.embed_content(
                model=self._model_name,
                contents=chunk,
                config=config,
            )
            for emb in response.embeddings:
                results.append(list(emb.values))

        return results

    def embed_query(self, text: str) -> List[float]:
        """Embeds a user query string with RETRIEVAL_QUERY task type."""
        return self._embed(text, task_type="RETRIEVAL_QUERY")


class GeminiLLMClient:
    """Concrete LLM client using Gemini 3.5 Flash-Lite for synthesis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        env_path: Union[str, Path] = ".env",
        model_name: str = "gemini-3.5-flash-lite",
        http_options: Optional[types.HttpOptions] = None,
        client: Optional[genai.Client] = None,
    ):
        self._model_name = model_name
        if client is not None:
            self._client = client
        else:
            self._client = create_gemini_client(
                api_key=api_key,
                env_path=env_path,
                http_options=http_options,
            )

    def generate_synthesis(self, prompt: str, system_instruction: str) -> str:
        """Invokes gemini-3.5-flash-lite with system instruction and context prompt."""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""
