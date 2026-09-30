import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import Button from './Button'

export interface ErrorBannerProps {
  message: string
  details?: string
  onRetry?: () => void
  className?: string
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  details,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`flex items-center justify-between p-4 gap-4 ${className}`}
      style={{
        backgroundColor: 'var(--danger-light)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderRadius: 'var(--radius-md)',
        color: '#fca5a5',
      }}
      role="alert"
    >
      <div className="flex items-center gap-3">
        <AlertTriangle size={20} style={{ color: 'var(--danger)', flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 600, fontSize: '13.5px', color: '#fecaca' }}>{message}</div>
          {details && (
            <div style={{ fontSize: '12px', color: '#f87171', marginTop: '2px' }}>
              {details}
            </div>
          )}
        </div>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          icon={<RefreshCw size={14} />}
          style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: '#fecaca' }}
        >
          Retry
        </Button>
      )}
    </div>
  )
}

export default ErrorBanner
