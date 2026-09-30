export interface RetrievalFilter {
  owner_id?: string
  department?: string
  tags?: string[]
  document_id?: string
  document_ids?: string[]
  version_number?: number
  document_type?: string
  start_date?: string
  end_date?: string
}

export interface RetrievedChunk {
  chunk_id: string
  document_id: string
  document_name: string
  document_version_id: string
  version_number: number
  page_number?: number | null
  source_filename: string
  content: string
  similarity_score: number
  chunk_index: number
  metadata: Record<string, unknown>
  citation_label?: string
  dense_score?: number | null
  keyword_score?: number | null
  fusion_score?: number | null
  reranker_score?: number | null
  retrieval_mode?: string
}

export interface SearchRequest {
  query: string
  top_k?: number
  similarity_threshold?: number
  filters?: RetrievalFilter
  mode?: "auto" | "dense" | "keyword" | "hybrid" | "hybrid_reranked"
}

export interface SearchResponse {
  query: string
  total_results: number
  execution_time_ms: number
  retrieval_mode?: string
  results: RetrievedChunk[]
}
