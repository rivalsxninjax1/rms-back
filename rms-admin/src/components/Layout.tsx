import { Link, NavLink, useLocation } from 'react-router-dom'
import { useAuthStore } from '../lib/auth'
import { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

const nav = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/orders', label: 'Orders' },
  { to: '/payments', label: 'Payments' },
  { to: '/admin/reservations', label: 'Reservations' },
  { to: '/admin/pos', label: 'POS' },
  { to: '/menu', label: 'Menu' },
  { to: '/coupons', label: 'Coupons' },
  { to: '/loyalty', label: 'Loyalty' },
  { to: '/reports', label: 'Reports' },
  { to: '/settings', label: 'Settings' },
  { to: '/users', label: 'Users' },
]

export default function Layout({ children }: LayoutProps) {
const clear = useAuthStore((s) => s.clear)
const location = useLocation()
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
{nav.map((n) => {
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
