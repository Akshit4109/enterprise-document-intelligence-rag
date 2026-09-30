import React, { useState } from 'react'
import { RouterProvider } from 'react-router-dom'
import { createRouter } from './routes'

export const App: React.FC = () => {
  const [currentUserId, setCurrentUserId] = useState<string>('usr_eng_lead')

  const router = createRouter(currentUserId, (newId) => setCurrentUserId(newId))

  return <RouterProvider router={router} />
}

export default App
