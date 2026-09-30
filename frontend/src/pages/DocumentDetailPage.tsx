import React, { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  FileText,
  Calendar,
  User,
  Building,
  Tag,
  Layers,
  History,
  CheckCircle2,
  Upload,
} from 'lucide-react'
import { documentsApi } from '../api'
import { DocumentDetail, DocumentVersion, Chunk } from '../types'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { Badge } from '../components/common/Badge'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { DocumentViewer } from '../components/documents/DocumentViewer'
import { VersionHistory } from '../components/documents/VersionHistory'
import { ChunkList } from '../components/documents/ChunkList'

export const DocumentDetailPage: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [selectedVersion, setSelectedVersion] = useState<DocumentVersion | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isActivating, setIsActivating] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'viewer' | 'chunks' | 'versions'>('viewer')

  const targetPage = searchParams.get('page') ? parseInt(searchParams.get('page')!, 10) : 1
  const targetChunkId = searchParams.get('chunk')

  const loadDocumentData = async () => {
    if (!documentId) return
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const doc = await documentsApi.getDocument(documentId)
      const vers = await documentsApi.listVersions(documentId)
      setDocument(doc)
      setVersions(vers)

      // Find active or latest version
      const activeVer =
        vers.find((v) => v.id === doc.active_version_id || v.is_active) || vers[0]
      setSelectedVersion(activeVer)

      if (activeVer) {
        const verChunks = await documentsApi.getVersionChunks(documentId, activeVer.id)
        setChunks(verChunks)
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load document details.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDocumentData()
  }, [documentId])

  const handleSelectVersion = async (ver: DocumentVersion) => {
    if (!documentId) return
    setSelectedVersion(ver)
    try {
      const verChunks = await documentsApi.getVersionChunks(documentId, ver.id)
      setChunks(verChunks)
    } catch (err) {
      console.error('Error fetching version chunks', err)
    }
  }

  const handleActivateVersion = async (versionId: string) => {
    if (!documentId) return
    setIsActivating(true)
    try {
      const updatedDoc = await documentsApi.activateVersion(documentId, versionId)
      setDocument((prev) => (prev ? { ...prev, active_version_id: updatedDoc.active_version_id } : null))
      // Refresh version list
      const vers = await documentsApi.listVersions(documentId)
      setVersions(vers)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to activate document version.')
    } finally {
      setIsActivating(false)
    }
  }

  if (isLoading) {
    return <LoadingSpinner label="Loading document and version artifacts..." />
  }

  if (errorMessage || !document || !selectedVersion) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="outline" onClick={() => navigate('/documents')} icon={<ArrowLeft size={16} />}>
          Back to Documents
        </Button>
        <ErrorBanner
          message="Failed to load document"
          details={errorMessage || 'Document record not found.'}
          onRetry={loadDocumentData}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Back button & Title Bar */}
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '12px' }}>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/documents')}
            icon={<ArrowLeft size={16} />}
          >
            Documents
          </Button>
          <div style={{ height: '18px', width: '1px', backgroundColor: 'var(--border-strong)' }} />
          <div>
            <div className="flex items-center gap-2">
              <h1 style={{ fontSize: '18px', fontWeight: 700 }}>{document.name}</h1>
              <Badge variant="blue">v{selectedVersion.version_number}</Badge>
              {selectedVersion.id === document.active_version_id && (
                <Badge variant="green" icon={<CheckCircle2 size={11} />}>
                  Active Search Target
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Tab buttons */}
          <Button
            variant={activeTab === 'viewer' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setActiveTab('viewer')}
            icon={<FileText size={14} />}
          >
            Document Viewer
          </Button>
          <Button
            variant={activeTab === 'chunks' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setActiveTab('chunks')}
            icon={<Layers size={14} />}
          >
            Chunks ({chunks.length})
          </Button>
          <Button
            variant={activeTab === 'versions' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setActiveTab('versions')}
            icon={<History size={14} />}
          >
            Versions ({versions.length})
          </Button>
        </div>
      </div>

      {/* Main Grid: Viewer/Content on Left, Metadata Inspector on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 320px', gap: '20px', alignItems: 'start' }}>
        {/* Left Area based on activeTab */}
        <div style={{ minHeight: '620px' }}>
          {activeTab === 'viewer' && (
            <DocumentViewer
              document={document}
              version={selectedVersion}
              chunks={chunks}
              activePage={targetPage}
              activeChunkId={targetChunkId}
              onPageChange={(p) => setSearchParams({ page: p.toString() })}
            />
          )}

          {activeTab === 'chunks' && (
            <ChunkList
              chunks={chunks}
              highlightChunkId={targetChunkId}
              highlightPage={targetPage}
            />
          )}

          {activeTab === 'versions' && (
            <VersionHistory
              versions={versions}
              activeVersionId={document.active_version_id}
              selectedVersionId={selectedVersion.id}
              onSelectVersion={handleSelectVersion}
              onActivateVersion={handleActivateVersion}
              isActivating={isActivating}
            />
          )}
        </div>

        {/* Right Metadata Inspector Sidebar */}
        <div className="flex flex-col gap-4">
          <Card title="Document Metadata">
            <div className="flex flex-col gap-3 text-sm">
              <div className="flex flex-col">
                <span className="text-muted text-xs">File Format</span>
                <span style={{ fontWeight: 600 }}>{document.document_type.toUpperCase()}</span>
              </div>

              <div className="flex flex-col">
                <span className="text-muted text-xs">Owner ID</span>
                <span className="font-mono text-xs text-primary">{document.owner_id}</span>
              </div>

              <div className="flex flex-col">
                <span className="text-muted text-xs">Department</span>
                <span>{document.department || 'General Enterprise'}</span>
              </div>

              <div className="flex flex-col">
                <span className="text-muted text-xs">Tags</span>
                <div className="flex items-center gap-1" style={{ flexWrap: 'wrap', marginTop: '4px' }}>
                  {document.tags && document.tags.length > 0 ? (
                    document.tags.map((t, idx) => (
                      <Badge key={idx} variant="gray">
                        <Tag size={10} style={{ marginRight: 3 }} />
                        {t}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted text-xs">None</span>
                  )}
                </div>
              </div>

              <div className="flex flex-col">
                <span className="text-muted text-xs">Created Date</span>
                <span className="text-xs">
                  {new Date(document.created_at).toLocaleString()}
                </span>
              </div>

              {document.description && (
                <div className="flex flex-col" style={{ marginTop: '4px' }}>
                  <span className="text-muted text-xs">Description</span>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    {document.description}
                  </p>
                </div>
              )}
            </div>
          </Card>

          {/* Version Switcher Quick Box */}
          <Card title="Version Controls">
            <div className="flex flex-col gap-2">
              <span className="text-muted text-xs">Active Version:</span>
              <select
                className="select"
                value={selectedVersion.id}
                onChange={(e) => {
                  const found = versions.find((v) => v.id === e.target.value)
                  if (found) handleSelectVersion(found)
                }}
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} — {v.file_name} ({v.id === document.active_version_id ? 'Active' : 'Archived'})
                  </option>
                ))}
              </select>

              {selectedVersion.id !== document.active_version_id && (
                <Button
                  variant="primary"
                  size="sm"
                  isLoading={isActivating}
                  onClick={() => handleActivateVersion(selectedVersion.id)}
                  style={{ marginTop: '8px' }}
                >
                  Set as Active Search Target
                </Button>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default DocumentDetailPage
