import math
import uuid
import pytest
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings.mock import MockEmbeddingProvider
from app.llm.mock import MockLLMProvider
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.chunk import Chunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranking.cross_encoder import MockReranker
from app.services.rag import RAGService


EVALUATION_DATASET: List[Dict[str, str]] = [
    {
        "query": "Who is Harry?",
        "target_key": "target_harry",
        "category": "entity_definition",
    },
    {
        "query": "Who is Ron?",
        "target_key": "target_ron",
        "category": "entity_definition",
    },
    {
        "query": "Who is Hermione?",
        "target_key": "target_hermione",
        "category": "entity_definition",
    },
    {
        "query": "Who is Voldemort?",
        "target_key": "target_voldemort",
        "category": "entity_definition",
    },
    {
        "query": "What is Hogwarts?",
        "target_key": "target_hogwarts",
        "category": "entity_definition",
    },
    {
        "query": "Where does Harry live before Hogwarts?",
        "target_key": "target_privet_drive",
        "category": "fact_lookup",
    },
    {
        "query": "Who are Harry's parents?",
        "target_key": "target_parents",
        "category": "fact_lookup",
    },
    {
        "query": "Why is Harry famous?",
        "target_key": "target_famous",
        "category": "fact_lookup",
    },
    {
        "query": "Who are Harry's closest friends?",
        "target_key": "target_friends",
        "category": "fact_lookup",
    },
    {
        "query": "What happens when Harry first arrives at Hogwarts?",
        "target_key": "target_arrival",
        "category": "event_lookup",
    },
]

# Synthetic, non-copyrighted factual test passages for deterministic evaluation
CORPUS_PASSAGES: Dict[str, str] = {
    "target_harry": "Harry Potter is a young wizard and the central protagonist of the story who discovered his magical heritage and attends Hogwarts.",
    "target_ron": "Ron Weasley is Harry Potter's loyal red-haired best friend and fellow Gryffindor student from an ancient wizarding family.",
    "target_hermione": "Hermione Granger is a brilliant muggle-born witch, avid reader, and top student who becomes Harry's closest confidante.",
    "target_voldemort": "Lord Voldemort is the feared dark wizard antagonist who sought supreme power and orphaned Harry.",
    "target_hogwarts": "Hogwarts School of Witchcraft and Wizardry is the premier British magical academy where young witches and wizards study.",
    "target_privet_drive": "Harry lived under the stairs with the Dursley family at number four Privet Drive before receiving his Hogwarts letter.",
    "target_parents": "James and Lily Potter were Harry's loving parents who gave their lives to shield him from the dark lord.",
    "target_famous": "Harry is widely famous across the wizarding world as The Boy Who Lived because he miraculously survived the killing curse.",
    "target_friends": "Ron Weasley and Hermione Granger are Harry Potter's closest friends, sharing every adventure and trial.",
    "target_arrival": "Upon arrival at Hogwarts castle, first-year students cross the Black Lake in boats and undergo the Sorting Hat ceremony in the Great Hall.",
    # Distractor passages
    "distractor_1": "Harry was holding on for dear life as the broomstick rattled in the heavy wind.",
    "distractor_2": "Harry, what are we doing here? Keep quiet and don't make a sound in the corridor.",
    "distractor_3": "Ron sneezed loudly and dropped his quill onto the stone floor of the classroom.",
    "distractor_4": "Hermione closed her heavy spellbook with a sharp snap and sighed deeply.",
    "distractor_5": "They were on the train station platform waiting for the steam engine to depart.",
    "distractor_6": "The owls flew over the high dining tables during morning breakfast.",
}


@pytest.fixture
def eval_corpus(db_session: Session):
    owner = "eval_runner"
    doc = Document(
        name="Magical Chronicles & Character Reference",
        document_type="txt",
        owner_id=owner,
        department="General",
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_name="characters.txt",
        file_size=4096,
        storage_path="/tmp/chars.txt",
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(ver)
    db_session.flush()

    doc.active_version_id = ver.id
    db_session.flush()

    embedder = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    key_to_chunk_id: Dict[str, uuid.UUID] = {}

    idx = 0
    for key, text in CORPUS_PASSAGES.items():
        vector = embedder.embed_text(text)
        chunk = Chunk(
            document_version_id=ver.id,
            chunk_index=idx,
            content=text,
            page_number=(idx // 3) + 1,
            embedding=vector,
            embedding_model="mock-embedding-v1",
            chunk_metadata={"passage_key": key},
        )
        db_session.add(chunk)
        db_session.flush()
        key_to_chunk_id[key] = chunk.id
        idx += 1

    db_session.commit()
    return doc, ver, key_to_chunk_id


def test_retrieval_ablation_comparison(db_session: Session, eval_corpus):
    doc, ver, key_map = eval_corpus

    embedder = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    dense_retriever = VectorRetriever(db=db_session, embedding_provider=embedder)
    hybrid_retriever = HybridRetriever(
        db=db_session,
        embedding_provider=embedder,
        reranker=None,
        reranker_enabled=False,
    )
    reranked_retriever = HybridRetriever(
        db=db_session,
        embedding_provider=embedder,
        reranker=MockReranker(),
        reranker_enabled=True,
    )

    modes = {
        "Dense Only": dense_retriever,
        "Hybrid (Dense + FTS)": hybrid_retriever,
        "Hybrid + Reranker": reranked_retriever,
    }

    llm = MockLLMProvider()
    results_summary = {}

    for mode_name, retriever in modes.items():
        rag_service = RAGService(retriever=retriever, llm_provider=llm)

        total_recall = 0.0
        total_precision = 0.0
        total_mrr = 0.0
        total_ndcg = 0.0
        total_grounded = 0
        total_citations = 0
        valid_citations = 0

        k = 5
        for item in EVALUATION_DATASET:
            query = item["query"]
            target_key = item["target_key"]

            # RAG synthesis check
            rag_res = rag_service.query(question=query, top_k=k, similarity_threshold=0.01)
            if rag_res.is_grounded:
                total_grounded += 1

            for cit in rag_res.sources:
                total_citations += 1
                if cit.document_id == doc.id and cit.snippet != "":
                    valid_citations += 1

            # Retrieval ranking check
            res = retriever.retrieve(query=query, top_k=k)
            found_rank = None
            for r, ch in enumerate(res.results, start=1):
                if ch.metadata.get("passage_key") == target_key:
                    found_rank = r
                    break

            rec = 1.0 if found_rank is not None else 0.0
            prec = (1.0 / k) if found_rank is not None else 0.0
            mrr = (1.0 / found_rank) if found_rank is not None else 0.0
            ndcg = (1.0 / math.log2(found_rank + 1)) if found_rank is not None else 0.0

            total_recall += rec
            total_precision += prec
            total_mrr += mrr
            total_ndcg += ndcg

        num_queries = len(EVALUATION_DATASET)
        avg_recall = round(total_recall / num_queries, 4)
        avg_precision = round(total_precision / num_queries, 4)
        avg_mrr = round(total_mrr / num_queries, 4)
        avg_ndcg = round(total_ndcg / num_queries, 4)
        grounded_rate = round((total_grounded / num_queries) * 100, 2)
        citation_acc = round((valid_citations / total_citations * 100) if total_citations > 0 else 100.0, 2)

        results_summary[mode_name] = {
            "Recall@5": avg_recall,
            "Precision@5": avg_precision,
            "MRR": avg_mrr,
            "NDCG@5": avg_ndcg,
            "GroundedRate": grounded_rate,
            "CitationAccuracy": citation_acc,
        }

    # Verify metrics for each mode
    assert results_summary["Hybrid (Dense + FTS)"]["Recall@5"] >= 0.8
    assert results_summary["Hybrid + Reranker"]["Recall@5"] >= 0.8
    assert results_summary["Hybrid + Reranker"]["MRR"] >= 0.6
    assert results_summary["Hybrid + Reranker"]["GroundedRate"] == 100.0
    assert results_summary["Hybrid + Reranker"]["CitationAccuracy"] == 100.0
