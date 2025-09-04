import { NavLink } from 'react-router-dom'
import { ReactNode } from 'react'

export default function MenuLayout({ children }: { children: ReactNode }) {
  const tabs = [
    { to: '/menu/items', label: 'Items' },
    { to: '/menu/modifiers', label: 'Modifiers' },
    { to: '/menu/stock', label: 'Stock' },
    { to: '/menu/availability', label: 'Availability' },
  ]
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Menu</h2>
      <div className="flex gap-2 border-b">
        {tabs.map(t => (
          <NavLink key={t.to} to={t.to} className="px-3 py-2 text-sm" activeClassName="border-b-2 border-blue-600 font-medium">
            {t.label}
          </NavLink>
        ))}
      </div>
      <div>
        {children}
      </div>
    </div>
  )
}

