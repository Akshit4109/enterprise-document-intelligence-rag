import os
import uuid
from typing import Optional
from pathlib import Path
from app.core.config import settings
from app.services.storage.base import BaseStorageService
from app.services.validator import FileValidator


class LocalStorageService(BaseStorageService):
    """
    Local filesystem implementation of BaseStorageService.
    Stores files securely under the configured root directory with path traversal protection
    and strict filename sanitization.
    """

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = Path(root_dir or settings.STORAGE_LOCAL_ROOT).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_path(self, storage_path: str) -> Path:
        """
        Validates and resolves a path, preventing directory traversal.
        """
        target = Path(storage_path).resolve()
        if not str(target).startswith(str(self.root_dir)):
            raise ValueError(f"Path traversal detected or path outside root directory: {storage_path}")
        return target

    def save(self, file_bytes: bytes, filename: str, subpath: Optional[str] = None) -> str:
        """
        Saves raw bytes into local directory with a unique UUID prefix and sanitized filename.
        Returns the absolute local file path string.
        """
        target_dir = self.root_dir
        if subpath:
            # Sanitize subpath components against traversal
            sanitized_parts = [FileValidator.sanitize_filename(p) for p in subpath.split("/") if p.strip()]
            target_dir = (self.root_dir / Path(*sanitized_parts)).resolve()
            if not str(target_dir).startswith(str(self.root_dir)):
                raise ValueError(f"Path traversal detected in subpath: {subpath}")
            target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = FileValidator.sanitize_filename(filename)
        unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
        file_path = target_dir / unique_filename

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return str(file_path)

    def get(self, storage_path: str) -> bytes:
        target = self._sanitize_path(storage_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found at storage path: {storage_path}")
        with open(target, "rb") as f:
            return f.read()

    def delete(self, storage_path: str) -> bool:
        try:
            target = self._sanitize_path(storage_path)
            if target.is_file():
                target.unlink()
                return True
            return False
        except Exception:
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            target = self._sanitize_path(storage_path)
            return target.is_file()
        except Exception:
            return False
