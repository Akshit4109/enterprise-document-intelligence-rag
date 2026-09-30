from typing import Dict, Type
from pathlib import Path
from app.core.exceptions import UnsupportedFileFormatException
from app.parsers.base import BaseDocumentParser
from app.parsers.pdf import PDFParser
from app.parsers.docx import DOCXParser
from app.parsers.txt import TXTParser


class DocumentParserFactory:
    """
    Factory registry for document parsers.
    Instantiates and returns the appropriate BaseDocumentParser based on file extension or document type.
    """

    _parsers: Dict[str, BaseDocumentParser] = {}

    @classmethod
    def register_parser(cls, extension: str, parser_instance: BaseDocumentParser) -> None:
        """Register a parser instance for a specific file extension."""
        cls._parsers[extension.lower().lstrip(".")] = parser_instance

    @classmethod
    def get_parser(cls, filename_or_type: str) -> BaseDocumentParser:
        """
        Resolves parser instance based on file extension or format name.
        """
        # Ensure default parsers are registered
        if not cls._parsers:
            cls._register_defaults()

        ext = Path(filename_or_type).suffix.lower().lstrip(".")
        if not ext:
            ext = filename_or_type.lower().strip()

        parser = cls._parsers.get(ext)
        if not parser:
            raise UnsupportedFileFormatException(
                message=f"No parser available for document format/extension '.{ext}'. Supported formats: {list(cls._parsers.keys())}",
                details={"extension": ext, "supported_formats": list(cls._parsers.keys())}
            )

        return parser

    @classmethod
    def _register_defaults(cls) -> None:
        cls._parsers["pdf"] = PDFParser()
        cls._parsers["docx"] = DOCXParser()
        cls._parsers["txt"] = TXTParser()


# Initialize default registrations
DocumentParserFactory._register_defaults()
