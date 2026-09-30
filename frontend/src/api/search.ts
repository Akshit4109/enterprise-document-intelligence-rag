import apiClient from './client'
import { SearchRequest, SearchResponse } from '../types'

export const searchApi = {
  async semanticSearch(request: SearchRequest): Promise<SearchResponse> {
    const response = await apiClient.post<SearchResponse>('/api/v1/search', request)
    return response.data
  },
}
