"""Abstract provider interfaces for embeddings, LLM synthesis, and backup storage.

Zero external vendor SDKs should be imported in this module.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Protocol, runtime_checkable


@dataclass
class RemoteBackupMetadata:
    """Metadata representing an archive stored in a remote destination."""

    file_id: str
    name: str
    created_at: datetime
    size_bytes: int


@runtime_checkable
class BaseBackupStorage(Protocol):
    """Abstract interface for remote/offsite backup storage targets."""

    def upload(self, local_path: Path, remote_filename: str) -> RemoteBackupMetadata:
        """Uploads an encrypted archive to the remote storage destination."""
        ...

    def list_backups(self) -> List[RemoteBackupMetadata]:
        """Lists available backup archives on remote storage, sorted newest first."""
        ...

    def download(self, file_id: str, destination_path: Path) -> Path:
        """Downloads a remote backup archive by ID to a local destination path."""
        ...


@runtime_checkable
class BaseEmbeddingModel(Protocol):
    """Abstract interface for dense vector embedding generators."""

    @property
    def dimensions(self) -> int:
        """Vector dimensionality expected by SQLite table (e.g. 768)."""
        ...

    def embed_document(self, text: str) -> List[float]:
        """Embeds a single document for ingestion."""
        ...

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds multiple documents in batches for efficient ingestion."""
        ...

    def embed_query(self, text: str) -> List[float]:
        """Embeds a user query string for vector search."""
        ...


@runtime_checkable
class BaseLLMClient(Protocol):
    """Abstract interface for text synthesis and introspection models."""

    def generate_synthesis(self, prompt: str, system_instruction: str) -> str:
        """Takes context and user question and returns formatted textual analysis."""
        ...
