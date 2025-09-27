// no explicit React import needed with new TS/JSX runtime

export interface OrderItem {
  id: number
  quantity: number
  menu_item?: { id: number; name: string }
  modifiers?: Array<{ id?: number; name?: string; price?: number }>
  notes?: string
  special_instructions?: string
  line_total?: number
  subtotal?: number
}

export interface Order {
  id: number
  order_number?: string
  customer_name?: string
  customer_phone?: string
  customer_email?: string
  delivery_option?: string
  table_number?: number
  status: string
  total_amount: number
  created_at: string
  items: OrderItem[]
  channel?: string
  payment_status?: string
  notes?: string
}

const statusColor = (status: string) => {
  const s = String(status||'').toLowerCase()
  if (s.includes('pending')) return 'border-yellow-400 bg-yellow-50'
  if (s.includes('preparing') || s.includes('confirmed') || s.includes('out_for_delivery')) return 'border-orange-400 bg-orange-50'
  if (s.includes('ready') || s.includes('served')) return 'border-green-500 bg-green-50'
  if (s.includes('completed')) return 'border-gray-300 bg-gray-50'
  if (s.includes('cancel')) return 'border-red-300 bg-red-50'
  return 'border-gray-200 bg-white'
}

const pillColor = (status: string) => {
  const s = String(status||'').toLowerCase()
  if (s.includes('pending')) return 'bg-yellow-100 text-yellow-800'
  if (s.includes('preparing') || s.includes('confirmed') || s.includes('out_for_delivery')) return 'bg-orange-100 text-orange-800'
  if (s.includes('ready') || s.includes('served')) return 'bg-green-100 text-green-800'
  if (s.includes('completed')) return 'bg-gray-100 text-gray-800'
  if (s.includes('cancel')) return 'bg-red-100 text-red-800'
  return 'bg-gray-100 text-gray-800'
}

export function OrderCard({ o, highlight, formatCurrency, onAction } : {
  o: Order
  highlight?: boolean
  formatCurrency: (n: number) => string
  onAction: (action: 'accept'|'start'|'ready'|'complete', id: number) => void
}) {
  return (
    <div className={`rounded-lg border p-3 shadow-sm ${statusColor(o.status)} ${highlight ? 'animate-pulse' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="space-y-0.5">
          <div className="font-semibold">#{o.id}{o.order_number ? ` · ${o.order_number}` : ''}</div>
          <div className="text-xs text-gray-600">{new Date(o.created_at).toLocaleString()}</div>
        </div>
        <span className={`px-2 py-0.5 rounded text-[11px] ${pillColor(o.status)}`}>{o.status}</span>
      </div>

      <div className="mt-2">
        <div className="text-sm font-medium">{o.customer_name || '—'}</div>
        <div className="text-xs text-gray-600">{o.customer_phone || o.customer_email || '—'}</div>
      </div>

      <div className="mt-3">
        <div className="text-xs text-gray-600 mb-1">Items</div>
        <ul className="text-sm space-y-1">
          {o.items?.map((it) => (
            <li key={it.id}>
              <div className="flex justify-between">
                <span>{it.quantity}× {it.menu_item?.name} {it.notes ? <span className="text-xs text-gray-600">— {it.notes}</span> : it.special_instructions ? <span className="text-xs text-gray-600">— {it.special_instructions}</span> : null}</span>
                <span className="text-gray-600">{formatCurrency(Number(it.subtotal || it.line_total || 0))}</span>
              </div>
              {it.modifiers && it.modifiers.length > 0 && (
                <div className="pl-4 text-xs text-gray-500">
                  {it.modifiers.map((m, idx) => (
                    <div key={idx}>• {m.name || m.id}{m.price ? ` (+${formatCurrency(Number(m.price))})` : ''}</div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-xs text-gray-600">Service</div>
          <div>{(o.delivery_option||'').toUpperCase()}{o.table_number ? ` · Table ${o.table_number}` : ''}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-600">Total</div>
          <div className="font-semibold">{formatCurrency(o.total_amount)}</div>
          <div className="text-[11px] mt-0.5">{String(o.payment_status||'').toUpperCase()==='COMPLETED' ? 'PAID' : 'UNPAID'}</div>
        </div>
      </div>

      {o.notes && (
        <div className="mt-2 text-xs"><span className="text-gray-600">Special Instructions:</span> {o.notes}</div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {String(o.status||'').toUpperCase().includes('PENDING') && (
          <button className="px-2 py-1 text-xs bg-yellow-600/10 rounded" onClick={() => onAction('accept', o.id)}>Accept</button>
        )}
        {String(o.status||'').toUpperCase().includes('CONFIRMED') && (
          <button className="px-2 py-1 text-xs bg-orange-600/10 rounded" onClick={() => onAction('start', o.id)}>Start Preparing</button>
        )}
        {(String(o.status||'').toUpperCase().includes('PREPARING') || String(o.status||'').toUpperCase().includes('CONFIRMED')) && (
          <button className="px-2 py-1 text-xs bg-green-600/10 rounded" onClick={() => onAction('ready', o.id)}>Ready</button>
        )}
        {!String(o.status||'').toUpperCase().includes('COMPLETED') && (
          <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={() => onAction('complete', o.id)}>Complete</button>
        )}
      </div>
    </div>
  )
}
