import io
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import SensitiveDataRedactor, log_duration, logger
from app.main import app
from app.services.ingestion import DocumentIngestionService


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestHealthChecks:
    def test_basic_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "uptime_seconds" in data
        assert data["version"] == "1.0.0"

    def test_database_health_check(self, client: TestClient):
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "postgresql"
        assert data["pgvector_installed"] is True
        assert data["latency_ms"] >= 0.0
        assert "pool" in data


class TestAsyncIngestionPipeline:
    def test_async_upload_and_status_polling(self, client: TestClient):
        file_content = io.BytesIO(b"Async Document Processing Test: Background chunking and vector indexing.")
        response = client.post(
            "/api/v1/documents/upload/async",
            files={"file": ("async_doc.txt", file_content, "text/plain")},
            data={"name": "Async Document Test", "owner_id": "usr_async"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        doc_id = data["document_id"]
        version_id = data["version_id"]
        poll_url = data["poll_url"]
        assert poll_url == f"/api/v1/documents/{doc_id}/versions/{version_id}/status"

        # Poll status endpoint
        status_res = client.get(poll_url)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["document_id"] == doc_id
        assert status_data["version_id"] == version_id
        assert status_data["status"] in ("processing", "ready")


class TestStructuredLoggingAndSecurity:
    def test_sensitive_data_redaction(self):
        redactor = SensitiveDataRedactor()

        # Test OpenAI API key masking
        raw_key = "Using OpenAI key sk-1234567890abcdefghijklmnopqrstuvwxyz for generation"
        redacted_key = redactor.redact(raw_key)
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in redacted_key
        assert "[REDACTED_API_KEY]" in redacted_key

        # Test Gemini API key masking
        raw_gemini = "Gemini key: AIzaSyD1234567890abcdefghijklmnopqrstuv"
        redacted_gemini = redactor.redact(raw_gemini)
        assert "AIzaSyD1234567890abcdefghijklmnopqrstuv" not in redacted_gemini
        assert "[REDACTED_GEMINI_KEY]" in redacted_gemini

        # Test password masking
        raw_pwd = 'Config: {"user": "admin", "password": "supersecretpassword123"}'
        redacted_pwd = redactor.redact(raw_pwd)
        assert "supersecretpassword123" not in redacted_pwd
        assert "[REDACTED_PASSWORD]" in redacted_pwd

        # Test bearer token masking
        raw_token = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
        redacted_token = redactor.redact(raw_token)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted_token
        assert "Bearer [REDACTED_TOKEN]" in redacted_token

    def test_log_duration_context_manager(self):
        extra = {"doc_id": "test-123"}
        with log_duration("Unit Test Duration", extra) as ctx:
            time.sleep(0.01)
        assert "duration_ms" in ctx
        assert ctx["duration_ms"] > 0


class TestCentralizedErrorHandling:
    def test_empty_file_error_response(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "EmptyFileException"
        assert "message" in data

    def test_not_found_error_response(self, client: TestClient):
        random_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/documents/{random_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "DocumentNotFoundException"
        assert "details" in data

    def test_validation_error_response(self, client: TestClient):
        # Invalid search request missing required query field
        response = client.post("/api/v1/search", json={})
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "ValidationError"
        assert "details" in data
        assert "errors" in data["details"]
