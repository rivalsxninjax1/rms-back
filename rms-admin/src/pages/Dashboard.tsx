import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface DashboardStats {
  total_orders: number
  total_revenue: number
  pending_orders: number
  completed_orders: number
  active_tables: number
  menu_items: number
}

interface RecentOrder {
  id: number
  customer_name?: string
  total_amount: number
  status: string
  created_at: string
  service_type: string
}

export default function Dashboard() {
  // const qc = useQueryClient()
  const stats = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      try {
        const response = await api.get<DashboardStats>('/dashboard/stats/')
        return response.data
      } catch (error) {
        // Fallback data if endpoint doesn't exist yet
        return {
          total_orders: 0,
          total_revenue: 0,
          pending_orders: 0,
          completed_orders: 0,
          active_tables: 0,
          menu_items: 0
        }
      }
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const recentOrders = useQuery({
    queryKey: ['dashboard', 'recent-orders'],
    queryFn: async () => {
      try {
        const response = await api.get<RecentOrder[]>('/orders/?limit=5&ordering=-created_at')
        return response.data
      } catch (error) {
        return []
      }
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const todayISO = new Date().toISOString().slice(0,10)
  const ordersOverview = useQuery({
    queryKey: ['analytics','orders','overview','today'],
    queryFn: async () => (await api.get('/analytics/orders/overview?days=1')).data,
    refetchInterval: 10000,
  })
  const salesByMethod = useQuery({
    queryKey: ['reports','daily-sales','payments', todayISO],
    queryFn: async () => (await api.get(`/reports/daily-sales/payments?date_from=${todayISO}&date_to=${todayISO}`)).data?.results || [],
    refetchInterval: 15000,
  })
  const reservationsToday = useQuery({
    queryKey: ['reservations','today', todayISO],
    queryFn: async () => (await api.get(`/reservations/?reservation_date=${todayISO}`)).data || [],
    refetchInterval: 15000,
  })

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      case 'confirmed': return 'bg-blue-100 text-blue-800'
      case 'preparing': return 'bg-orange-100 text-orange-800'
      case 'ready': return 'bg-green-100 text-green-800'
      case 'completed': return 'bg-gray-100 text-gray-800'
      case 'cancelled': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <div className="text-sm text-gray-500">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Total Orders</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : stats.data?.total_orders || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Total Revenue</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : formatCurrency(stats.data?.total_revenue || 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Pending Orders</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : stats.data?.pending_orders || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-lg">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Active Tables</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : stats.data?.active_tables || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Menu Items</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : stats.data?.menu_items || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-lg">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Completed Orders</p>
              <p className="text-2xl font-semibold text-gray-900">
                {stats.isLoading ? '...' : stats.data?.completed_orders || 0}
              </p>
            </div>
          </div>
        </div>

        {/* Live Orders by Status */}
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="text-sm font-medium text-gray-600">Live Orders</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            {(() => {
              const br = ordersOverview.data?.status_breakdown || []
              const get = (k:string) => br.find((x:any)=> (x.status||'').toUpperCase()===k)?.count || 0
              const pending = get('PENDING')
              const inprog = get('CONFIRMED') + get('PREPARING') + get('OUT_FOR_DELIVERY')
              const served = get('READY')
              const completed = get('COMPLETED')
              const cancelled = get('CANCELLED') + get('REFUNDED')
              return (
                <>
                  <div className="flex items-center justify-between"><span>Pending</span><span className="font-semibold">{pending}</span></div>
                  <div className="flex items-center justify-between"><span>In Progress</span><span className="font-semibold">{inprog}</span></div>
                  <div className="flex items-center justify-between"><span>Served</span><span className="font-semibold">{served}</span></div>
                  <div className="flex items-center justify-between"><span>Completed</span><span className="font-semibold">{completed}</span></div>
                  <div className="flex items-center justify-between"><span>Cancelled</span><span className="font-semibold">{cancelled}</span></div>
                </>
              )
            })()}
          </div>
        </div>

        {/* Today’s Sales by Method */}
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="text-sm font-medium text-gray-600">Today's Sales</div>
          <div className="mt-3 space-y-1 text-sm">
            {(() => {
              const rows = salesByMethod.data || []
              const sum = (m:string) => {
                const r = rows.find((x:any)=> (x.method||'')===m)
                return r ? r.total : 0
              }
              const cash = sum('cash') || 0
              const pos = sum('pos_card') || 0
              const stripe = sum('stripe') || 0
              return (
                <>
                  <div className="flex items-center justify-between"><span>Cash</span><span className="font-semibold">{formatCurrency(cash)}</span></div>
                  <div className="flex items-center justify-between"><span>POS Card</span><span className="font-semibold">{formatCurrency(pos)}</span></div>
                  <div className="flex items-center justify-between"><span>Stripe</span><span className="font-semibold">{formatCurrency(stripe)}</span></div>
                </>
              )
            })()}
          </div>
        </div>

        {/* Avg Prep Time */}
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="text-sm font-medium text-gray-600">Avg Prep Time</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900">—</div>
          <div className="text-xs text-gray-500">Between start preparing and ready.</div>
        </div>

        {/* Reservations */}
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="text-sm font-medium text-gray-600">Reservations</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            {(() => {
              const list = reservationsToday.data || []
              const now = Date.now()
              const active = list.filter((r:any)=> new Date(r.start_time).getTime() <= now && new Date(r.end_time).getTime() > now && !['cancelled','no_show','completed'].includes(String(r.status||'').toLowerCase())).length
              const today = list.length
              return (
                <>
                  <div className="flex items-center justify-between"><span>Now</span><span className="font-semibold">{active}</span></div>
                  <div className="flex items-center justify-between"><span>Today</span><span className="font-semibold">{today}</span></div>
                </>
              )
            })()}
          </div>
        </div>
      </div>

      {/* Shift Control */}
      <ShiftControl todayISO={todayISO} />

      {/* Recent Orders */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Recent Orders</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {recentOrders.isLoading ? (
            <div className="px-6 py-4 text-center text-gray-500">Loading recent orders...</div>
          ) : recentOrders.data?.length === 0 ? (
            <div className="px-6 py-4 text-center text-gray-500">No recent orders</div>
          ) : (
            recentOrders.data?.map((order) => (
              <div key={order.id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center space-x-4">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Order #{order.id}</p>
                    <p className="text-sm text-gray-500">
                      {order.customer_name || 'Guest'} • {order.service_type}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(order.status)}`}>
                    {order.status}
                  </span>
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900">{formatCurrency(order.total_amount)}</p>
                    <p className="text-sm text-gray-500">{formatDate(order.created_at)}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function ShiftControl({ todayISO }: { todayISO: string }) {
  const qc = useQueryClient()
  const open = useMutation({
    mutationFn: ({ shift, staff, cash_open_cents }: { shift: string; staff: string; cash_open_cents: number }) =>
      api.post('/reports/shifts/open/', { date: todayISO, shift, staff, cash_open_cents }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports','shifts', todayISO] })
  })
  const closeM = useMutation({
    mutationFn: ({ shift, cash_close_cents, cash_sales_cents, notes }: { shift: string; cash_close_cents: number; cash_sales_cents: number; notes?: string }) =>
      api.post('/reports/shifts/close/', { date: todayISO, shift, cash_close_cents, cash_sales_cents, notes: notes||'' }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports','shifts', todayISO] })
  })

  const [shift, setShift] = useState('evening') as any
  const [staff, setStaff] = useState('')
  const [openAmt, setOpenAmt] = useState('0')
  const [closeAmt, setCloseAmt] = useState('0')
  const [cashSales, setCashSales] = useState('0')
  const [notes, setNotes] = useState('')

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-medium text-gray-900">Shift Control</h3>
        <div className="text-xs text-gray-500">{todayISO}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="text-sm font-medium">Open Shift</div>
          <label className="text-xs text-gray-600">Shift
            <input className="mt-1 w-full border rounded px-2 py-1" value={shift} onChange={(e)=>setShift(e.target.value)} />
          </label>
          <label className="text-xs text-gray-600">Staff
            <input className="mt-1 w-full border rounded px-2 py-1" value={staff} onChange={(e)=>setStaff(e.target.value)} />
          </label>
          <label className="text-xs text-gray-600">Cash Float (¢)
            <input type="number" className="mt-1 w-full border rounded px-2 py-1" value={openAmt} onChange={(e)=>setOpenAmt(e.target.value)} />
          </label>
          <button className="px-3 py-1 bg-indigo-600 text-white rounded" disabled={open.isPending} onClick={()=>open.mutate({ shift, staff, cash_open_cents: parseInt(openAmt||'0',10) })}>Open</button>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">Close Shift</div>
          <label className="text-xs text-gray-600">Cash Close (¢)
            <input type="number" className="mt-1 w-full border rounded px-2 py-1" value={closeAmt} onChange={(e)=>setCloseAmt(e.target.value)} />
          </label>
          <label className="text-xs text-gray-600">Cash Sales (¢)
            <input type="number" className="mt-1 w-full border rounded px-2 py-1" value={cashSales} onChange={(e)=>setCashSales(e.target.value)} />
          </label>
          <label className="text-xs text-gray-600">Notes
            <input className="mt-1 w-full border rounded px-2 py-1" value={notes} onChange={(e)=>setNotes(e.target.value)} />
          </label>
          <button className="px-3 py-1 bg-green-600 text-white rounded" disabled={closeM.isPending} onClick={()=>closeM.mutate({ shift, cash_close_cents: parseInt(closeAmt||'0',10), cash_sales_cents: parseInt(cashSales||'0',10), notes })}>Close</button>
        </div>
      </div>
    </div>
  )
}
