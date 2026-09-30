import os
from typing import Optional, Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Document Intelligence & RAG Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg://rag_user:rag_password@localhost:5433/enterprise_rag_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Storage Settings
    STORAGE_LOCAL_ROOT: str = os.path.join(os.getcwd(), "storage", "documents")
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: Set[str] = {"pdf", "docx", "txt"}

    # Chunking Settings
    DEFAULT_CHUNK_SIZE: int = 500  # Default character count per chunk
    DEFAULT_CHUNK_OVERLAP: int = 50  # Overlap in characters

    # Embedding Settings
    EMBEDDING_PROVIDER: str = "local"  # "local", "mock", or "openai"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # LLM & RAG Settings
    LLM_PROVIDER: str = "mock"  # "mock", "openai", or "gemini"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"

    RAG_MIN_RELEVANCE_THRESHOLD: float = 0.25
    RAG_DEFAULT_TOP_K: int = 5
    RAG_TEMPERATURE: float = 0.0
    USE_LANGCHAIN_RAG: bool = False
    USE_LANGGRAPH_RAG: bool = False
    LANGGRAPH_MAX_RETRIES: int = 2

    # Advanced Hybrid Retrieval & Reranking Settings (Phase 22)
    USE_HYBRID_RETRIEVAL: bool = False
    RERANKER_ENABLED: bool = False
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
    RERANKER_CANDIDATE_K: int = 20
    RERANKER_TOP_K: int = 5
    HYBRID_FUSION_RRF_K: int = 60
    HYBRID_DENSE_WEIGHT: float = 0.6
    HYBRID_KEYWORD_WEIGHT: float = 0.4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
