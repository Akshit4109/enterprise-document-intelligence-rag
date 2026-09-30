import React from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, ArrowUpRight, CheckCircle2, Bookmark, Hash, Layers, Cpu, Search } from 'lucide-react'
import { RetrievedChunk } from '../../types'
import { Badge } from '../common/Badge'
import { Button } from '../common/Button'

export interface SearchResultCardProps {
  result: RetrievedChunk
  onNavigate?: (documentId: string, pageNumber?: number | null, chunkId?: string) => void
}

export const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, onNavigate }) => {
  const navigate = useNavigate()

  const handleOpen = () => {
    if (onNavigate) {
      onNavigate(result.document_id, result.page_number, result.chunk_id)
    } else {
      const pageParam = result.page_number ? `?page=${result.page_number}&chunk=${result.chunk_id}` : `?chunk=${result.chunk_id}`
      navigate(`/documents/${result.document_id}${pageParam}`)
    }
  }

  // Calculate similarity percentage
  const scorePercent = Math.round(result.similarity_score * 100)
  const getScoreVariant = (score: number) => {
    if (score >= 0.7) return 'green'
    if (score >= 0.4) return 'blue'
    return 'amber'
  }

  return (
    <div
      className="card"
      style={{
        padding: '16px 20px',
        transition: 'all 0.15s ease',
        backgroundColor: 'var(--bg-surface)',
      }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
        <div className="flex items-center gap-2 flex-wrap">
          <FileText size={18} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: 600, fontSize: '14.5px', color: 'var(--text-primary)' }}>
            {result.document_name}
          </span>
          <Badge variant="gray">v{result.version_number}</Badge>
          {result.page_number && (
            <Badge variant="purple">Page {result.page_number}</Badge>
          )}
          <Badge variant="blue" icon={<Hash size={11} />}>
            Chunk #{result.chunk_index}
          </Badge>
          {result.retrieval_mode && (
            <Badge
              variant={result.retrieval_mode.includes('reranked') ? 'green' : result.retrieval_mode.includes('hybrid') ? 'purple' : 'gray'}
              icon={result.retrieval_mode.includes('reranked') ? <Cpu size={11} /> : <Layers size={11} />}
            >
              {result.retrieval_mode}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Badge variant={getScoreVariant(result.similarity_score)} icon={<CheckCircle2 size={12} />}>
            Similarity: {result.similarity_score.toFixed(4)} ({scorePercent}%)
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpen}
            icon={<ArrowUpRight size={13} />}
          >
            Inspect
          </Button>
        </div>
      </div>

      <p
        style={{
          fontSize: '13.5px',
          color: 'var(--text-primary)',
          lineHeight: 1.65,
          backgroundColor: 'rgba(11, 15, 23, 0.6)',
          padding: '12px 14px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          fontFamily: 'inherit',
          whiteSpace: 'pre-wrap',
        }}
      >
        {result.content}
      </p>

      <div
        className="flex items-center justify-between text-muted text-xs"
        style={{ marginTop: '10px', flexWrap: 'wrap', gap: '8px' }}
      >
        <div className="flex items-center gap-3">
          <span className="font-mono">{result.source_filename}</span>
          {result.dense_score !== undefined && result.dense_score !== null && (
            <span>Dense: {result.dense_score.toFixed(3)}</span>
          )}
          {result.keyword_score !== undefined && result.keyword_score !== null && (
            <span>Keyword: {result.keyword_score.toFixed(3)}</span>
          )}
          {result.fusion_score !== undefined && result.fusion_score !== null && (
            <span>RRF: {result.fusion_score.toFixed(3)}</span>
          )}
          {result.reranker_score !== undefined && result.reranker_score !== null && (
            <span style={{ color: 'var(--accent-green)' }}>Reranker: {result.reranker_score.toFixed(3)}</span>
          )}
        </div>
        <span className="font-mono">Chunk ID: {result.chunk_id.slice(0, 8)}...</span>
      </div>
    </div>
  )
}

export default SearchResultCard
