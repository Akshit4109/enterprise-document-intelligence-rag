import uuid
from typing import Any, Dict, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chunking.base import BaseChunker, RawChunk
from app.parsers.base import ParsedDocument


class LangChainRecursiveChunker(BaseChunker):
    """
    Adapter strategy that utilizes LangChain's RecursiveCharacterTextSplitter
    while strictly conforming to the enterprise platform's BaseChunker contract and metadata conventions.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.separators = separators or ["\n\n", "\n", " ", ""]
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
            keep_separator=True,
            strip_whitespace=True,
        )

    def chunk_text(self, text: str, page_number: Optional[int] = None) -> List[RawChunk]:
        """
        Splits a single block of text into RawChunks using LangChain's splitter.
        """
        if not text or not text.strip():
            return []

        split_texts = self.splitter.split_text(text)
        chunks: List[RawChunk] = []

        current_offset = 0
        for i, chunk_str in enumerate(split_texts):
            clean_str = chunk_str.strip()
            if not clean_str:
                continue

            # Estimate start & end character positions
            char_start = text.find(clean_str, current_offset)
            if char_start == -1:
                char_start = current_offset
            char_end = char_start + len(clean_str)
            current_offset = char_start + max(1, len(clean_str) - self.chunk_overlap)

            token_count = max(1, len(clean_str) // 4)

            chunks.append(
                RawChunk(
                    chunk_index=i,
                    content=clean_str,
                    page_number=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    token_count_estimate=token_count,
                    metadata={"splitter": "langchain_recursive", "page_number": page_number},
                )
            )

        return chunks

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_id: Optional[uuid.UUID] = None,
        version_id: Optional[uuid.UUID] = None,
        filename: Optional[str] = None,
    ) -> List[RawChunk]:
        """
        Processes a parsed document page-by-page, creating sequentially indexed RawChunks
        enriched with complete source attribution metadata.
        """
        all_chunks: List[RawChunk] = []
        global_index = 0

        for page in parsed_doc.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            page_chunks = self.chunk_text(text=page_text, page_number=page.page_number)
            for pc in page_chunks:
                meta = {
                    "document_id": str(document_id) if document_id else None,
                    "document_version_id": str(version_id) if version_id else None,
                    "source_filename": filename,
                    "page_number": page.page_number,
                    "page_metadata": page.metadata,
                    "format": parsed_doc.metadata.get("format", "UNKNOWN"),
                    "splitter": "langchain_recursive",
                }
                pc.chunk_index = global_index
                pc.metadata = meta
                all_chunks.append(pc)
                global_index += 1

        # Fallback if document has empty pages but non-empty aggregated text
        if not all_chunks and parsed_doc.text and parsed_doc.text.strip():
            doc_chunks = self.chunk_text(text=parsed_doc.text, page_number=1)
            for pc in doc_chunks:
                meta = {
                    "document_id": str(document_id) if document_id else None,
                    "document_version_id": str(version_id) if version_id else None,
                    "source_filename": filename,
                    "page_number": 1,
                    "format": parsed_doc.metadata.get("format", "UNKNOWN"),
                    "splitter": "langchain_recursive",
                }
                pc.chunk_index = global_index
                pc.metadata = meta
                all_chunks.append(pc)
                global_index += 1

        return all_chunks
