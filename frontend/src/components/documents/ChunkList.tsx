import React, { useState } from 'react'
import { Layers, Copy, Check, Hash, FileCode } from 'lucide-react'
import { Chunk } from '../../types'
import { Badge } from '../common/Badge'

export interface ChunkListProps {
  chunks: Chunk[]
  highlightChunkId?: string | null
  highlightPage?: number | null
}

export const ChunkList: React.FC<ChunkListProps> = ({
  chunks,
  highlightChunkId,
  highlightPage,
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const handleCopy = (content: string, id: string) => {
    navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2" style={{ fontWeight: 600, fontSize: '13.5px' }}>
          <Layers size={16} style={{ color: 'var(--accent-cyan)' }} />
          <span>Extracted Semantic Chunks ({chunks.length})</span>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {chunks.map((chunk) => {
          const isHighlighted =
            chunk.id === highlightChunkId ||
            (highlightPage !== null && highlightPage !== undefined && chunk.page_number === highlightPage)

          return (
            <div
              key={chunk.id}
              id={`chunk-${chunk.id}`}
              className="card"
              style={{
                padding: '14px',
                backgroundColor: isHighlighted ? 'rgba(37, 99, 235, 0.12)' : 'var(--bg-input)',
                borderColor: isHighlighted ? 'var(--primary)' : 'var(--border-subtle)',
                transition: 'all 0.2s ease',
              }}
            >
              <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
                <div className="flex items-center gap-2">
                  <Badge variant="blue" icon={<Hash size={11} />}>
                    Chunk #{chunk.chunk_index}
                  </Badge>
                  {chunk.page_number && (
                    <Badge variant="purple">Page {chunk.page_number}</Badge>
                  )}
                  {chunk.has_embedding && (
                    <Badge variant="green">Vector Embedded</Badge>
                  )}
                </div>
                <button
                  className="btn-icon"
                  style={{ padding: '4px' }}
                  onClick={() => handleCopy(chunk.content, chunk.id)}
                  title="Copy chunk content"
                  aria-label="Copy chunk content"
                >
                  {copiedId === chunk.id ? (
                    <Check size={14} style={{ color: 'var(--success)' }} />
                  ) : (
                    <Copy size={14} />
                  )}
                </button>
              </div>

              <p
                style={{
                  fontSize: '13px',
                  color: 'var(--text-primary)',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'inherit',
                }}
              >
                {chunk.content}
              </p>

              <div
                className="flex items-center justify-between text-muted text-xs"
                style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}
              >
                <span className="font-mono text-xs">ID: {chunk.id.slice(0, 8)}...</span>
                <span>{chunk.content.length} characters</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ChunkList
