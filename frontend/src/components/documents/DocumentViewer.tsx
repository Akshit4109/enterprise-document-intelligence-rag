import React, { useState } from 'react'
import { FileText, Download, ExternalLink, ChevronLeft, ChevronRight, Eye, Layers } from 'lucide-react'
import { documentsApi } from '../../api'
import { Document, DocumentVersion, Chunk } from '../../types'
import { Button } from '../common/Button'
import { Badge } from '../common/Badge'

export interface DocumentViewerProps {
  document: Document
  version: DocumentVersion
  chunks: Chunk[]
  activePage?: number | null
  activeChunkId?: string | null
  onPageChange?: (page: number) => void
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  document,
  version,
  chunks,
  activePage = 1,
  activeChunkId,
  onPageChange,
}) => {
  const [viewMode, setViewMode] = useState<'preview' | 'chunks'>('preview')
  const [currentPage, setCurrentPage] = useState<number>(activePage || 1)

  const isPdf = document.document_type.toLowerCase() === 'pdf'
  const fileUrl = documentsApi.getDocumentFileUrl(document.id, version.id)

  const maxPage = Math.max(...chunks.map((c) => c.page_number || 1), 1)

  const handlePageSelect = (newPage: number) => {
    const pageClamped = Math.max(1, Math.min(newPage, maxPage))
    setCurrentPage(pageClamped)
    if (onPageChange) onPageChange(pageClamped)
  }

  // Filter chunks for current page in text mode
  const pageChunks = chunks.filter((c) => (c.page_number || 1) === currentPage)

  return (
    <div className="card" style={{ padding: '0', overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%', minHeight: '600px' }}>
      {/* Top Toolbar */}
      <div
        className="flex items-center justify-between p-3"
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-sidebar)',
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <FileText size={18} style={{ color: 'var(--primary)' }} />
            <span style={{ fontWeight: 600, fontSize: '13.5px' }}>{version.file_name}</span>
          </div>
          <Badge variant="blue">v{version.version_number}</Badge>
        </div>

        <div className="flex items-center gap-3">
          {/* Page Navigator */}
          <div className="flex items-center gap-1">
            <button
              className="btn-icon"
              disabled={currentPage <= 1}
              onClick={() => handlePageSelect(currentPage - 1)}
              aria-label="Previous Page"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-secondary text-xs" style={{ minWidth: '60px', textAlign: 'center' }}>
              Page {currentPage} of {maxPage}
            </span>
            <button
              className="btn-icon"
              disabled={currentPage >= maxPage}
              onClick={() => handlePageSelect(currentPage + 1)}
              aria-label="Next Page"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <div style={{ height: '18px', width: '1px', backgroundColor: 'var(--border-strong)' }} />

          {/* View Mode Switcher */}
          <div className="flex items-center gap-1">
            <Button
              variant={viewMode === 'preview' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setViewMode('preview')}
              icon={<Eye size={13} />}
            >
              Document View
            </Button>
            <Button
              variant={viewMode === 'chunks' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setViewMode('chunks')}
              icon={<Layers size={13} />}
            >
              Chunks View
            </Button>
          </div>

          <div style={{ height: '18px', width: '1px', backgroundColor: 'var(--border-strong)' }} />

          {/* Download & External Tab actions */}
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-outline btn-sm"
            title="Open in new window"
          >
            <ExternalLink size={13} />
          </a>
          <a
            href={fileUrl}
            download={version.file_name}
            className="btn btn-secondary btn-sm"
            title="Download file"
          >
            <Download size={13} />
          </a>
        </div>
      </div>

      {/* Main Viewport */}
      <div style={{ flex: 1, backgroundColor: '#090d16', position: 'relative', overflowY: 'auto' }}>
        {viewMode === 'preview' && isPdf ? (
          <iframe
            src={`${fileUrl}#page=${currentPage}`}
            title={`Document Viewer - ${version.file_name}`}
            style={{ width: '100%', height: '100%', minHeight: '620px', border: 'none' }}
          />
        ) : (
          <div style={{ padding: '24px', maxWidth: '840px', margin: '0 auto' }}>
            <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: '13px' }}>
                Extracted Page {currentPage} Text
              </span>
              <span className="text-muted text-xs font-mono">{pageChunks.length} chunks mapped</span>
            </div>

            {pageChunks.length > 0 ? (
              <div className="flex flex-col gap-3">
                {pageChunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="card"
                    style={{
                      padding: '16px',
                      backgroundColor: chunk.id === activeChunkId ? 'var(--primary-light)' : 'var(--bg-surface)',
                      borderColor: chunk.id === activeChunkId ? 'var(--primary)' : 'var(--border-subtle)',
                    }}
                  >
                    <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
                      <Badge variant="blue">Chunk #{chunk.chunk_index}</Badge>
                      <span className="text-muted text-xs">{chunk.content.length} chars</span>
                    </div>
                    <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: '13.5px', color: 'var(--text-primary)' }}>
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="card"
                    style={{
                      padding: '16px',
                      backgroundColor: chunk.id === activeChunkId ? 'var(--primary-light)' : 'var(--bg-surface)',
                      borderColor: chunk.id === activeChunkId ? 'var(--primary)' : 'var(--border-subtle)',
                    }}
                  >
                    <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
                      <div className="flex items-center gap-2">
                        <Badge variant="blue">Chunk #{chunk.chunk_index}</Badge>
                        {chunk.page_number && <Badge variant="purple">Page {chunk.page_number}</Badge>}
                      </div>
                      <span className="text-muted text-xs">{chunk.content.length} chars</span>
                    </div>
                    <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: '13.5px', color: 'var(--text-primary)' }}>
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default DocumentViewer
