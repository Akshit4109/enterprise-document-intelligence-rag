import apiClient from './client'
import { RAGQueryRequest, RAGQueryResponse } from '../types'

export const ragApi = {
  async query(request: RAGQueryRequest): Promise<RAGQueryResponse> {
    const response = await apiClient.post<RAGQueryResponse>('/api/v1/query', request)
    return response.data
  },
}
