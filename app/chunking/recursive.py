import uuid
from typing import Any, Dict, List, Optional
from app.chunking.base import BaseChunker, RawChunk
from app.parsers.base import ParsedDocument


class RecursiveCharacterChunker(BaseChunker):
    """
    Production-grade Recursive Character Chunker.
    Splits text hierarchically using a priority list of semantic separators:
    1. Paragraphs ("\\n\\n")
    2. Lines ("\\n")
    3. Sentence terminators (". ", "? ", "! ")
    4. Clauses ("; ", ", ")
    5. Word boundaries (" ")
    6. Individual characters ("") as last resort.
    
    Preserves context by applying a sliding overlap window while preventing arbitrary word cuts.
    """

    DEFAULT_SEPARATORS: List[str] = [
        "\n\n",
        "\n",
        ". ",
        "? ",
        "! ",
        "; ",
        ", ",
        " ",
        "",
    ]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.separators = separators or self.DEFAULT_SEPARATORS

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_id: Optional[uuid.UUID] = None,
        version_id: Optional[uuid.UUID] = None,
        filename: Optional[str] = None,
    ) -> List[RawChunk]:
        """
        Processes all pages in ParsedDocument and yields sequential, globally-indexed RawChunks.
        """
        all_chunks: List[RawChunk] = []
        global_index = 0

        # If document has distinct page boundaries (e.g. PDF), chunk per page
        if parsed_doc.pages:
            for page in parsed_doc.pages:
                if not page.text.strip():
                    continue

                page_chunks = self._split_text_to_chunks(page.text)
                for chunk_text in page_chunks:
                    meta: Dict[str, Any] = {
                        "source_filename": filename or "",
                        "format": parsed_doc.metadata.get("format", ""),
                        "page_number": page.page_number,
                    }
                    if document_id:
                        meta["document_id"] = str(document_id)
                    if version_id:
                        meta["document_version_id"] = str(version_id)
                    if page.metadata:
                        meta["page_metadata"] = page.metadata

                    all_chunks.append(
                        RawChunk(
                            chunk_index=global_index,
                            content=chunk_text,
                            page_number=page.page_number,
                            char_start=0,
                            char_end=len(chunk_text),
                            token_count_estimate=max(1, len(chunk_text.split())),
                            metadata=meta,
                        )
                    )
                    global_index += 1
        else:
            # Flat text fallback
            if parsed_doc.text.strip():
                text_chunks = self._split_text_to_chunks(parsed_doc.text)
                for chunk_text in text_chunks:
                    meta = {
                        "source_filename": filename or "",
                        "format": parsed_doc.metadata.get("format", ""),
                        "page_number": None,
                    }
                    if document_id:
                        meta["document_id"] = str(document_id)
                    if version_id:
                        meta["document_version_id"] = str(version_id)

                    all_chunks.append(
                        RawChunk(
                            chunk_index=global_index,
                            content=chunk_text,
                            page_number=None,
                            char_start=0,
                            char_end=len(chunk_text),
                            token_count_estimate=max(1, len(chunk_text.split())),
                            metadata=meta,
                        )
                    )
                    global_index += 1

        return all_chunks

    def chunk_text(self, text: str, page_number: Optional[int] = None) -> List[RawChunk]:
        """
        Splits a single raw text string into RawChunks.
        """
        if not text or not text.strip():
            return []

        raw_strings = self._split_text_to_chunks(text)
        chunks: List[RawChunk] = []

        for idx, chunk_str in enumerate(raw_strings):
            chunks.append(
                RawChunk(
                    chunk_index=idx,
                    content=chunk_str,
                    page_number=page_number,
                    char_start=0,
                    char_end=len(chunk_str),
                    token_count_estimate=max(1, len(chunk_str.split())),
                    metadata={"page_number": page_number},
                )
            )
        return chunks

    def _split_text_to_chunks(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []

        # If text is already smaller than chunk_size, return directly
        if len(text) <= self.chunk_size:
            return [text]

        # Recursively split into pieces
        pieces = self._recursive_split(text, self.separators)

        # Merge pieces with overlap
        return self._merge_pieces_with_overlap(pieces)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if not text:
            return []

        # Find the first matching separator
        separator = ""
        new_separators: List[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        if separator:
            splits = text.split(separator)
        else:
            # Fallback to character split
            splits = list(text)

        final_pieces: List[str] = []
        for split in splits:
            if not split:
                continue
            # Reattach separator if non-empty
            piece = split + separator if separator else split
            if len(piece) <= self.chunk_size:
                final_pieces.append(piece)
            else:
                if new_separators:
                    sub_pieces = self._recursive_split(piece, new_separators)
                    final_pieces.extend(sub_pieces)
                else:
                    # Hard split if no more separators exist
                    for j in range(0, len(piece), self.chunk_size):
                        final_pieces.append(piece[j: j + self.chunk_size])

        return final_pieces

    def _merge_pieces_with_overlap(self, pieces: List[str]) -> List[str]:
        """
        Combines small pieces into chunks up to self.chunk_size with self.chunk_overlap.
        """
        chunks: List[str] = []
        current_chunk_pieces: List[str] = []
        current_length = 0

        for piece in pieces:
            piece_len = len(piece)
            if current_length + piece_len > self.chunk_size and current_chunk_pieces:
                # Flush current chunk
                combined_chunk = "".join(current_chunk_pieces).strip()
                if combined_chunk:
                    chunks.append(combined_chunk)

                # Keep overlap pieces from the tail of current_chunk_pieces
                overlap_pieces: List[str] = []
                overlap_len = 0
                for prev_piece in reversed(current_chunk_pieces):
                    if overlap_len + len(prev_piece) <= self.chunk_overlap:
                        overlap_pieces.insert(0, prev_piece)
                        overlap_len += len(prev_piece)
                    else:
                        break

                current_chunk_pieces = overlap_pieces
                current_length = overlap_len

            current_chunk_pieces.append(piece)
            current_length += piece_len

        if current_chunk_pieces:
            combined_chunk = "".join(current_chunk_pieces).strip()
            if combined_chunk:
                chunks.append(combined_chunk)

        return chunks
