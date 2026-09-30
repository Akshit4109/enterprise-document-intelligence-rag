export interface HealthResponse {
  status: string
  service: string
  environment: string
  uptime_seconds: number
  version: string
}

export interface DbPoolStatus {
  size: number
  checked_in: number
  checked_out: number
  overflow: number
}

export interface DbHealthResponse {
  status: string
  database: string
  pgvector_installed: boolean
  latency_ms: number
  pool: DbPoolStatus
}
