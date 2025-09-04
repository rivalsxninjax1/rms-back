import { Route, Redirect } from 'react-router-dom'
import { ReactNode } from 'react'
import { useProfile } from '../hooks/settings'

type Props = {
  roles?: Array<'Manager'|'Cashier'|'Kitchen'|'Host'>
  locations?: number[]
  component?: any
  children?: ReactNode
  path?: string
  exact?: boolean
}

export default function RBACRoute({ roles, locations, component: Comp, children, ...rest }: Props) {
  const { data: profile, isLoading } = useProfile()

  return (
    <Route
      {...rest}
      render={(props) => {
        if (isLoading) return null
        if (!profile) return <Redirect to="/login" />
        const hasRole = !roles || roles.some((r) => (profile.roles || []).includes(r))
        const inLoc = !locations || locations.includes(profile.active_location_id)
        if (!hasRole || !inLoc) return <Redirect to="/dashboard" />
        return Comp ? <Comp {...props} /> : (children as any)
      }}
    />
  )
}

