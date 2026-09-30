import React, { useEffect, useState } from 'react'
import { Upload, Search, Filter, RefreshCw, FileText } from 'lucide-react'
import { documentsApi } from '../api'
import { Document } from '../types'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { DocumentTable } from '../components/documents/DocumentTable'
import { DocumentUploadModal } from '../components/documents/DocumentUploadModal'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorBanner } from '../components/common/ErrorBanner'

export interface DocumentsPageProps {
  currentUserId: string
}

export const DocumentsPage: React.FC<DocumentsPageProps> = ({ currentUserId }) => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState('')
  const [selectedFormat, setSelectedFormat] = useState('')

  const fetchDocuments = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const data = await documentsApi.listDocuments({
        department: selectedDepartment || undefined,
      })
      setDocuments(data)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch documents.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [selectedDepartment])

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      !searchQuery ||
      doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.description && doc.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (doc.tags && doc.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase())))

    const matchesFormat = !selectedFormat || doc.document_type.toLowerCase() === selectedFormat.toLowerCase()

    return matchesSearch && matchesFormat
  })

  return (
    <div className="flex flex-col gap-6">
      {/* Top Header Controls */}
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Documents Repository</h1>
          <p className="text-secondary text-sm">
            Manage multi-format documents, inspect versions, and browse extracted semantic chunks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={fetchDocuments}
            disabled={isLoading}
            icon={<RefreshCw size={15} />}
          >
            Refresh
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

      {errorMessage && (
        <ErrorBanner message="Unable to load documents" details={errorMessage} onRetry={fetchDocuments} />
      )}

      {/* Filter and Search Bar */}
      <div className="card" style={{ padding: '14px 18px' }}>
        <div className="flex items-center gap-4" style={{ flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
              }}
            />
            <input
              type="text"
              className="input"
              style={{ paddingLeft: '36px' }}
              placeholder="Filter by title, description, or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ width: '180px' }}>
            <select
              className="select"
              value={selectedDepartment}
              onChange={(e) => setSelectedDepartment(e.target.value)}
              aria-label="Filter by department"
            >
              <option value="">All Departments</option>
              <option value="Engineering">Engineering</option>
              <option value="Security">Security</option>
              <option value="HR">HR</option>
              <option value="Legal">Legal</option>
              <option value="Finance">Finance</option>
            </select>
          </div>

          <div style={{ width: '150px' }}>
            <select
              className="select"
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
              aria-label="Filter by file format"
            >
              <option value="">All Formats</option>
              <option value="pdf">PDF Documents</option>
              <option value="docx">DOCX Word</option>
              <option value="txt">TXT Plaintext</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table Content */}
      <Card>
        {isLoading ? (
          <LoadingSpinner label="Loading document repository..." />
        ) : filteredDocuments.length > 0 ? (
          <DocumentTable documents={filteredDocuments} />
        ) : (
          <EmptyState
            icon={<FileText size={40} />}
            title="No documents match your filters"
            description="Try changing your search query or upload a new document to the platform."
            action={
              <Button
                variant="primary"
                onClick={() => setIsUploadOpen(true)}
                icon={<Upload size={14} />}
              >
                Upload Document
              </Button>
            }
          />
        )}
      </Card>

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => {
          fetchDocuments()
        }}
        currentUserId={currentUserId}
      />
    </div>
  )
}

export default DocumentsPage
