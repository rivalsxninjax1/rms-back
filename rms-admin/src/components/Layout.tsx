import { Link, NavLink, useLocation } from 'react-router-dom'
import { useAuthStore } from '../lib/auth'
import { useProfile } from '../hooks/settings'
import { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

const nav = [
  { to: '/dashboard', label: 'Dashboard', roles: ['Manager','Cashier','Kitchen','Host'] },
  { to: '/orders', label: 'Orders', roles: ['Manager','Cashier','Kitchen','Host'] },
  { to: '/payments', label: 'Payments', roles: ['Manager','Cashier'] },
  { to: '/admin/reservations', label: 'Reservations', roles: ['Manager','Host'] },
  // New LiveDashboard directly under Reservations
  { to: '/admin/liveDashboard', label: 'LiveDashboard', roles: ['Manager','Cashier','Kitchen','Host'] },
  { to: '/admin/pos', label: 'POS', roles: ['Manager','Cashier','Host'] },
  { to: '/menu', label: 'Menu', roles: ['Manager'] },
  { to: '/coupons', label: 'Coupons', roles: ['Manager'] },
  { to: '/loyalty', label: 'Loyalty', roles: ['Manager','Cashier'] },
  { to: '/reports', label: 'Reports', roles: ['Manager','Cashier','Kitchen','Host'] },
  { to: '/settings', label: 'Settings', roles: ['Manager'] },
  { to: '/users', label: 'Users', roles: ['Manager'] },
]

export default function Layout({ children }: LayoutProps) {
const clear = useAuthStore((s) => s.clear)
const location = useLocation()
const { data: profile } = useProfile()

// Filter navigation items based on user roles
const visibleNav = nav.filter(item => {
  if (!item.roles || !profile?.roles) return true
  return item.roles.some(role => profile.roles.includes(role))
})

return (
<div className="min-h-screen grid grid-cols-[240px_1fr] grid-rows-[56px_1fr]">
<header className="col-span-2 h-14 border-b flex items-center px-4 justify-between">
<Link to="/" className="font-semibold">RMS Admin</Link>
<button
className="text-sm px-3 py-1 border rounded-md hover:bg-gray-50"
onClick={clear}
>Sign out</button>
</header>

<aside className="border-r p-3">
<nav className="space-y-1">
{visibleNav.map((n) => {
  const isActive = location.pathname === n.to || location.pathname.startsWith(n.to + '/')
  return (
<NavLink
key={n.to}
to={n.to}
exact={n.to === '/'}
className={`block rounded-md px-3 py-2 text-sm hover:bg-gray-100 ${
isActive ? 'bg-gray-100 font-medium' : ''
}`}
>
{n.label}
</NavLink>
  )
})}
</nav>
</aside>

<main className="p-6">
{children}
</main>
</div>
)
}
