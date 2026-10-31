"""Abstract provider interfaces for embeddings and LLM synthesis.

Zero external vendor SDKs should be imported in this module.
"""

from typing import List, Protocol, runtime_checkable


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
