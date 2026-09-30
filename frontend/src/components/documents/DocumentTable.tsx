import React from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Calendar, User, Tag, ChevronRight, CheckCircle, Clock } from 'lucide-react'
import { Document } from '../../types'
import { Badge } from '../common/Badge'

export interface DocumentTableProps {
  documents: Document[]
  isLoading?: boolean
  onSelectDocument?: (doc: Document) => void
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  isLoading,
  onSelectDocument,
}) => {
  const navigate = useNavigate()

  const handleRowClick = (doc: Document) => {
    if (onSelectDocument) {
      onSelectDocument(doc)
    } else {
      navigate(`/documents/${doc.id}`)
    }
  }

  const getFormatBadgeVariant = (type: string) => {
    const t = type.toLowerCase()
    if (t === 'pdf') return 'red'
    if (t === 'docx') return 'blue'
    return 'amber'
  }

  return (
    <div className="table-container">
      <table className="table" aria-label="Documents list table">
        <thead>
          <tr>
            <th>Document Name</th>
            <th>Type</th>
            <th>Department</th>
            <th>Owner</th>
            <th>Tags</th>
            <th>Status</th>
            <th>Uploaded</th>
            <th style={{ width: '40px' }}></th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => {
            const formattedDate = doc.created_at
              ? new Date(doc.created_at).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })
              : 'N/A'

            return (
              <tr
                key={doc.id}
                onClick={() => handleRowClick(doc)}
                style={{ cursor: 'pointer' }}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRowClick(doc)
                }}
              >
                <td>
                  <div className="flex items-center gap-2">
                    <FileText size={18} style={{ color: 'var(--primary)', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{doc.name}</div>
                      {doc.description && (
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {doc.description.slice(0, 60)}
                          {doc.description.length > 60 ? '...' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                <td>
                  <Badge variant={getFormatBadgeVariant(doc.document_type)}>
                    {doc.document_type.toUpperCase()}
                  </Badge>
                </td>
                <td>
                  <span className="text-secondary">{doc.department || 'General'}</span>
                </td>
                <td>
                  <div className="flex items-center gap-1 text-secondary text-xs">
                    <User size={13} />
                    <span>{doc.owner_id}</span>
                  </div>
                </td>
                <td>
                  <div className="flex items-center gap-1" style={{ flexWrap: 'wrap' }}>
                    {doc.tags && doc.tags.length > 0 ? (
                      doc.tags.slice(0, 2).map((t, idx) => (
                        <Badge key={idx} variant="gray">
                          <Tag size={10} style={{ marginRight: 3 }} />
                          {t}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted text-xs">—</span>
                    )}
                    {doc.tags && doc.tags.length > 2 && (
                      <span className="text-muted text-xs">+{doc.tags.length - 2}</span>
                    )}
                  </div>
                </td>
                <td>
                  <Badge
                    variant={doc.status === 'active' ? 'green' : 'amber'}
                    icon={
                      doc.status === 'active' ? <CheckCircle size={12} /> : <Clock size={12} />
                    }
                  >
                    {doc.status}
                  </Badge>
                </td>
                <td>
                  <div className="flex items-center gap-1 text-secondary text-xs">
                    <Calendar size={13} />
                    <span>{formattedDate}</span>
                  </div>
                </td>
                <td style={{ textAlign: 'right' }}>
                  <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default DocumentTable
