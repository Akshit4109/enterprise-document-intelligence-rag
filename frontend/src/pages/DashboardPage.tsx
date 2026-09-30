import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText,
  Search,
  Bot,
  Layers,
  Database,
  Upload,
  ArrowRight,
  TrendingUp,
  Cpu,
  Sparkles,
} from 'lucide-react'
import { documentsApi, conversationsApi, healthApi } from '../api'
import { Document, Conversation, HealthResponse, DbHealthResponse } from '../types'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { Badge } from '../components/common/Badge'
import { DocumentTable } from '../components/documents/DocumentTable'
import { DocumentUploadModal } from '../components/documents/DocumentUploadModal'
import { LoadingSpinner } from '../components/common/LoadingSpinner'

export interface DashboardPageProps {
  currentUserId: string
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ currentUserId }) => {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<Document[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [dbHealth, setDbHealth] = useState<DbHealthResponse | null>(null)
  const [serviceHealth, setServiceHealth] = useState<HealthResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUploadOpen, setIsUploadOpen] = useState(false)

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const [docs, convs, dbH, sH] = await Promise.all([
        documentsApi.listDocuments({ limit: 10 }),
        conversationsApi.listConversations({ user_id: currentUserId, limit: 5 }),
        healthApi.getDbHealth().catch(() => null),
        healthApi.getHealth().catch(() => null),
      ])
      setDocuments(docs)
      setConversations(convs)
      setDbHealth(dbH)
      setServiceHealth(sH)
    } catch (err) {
      console.error('Error loading dashboard data', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDashboardData()
  }, [currentUserId])

  const totalDocs = documents.length
  const pdfCount = documents.filter((d) => d.document_type.toLowerCase() === 'pdf').length
  const activeCount = documents.filter((d) => d.status === 'active').length

  return (
    <div className="flex flex-col gap-6">
      {/* Top Welcome Banner */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.15) 0%, rgba(6, 182, 212, 0.1) 100%)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          padding: '24px',
        }}
      >
        <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div className="flex items-center gap-2" style={{ marginBottom: '6px' }}>
              <Sparkles size={20} style={{ color: 'var(--accent-cyan)' }} />
              <h1 style={{ fontSize: '20px', fontWeight: 700 }}>
                Enterprise Document Intelligence Workspace
              </h1>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px', maxWidth: '650px' }}>
              High-performance RAG platform orchestrating PostgreSQL pgvector semantic retrieval, LangGraph stateful loops, and grounded answer synthesis.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={() => navigate('/search')}
              icon={<Search size={16} />}
            >
              Search Documents
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate('/assistant')}
              icon={<Bot size={16} />}
            >
              Ask AI Assistant
            </Button>
            <Button
              variant="primary"
              onClick={() => setIsUploadOpen(true)}
              icon={<Upload size={16} />}
            >
              Upload Document
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        <Card>
          <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
            <span className="text-secondary text-xs" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Total Documents
            </span>
            <FileText size={18} style={{ color: 'var(--primary)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {totalDocs}
          </div>
          <div className="flex items-center gap-2 text-muted text-xs" style={{ marginTop: '6px' }}>
            <span>{pdfCount} PDFs</span>
            <span>•</span>
            <span>{totalDocs - pdfCount} Other formats</span>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
            <span className="text-secondary text-xs" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Active Knowledge Base
            </span>
            <Layers size={18} style={{ color: 'var(--success)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--success)' }}>
            {activeCount}
          </div>
          <div className="flex items-center gap-2 text-muted text-xs" style={{ marginTop: '6px' }}>
            <span>100% Vector Indexed</span>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
            <span className="text-secondary text-xs" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Conversations
            </span>
            <Bot size={18} style={{ color: 'var(--accent-cyan)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {conversations.length}
          </div>
          <div className="text-muted text-xs" style={{ marginTop: '6px' }}>
            Multi-turn sessions persisted
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
            <span className="text-secondary text-xs" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Vector Index Latency
            </span>
            <Database size={18} style={{ color: 'var(--purple)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {dbHealth ? `${dbHealth.latency_ms}ms` : '—'}
          </div>
          <div className="flex items-center gap-2 text-muted text-xs" style={{ marginTop: '6px' }}>
            <span>pgvector 16 active</span>
          </div>
        </Card>
      </div>

      {/* Recent Documents Section */}
      <Card
        title="Recently Ingested Documents"
        subtitle="Catalog of enterprise documents available for RAG question answering"
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/documents')}
            icon={<ArrowRight size={14} />}
          >
            View All Documents
          </Button>
        }
      >
        {isLoading ? (
          <LoadingSpinner label="Loading document catalog..." />
        ) : documents.length > 0 ? (
          <DocumentTable documents={documents.slice(0, 5)} />
        ) : (
          <div className="text-center p-8 text-secondary text-sm">
            No documents ingested yet. Click "Upload Document" to begin!
          </div>
        )}
      </Card>

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => {
          loadDashboardData()
        }}
        currentUserId={currentUserId}
      />
    </div>
  )
}

export default DashboardPage
