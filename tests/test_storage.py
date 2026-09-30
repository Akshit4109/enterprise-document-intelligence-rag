import pytest
import os
from pathlib import Path
from app.services.storage.local import LocalStorageService


@pytest.fixture
def temp_storage(tmp_path: Path) -> LocalStorageService:
    return LocalStorageService(root_dir=str(tmp_path / "storage"))


class TestLocalStorageService:
    def test_save_and_get_file(self, temp_storage: LocalStorageService):
        content = b"Sample Document Data for Storage Test"
        filename = "test_doc.txt"

        storage_path = temp_storage.save(content, filename, subpath="user_1/txt")

        assert storage_path is not None
        assert os.path.isabs(storage_path)
        assert temp_storage.exists(storage_path) is True

        retrieved_content = temp_storage.get(storage_path)
        assert retrieved_content == content

    def test_delete_file(self, temp_storage: LocalStorageService):
        content = b"Data to be deleted"
        storage_path = temp_storage.save(content, "delete_me.txt")

        assert temp_storage.exists(storage_path) is True
        assert temp_storage.delete(storage_path) is True
        assert temp_storage.exists(storage_path) is False

    def test_get_nonexistent_file(self, temp_storage: LocalStorageService):
        fake_path = str(temp_storage.root_dir / "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            temp_storage.get(fake_path)

    def test_path_traversal_prevention(self, temp_storage: LocalStorageService):
        with pytest.raises(ValueError, match="Path traversal"):
            temp_storage.get("/etc/passwd")
