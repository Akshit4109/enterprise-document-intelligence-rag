import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

export interface AppLayoutProps {
  currentUserId: string
  onUserChange: (userId: string) => void
}

export const AppLayout: React.FC<AppLayoutProps> = ({ currentUserId, onUserChange }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="app-container">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="main-wrapper">
        <Header currentUserId={currentUserId} onUserChange={onUserChange} />
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
