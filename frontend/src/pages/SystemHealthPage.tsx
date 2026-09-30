import React, { useEffect, useState } from 'react'
import {
  Activity,
  Database,
  Server,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Layers,
  Clock,
  Shield,
} from 'lucide-react'
import { healthApi } from '../api'
import { HealthResponse, DbHealthResponse } from '../types'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { Badge } from '../components/common/Badge'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorBanner } from '../components/common/ErrorBanner'

export const SystemHealthPage: React.FC = () => {
  const [serviceHealth, setServiceHealth] = useState<HealthResponse | null>(null)
  const [dbHealth, setDbHealth] = useState<DbHealthResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchHealth = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const [sH, dH] = await Promise.all([healthApi.getHealth(), healthApi.getDbHealth()])
      setServiceHealth(sH)
      setDbHealth(dH)
    } catch (err: any) {
      setErrorMessage(err.message || 'System health check failed.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  return (
    <div className="flex flex-col gap-6">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>System Telemetry & Health</h1>
          <p className="text-secondary text-sm">
            Live infrastructure diagnostics for FastAPI backend, PostgreSQL database pool, and pgvector extension.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={fetchHealth}
          disabled={isLoading}
          icon={<RefreshCw size={15} />}
        >
          Run Diagnostic Check
        </Button>
      </div>

      {errorMessage && (
        <ErrorBanner
          message="Health check warning"
          details={errorMessage}
          onRetry={fetchHealth}
        />
      )}

      {isLoading ? (
        <LoadingSpinner label="Querying backend & database health endpoints..." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Backend Service Card */}
          <Card
            title={
              <div className="flex items-center gap-2">
                <Server size={18} style={{ color: 'var(--primary)' }} />
                <span>FastAPI Application Service</span>
              </div>
            }
          >
            {serviceHealth ? (
              <div className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted">Status</span>
                  <Badge variant="green" icon={<CheckCircle2 size={12} />}>
                    {serviceHealth.status.toUpperCase()}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Service Name</span>
                  <span style={{ fontWeight: 600 }}>{serviceHealth.service}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Environment</span>
                  <Badge variant="blue">{serviceHealth.environment}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Version</span>
                  <span className="font-mono text-xs">{serviceHealth.version}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Uptime</span>
                  <span className="font-mono text-xs">
                    {Math.floor(serviceHealth.uptime_seconds / 60)} mins ({serviceHealth.uptime_seconds.toFixed(0)}s)
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-secondary text-xs">Service health unavailable.</div>
            )}
          </Card>

          {/* Database & Vector Store Card */}
          <Card
            title={
              <div className="flex items-center gap-2">
                <Database size={18} style={{ color: 'var(--purple)' }} />
                <span>PostgreSQL 16 & pgvector</span>
              </div>
            }
          >
            {dbHealth ? (
              <div className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted">Database Engine</span>
                  <span style={{ fontWeight: 600 }}>PostgreSQL 16</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">pgvector Extension</span>
                  <Badge
                    variant={dbHealth.pgvector_installed ? 'green' : 'red'}
                    icon={dbHealth.pgvector_installed ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                  >
                    {dbHealth.pgvector_installed ? 'Installed & Active' : 'Missing'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Ping Round-Trip Latency</span>
                  <span className="font-mono text-xs" style={{ color: 'var(--success)' }}>
                    {dbHealth.latency_ms} ms
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Connection Pool Size</span>
                  <span className="font-mono text-xs">{dbHealth.pool?.size || 10}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Checked Out Connections</span>
                  <span className="font-mono text-xs">{dbHealth.pool?.checked_out || 0}</span>
                </div>
              </div>
            ) : (
              <div className="text-secondary text-xs">Database health check unavailable.</div>
            )}
          </Card>

          {/* RAG Engine Topology Card */}
          <Card
            title={
              <div className="flex items-center gap-2">
                <Cpu size={18} style={{ color: 'var(--accent-cyan)' }} />
                <span>RAG Architecture & Orchestration</span>
              </div>
            }
          >
            <div className="flex flex-col gap-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted">Primary Orchestration</span>
                <Badge variant="purple">LangGraph Stateful Workflow</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Dense Embedding Model</span>
                <span className="font-mono text-xs">all-MiniLM-L6-v2 (384d)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Vector Distance Metric</span>
                <span className="font-mono text-xs">Cosine Similarity (&lt;=&gt;)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Query Rewriting & Loops</span>
                <Badge variant="blue">Bounded Retry (Max 2 Attempts)</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Citation Preservation</span>
                <Badge variant="green">Chunk & Page Level Provenance</Badge>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

export default SystemHealthPage
