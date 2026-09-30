import apiClient from './client'
import {
  Document,
  DocumentDetail,
  DocumentUploadResponse,
  AsyncUploadResponse,
  DocumentVersion,
  VersionStatusResponse,
  Chunk,
} from '../types'

export interface ListDocumentsParams {
  skip?: number
  limit?: number
  owner_id?: string
  department?: string
}

export interface UploadDocumentParams {
  file: File
  name?: string
  description?: string
  owner_id?: string
  department?: string
  tags?: string[]
  effective_date?: string
  document_id?: string
  chunk_size?: number
  chunk_overlap?: number
}

export const documentsApi = {
  async listDocuments(params?: ListDocumentsParams): Promise<Document[]> {
    const response = await apiClient.get<Document[]>('/api/v1/documents', { params })
    return response.data
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    const response = await apiClient.get<DocumentDetail>(`/api/v1/documents/${documentId}`)
    return response.data
  },

  async uploadDocument(params: UploadDocumentParams): Promise<DocumentUploadResponse> {
    const formData = new FormData()
    formData.append('file', params.file)
    if (params.name) formData.append('name', params.name)
    if (params.description) formData.append('description', params.description)
    if (params.owner_id) formData.append('owner_id', params.owner_id)
    if (params.department) formData.append('department', params.department)
    if (params.tags && params.tags.length > 0) formData.append('tags', JSON.stringify(params.tags))
    if (params.effective_date) formData.append('effective_date', params.effective_date)
    if (params.document_id) formData.append('document_id', params.document_id)
    if (params.chunk_size) formData.append('chunk_size', params.chunk_size.toString())
    if (params.chunk_overlap) formData.append('chunk_overlap', params.chunk_overlap.toString())

    const response = await apiClient.post<DocumentUploadResponse>('/api/v1/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  async uploadDocumentAsync(params: UploadDocumentParams): Promise<AsyncUploadResponse> {
    const formData = new FormData()
    formData.append('file', params.file)
    if (params.name) formData.append('name', params.name)
    if (params.description) formData.append('description', params.description)
    if (params.owner_id) formData.append('owner_id', params.owner_id)
    if (params.department) formData.append('department', params.department)
    if (params.tags && params.tags.length > 0) formData.append('tags', JSON.stringify(params.tags))
    if (params.effective_date) formData.append('effective_date', params.effective_date)
    if (params.chunk_size) formData.append('chunk_size', params.chunk_size.toString())
    if (params.chunk_overlap) formData.append('chunk_overlap', params.chunk_overlap.toString())

    const response = await apiClient.post<AsyncUploadResponse>('/api/v1/documents/upload/async', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  async listVersions(documentId: string): Promise<DocumentVersion[]> {
    const response = await apiClient.get<DocumentVersion[]>(`/api/v1/documents/${documentId}/versions`)
    return response.data
  },

  async getVersion(documentId: string, versionId: string): Promise<DocumentVersion> {
    const response = await apiClient.get<DocumentVersion>(`/api/v1/documents/${documentId}/versions/${versionId}`)
    return response.data
  },

  async getVersionStatus(documentId: string, versionId: string): Promise<VersionStatusResponse> {
    const response = await apiClient.get<VersionStatusResponse>(`/api/v1/documents/${documentId}/versions/${versionId}/status`)
    return response.data
  },

  async activateVersion(documentId: string, versionId: string): Promise<Document> {
    const response = await apiClient.put<Document>(`/api/v1/documents/${documentId}/versions/${versionId}/activate`)
    return response.data
  },

  async getVersionChunks(documentId: string, versionId: string, skip: number = 0, limit: number = 100): Promise<Chunk[]> {
    const response = await apiClient.get<Chunk[]>(`/api/v1/documents/${documentId}/versions/${versionId}/chunks`, {
      params: { skip, limit },
    })
    return response.data
  },

  getDocumentFileUrl(documentId: string, versionId: string): string {
    const base = apiClient.defaults.baseURL || ''
    return `${base}/api/v1/documents/${documentId}/versions/${versionId}/file`
  },
}
