import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Search,
  Bot,
  Activity,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

export interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const navItems = [
    { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { to: '/documents', label: 'Documents', icon: <FileText size={18} /> },
    { to: '/search', label: 'Semantic Search', icon: <Search size={18} /> },
    { to: '/assistant', label: 'AI Assistant', icon: <Bot size={18} /> },
    { to: '/health', label: 'System Telemetry', icon: <Activity size={18} /> },
  ]

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && (
          <div className="brand-logo">
            <div className="brand-badge">ED</div>
            <span>Enterprise RAG</span>
          </div>
        )}
        {collapsed && (
          <div className="brand-badge" style={{ margin: '0 auto' }}>
            ED
          </div>
        )}
        <button
          className="btn-icon"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{ marginLeft: collapsed ? '0' : 'auto' }}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            title={collapsed ? item.label : undefined}
          >
            <span style={{ display: 'inline-flex', flexShrink: 0 }}>{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        {!collapsed ? (
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            <div>PostgreSQL 16 + pgvector</div>
            <div>LangGraph Stateful RAG</div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', fontSize: '10px', color: 'var(--text-muted)' }}>
            v1.0
          </div>
        )}
      </div>
    </aside>
  )
}

export default Sidebar
