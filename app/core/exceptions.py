from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for all domain and application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DocumentIngestionException(AppException):
    """Base exception for document ingestion errors."""
    pass


class UnsupportedFileFormatException(DocumentIngestionException):
    def __init__(self, message: str = "Unsupported file format", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=415, details=details)


class CorruptedFileException(DocumentIngestionException):
    def __init__(self, message: str = "The uploaded file is corrupted or unreadable", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=422, details=details)


class FileTooLargeException(DocumentIngestionException):
    def __init__(self, message: str = "The uploaded file exceeds the maximum allowed size", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=413, details=details)


class EmptyFileException(DocumentIngestionException):
    def __init__(self, message: str = "The uploaded file is empty", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=400, details=details)


class ParserException(DocumentIngestionException):
    def __init__(self, message: str = "Failed to parse document contents", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=422, details=details)


class DocumentNotFoundException(AppException):
    def __init__(self, message: str = "Document not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=404, details=details)
