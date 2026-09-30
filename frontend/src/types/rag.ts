import { RetrievalFilter } from './search'

export interface CitationSource {
  source_index: number
  document_id: string
  document_name: string
  document_version_id: string
  version_number: number
  page_number?: number | null
  source_filename: string
  chunk_id: string
  similarity_score: number
  snippet: string
  citation_label: string
}

export interface RAGQueryRequest {
  question: string
  top_k?: number
  similarity_threshold?: number
  filters?: RetrievalFilter
  temperature?: number
}

export interface RAGQueryResponse {
  question: string
  answer: string
  sources: CitationSource[]
  is_grounded: boolean
  llm_model?: string | null
  token_usage: Record<string, number>
  retrieval_metadata: {
    engine?: string
    retrieved_count?: number
    max_similarity?: number
    top_similarity?: number
    threshold_applied?: number
    retry_attempts?: number
    rewritten_query?: string | null
    fallback_triggered?: boolean
    latency_ms?: number
    [key: string]: unknown
  }
}
