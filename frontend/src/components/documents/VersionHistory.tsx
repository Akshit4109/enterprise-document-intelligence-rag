import React from 'react'
import { CheckCircle2, History, ArrowUpRight, Clock, FileCheck } from 'lucide-react'
import { DocumentVersion } from '../../types'
import { Badge } from '../common/Badge'
import { Button } from '../common/Button'

export interface VersionHistoryProps {
  versions: DocumentVersion[]
  activeVersionId?: string | null
  selectedVersionId?: string | null
  onSelectVersion: (version: DocumentVersion) => void
  onActivateVersion: (versionId: string) => void
  isActivating?: boolean
}

export const VersionHistory: React.FC<VersionHistoryProps> = ({
  versions,
  activeVersionId,
  selectedVersionId,
  onSelectVersion,
  onActivateVersion,
  isActivating,
}) => {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2" style={{ fontWeight: 600, fontSize: '13.5px' }}>
          <History size={16} style={{ color: 'var(--primary)' }} />
          <span>Version History ({versions.length})</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {versions.map((ver) => {
          const isActive = ver.id === activeVersionId || ver.is_active
          const isSelected = ver.id === selectedVersionId

          const formattedDate = ver.created_at
            ? new Date(ver.created_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : 'N/A'

          return (
            <div
              key={ver.id}
              onClick={() => onSelectVersion(ver)}
              className="card"
              style={{
                padding: '12px 14px',
                cursor: 'pointer',
                backgroundColor: isSelected ? 'var(--bg-surface-active)' : 'var(--bg-input)',
                borderColor: isSelected ? 'var(--primary)' : 'var(--border-subtle)',
                transition: 'all 0.15s ease',
              }}
            >
              <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
                <div className="flex items-center gap-2">
                  <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>
                    v{ver.version_number}
                  </span>
                  {isActive ? (
                    <Badge variant="green" icon={<CheckCircle2 size={11} />}>
                      Active Search Target
                    </Badge>
                  ) : (
                    <Badge variant="gray">Archived</Badge>
                  )}
                </div>
                {!isActive && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isActivating}
                    onClick={(e) => {
                      e.stopPropagation()
                      onActivateVersion(ver.id)
                    }}
                    style={{ fontSize: '11px', padding: '2px 8px' }}
                  >
                    Activate
                  </Button>
                )}
              </div>

              <div className="flex items-center justify-between text-secondary text-xs">
                <span>{ver.file_name}</span>
                <span>{(ver.file_size / 1024).toFixed(1)} KB</span>
              </div>

              <div className="flex items-center justify-between text-muted text-xs" style={{ marginTop: '4px' }}>
                <div className="flex items-center gap-1">
                  <Clock size={11} />
                  <span>{formattedDate}</span>
                </div>
                {ver.chunk_count !== undefined && (
                  <span className="font-mono text-xs">{ver.chunk_count} chunks</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default VersionHistory
