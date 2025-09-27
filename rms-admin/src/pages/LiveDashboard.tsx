import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useOrders, useOrderUpdateStatus } from '../hooks/orders'
import { Summary } from '../components/live/Summary'
import { Controls } from '../components/live/Controls'
import { OrderCard } from '../components/live/OrderCard'

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

// styling moved into OrderCard component

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

  return (
    <div className="space-y-4">
      <Summary active={summary.active} pending={summary.pending} preparing={summary.preparing} ready={summary.ready} wsConnected={!!wsRef.current} />
      <Controls mute={mute} setMute={(v)=>{ try{ localStorage.setItem('ordersMute', v ? '1' : '0') }catch{}; setMute(v) }} count={live.length} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {orders.isLoading && (
          <div className="text-gray-500">Loading…</div>
        )}
        {orders.isError && (
          <div className="text-rose-700">Unable to load orders. Ensure you are signed in and have Manager/Cashier/Kitchen/Host role.</div>
        )}
        {!orders.isLoading && live.length === 0 && (
          <div className="text-gray-500">No live online orders</div>
        )}
        {live.map((o) => (
          <OrderCard
            key={o.id}
            // @ts-ignore use shared OrderCard type
            o={o}
            highlight={!!highlights[o.id]}
            formatCurrency={formatCurrency}
            onAction={(a, id) => {
              if (a==='accept') updateOrderStatus.mutate({ id, status: 'in_progress' })
              else if (a==='start') updateOrderStatus.mutate({ id, status: 'in_progress' })
              else if (a==='ready') updateOrderStatus.mutate({ id, status: 'served' })
              else if (a==='complete') updateOrderStatus.mutate({ id, status: 'completed' })
            }}
          />
        ))}
      </div>

      <audio ref={beepRef} preload="auto">
        <source src="data:audio/mp3;base64,//uQZAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcQCA//////////////////////////////8AAAACAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==" type="audio/mpeg" />
      </audio>
    </div>
  )
}
