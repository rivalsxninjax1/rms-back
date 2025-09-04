import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useOrders, useOrderUpdateStatus, useOrderCancel } from '../hooks/orders'
import { useReceiptLink } from '../hooks/payments'
import api from '../lib/api'

interface Order {
  id: number
  customer_name?: string
  customer_email?: string
  customer_phone?: string
  service_type: string
  table_number?: number
  status: string
  total_amount: number
  created_at: string
  updated_at: string
  items: OrderItem[]
  channel?: string
  payment_status?: string
}

interface OrderItem {
  id: number
  menu_item: {
    id: number
    name: string
    price: number
  }
  quantity: number
  special_instructions?: string
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
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [tableFilter, setTableFilter] = useState<string>('')
  const [paymentMethod, setPaymentMethod] = useState<string>('')
  const [settleFor, setSettleFor] = useState<Order|null>(null)

  const queryClient = useQueryClient()
  const orders = useOrders(statusFilter !== 'all' ? `?status=${statusFilter}` : '')
  const updateOrderStatus = useOrderUpdateStatus()
  const cancelOrder = useOrderCancel()
  // const refundOrder = useOrderRefund()

  const formatCurrency = (amount: number) => new Intl.NumberFormat('en-US', { style:'currency', currency:'USD' }).format(amount)
  const formatDate = (s: string) => new Date(s).toLocaleString()
  const getStatusColor = (status: string) => ORDER_STATUSES.find(s=>s.value===status.toLowerCase())?.color || 'bg-gray-100 text-gray-800'
  const placeSampleOrder = () => alert('Order creation moved to POS/customer flow. Use payment links or POS to create orders.')

  useEffect(() => {
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    }, 30000)
    return () => clearInterval(interval)
  }, [queryClient])

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
    return orders.data.filter((order: Order) => {
      if (channel !== 'ALL' && order.channel !== channel) return false
      if (dateFrom && new Date(order.created_at) < new Date(dateFrom)) return false
      if (dateTo && new Date(order.created_at) > new Date(dateTo + 'T23:59:59')) return false
      if (tableFilter && !order.table_number?.toString().includes(tableFilter)) return false
      if (paymentMethod && order.payment_status !== paymentMethod) return false
      return true
    })
  }, [orders.data, channel, statusFilter, dateFrom, dateTo, tableFilter, paymentMethod])

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

      <div className="bg-white border rounded-md overflow-hidden">
        <div className="px-3 py-2 border-b text-sm text-gray-700">{filtered.length} orders</div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Channel</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Paid</th>
                <th className="px-3 py-2 text-left">Table</th>
                <th className="px-3 py-2 text-left">Total</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {orders.isLoading ? (
                <tr><td className="px-3 py-4" colSpan={8}>Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td className="px-3 py-4 text-gray-500" colSpan={8}>No orders</td></tr>
              ) : filtered.map((order: Order) => (
                <tr key={order.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2">{order.id}</td>
                  <td className="px-3 py-2">{order.channel || '—'}</td>
                  <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-[11px] ${getStatusColor(order.status)}`}>{order.status}</span></td>
                  <td className="px-3 py-2">
                    {String(order.payment_status||'').toUpperCase()==='COMPLETED' ? (
                      <span className="px-2 py-0.5 rounded bg-green-100 text-green-800 text-[11px]">PAID</span>
                    ) : (
                      <button className="px-2 py-0.5 rounded bg-yellow-100 text-yellow-800 text-[11px]" onClick={()=>setSettleFor(order)}>Settle</button>
                    )}
                  </td>
                  <td className="px-3 py-2">{order.table_number || '—'}</td>
                  <td className="px-3 py-2">{formatCurrency(order.total_amount)}</td>
                  <td className="px-3 py-2">{formatDate(order.created_at)}</td>
                  <td className="px-3 py-2 text-right space-x-2">
                    <button className="px-2 py-1 text-xs border rounded" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'in_progress' })}>Start</button>
                    <button className="px-2 py-1 text-xs border rounded" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'served' })}>Serve</button>
                    <button className="px-2 py-1 text-xs border rounded" onClick={()=>updateOrderStatus.mutate({ id: order.id, status: 'completed' })}>Complete</button>
                    <button className="px-2 py-1 text-xs border rounded text-red-700" onClick={()=>askCancel(order.id)}>Cancel</button>
                    <button className="px-2 py-1 text-xs border rounded" onClick={()=>printTicket(order.id)}>Print Ticket</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

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
