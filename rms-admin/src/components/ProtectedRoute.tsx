import { Redirect, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
const { isAuthenticated } = useAuth()
const location = useLocation()
if (!isAuthenticated) {
return <Redirect to={{ pathname: '/login', state: { from: location } }} />
}
return <>{children}</>
}
