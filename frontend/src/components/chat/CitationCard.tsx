import React from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, ArrowUpRight, CheckCircle2 } from 'lucide-react'
import { CitationSource } from '../../types'
import { Badge } from '../common/Badge'

export interface CitationCardProps {
  citation: CitationSource
  onNavigateToCitation?: (citation: CitationSource) => void
}

export const CitationCard: React.FC<CitationCardProps> = ({
  citation,
  onNavigateToCitation,
}) => {
  const navigate = useNavigate()

  const handleClick = () => {
    if (onNavigateToCitation) {
      onNavigateToCitation(citation)
    } else {
      const pageQuery = citation.page_number
        ? `?page=${citation.page_number}&chunk=${citation.chunk_id}`
        : `?chunk=${citation.chunk_id}`
      navigate(`/documents/${citation.document_id}${pageQuery}`)
    }
  }

  return (
    <div
      onClick={handleClick}
      className="citation-card flex items-center justify-between"
      style={{ cursor: 'pointer' }}
      title={`Open ${citation.document_name} at Page ${citation.page_number || 1}`}
    >
      <div className="flex items-center gap-3">
        <div
          className="brand-badge"
          style={{
            width: '24px',
            height: '24px',
            fontSize: '12px',
            borderRadius: 'var(--radius-sm)',
            flexShrink: 0,
          }}
        >
          {citation.source_index}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              {citation.document_name}
            </span>
            {citation.page_number && (
              <Badge variant="purple" className="text-xs">
                Page {citation.page_number}
              </Badge>
            )}
            <Badge variant="blue" className="text-xs">
              v{citation.version_number}
            </Badge>
          </div>
          <div
            style={{
              fontSize: '12px',
              color: 'var(--text-muted)',
              marginTop: '2px',
              maxWidth: '520px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            "{citation.snippet}"
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant="green" icon={<CheckCircle2 size={10} />} className="text-xs">
          {(citation.similarity_score * 100).toFixed(0)}% Match
        </Badge>
        <span className="btn-icon" style={{ padding: '4px' }}>
          <ArrowUpRight size={15} style={{ color: 'var(--text-secondary)' }} />
        </span>
      </div>
    </div>
  )
}

export default CitationCard
