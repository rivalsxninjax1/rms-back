import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useOrders, useOrderUpdateStatus } from '../hooks/orders'

interface OrderItem {
  id: number
  quantity: number
  menu_item?: { id: number; name: string }
  modifiers?: Array<{ id?: number; name?: string; price?: number }>
  notes?: string
  special_instructions?: string
  line_total?: number
  subtotal?: number
}

interface Order {
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

export default function LiveDashboard() {
  const [mute, setMute] = useState<boolean>(() => {
    try { return localStorage.getItem('ordersMute') === '1' } catch { return false }
  })
  const [highlights, setHighlights] = useState<Record<number, number>>({})
  const wsRef = useRef<WebSocket | null>(null)
  const beepRef = useRef<HTMLAudioElement | null>(null)
  const queryClient = useQueryClient()

  const playBeep = () => {
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const o = ctx.createOscillator(); const g = ctx.createGain()
      o.type = 'sine'; o.frequency.setValueAtTime(880, ctx.currentTime)
      o.connect(g); g.connect(ctx.destination)
      g.gain.setValueAtTime(0.0001, ctx.currentTime)
      g.gain.exponentialRampToValueAtTime(0.05, ctx.currentTime + 0.01)
      o.start(); o.stop(ctx.currentTime + 0.15)
    } catch { beepRef.current?.play().catch(()=>{}) }
  }

  // Fetch all orders (we will filter to ONLINE + active)
  const orders = useOrders('')
  const updateOrderStatus = useOrderUpdateStatus()

  useEffect(() => {
    // periodic refresh + clear expired highlights
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      const now = Date.now()
      setHighlights((h) => {
        const next: Record<number, number> = {}
        for (const k in h) { const id = Number(k); if (h[id] > now) next[id] = h[id] }
        return next
      })
    }, 15000)
    return () => clearInterval(interval)
  }, [queryClient])

  // WebSocket live feed
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/ws/orders/`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data || '{}') as any
        const evName = String(msg.event || '')
        const id = Number(msg.order_id || msg.id)
        if (['order_created','order_updated','order_status_changed','order_paid'].includes(evName)) {
          queryClient.invalidateQueries({ queryKey: ['orders'] })
          if (evName === 'order_created' && id) {
            setHighlights((h) => ({ ...h, [id]: Date.now() + 7000 }))
            if (!mute) playBeep()
          }
        }
      } catch {}
    }
    ws.onerror = () => {}
    ws.onclose = () => { wsRef.current = null }
    return () => ws.close()
  }, [mute, queryClient])

  const formatCurrency = (amount: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)

  // Only ONLINE and not completed/cancelled; newest first
  const live = useMemo<Order[]>(() => {
    const data: Order[] = orders.data || []
    return data
      .filter(o => (o.channel === 'ONLINE') && !['completed','cancelled'].includes(String(o.status||'').toLowerCase()))
      .sort((a: Order, b: Order) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }, [orders.data])

  const summary = useMemo<{ active: number; pending: number; preparing: number; ready: number }>(() => {
    const counts = { active: 0, pending: 0, preparing: 0, ready: 0 }
    counts.active = live.length
    for (const o of live) {
      const s = String(o.status||'').toLowerCase()
      if (s.includes('pending')) counts.pending++
      else if (s.includes('preparing') || s.includes('confirmed') || s.includes('out_for_delivery')) counts.preparing++
      else if (s.includes('ready') || s.includes('served')) counts.ready++
    }
    return counts
  }, [live])

  const actionBtn = (label: string, onClick: () => void, className = '') => (
    <button onClick={onClick} className={`px-2 py-1 text-xs border rounded ${className}`}>{label}</button>
  )

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border rounded-md">
        <div className="px-3 py-2 flex items-center justify-between text-sm">
          <div className="font-medium">Active Orders: {summary.active} | Preparing: {summary.preparing} | Ready: {summary.ready}</div>
          <div className="flex items-center gap-3">
            <button onClick={()=>{ setMute(m=>{ try{ localStorage.setItem('ordersMute', !m ? '1':'0') }catch{} return !m }) }} className="px-2 py-1 border rounded text-xs">{mute ? 'Unmute' : 'Mute'}</button>
            <span className="text-gray-500">{live.length} shown</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {orders.isLoading && (
          <div className="text-gray-500">Loading…</div>
        )}
        {!orders.isLoading && live.length === 0 && (
          <div className="text-gray-500">No live online orders</div>
        )}
        {live.map((o) => {
          const highlight = highlights[o.id]
          return (
            <div key={o.id} className={`rounded-lg border p-3 shadow-sm ${statusColor(o.status)} ${highlight ? 'animate-pulse' : ''}`}>
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
                {String(o.status||'').toUpperCase().includes('PENDING') && actionBtn('Accept', () => updateOrderStatus.mutate({ id: o.id, status: 'in_progress' }), 'bg-yellow-600/10')}
                {String(o.status||'').toUpperCase().includes('CONFIRMED') && actionBtn('Start Preparing', () => updateOrderStatus.mutate({ id: o.id, status: 'in_progress' }), 'bg-orange-600/10')}
                {(String(o.status||'').toUpperCase().includes('PREPARING') || String(o.status||'').toUpperCase().includes('CONFIRMED')) && actionBtn('Ready', () => updateOrderStatus.mutate({ id: o.id, status: 'served' }), 'bg-green-600/10')}
                {!String(o.status||'').toUpperCase().includes('COMPLETED') && actionBtn('Complete', () => updateOrderStatus.mutate({ id: o.id, status: 'completed' }))}
              </div>
            </div>
          )
        })}
      </div>

      <audio ref={beepRef} preload="auto">
        <source src="data:audio/mp3;base64,//uQZAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcQCA//////////////////////////////8AAAACAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==" type="audio/mpeg" />
      </audio>
    </div>
  )
}
