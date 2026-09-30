import hashlib
import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import Tuple
from app.core.config import settings
from app.core.exceptions import (
    EmptyFileException,
    FileTooLargeException,
    UnsupportedFileFormatException,
    CorruptedFileException,
)


class FileValidator:
    """
    Validates uploaded document files against extension whitelist, size constraints,
    empty content, binary magic-byte signatures, and unsafe filenames.
    """

    MAGIC_SIGNATURES = {
        "pdf": b"%PDF-",
        "docx": b"PK\x03\x04",  # Standard ZIP signature used by OpenXML docx
    }

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitizes input filenames: removes path traversal tokens, null bytes,
        control characters, and illegal filesystem characters.
        """
        if not filename:
            return f"document_{uuid.uuid4().hex[:8]}.txt"
        # 1. Strip path components (handles ../, /etc/passwd, C:\windows, etc.)
        base = Path(filename).name
        # 2. Strip null bytes and non-printable control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', base)
        # 3. Strip hazardous shell and file path characters
        cleaned = re.sub(r'[\\/:*?"<>|]', '_', cleaned)
        # 4. Strip leading/trailing dots and spaces
        cleaned = cleaned.strip(". ")
        if not cleaned:
            cleaned = f"document_{uuid.uuid4().hex[:8]}"
        return cleaned

    @classmethod
    def validate(cls, file_bytes: bytes, filename: str) -> Tuple[str, str]:
        """
        Validates the file bytes and filename.
        Returns a tuple of (detected_extension, sha256_checksum).
        """
        # 1. Empty check
        if not file_bytes or len(file_bytes) == 0:
            raise EmptyFileException(
                message=f"Uploaded file '{filename}' is empty (0 bytes).",
                details={"filename": filename}
            )

        # 2. File size limit
        file_size = len(file_bytes)
        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise FileTooLargeException(
                message=f"File '{filename}' ({actual_mb:.2f}MB) exceeds maximum allowed size of {max_mb:.2f}MB.",
                details={"file_size": file_size, "max_size": settings.MAX_UPLOAD_SIZE_BYTES}
            )

        # 3. Extension check
        clean_name = cls.sanitize_filename(filename)
        ext = Path(clean_name).suffix.lower().lstrip(".")
        if not ext or ext not in settings.ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatException(
                message=f"File extension '.{ext}' is not supported. Allowed formats: {list(settings.ALLOWED_EXTENSIONS)}",
                details={"extension": ext, "allowed_extensions": list(settings.ALLOWED_EXTENSIONS)}
            )

        # 4. Deep magic byte / signature check (do not trust only file extension)
        cls._verify_content_signature(file_bytes, ext, filename)

        # 5. Compute SHA-256 Checksum
        checksum = hashlib.sha256(file_bytes).hexdigest()

        return ext, checksum

    @classmethod
    def _verify_content_signature(cls, file_bytes: bytes, ext: str, filename: str) -> None:
        if ext == "pdf":
            # PDF header starts with %PDF- within the first 1024 bytes
            if b"%PDF-" not in file_bytes[:1024]:
                raise UnsupportedFileFormatException(
                    message=f"File '{filename}' has a .pdf extension but is not a valid PDF document (missing PDF magic header).",
                    details={"filename": filename, "extension": ext}
                )

        elif ext == "docx":
            # DOCX must start with PK ZIP header and contain [Content_Types].xml
            if not file_bytes.startswith(b"PK\x03\x04"):
                raise UnsupportedFileFormatException(
                    message=f"File '{filename}' has a .docx extension but is not a valid OpenXML document (invalid ZIP header).",
                    details={"filename": filename, "extension": ext}
                )
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    namelist = zf.namelist()
                    if "[Content_Types].xml" not in namelist:
                        raise UnsupportedFileFormatException(
                            message=f"File '{filename}' is a ZIP archive but not a valid DOCX document.",
                            details={"filename": filename}
                        )
            except zipfile.BadZipFile:
                raise CorruptedFileException(
                    message=f"DOCX file '{filename}' contains a corrupted archive structure.",
                    details={"filename": filename}
                )

        elif ext == "txt":
            # Plain text should not contain binary NUL bytes
            if b"\x00" in file_bytes[:1024]:
                raise UnsupportedFileFormatException(
                    message=f"File '{filename}' has a .txt extension but contains binary data.",
                    details={"filename": filename}
                )
