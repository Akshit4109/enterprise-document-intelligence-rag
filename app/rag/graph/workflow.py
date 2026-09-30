from __future__ import annotations

from typing import Any, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.rag.graph.nodes import RAGGraphNodes
from app.rag.graph.state import RAGGraphState


def should_generate_or_rewrite(state: RAGGraphState) -> str:
    """
    Conditional routing function evaluating whether to generate an answer
    or loop back through query rewriting and another retrieval attempt.
    """
    sufficient = state.get("retrieval_sufficient", False)
    attempt = state.get("retrieval_attempt", 1)
    max_retries = state.get("max_retries", settings.LANGGRAPH_MAX_RETRIES)

    if sufficient:
        return "generate_answer"
    elif attempt < max_retries:
        return "rewrite_query"
    else:
        return "generate_answer"


def create_rag_graph(
    nodes: RAGGraphNodes,
    checkpointer: Optional[Any] = None,
) -> CompiledStateGraph:
    """
    Constructs and compiles the cyclic, stateful LangGraph RAG workflow.
    
    Graph Topology:
    START -> retrieve_documents -> grade_documents -> [conditional branch]
       ├─ (sufficient OR retries exhausted) ──> generate_answer -> finalize_response -> END
       └─ (insufficient AND retries remain) ──> rewrite_query -> retrieve_documents (Loop)
    """
    workflow = StateGraph(RAGGraphState)

    # 1. Register Graph Nodes
    workflow.add_node("retrieve_documents", nodes.retrieve_documents)
    workflow.add_node("grade_documents", nodes.grade_documents)
    workflow.add_node("rewrite_query", nodes.rewrite_query)
    workflow.add_node("generate_answer", nodes.generate_answer)
    workflow.add_node("finalize_response", nodes.finalize_response)

    # 2. Add Fixed Edges
    workflow.add_edge(START, "retrieve_documents")
    workflow.add_edge("retrieve_documents", "grade_documents")

    # 3. Add Conditional Edge for Retrieval Sufficiency & Retry Loop
    workflow.add_conditional_edges(
        "grade_documents",
        should_generate_or_rewrite,
        {
            "generate_answer": "generate_answer",
            "rewrite_query": "rewrite_query",
        },
    )

    # 4. Loop back from rewrite_query to retrieve_documents
    workflow.add_edge("rewrite_query", "retrieve_documents")

    # 5. Output pipeline edges
    workflow.add_edge("generate_answer", "finalize_response")
    workflow.add_edge("finalize_response", END)

    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()
