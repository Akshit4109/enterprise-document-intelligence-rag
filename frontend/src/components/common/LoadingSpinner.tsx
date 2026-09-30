import React from 'react'
import { Loader2 } from 'lucide-react'

export interface LoadingSpinnerProps {
  label?: string
  size?: number
  className?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading...',
  size = 24,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 p-8 ${className}`}
      style={{ minHeight: '160px' }}
      role="status"
    >
      <Loader2
        size={size}
        style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)' }}
      />
      {label && <span className="text-secondary text-sm">{label}</span>}
    </div>
  )
}

export default LoadingSpinner
