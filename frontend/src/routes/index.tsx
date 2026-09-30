import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { LoadingSpinner } from '../components/common/LoadingSpinner'

const DashboardPage = lazy(() => import('../pages/DashboardPage'))
const DocumentsPage = lazy(() => import('../pages/DocumentsPage'))
const DocumentDetailPage = lazy(() => import('../pages/DocumentDetailPage'))
const SearchPage = lazy(() => import('../pages/SearchPage'))
const AssistantPage = lazy(() => import('../pages/AssistantPage'))
const SystemHealthPage = lazy(() => import('../pages/SystemHealthPage'))

export const createRouter = (currentUserId: string, onUserChange: (u: string) => void) => {
  return createBrowserRouter([
    {
      path: '/',
      element: <AppLayout currentUserId={currentUserId} onUserChange={onUserChange} />,
      children: [
        {
          index: true,
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading dashboard..." />}>
              <DashboardPage currentUserId={currentUserId} />
            </Suspense>
          ),
        },
        {
          path: 'documents',
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading documents..." />}>
              <DocumentsPage currentUserId={currentUserId} />
            </Suspense>
          ),
        },
        {
          path: 'documents/:documentId',
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading document viewer..." />}>
              <DocumentDetailPage />
            </Suspense>
          ),
        },
        {
          path: 'search',
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading search..." />}>
              <SearchPage />
            </Suspense>
          ),
        },
        {
          path: 'assistant',
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading AI assistant..." />}>
              <AssistantPage currentUserId={currentUserId} />
            </Suspense>
          ),
        },
        {
          path: 'health',
          element: (
            <Suspense fallback={<LoadingSpinner label="Loading system health..." />}>
              <SystemHealthPage />
            </Suspense>
          ),
        },
        {
          path: '*',
          element: <Navigate to="/" replace />,
        },
      ],
    },
  ])
}
