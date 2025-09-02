import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
  const [selectedStatus, setSelectedStatus] = useState<string>('all')
  const [showOrderForm, setShowOrderForm] = useState(false)
  const queryClient = useQueryClient()

  const orders = useQuery({
    queryKey: ['orders', selectedStatus],
    queryFn: async () => {
      const params = selectedStatus !== 'all' ? `?status=${selectedStatus}` : ''
      const response = await api.get<Order[]>(`/orders/${params}`)
      return response.data
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  const updateOrderStatus = useMutation({
    mutationFn: async ({ orderId, status }: { orderId: number; status: string }) => {
      const response = await api.patch(`/orders/${orderId}/`, { status })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })

  const createOrder = useMutation({
    mutationFn: async (orderData: any) => {
      const response = await api.post('/orders/', orderData)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      setShowOrderForm(false)
    },
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
    const statusObj = ORDER_STATUSES.find(s => s.value === status.toLowerCase())
    return statusObj?.color || 'bg-gray-100 text-gray-800'
  }

  const placeSampleOrder = () => {
    const orderData = {
      customer_name: 'John Doe',
      customer_email: 'john@example.com',
      customer_phone: '+1234567890',
      service_type: 'dine_in',
      table_number: 5,
      items: [
        {
          menu_item: 1,
          quantity: 2,
          special_instructions: 'No onions'
        },
        {
          menu_item: 2,
          quantity: 1
        }
      ]
    }
    createOrder.mutate(orderData)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Orders Management</h2>
        <div className="flex space-x-3">
          <button
            onClick={placeSampleOrder}
            disabled={createOrder.isPending}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {createOrder.isPending ? 'Creating...' : 'Create Sample Order'}
          </button>
        </div>
      </div>

      {/* Status Filter */}
      <div className="flex space-x-2 overflow-x-auto">
        <button
          onClick={() => setSelectedStatus('all')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedStatus === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          All Orders
        </button>
        {ORDER_STATUSES.map((status) => (
          <button
            key={status.value}
            onClick={() => setSelectedStatus(status.value)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              selectedStatus === status.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {status.label}
          </button>
        ))}
      </div>

      {/* Error Messages */}
      {createOrder.isError && (
        <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
          Error creating order: {createOrder.error?.message}
        </div>
      )}

      {updateOrderStatus.isError && (
        <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
          Error updating order: {updateOrderStatus.error?.message}
        </div>
      )}

      {/* Orders List */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            {selectedStatus === 'all' ? 'All Orders' : `${ORDER_STATUSES.find(s => s.value === selectedStatus)?.label} Orders`}
            {orders.data && (
              <span className="ml-2 text-sm text-gray-500">({orders.data.length})</span>
            )}
          </h3>
        </div>
        
        {orders.isLoading ? (
          <div className="px-6 py-8 text-center text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            Loading orders...
          </div>
        ) : orders.data?.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No orders found
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {orders.data?.map((order) => (
              <div key={order.id} className="px-6 py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h4 className="text-lg font-medium text-gray-900">Order #{order.id}</h4>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(order.status)}`}>
                        {order.status}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Customer:</span> {order.customer_name || 'Guest'}
                        </p>
                        {order.customer_email && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Email:</span> {order.customer_email}
                          </p>
                        )}
                        {order.customer_phone && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Phone:</span> {order.customer_phone}
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Service:</span> {order.service_type.replace('_', ' ')}
                        </p>
                        {order.table_number && (
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">Table:</span> {order.table_number}
                          </p>
                        )}
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Created:</span> {formatDate(order.created_at)}
                        </p>
                      </div>
                    </div>

                    {/* Order Items */}
                    <div className="mb-4">
                      <h5 className="text-sm font-medium text-gray-900 mb-2">Items:</h5>
                      <div className="space-y-2">
                        {order.items?.map((item) => (
                          <div key={item.id} className="flex justify-between items-center text-sm">
                            <div>
                              <span className="font-medium">{item.menu_item.name}</span>
                              <span className="text-gray-500 ml-2">x{item.quantity}</span>
                              {item.special_instructions && (
                                <div className="text-xs text-gray-500 italic">
                                  Note: {item.special_instructions}
                                </div>
                              )}
                            </div>
                            <span className="font-medium">{formatCurrency(item.subtotal)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="text-lg font-semibold text-gray-900">
                        Total: {formatCurrency(order.total_amount)}
                      </div>
                      
                      {/* Status Update Buttons */}
                      <div className="flex space-x-2">
                        {ORDER_STATUSES.map((status) => {
                          if (status.value === order.status.toLowerCase()) return null
                          return (
                            <button
                              key={status.value}
                              onClick={() => updateOrderStatus.mutate({ orderId: order.id, status: status.value })}
                              disabled={updateOrderStatus.isPending}
                              className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50 transition-colors"
                            >
                              Mark as {status.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}