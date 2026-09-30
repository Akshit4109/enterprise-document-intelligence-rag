"""
Phase 22 Retrieval Benchmark & Ablation Evaluation Script
Evaluates and reports:
- Recall@5
- Precision@5
- MRR (Mean Reciprocal Rank)
- NDCG@5
- Citation Accuracy
- Grounded Answer Rate
- End-to-end Latency

Across:
- Mode A: Dense Semantic Vector Retrieval (pgvector)
- Mode B: Hybrid Rank Fusion (Dense + PostgreSQL FTS TSVECTOR via RRF)
- Mode C: Hybrid + Neural Cross-Encoder Reranking
"""
import math
import os
import sys
import time
import uuid
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.embeddings.mock import MockEmbeddingProvider
from app.llm.mock import MockLLMProvider
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.chunk import Chunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranking.cross_encoder import MockReranker
from app.services.rag import RAGService


BENCHMARK_QUERIES = [
    {"query": "Who is Harry?", "target_key": "target_harry", "category": "entity_definition"},
    {"query": "Who is Ron?", "target_key": "target_ron", "category": "entity_definition"},
    {"query": "Who is Hermione?", "target_key": "target_hermione", "category": "entity_definition"},
    {"query": "Who is Voldemort?", "target_key": "target_voldemort", "category": "entity_definition"},
    {"query": "What is Hogwarts?", "target_key": "target_hogwarts", "category": "entity_definition"},
    {"query": "Where does Harry live before Hogwarts?", "target_key": "target_privet_drive", "category": "fact_lookup"},
    {"query": "Who are Harry's parents?", "target_key": "target_parents", "category": "fact_lookup"},
    {"query": "Why is Harry famous?", "target_key": "target_famous", "category": "fact_lookup"},
    {"query": "Who are Harry's closest friends?", "target_key": "target_friends", "category": "fact_lookup"},
    {"query": "What happens when Harry first arrives at Hogwarts?", "target_key": "target_arrival", "category": "event_lookup"},
]

# Synthetic, non-copyrighted factual test passages for deterministic evaluation
CORPUS_PASSAGES = {
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


def run_benchmark():
    import logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    db: Session = SessionLocal()
    try:
        # Seed evaluation document
        owner = f"benchmark_{uuid.uuid4().hex[:6]}"
        doc = Document(
            name="Evaluation Corpus",
            document_type="txt",
            owner_id=owner,
            department="General",
        )
        db.add(doc)
        db.flush()

        ver = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="eval_corpus.txt",
            file_size=4096,
            storage_path="/tmp/eval.txt",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        db.add(ver)
        db.flush()

        doc.active_version_id = ver.id
        db.flush()

        embedder = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

        for idx, (key, text) in enumerate(CORPUS_PASSAGES.items()):
            vec = embedder.embed_text(text)
            chunk = Chunk(
                document_version_id=ver.id,
                chunk_index=idx,
                content=text,
                page_number=(idx // 3) + 1,
                embedding=vec,
                embedding_model="mock-embedding-v1",
                chunk_metadata={"passage_key": key},
            )
            db.add(chunk)

        db.commit()

        # Instantiate Retrievers
        dense_retriever = VectorRetriever(db=db, embedding_provider=embedder)
        hybrid_retriever = HybridRetriever(
            db=db,
            embedding_provider=embedder,
            reranker=None,
            reranker_enabled=False,
        )
        reranked_retriever = HybridRetriever(
            db=db,
            embedding_provider=embedder,
            reranker=MockReranker(),
            reranker_enabled=True,
        )

        modes = {
            "Mode A (Dense Only Baseline)": dense_retriever,
            "Mode B (Hybrid: Dense + FTS RRF)": hybrid_retriever,
            "Mode C (Hybrid + Reranker)": reranked_retriever,
        }

        print("\n==========================================================================")
        print(" PHASE 22 ADVANCED RAG EVALUATION BENCHMARK & ABLATION RESULTS")
        print("==========================================================================\n")

        llm = MockLLMProvider()

        for mode_name, retriever in modes.items():
            rag_service = RAGService(retriever=retriever, llm_provider=llm)

            total_recall = 0.0
            total_precision = 0.0
            total_mrr = 0.0
            total_ndcg = 0.0
            total_latency_ms = 0.0
            total_grounded = 0
            valid_citations_count = 0
            total_citations_count = 0

            k = 5
            for q_idx, item in enumerate(BENCHMARK_QUERIES, start=1):
                query = item["query"]
                target_key = item["target_key"]

                t0 = time.perf_counter()
                rag_res = rag_service.query(question=query, top_k=k, similarity_threshold=0.01)
                latency = (time.perf_counter() - t0) * 1000
                total_latency_ms += latency

                # Evaluate Grounded Answer Rate
                if rag_res.is_grounded:
                    total_grounded += 1

                # Evaluate Citation Accuracy
                for cit in rag_res.sources:
                    total_citations_count += 1
                    # Verify citation points to existing valid document version and snippet
                    if cit.document_id == doc.id and cit.snippet != "":
                        valid_citations_count += 1

                # Evaluate Retrieval metrics (finding the target passage in retrieved chunks)
                res_chunks = retriever.retrieve(query=query, top_k=k)
                found_rank = None
                relevant_in_top_k = 0

                for r, ch in enumerate(res_chunks.results, start=1):
                    if ch.metadata.get("passage_key") == target_key:
                        found_rank = r
                        relevant_in_top_k += 1

                rec = 1.0 if found_rank is not None else 0.0
                prec = relevant_in_top_k / k
                mrr = (1.0 / found_rank) if found_rank is not None else 0.0
                ndcg = (1.0 / math.log2(found_rank + 1)) if found_rank is not None else 0.0

                total_recall += rec
                total_precision += prec
                total_mrr += mrr
                total_ndcg += ndcg

            n = len(BENCHMARK_QUERIES)
            avg_recall = total_recall / n
            avg_precision = total_precision / n
            avg_mrr = total_mrr / n
            avg_ndcg = total_ndcg / n
            avg_lat = total_latency_ms / n
            grounded_rate = (total_grounded / n) * 100
            citation_acc = (valid_citations_count / total_citations_count * 100) if total_citations_count > 0 else 100.0

            print(f"[{mode_name}]")
            print(f"  • Recall@5:             {avg_recall * 100:.1f}%")
            print(f"  • Precision@5:          {avg_precision * 100:.1f}%")
            print(f"  • MRR:                  {avg_mrr:.4f}")
            print(f"  • NDCG@5:               {avg_ndcg:.4f}")
            print(f"  • Grounded Answer Rate: {grounded_rate:.1f}%")
            print(f"  • Citation Accuracy:    {citation_acc:.1f}%")
            print(f"  • Avg Latency:          {avg_lat:.2f} ms\n")

        print("==========================================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_benchmark()
