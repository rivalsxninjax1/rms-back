import { useState } from 'react'
import { usePaymentAnalytics, usePaymentIntents, useRefund, useCancelPaymentIntent, useWebhookEvents, usePayments, useRefunds } from '../hooks/payments'
import { Link } from 'react-router-dom'

export default function Payments() {
  const [activeTab, setActiveTab] = useState('payments')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  
  const { data: analytics } = usePaymentAnalytics()
  const { data: payments, isLoading: paymentsLoading } = usePayments()
  const { data: intents, isLoading: intentsLoading } = usePaymentIntents({ q: searchTerm })
  const { data: refunds, isLoading: refundsLoading } = useRefunds()
  const { data: webhookEvents, isLoading: webhooksLoading } = useWebhookEvents()
  const refund = useRefund()
  const cancel = useCancelPaymentIntent()

  const tabs = [
    { id: 'payments', label: 'Payments', count: payments?.length || 0 },
    { id: 'intents', label: 'Payment Intents', count: intents?.length || 0 },
    { id: 'refunds', label: 'Refunds', count: refunds?.length || 0 },
    { id: 'webhooks', label: 'Webhook Events', count: webhookEvents?.length || 0 },
    { id: 'reconciliation', label: 'Reconciliation', count: 0 }
  ]

  const renderPayments = () => {
    if (paymentsLoading) return <div className="p-4">Loading payments...</div>
    
    const filteredPayments = payments?.filter((payment: any) => {
      const matchesSearch = payment.id.toString().includes(searchTerm) || 
                           payment.order?.id.toString().includes(searchTerm)
      const matchesStatus = statusFilter === 'all' || payment.status === statusFilter
      return matchesSearch && matchesStatus
    }) || []

    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="flex space-x-4">
            <input
              type="text"
              placeholder="Search by payment or order ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md"
            />
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="refunded">Refunded</option>
            </select>
          </div>
        </div>

        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Payment ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Order</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Method</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredPayments.map((payment: any) => (
                <tr key={payment.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">#{payment.id}</td>
                  <td className="px-4 py-3 text-sm">
                    <Link to={`/orders/${payment.order?.id}`} className="text-blue-600 hover:underline">
                      Order #{payment.order?.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">${payment.amount}</td>
                  <td className="px-4 py-3 text-sm">{payment.method}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      payment.status === 'completed' ? 'bg-green-100 text-green-800' :
                      payment.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      payment.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {payment.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(payment.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex space-x-2">
                      <button className="text-blue-600 hover:underline">View</button>
                      {payment.status === 'completed' && (
                        <button className="text-red-600 hover:underline">Refund</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderIntents = () => {
    if (intentsLoading) return <div className="p-4">Loading payment intents...</div>
    
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <input
            type="text"
            placeholder="Search payment intents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md"
          />
        </div>
        
        <div className="bg-white border rounded">
          <div className="divide-y">
            {intents?.map((pi:any) => (
              <div key={pi.id} className="px-4 py-2 flex items-center justify-between">
                <div className="text-sm">
                  <div className="font-medium">{pi.stripe_payment_intent_id} · ${pi.amount_cents/100} · {pi.status}</div>
                  <div className="text-gray-500">{pi.currency?.toUpperCase()} · {pi.user || 'guest'} · {pi.created_at}</div>
                </div>
                <div className="flex gap-2">
                  <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={()=>cancel.mutate(pi.stripe_payment_intent_id)}>Cancel</button>
                  <button className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded" onClick={()=>refund.mutate({ payment_intent_id: pi.stripe_payment_intent_id, amount_cents: null })}>Refund</button>
                </div>
              </div>
            ))}
            {!intents?.length && <div className="px-4 py-4 text-gray-500">No payment intents.</div>}
          </div>
        </div>
      </div>
    )
  }

  const renderRefunds = () => {
    if (refundsLoading) return <div className="p-4">Loading refunds...</div>
    
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Refund ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Payment</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {refunds?.map((refund: any) => (
                <tr key={refund.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">#{refund.id}</td>
                  <td className="px-4 py-3 text-sm">#{refund.payment_id}</td>
                  <td className="px-4 py-3 text-sm font-medium">${refund.amount}</td>
                  <td className="px-4 py-3 text-sm">{refund.reason}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      refund.status === 'succeeded' ? 'bg-green-100 text-green-800' :
                      refund.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      refund.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {refund.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(refund.created_at).toLocaleDateString()}
                  </td>
                </tr>
              )) || []}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderWebhooks = () => {
    if (webhooksLoading) return <div className="p-4">Loading webhook events...</div>
    
    return (
      <div className="bg-white border rounded">
        <div className="px-4 py-2 border-b"><h3 className="font-medium">Webhook Events</h3></div>
        <div className="divide-y">
          {webhookEvents?.map((ev:any)=>(
            <div key={ev.id} className="px-4 py-2 text-sm">
              <div className="font-medium">{ev.event_type} · {ev.event_id} · {ev.processed ? 'processed' : 'pending'}</div>
              <div className="text-gray-500">{ev.created_at}</div>
            </div>
          ))}
          {!webhookEvents?.length && <div className="px-4 py-4 text-gray-500">No events.</div>}
        </div>
      </div>
    )
  }

  const renderReconciliation = () => {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white p-6 rounded-lg border">
            <h3 className="text-lg font-semibold mb-2">Daily Reconciliation</h3>
            <p className="text-3xl font-bold text-green-600">${analytics?.total_processed || 0}</p>
            <p className="text-sm text-gray-600">Total processed today</p>
          </div>
          <div className="bg-white p-6 rounded-lg border">
            <h3 className="text-lg font-semibold mb-2">Pending Settlements</h3>
            <p className="text-3xl font-bold text-yellow-600">$2,340.00</p>
            <p className="text-sm text-gray-600">Awaiting settlement</p>
          </div>
          <div className="bg-white p-6 rounded-lg border">
            <h3 className="text-lg font-semibold mb-2">Failed Transactions</h3>
            <p className="text-3xl font-bold text-red-600">{analytics?.failed || 0}</p>
            <p className="text-sm text-gray-600">Require attention</p>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Reconciliation Actions</h3>
          <div className="space-y-3">
            <button className="w-full md:w-auto px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
              Generate Daily Report
            </button>
            <button className="w-full md:w-auto px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 ml-0 md:ml-3">
              Export Settlement Data
            </button>
            <button className="w-full md:w-auto px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 ml-0 md:ml-3">
              Review Discrepancies
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Payments</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-white border rounded">
          <div className="text-sm text-gray-500">Total Processed</div>
          <div className="text-xl font-semibold">${analytics?.total_processed || 0}</div>
        </div>
        <div className="p-4 bg-white border rounded">
          <div className="text-sm text-gray-500">Succeeded</div>
          <div className="text-xl font-semibold">{analytics?.succeeded || 0}</div>
        </div>
        <div className="p-4 bg-white border rounded">
          <div className="text-sm text-gray-500">Failed</div>
          <div className="text-xl font-semibold">{analytics?.failed || 0}</div>
        </div>
      </div>

      <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-2 px-2 py-1 text-xs bg-gray-200 rounded-full">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      <div>
        {activeTab === 'payments' && renderPayments()}
        {activeTab === 'intents' && renderIntents()}
        {activeTab === 'refunds' && renderRefunds()}
        {activeTab === 'webhooks' && renderWebhooks()}
        {activeTab === 'reconciliation' && renderReconciliation()}
      </div>
    </div>
  )}

