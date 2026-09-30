import apiClient from './client'
import { HealthResponse, DbHealthResponse } from '../types'

export const healthApi = {
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/health')
    return response.data
  },

  async getDbHealth(): Promise<DbHealthResponse> {
    const response = await apiClient.get<DbHealthResponse>('/health/db')
    return response.data
  },
}
