import React from 'react'
import { FolderOpen } from 'lucide-react'

export interface EmptyStateProps {
  title?: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description = 'There is currently no data to display.',
  icon,
  action,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 gap-3 ${className}`}
      style={{
        border: '1px dashed var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        backgroundColor: 'rgba(15, 23, 42, 0.2)',
        minHeight: '200px',
      }}
    >
      <div style={{ color: 'var(--text-muted)' }}>
        {icon || <FolderOpen size={36} />}
      </div>
      <div>
        <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
          {title}
        </h4>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '400px' }}>
          {description}
        </p>
      </div>
      {action && <div style={{ marginTop: '6px' }}>{action}</div>}
    </div>
  )
}

export default EmptyState
