import { Redirect, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ReactNode, useEffect, useState } from 'react'
import { useAuthStore } from '../lib/auth'
import api from '../lib/api'

interface ProtectedRouteProps {
  children: ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuth()
  const setTokens = useAuthStore((s) => s.setTokens)
  const location = useLocation()
  const [bootstrapping, setBootstrapping] = useState(false)
  const [attempted, setAttempted] = useState(false)

  useEffect(() => {
    if (!isAuthenticated && !attempted && !bootstrapping) {
      setBootstrapping(true)
      setAttempted(true)
      api.post('/accounts/api/token/session/')
        .then(({ data }) => {
          if (data?.access && data?.refresh) {
            setTokens({ access: data.access, refresh: data.refresh })
          }
        })
        .catch(() => {})
        .finally(() => setBootstrapping(false))
    }
  }, [isAuthenticated, attempted, bootstrapping, setTokens])

  if (isAuthenticated) {
    return <>{children}</>
  }

  if (bootstrapping) {
    return <div className="p-6 text-center text-gray-500">Preparing dashboard…</div>
  }

  return <Redirect to={{ pathname: '/login', state: { from: location } }} />
}
