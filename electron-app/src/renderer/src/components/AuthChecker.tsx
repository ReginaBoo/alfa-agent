import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import api from '../api/client'

export function AuthChecker({
  children,
}: {
  children: React.ReactNode
}) {
  const [loading, setLoading] = useState(true)
  const [authorized, setAuthorized] = useState(false)

  useEffect(() => {
    api
      .get('/auth/me')
      .then(() => {
        setAuthorized(true)
      })
      .catch(() => {
        setAuthorized(false)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  if (loading) {
    return <div>Loading...</div>
  }

  if (!authorized) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}