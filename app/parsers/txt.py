import re
from typing import Any, Dict, List
from app.core.exceptions import CorruptedFileException, ParserException
from app.parsers.base import BaseDocumentParser, ParsedDocument, ParsedPage


class TXTParser(BaseDocumentParser):
    """
    Parser for plain text files (.txt).
    Supports multi-encoding fallback detection (utf-8, latin-1, cp1252).
    """

    ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        text = None
        used_encoding = None

        for encoding in self.ENCODINGS:
            try:
                text = file_bytes.decode(encoding)
                used_encoding = encoding
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if text is None:
            raise CorruptedFileException(
                message=f"Failed to decode TXT file '{filename}' using supported encodings.",
                details={"filename": filename, "attempted_encodings": self.ENCODINGS}
            )

        try:
            full_text = self._clean_text(text)
            words = full_text.split()
            word_count = len(words)
            char_count = len(full_text)

            pages = [
                ParsedPage(
                    page_number=1,
                    text=full_text,
                    metadata={"encoding": used_encoding, "line_count": len(full_text.splitlines())}
                )
            ]

            metadata: Dict[str, Any] = {
                "format": "TXT",
                "encoding": used_encoding,
            }

            return ParsedDocument(
                text=full_text,
                pages=pages,
                total_pages=1,
                word_count=word_count,
                character_count=char_count,
                metadata=metadata,
            )
        except Exception as e:
            raise ParserException(
                message=f"Error parsing TXT '{filename}': {str(e)}",
                details={"filename": filename, "original_error": str(e)}
            )

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
