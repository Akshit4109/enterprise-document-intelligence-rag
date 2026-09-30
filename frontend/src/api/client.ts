import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export interface ApiErrorPayload {
  error: string
  message: string
  details?: Record<string, unknown>
}

export class ApiClientError extends Error {
  public status: number
  public details?: Record<string, unknown>

  constructor(message: string, status: number, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.details = details
  }
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
  headers: {
    'Accept': 'application/json',
  },
})

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorPayload>) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      const message = data?.message || error.message || 'An unexpected API error occurred.'
      const details = data?.details || {}
      return Promise.reject(new ApiClientError(message, status, details))
    } else if (error.request) {
      return Promise.reject(new ApiClientError('Backend server is unreachable. Please verify that FastAPI is running.', 0))
    }
    return Promise.reject(new ApiClientError(error.message, 0))
  }
)

export default apiClient
