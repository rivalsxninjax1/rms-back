import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useOrders, useOrderUpdateStatus, useOrderCancel } from '../hooks/orders'
import { useReceiptLink } from '../hooks/payments'
import api from '../lib/api'

interface Order {
  id: number
  order_number?: string
  customer_name?: string
  customer_email?: string
  customer_phone?: string
  delivery_option?: string
  table_number?: number
  status: string
  total_amount: number
  created_at: string
  updated_at: string
  items: OrderItem[]
  channel?: string
  payment_status?: string
  source?: string
}

interface OrderItem {
  id: number
  menu_item: {
    id: number
    name: string
    price: number
  }
  quantity: number
  // Backend uses 'notes' for special instructions; keep backward compat
  notes?: string
  special_instructions?: string
  modifiers?: any[]
  subtotal: number
}

const ORDER_STATUSES = [
  { value: 'pending', label: 'Pending', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'confirmed', label: 'Confirmed', color: 'bg-blue-100 text-blue-800' },
  { value: 'preparing', label: 'Preparing', color: 'bg-orange-100 text-orange-800' },
  { value: 'ready', label: 'Ready', color: 'bg-green-100 text-green-800' },
  { value: 'completed', label: 'Completed', color: 'bg-gray-100 text-gray-800' },
  { value: 'cancelled', label: 'Cancelled', color: 'bg-red-100 text-red-800' }
]

export default function Orders() {
  const [channel, setChannel] = useState<'ALL'|'IN_HOUSE'|'ONLINE'>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [serviceFilter, setServiceFilter] = useState<string>('all') // DINE_IN | PICKUP | DELIVERY
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [tableFilter, setTableFilter] = useState<string>('')
  const [paymentMethod, setPaymentMethod] = useState<string>('')
  const [settleFor, setSettleFor] = useState<Order|null>(null)
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  const [mute, setMute] = useState<boolean>(() => {
    try { return localStorage.getItem('ordersMute') === '1' } catch { return false }
  })
  const [highlights, setHighlights] = useState<Record<number, number>>({}) // id -> expiresAt ms
  const wsRef = useRef<WebSocket | null>(null)
  const beepRef = useRef<HTMLAudioElement | null>(null)
  function playBeep(){
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

  const queryClient = useQueryClient()
  // Build query string for server-side filtering where possible
  const queryParams = (() => {
    const qs = new URLSearchParams()
    if (statusFilter !== 'all') qs.set('status', statusFilter)
    if (serviceFilter !== 'all') qs.set('delivery_option', serviceFilter)
    return qs.toString() ? `?${qs.toString()}` : ''
  })()
  const orders = useOrders(queryParams)
  const updateOrderStatus = useOrderUpdateStatus()
  const cancelOrder = useOrderCancel()
  // const refundOrder = useOrderRefund()

  const formatCurrency = (amount: number) => new Intl.NumberFormat('en-US', { style:'currency', currency:'USD' }).format(amount)
  const formatDate = (s: string) => new Date(s).toLocaleString()
  const getStatusColor = (status: string) => {
    const s = String(status||'').toLowerCase()
    if (s.includes('pending')) return 'bg-yellow-100 text-yellow-800'    // New → Yellow
    if (s.includes('preparing') || s.includes('confirmed') || s.includes('out_for_delivery')) return 'bg-orange-100 text-orange-800' // Preparing → Orange
    if (s.includes('ready') || s.includes('served')) return 'bg-green-100 text-green-800'   // Ready → Green
    if (s.includes('completed')) return 'bg-gray-100 text-gray-800'      // Completed → Gray
    if (s.includes('cancel')) return 'bg-red-100 text-red-800'
    return 'bg-gray-100 text-gray-800'
  }
  const serviceLabel = (o: Order) => {
    const d = (o.delivery_option||'').toUpperCase()
    if (d === 'DINE_IN') return `DINE_IN${o.table_number? ' · Table '+o.table_number : ''}`
    if (d === 'PICKUP') return 'PICKUP'
    if (d === 'DELIVERY') return 'DELIVERY'
    return o.channel || '—'
  }
  const providerLabel = (o: Order) => {
    const src = String(o.source||'').toUpperCase()
    if (src.includes('UBER')) return 'Uber Eats'
    if (src.includes('DOORDASH')) return 'DoorDash'
    if (src.includes('WEB')) return 'Website'
    if (src.includes('MOBILE')) return 'Mobile'
    if (src.includes('WAITER')) return 'POS/Waiter'
    if (src.includes('ADMIN')) return 'Admin'
    return o.channel === 'ONLINE' ? 'Online' : (o.channel || '—')
  }
  const placeSampleOrder = () => alert('Order creation moved to POS/customer flow. Use payment links or POS to create orders.')

  useEffect(() => {
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      // Clear expired highlights
      const now = Date.now()
      setHighlights((h) => {
        const next: Record<number, number> = {}
        for (const k in h) { const id = Number(k); if (h[id] > now) next[id] = h[id] }
        return next
      })
    }, 15000)
    return () => clearInterval(interval)
  }, [queryClient])

  // WebSocket live updates
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
            // Add highlight and play sound
            setHighlights((h) => ({ ...h, [id]: Date.now() + 7000 }))
            if (!mute) playBeep()
          }
        }
      } catch {}
    }
    ws.onerror = () => {}
    ws.onclose = () => { wsRef.current = null }
    return () => { try { ws.close() } catch {} }
  }, [queryClient, mute])

  useEffect(() => {
    try { localStorage.setItem('ordersMute', mute ? '1' : '0') } catch {}
  }, [mute])

  const askCancel = (orderId: number) => {
    if (confirm('Cancel this order?')) {
      cancelOrder.mutate({ id: orderId, reason: 'Cancelled by admin' })
    }
  }

  // const askRefund = (orderId: number) => {
  //   if (confirm('Refund this order?')) {
  //     refundOrder.mutate({ id: orderId, amount: '0.00' })
  //   }
  // }

  const printTicket = (orderId: number) => {
    window.open(`/api/orders/${orderId}/ticket/`, '_blank')
  }

  const filtered: Order[] = useMemo(() => {
    if (!orders.data) return []
    const list = orders.data.filter((order: Order) => {
      if (channel !== 'ALL' && order.channel !== channel) return false
      if (serviceFilter !== 'all' && (String(order.delivery_option||'').toUpperCase() !== serviceFilter)) return false
      if (dateFrom && new Date(order.created_at) < new Date(dateFrom)) return false
      if (dateTo && new Date(order.created_at) > new Date(dateTo + 'T23:59:59')) return false
      if (tableFilter && !order.table_number?.toString().includes(tableFilter)) return false
      if (paymentMethod && order.payment_status !== paymentMethod) return false
      return true
    })
    // Ensure newest first
    return list.sort((a: Order, b: Order) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }, [orders.data, channel, statusFilter, dateFrom, dateTo, tableFilter, paymentMethod, serviceFilter])

  // Summary counts (active excludes completed/cancelled)
  const summary = useMemo<{ active: number; pending: number; preparing: number; ready: number }>(() => {
    const active = filtered.filter(o => !['completed','cancelled'].includes(String(o.status||'').toLowerCase()))
    const counts: { pending: number; preparing: number; ready: number } = { pending:0, preparing:0, ready:0 }
    for (const o of active) {
      const s = String(o.status||'').toLowerCase()
      if (s.includes('pending')) counts.pending++
      else if (s.includes('preparing') || s.includes('confirmed') || s.includes('out_for_delivery')) counts.preparing++
      else if (s.includes('ready')) counts.ready++
    }
    return { active: active.length, ...counts }
  }, [filtered])

  async function settleOffline(order: Order, method: 'cash'|'pos_card') {
    try {
      await api.post(`/api/orders/${order.id}/settle/`, { method })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      setSettleFor(null)
    } catch (error) {
      alert('Settlement failed')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Orders Management</h2>
        <div className="flex space-x-3">
          <button onClick={placeSampleOrder} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">Create Sample Order</button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 p-3 border rounded-md bg-white">
        <div>
          <label className="block text-xs text-gray-600">Channel</label>
          <select value={channel} onChange={(e)=>setChannel(e.target.value as any)} className="border rounded px-2 py-1 text-sm">
            <option>ALL</option>
            <option>IN_HOUSE</option>
            <option>ONLINE</option>
          </select>
        </div>
      <div>
          <label className="block text-xs text-gray-600">Service</label>
          <select value={serviceFilter} onChange={(e)=>setServiceFilter(e.target.value)} className="border rounded px-2 py-1 text-sm">
            <option value="all">All</option>
            <option value="DELIVERY">Delivery</option>
            <option value="PICKUP">Pickup</option>
            <option value="DINE_IN">Dine-in</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-600">Status</label>
          <select value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)} className="border rounded px-2 py-1 text-sm">
            <option value="all">All</option>
            {ORDER_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-600">From</label>
          <input type="date" value={dateFrom} onChange={(e)=>setDateFrom(e.target.value)} className="border rounded px-2 py-1 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-600">To</label>
          <input type="date" value={dateTo} onChange={(e)=>setDateTo(e.target.value)} className="border rounded px-2 py-1 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-600">Table</label>
          <input value={tableFilter} onChange={(e)=>setTableFilter(e.target.value)} placeholder="e.g., 12" className="border rounded px-2 py-1 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-600">Payment</label>
          <select value={paymentMethod} onChange={(e)=>setPaymentMethod(e.target.value)} className="border rounded px-2 py-1 text-sm">
            <option value="">All</option>
            <option value="CASH">Cash</option>
            <option value="CARD">Card</option>
            <option value="DIGITAL_WALLET">Wallet</option>
            <option value="LOYALTY_POINTS">Loyalty</option>
          </select>
        </div>
      </div>

      <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border rounded-md">
        <div className="px-3 py-2 flex items-center justify-between text-sm">
          <div className="font-medium">Active Orders: {summary.active} | Preparing: {summary.preparing} | Ready: {summary.ready}</div>
          <div className="flex items-center gap-3">
            <button onClick={()=>setMute(m=>!m)} className="px-2 py-1 border rounded text-xs">{mute ? 'Unmute' : 'Mute'}</button>
            <span className="text-gray-500">{filtered.length} shown</span>
          </div>
        </div>
      </div>

      <div className="bg-white border rounded-md overflow-hidden">
        <div className="px-3 py-2 border-b text-sm text-gray-700">{filtered.length} orders</div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Customer</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Paid</th>
                <th className="px-3 py-2 text-left">Service</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Total</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {orders.isLoading ? (
                <tr><td className="px-3 py-4" colSpan={9}>Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td className="px-3 py-4 text-gray-500" colSpan={9}>No orders</td></tr>
              ) : filtered.map((order: Order) => (
                <>
                <tr key={order.id} className={`hover:bg-gray-50 ${highlights[order.id] ? 'animate-pulse bg-yellow-50' : ''}`}>
                  <td className="px-3 py-2">
                    <button className="underline" onClick={()=>setExpanded(e=>({...e,[order.id]:!e[order.id]}))}>#{order.id}{order.order_number ? ` · ${order.order_number}` : ''}</button>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{order.customer_name || '—'}</div>
                    <div className="text-xs text-gray-500">{order.customer_phone || order.customer_email || order.channel || '—'}</div>
                  </td>
                  <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-[11px] ${getStatusColor(order.status)}`}>{order.status}</span></td>
                  <td className="px-3 py-2">
                    {String(order.payment_status||'').toUpperCase()==='COMPLETED' ? (
                      <span className="px-2 py-0.5 rounded bg-green-100 text-green-800 text-[11px]">PAID</span>
                    ) : (
                      <button className="px-2 py-0.5 rounded bg-yellow-100 text-yellow-800 text-[11px]" onClick={()=>setSettleFor(order)}>Settle</button>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div>{serviceLabel(order)}</div>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-700">{providerLabel(order)}</td>
                  <td className="px-3 py-2">{formatCurrency(order.total_amount)}</td>
                  <td className="px-3 py-2">{formatDate(order.created_at)}</td>
                  <td className="px-3 py-2 text-right space-x-2">
                    {String(order.status||'').toUpperCase().includes('PENDING') && (
                      <button className="px-2 py-1 text-xs border rounded bg-yellow-600/10" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'in_progress' })}>Accept</button>
                    )}
                    {String(order.status||'').toUpperCase().includes('CONFIRMED') && (
                      <button className="px-2 py-1 text-xs border rounded bg-orange-600/10" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'in_progress' })}>Start Preparing</button>
                    )}
                    {(
                      String(order.status||'').toUpperCase().includes('PREPARING') ||
                      String(order.status||'').toUpperCase().includes('CONFIRMED')
                    ) && (
                      <button className="px-2 py-1 text-xs border rounded bg-green-600/10" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'served' })}>Ready</button>
                    )}
                    {!String(order.status||'').toUpperCase().includes('COMPLETED') && (
                      <button className="px-2 py-1 text-xs border rounded" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'completed' })}>Complete</button>
                    )}
                    <button className="px-2 py-1 text-xs border rounded text-red-700" onClick={()=>askCancel(order.id)}>Cancel</button>
                    <button className="px-2 py-1 text-xs border rounded" onClick={()=>printTicket(order.id)}>Print Ticket</button>
                  </td>
                </tr>
                {expanded[order.id] && (
                  <tr className="bg-gray-50/60">
                    <td colSpan={9} className="px-3 py-3">
                      <div className="grid md:grid-cols-3 gap-4">
                        <div>
                          <div className="text-xs text-gray-600 mb-1">Items</div>
                          <ul className="space-y-1">
                            {order.items?.map((it: any) => (
                              <li key={it.id}>
                                <div className="flex justify-between">
                                  <span>
                                    {it.quantity}× {it.menu_item?.name}
                                    {(it.notes || it.special_instructions) ? (
                                      <span className="text-xs text-gray-600"> — {(it.notes || it.special_instructions)}</span>
                                    ) : null}
                                  </span>
                                  <span className="text-gray-600">{formatCurrency((it.subtotal || it.line_total || 0) as number)}</span>
                                </div>
                                {it.modifiers && it.modifiers.length > 0 && (
                                  <div className="pl-5 text-xs text-gray-500">
                                    {(it.modifiers||[]).map((m:any, idx:number)=>(
                                      <div key={idx}>• {m.name || m.id}{m.price ? ` (+${formatCurrency(Number(m.price))})` : ''}</div>
                                    ))}
                                  </div>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <div className="text-xs text-gray-600 mb-1">Customer</div>
                          <div className="text-sm">{order.customer_name || '—'}</div>
                          <div className="text-xs text-gray-600">{order.customer_phone || '—'}</div>
                          <div className="text-xs text-gray-600">{order.customer_email || '—'}</div>
                        </div>
                         <div>
                           <div className="text-xs text-gray-600 mb-1">Details</div>
                          <div className="text-xs">Service: {order.delivery_option || (order.table_number ? `DINE_IN (Table ${order.table_number})` : '—')}</div>
                          <div className="text-xs">Placed: {formatDate(order.created_at)}</div>
                          <div className="text-xs">Payment: {order.payment_status || '—'}</div>
                          {(order as any)['notes'] && (
                            <div className="text-xs">Special Instructions: {(order as any)['notes']}</div>
                          )}
                          <div className="text-xs">Source: {providerLabel(order)}</div>
                         </div>
                      </div>
                    </td>
                  </tr>
                )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* silent beep */}
      <audio ref={beepRef} preload="auto">
        <source src="data:audio/mp3;base64,//uQZAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcQCA//////////////////////////////8AAAACAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==" type="audio/mpeg" />
      </audio>

      {settleFor && (
        <div className="fixed inset-0 bg-black/30 flex items-end md:items-center md:justify-center z-50" onClick={()=>setSettleFor(null)}>
          <div className="bg-white w-full md:w-[420px] max-h-[90vh] overflow-auto rounded-t-lg md:rounded-lg shadow-xl" onClick={(e)=>e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between">
              <div className="font-semibold">Settle Order #{settleFor.id}</div>
              <button onClick={()=>setSettleFor(null)} className="text-gray-500">✕</button>
            </div>
            <div className="p-4 space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>Total</span><span className="font-semibold">{formatCurrency(settleFor.total_amount)}</span></div>
              <div className="text-xs text-gray-600">Channel: {settleFor.channel || '—'}</div>
              {settleFor.channel === 'ONLINE' && (
                <a className="inline-block px-3 py-1 border rounded text-blue-700" href={useReceiptLink(settleFor.id)} target="_blank" rel="noreferrer">Open Invoice</a>
              )}
              <div className="pt-2 border-t">
                <div className="text-xs text-gray-600 mb-2">Offline Payment</div>
                <div className="flex gap-2">
                  <button className="px-3 py-1 border rounded" onClick={()=>settleOffline(settleFor!, 'cash')}>Cash</button>
                  <button className="px-3 py-1 border rounded" onClick={()=>settleOffline(settleFor!, 'pos_card')}>POS Card</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
