import React, { useEffect, useState } from 'react'
import { Activity, Database, Sparkles, User } from 'lucide-react'
import { healthApi } from '../../api'
import { Badge } from '../common/Badge'

export interface HeaderProps {
  currentUserId: string
  onUserChange: (userId: string) => void
}

export const Header: React.FC<HeaderProps> = ({ currentUserId, onUserChange }) => {
  const [dbHealthy, setDbHealthy] = useState<boolean | null>(null)
  const [pgvectorReady, setPgvectorReady] = useState<boolean>(false)

  useEffect(() => {
    let isMounted = true
    const checkHealth = async () => {
      try {
        const res = await healthApi.getDbHealth()
        if (isMounted) {
          setDbHealthy(res.status === 'healthy')
          setPgvectorReady(res.pgvector_installed)
        }
      } catch {
        if (isMounted) {
          setDbHealthy(false)
        }
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="flex items-center gap-2">
          <Sparkles size={18} style={{ color: 'var(--accent-cyan)' }} />
          <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
            Enterprise Document Intelligence & RAG
          </span>
        </div>
      </div>

      <div className="header-right">
        {/* System & DB Status Pill */}
        <div className="flex items-center gap-2">
          <Badge
            variant={dbHealthy ? 'green' : dbHealthy === false ? 'red' : 'gray'}
            icon={<Database size={12} />}
          >
            {dbHealthy ? 'PostgreSQL pgvector' : dbHealthy === false ? 'DB Offline' : 'Checking DB...'}
          </Badge>
          {pgvectorReady && (
            <Badge variant="purple" icon={<Activity size={12} />}>
              Vector 384d
            </Badge>
          )}
        </div>

        {/* User / Tenant Switcher */}
        <div className="flex items-center gap-2" style={{ marginLeft: '8px' }}>
          <User size={15} style={{ color: 'var(--text-muted)' }} />
          <select
            className="select"
            style={{ padding: '4px 10px', fontSize: '12.5px', width: 'auto' }}
            value={currentUserId}
            onChange={(e) => onUserChange(e.target.value)}
            aria-label="Select active user/tenant identity"
          >
            <option value="usr_eng_lead">usr_eng_lead (Engineering)</option>
            <option value="usr_compliance_dept">usr_compliance_dept (Security)</option>
            <option value="usr_legal_team">usr_legal_team (Legal)</option>
            <option value="default_user">default_user (General)</option>
          </select>
        </div>
      </div>
    </header>
  )
}

export default Header
