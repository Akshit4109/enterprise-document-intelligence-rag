from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface for embedding generation providers.
    Decouples the core application from specific model vendors or libraries.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the fixed vector dimension size produced by this model."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the canonical model identifier string."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a normalized embedding vector for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generates normalized embedding vectors for a list of text strings in batches.
        """
        pass
