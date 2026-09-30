export interface Document {
  id: string
  name: string
  description?: string | null
  document_type: string
  owner_id: string
  department?: string | null
  tags: string[]
  effective_date?: string | null
  extra_metadata: Record<string, unknown>
  status: string
  active_version_id?: string | null
  created_at: string
  updated_at: string
}

export interface DocumentVersion {
  id: string
  document_id: string
  version_number: number
  file_name: string
  storage_path: string
  file_size: number
  checksum: string
  created_by?: string | null
  status: string
  created_at: string
  chunk_count?: number
  is_active?: boolean
}

export interface Chunk {
  id: string
  document_version_id: string
  chunk_index: number
  content: string
  page_number?: number | null
  metadata: Record<string, unknown>
  embedding_model?: string | null
  has_embedding: boolean
  created_at: string
}

export interface ParsedSummary {
  total_pages: number
  word_count: number
  character_count: number
  chunk_count: number
  embedding_model?: string | null
  embedding_dimension?: number | null
  metadata: Record<string, unknown>
  preview_text: string
}

export interface DocumentUploadResponse {
  message: string
  document: Document
  version: DocumentVersion
  parsing_summary: ParsedSummary
}

export interface AsyncUploadResponse {
  message: string
  document_id: string
  version_id: string
  version_number: number
  status: string
  poll_url: string
}

export interface VersionStatusResponse {
  document_id: string
  version_id: string
  version_number: number
  file_name: string
  status: string
  chunk_count: number
  is_active: boolean
  created_at: string
}

export interface DocumentDetail extends Document {
  versions: DocumentVersion[]
}
