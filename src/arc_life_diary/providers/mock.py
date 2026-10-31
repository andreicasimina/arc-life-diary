"""Mock provider for unit tests and deterministic offline operations."""

import hashlib
import math
from typing import List


class MockEmbeddingModel:
    """Deterministic mock embedding model without external network dependencies."""

    def __init__(self, dimensions: int = 4):
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _generate_vector(self, text: str) -> List[float]:
        # Generate deterministic vector based on MD5 digest of input text
        digest = hashlib.md5(text.encode("utf-8")).digest()
        vec = []
        for i in range(self._dimensions):
            byte_val = digest[i % len(digest)]
            vec.append(float(byte_val) / 255.0)

        # Normalize to unit vector for cosine distance
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_document(self, text: str) -> List[float]:
        return self._generate_vector(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._generate_vector(text)


class MockLLMClient:
    """Deterministic mock LLM client for testing synthesis output."""

    def __init__(self, custom_response: str = ""):
        self.custom_response = custom_response
        self.last_prompt = ""
        self.last_system_instruction = ""

    def generate_synthesis(self, prompt: str, system_instruction: str) -> str:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction

        if self.custom_response:
            return self.custom_response

        return (
            "Over time, an evident maturation in coping strategies emerges. "
            "Past recollections show high initial stress that transitioned into proactive emotional regulation.\n\n"
            "## Relevant Entries\n"
            "- Date: 2021-04-15 | Title: High Stress | Distance: 0.15\n"
            "- Date: 2024-02-10 | Title: Retrospective Peace | Distance: 0.28"
        )
