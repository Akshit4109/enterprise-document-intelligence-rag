from typing import Dict, List, Optional, Tuple
from app.rag.citation import CitationSource
from app.retrieval.base import RetrievedChunk


class GroundedPromptBuilder:
    """
    Constructs anti-hallucination, citation-enforcing prompts for LLM generation with multi-turn chat context support.
    """

    SYSTEM_INSTRUCTIONS = (
        "You are an accurate, enterprise document intelligence assistant. "
        "Your task is to answer the user's question directly, concisely, and naturally based strictly on the provided context passages.\n\n"
        "MANDATORY RULES:\n"
        "1. Synthesize a direct, natural, and concise answer using ONLY the explicit facts stated in the context.\n"
        "2. Avoid verbose repetitive preambles such as 'According to the source documentation...'. State the facts directly.\n"
        "3. For every factual claim, cite the relevant source passage number in square brackets (e.g. [1], [2]).\n"
        "4. If the provided context does not contain sufficient facts to answer the question, state clearly: "
        "'Based on the provided documents, I could not find sufficient information to answer this question.'\n"
        "5. Do NOT extrapolate, speculate, or fabricate citations or facts.\n"
        "6. In multi-turn conversations, resolve pronouns/references from chat history while grounding answers in the context passages."
    )

    @classmethod
    def build_prompt(
        cls,
        question: str,
        retrieved_chunks: List[RetrievedChunk],
        citations: List[CitationSource],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, str]:
        """
        Builds (user_prompt, system_instructions) formatted with numbered context passages and recent conversation history.
        """
        context_blocks = []
        for i, (chunk, citation) in enumerate(zip(retrieved_chunks, citations), start=1):
            page_info = f", Page {chunk.page_number}" if chunk.page_number else ""
            header = f"[{i}] Document: '{chunk.document_name}' (Version {chunk.version_number}{page_info}, File: {chunk.source_filename})"
            block = f"{header}\nContent:\n{chunk.content.strip()}"
            context_blocks.append(block)

        context_text = "\n\n---\n\n".join(context_blocks)

        history_section = ""
        if chat_history:
            formatted_turns = []
            for turn in chat_history:
                role_label = "User" if turn.get("role") == "user" else "Assistant"
                formatted_turns.append(f"{role_label}: {turn.get('content', '').strip()}")
            history_section = "RECENT CONVERSATION HISTORY:\n" + "\n".join(formatted_turns) + "\n\n==============================\n"

        user_prompt = (
            f"CONTEXT PASSAGES:\n"
            f"{context_text}\n\n"
            f"==============================\n"
            f"{history_section}"
            f"CURRENT USER QUESTION: {question.strip()}\n\n"
            f"GROUNDED ANSWER (with citations [1], [2]):"
        )

        return user_prompt, cls.SYSTEM_INSTRUCTIONS
