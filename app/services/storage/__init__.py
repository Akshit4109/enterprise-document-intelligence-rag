from app.services.storage.base import BaseStorageService
from app.services.storage.local import LocalStorageService

# Default singleton instance for dependency injection
default_storage_service: BaseStorageService = LocalStorageService()


def get_storage_service() -> BaseStorageService:
    return default_storage_service


__all__ = ["BaseStorageService", "LocalStorageService", "get_storage_service", "default_storage_service"]
