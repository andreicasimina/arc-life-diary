"""Provider resolution and factory functions for AI and backup storage backends."""

import os
from pathlib import Path
from typing import Optional, Tuple, Union

from arc_life_diary.exceptions import UnknownProviderError
from arc_life_diary.interfaces import (
    BaseBackupStorage,
    BaseEmbeddingModel,
    BaseLLMClient,
)


def get_ai_providers(
    provider_name: Optional[str] = None,
    env_path: Union[str, Path] = ".env",
) -> Tuple[BaseEmbeddingModel, BaseLLMClient]:
    """Resolves and instantiates the configured AI embedding and LLM providers."""
    name = (provider_name or os.environ.get("DIARY_AI_PROVIDER", "gemini")).strip().lower()
    if name == "gemini":
        from arc_life_diary.providers.gemini import (
            GeminiEmbeddingModel,
            GeminiLLMClient,
            create_gemini_client,
        )

        client = create_gemini_client(env_path=env_path)
        return GeminiEmbeddingModel(client=client), GeminiLLMClient(client=client)
    elif name == "mock":
        from arc_life_diary.providers.mock import MockEmbeddingModel, MockLLMClient

        return MockEmbeddingModel(dimensions=768), MockLLMClient()

    raise UnknownProviderError(f"Unknown AI provider: {name}")


def get_backup_storage(
    storage_name: Optional[str] = None,
    env_path: Union[str, Path] = ".env",
) -> BaseBackupStorage:
    """Resolves and instantiates the configured backup storage provider."""
    name = (storage_name or os.environ.get("DIARY_STORAGE_PROVIDER", "gdrive")).strip().lower()
    if name == "gdrive":
        from arc_life_diary.providers.gdrive import GoogleDriveStorage

        return GoogleDriveStorage(env_path=env_path)

    raise UnknownProviderError(f"Unknown storage provider: {name}")
