import logging
import re
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional
from app.core.config import settings


class SensitiveDataRedactor(logging.Filter):
    """
    Log filter that intercepts log records and redacts sensitive data such as
    API keys, passwords, bearer tokens, and credentials before emission.
    """

    PATTERNS = [
        # OpenAI / generic API keys
        (re.compile(r"(sk-[a-zA-Z0-9_-]{20,})", re.IGNORECASE), "[REDACTED_API_KEY]"),
        # Google Gemini API keys
        (re.compile(r"(AIza[0-9A-Za-z-_]{35})", re.IGNORECASE), "[REDACTED_GEMINI_KEY]"),
        # Bearer tokens
        (re.compile(r"(Bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        # Passwords in URLs / JSON
        (re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r"\1[REDACTED_PASSWORD]\3"),
        # Database passwords in connection strings
        (re.compile(r"(://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1[REDACTED_DB_PASSWORD]\3"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        for pattern, replacement in cls.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_logging() -> logging.Logger:
    """
    Initializes structured logging with custom formatting and sensitive data redaction.
    """
    logger = logging.getLogger("enterprise_rag")
    logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataRedactor())
        logger.addHandler(handler)

    return logger


logger = setup_logging()


@contextmanager
def log_duration(action_name: str, extra: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to log the duration of an operational stage (parsing, chunking, embedding, retrieval, RAG).
    """
    start_time = time.perf_counter()
    ctx: Dict[str, Any] = extra or {}
    logger.info(f"START {action_name} | {ctx}")
    try:
        yield ctx
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(f"FAILED {action_name} after {elapsed_ms}ms | Error: {exc} | {ctx}")
        raise
    else:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        ctx["duration_ms"] = elapsed_ms
        logger.info(f"FINISHED {action_name} in {elapsed_ms}ms | {ctx}")
