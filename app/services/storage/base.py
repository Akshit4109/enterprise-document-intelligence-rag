from abc import ABC, abstractmethod
from typing import Optional


class BaseStorageService(ABC):
    """
    Abstract Storage Interface for enterprise document artifact management.
    Enables pluggable backend replacements (Local Filesystem, AWS S3, Azure Blob, GCP).
    """

    @abstractmethod
    def save(self, file_bytes: bytes, filename: str, subpath: Optional[str] = None) -> str:
        """
        Persists file bytes into storage and returns the unique storage path/URI.
        """
        pass

    @abstractmethod
    def get(self, storage_path: str) -> bytes:
        """
        Retrieves raw file bytes from storage.
        """
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        """
        Deletes the file at storage_path. Returns True if deleted, False otherwise.
        """
        pass

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """
        Checks whether the file exists at storage_path.
        """
        pass
