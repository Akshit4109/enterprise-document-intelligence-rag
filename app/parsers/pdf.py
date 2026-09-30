import re
from typing import Any, Dict, List
import fitz  # PyMuPDF
from app.core.exceptions import CorruptedFileException, ParserException
from app.parsers.base import BaseDocumentParser, ParsedDocument, ParsedPage


class PDFParser(BaseDocumentParser):
    """
    Production-grade PDF Parser using PyMuPDF (fitz).
    Preserves exact page boundaries, cleans text whitespace, and extracts PDF metadata.
    """

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise CorruptedFileException(
                message=f"Failed to open PDF document '{filename}'. File may be corrupt or encrypted.",
                details={"original_error": str(e), "filename": filename}
            )

        try:
            pages: List[ParsedPage] = []
            full_text_parts: List[str] = []
            total_pages = doc.page_count

            if total_pages == 0:
                raise CorruptedFileException(
                    message=f"PDF document '{filename}' contains 0 pages.",
                    details={"filename": filename}
                )

            for page_idx in range(total_pages):
                page = doc.load_page(page_idx)
                page_text = page.get_text("text")

                # Normalize extra spaces and empty lines
                cleaned_text = self._clean_text(page_text)
                full_text_parts.append(cleaned_text)

                pages.append(
                    ParsedPage(
                        page_number=page_idx + 1,
                        text=cleaned_text,
                        metadata={
                            "page_width": page.rect.width,
                            "page_height": page.rect.height,
                            "rotation": page.rotation,
                        }
                    )
                )

            full_text = "\n\n".join(part for part in full_text_parts if part).strip()

            doc_metadata: Dict[str, Any] = {
                "title": doc.metadata.get("title") or "",
                "author": doc.metadata.get("author") or "",
                "subject": doc.metadata.get("subject") or "",
                "creator": doc.metadata.get("creator") or "",
                "producer": doc.metadata.get("producer") or "",
                "format": "PDF",
                "page_count": total_pages,
            }

            words = full_text.split()
            word_count = len(words)
            char_count = len(full_text)

            return ParsedDocument(
                text=full_text,
                pages=pages,
                total_pages=total_pages,
                word_count=word_count,
                character_count=char_count,
                metadata=doc_metadata,
            )
        except CorruptedFileException:
            raise
        except Exception as e:
            raise ParserException(
                message=f"Error parsing PDF '{filename}': {str(e)}",
                details={"filename": filename, "original_error": str(e)}
            )
        finally:
            doc.close()

    @staticmethod
    def _clean_text(text: str) -> str:
        # Standardize line breaks and trim extraneous whitespace
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
