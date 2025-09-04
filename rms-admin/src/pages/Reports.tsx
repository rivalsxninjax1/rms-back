import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

// interface SalesReport {
//   total_revenue: number
//   total_orders: number
//   average_order_value: number
//   top_selling_items: Array<{
//     name: string
//     quantity_sold: number
//     revenue: number
//   }>
//   daily_sales: Array<{
//     date: string
//     revenue: number
//     orders: number
//   }>
//   payment_methods: Array<{
//     method: string
//     count: number
//     total: number
//   }>
// }

// interface InventoryReport {
//   low_stock_items: Array<{
//     name: string
//     current_stock: number
//     minimum_stock: number
//   }>
//   out_of_stock_items: Array<{
//     name: string
//     sku: string
//   }>
//   total_inventory_value: number
// }

// interface CustomerReport {
//   total_customers: number
//   new_customers_this_month: number
//   repeat_customers: number
//   customer_retention_rate: number
// }

const REPORT_PERIODS = [
  { value: '7', label: 'Last 7 Days' },
  { value: '30', label: 'Last 30 Days' },
  { value: '90', label: 'Last 3 Months' },
  { value: '365', label: 'Last Year' }
]

export default function Reports() {
  const [selectedPeriod, setSelectedPeriod] = useState('30')
  const [activeTab, setActiveTab] = useState<'sales' | 'inventory' | 'customers'>('sales')

  const { data: salesReport, isLoading: salesLoading } = useQuery({
    queryKey: ['reports', 'sales', selectedPeriod],
    queryFn: () => api.get(`/reports/sales/?period=${selectedPeriod}`).then((res: any) => res.data)
  })

  const { data: inventoryReport, isLoading: inventoryLoading } = useQuery({
    queryKey: ['reports', 'inventory'],
    queryFn: () => api.get('/reports/inventory/').then((res: any) => res.data)
  })

  const { data: customerReport, isLoading: customerLoading } = useQuery({
    queryKey: ['reports', 'customers', selectedPeriod],
    queryFn: () => api.get(`/reports/customers/?period=${selectedPeriod}`).then((res: any) => res.data)
  })

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  }

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    })
  }

  const StatCard = ({ title, value, subtitle, trend }: {
    title: string
    value: string | number
    subtitle?: string
    trend?: { value: number; isPositive: boolean }
  }) => (
    <div className="bg-white p-6 rounded-lg shadow">
      <h3 className="text-sm font-medium text-gray-500 mb-2">{title}</h3>
      <div className="flex items-baseline justify-between">
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        {trend && (
          <span className={`text-sm font-medium ${
            trend.isPositive ? 'text-green-600' : 'text-red-600'
          }`}>
            {trend.isPositive ? '+' : ''}{trend.value.toFixed(1)}%
          </span>
        )}
      </div>
      {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
    </div>
  )

  const TabButton = ({ label, isActive, onClick }: {
    label: string
    isActive: boolean
    onClick: () => void
  }) => (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg ${
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Reports & Analytics</h1>
        <select
          value={selectedPeriod}
          onChange={(e) => setSelectedPeriod(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {REPORT_PERIODS.map(period => (
            <option key={period.value} value={period.value}>{period.label}</option>
          ))}
        </select>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-2">
        <TabButton
          label="Sales"
          isActive={activeTab === 'sales'}
          onClick={() => setActiveTab('sales')}
        />
        <TabButton
          label="Inventory"
          isActive={activeTab === 'inventory'}
          onClick={() => setActiveTab('inventory')}
        />
        <TabButton
          label="Customers"
          isActive={activeTab === 'customers'}
          onClick={() => setActiveTab('customers')}
        />
      </div>

      {/* Sales Tab */}
      {activeTab === 'sales' && (
        <div className="space-y-6">
          {salesLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : salesReport ? (
            <>
              {/* Sales Overview */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                  title="Total Revenue"
                  value={formatCurrency(salesReport.total_revenue)}
                  subtitle={`From ${salesReport.total_orders} orders`}
                />
                <StatCard
                  title="Total Orders"
                  value={salesReport.total_orders.toLocaleString()}
                />
                <StatCard
                  title="Average Order Value"
                  value={formatCurrency(salesReport.average_order_value)}
                />
              </div>

              {/* Daily Sales Chart */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Daily Sales</h3>
                <div className="space-y-2">
                  {salesReport.daily_sales?.map((day: any, index: number) => (
                     <div key={index} className="flex items-center justify-between py-2">
                       <span className="text-sm text-gray-600">{formatDate(day.date)}</span>
                       <div className="flex items-center space-x-4">
                         <span className="text-sm font-medium">{formatCurrency(day.revenue)}</span>
                         <span className="text-xs text-gray-500">({day.orders} orders)</span>
                         <div className="w-32 bg-gray-200 rounded-full h-2">
                           <div
                             className="bg-blue-600 h-2 rounded-full"
                             style={{
                               width: `${Math.min((day.revenue / Math.max(...salesReport.daily_sales.map((d: any) => d.revenue))) * 100, 100)}%`
                             }}
                           ></div>
                         </div>
                       </div>
                     </div>
                   ))}
                </div>
              </div>

              {/* Top Selling Items */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Top Selling Items</h3>
                <div className="space-y-3">
                  {salesReport.top_selling_items?.map((item: any, index: number) => (
                     <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                       <div>
                         <span className="font-medium text-gray-900">{item.name}</span>
                         <span className="text-sm text-gray-500 ml-2">({item.quantity_sold} sold)</span>
                       </div>
                       <span className="font-medium text-green-600">{formatCurrency(item.revenue)}</span>
                     </div>
                   ))}
                </div>
              </div>

              {/* Payment Methods */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Payment Methods</h3>
                <div className="space-y-3">
                  {salesReport.payment_methods?.map((method: any, index: number) => (
                     <div key={index} className="flex items-center justify-between py-2">
                       <span className="font-medium text-gray-900 capitalize">{method.method}</span>
                       <div className="text-right">
                         <div className="font-medium">{formatCurrency(method.total)}</div>
                         <div className="text-sm text-gray-500">({method.count} transactions)</div>
                       </div>
                     </div>
                   ))}
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500">No sales data available</p>
            </div>
          )}
        </div>
      )}

      {/* Inventory Tab */}
      {activeTab === 'inventory' && (
        <div className="space-y-6">
          {inventoryLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : inventoryReport ? (
            <>
              {/* Inventory Overview */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                  title="Total Inventory Value"
                  value={formatCurrency(inventoryReport.total_inventory_value)}
                />
                <StatCard
                  title="Low Stock Items"
                  value={inventoryReport.low_stock_items?.length || 0}
                  subtitle="Items below minimum stock"
                />
                <StatCard
                  title="Out of Stock"
                  value={inventoryReport.out_of_stock_items?.length || 0}
                  subtitle="Items completely out of stock"
                />
              </div>

              {/* Low Stock Items */}
              {inventoryReport.low_stock_items && inventoryReport.low_stock_items.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Low Stock Items</h3>
                  <div className="space-y-3">
                    {inventoryReport.low_stock_items.map((item: any, index: number) => (
                       <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                         <span className="font-medium text-gray-900">{item.name}</span>
                         <div className="text-right">
                           <div className="text-sm">
                             <span className="text-red-600 font-medium">{item.current_stock}</span>
                             <span className="text-gray-500"> / {item.minimum_stock} min</span>
                           </div>
                         </div>
                       </div>
                     ))}
                  </div>
                </div>
              )}

              {/* Out of Stock Items */}
              {inventoryReport.out_of_stock_items && inventoryReport.out_of_stock_items.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Out of Stock Items</h3>
                  <div className="space-y-3">
                    {inventoryReport.out_of_stock_items.map((item: any, index: number) => (
                       <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                         <span className="font-medium text-gray-900">{item.name}</span>
                         <span className="text-sm text-gray-500">{item.sku}</span>
                       </div>
                     ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500">No inventory data available</p>
            </div>
          )}
        </div>
      )}

      {/* Customers Tab */}
      {activeTab === 'customers' && (
        <div className="space-y-6">
          {customerLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : customerReport ? (
            <>
              {/* Customer Overview */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard
                  title="Total Customers"
                  value={customerReport.total_customers.toLocaleString()}
                />
                <StatCard
                  title="New Customers"
                  value={customerReport.new_customers_this_month.toLocaleString()}
                  subtitle="This month"
                />
                <StatCard
                  title="Repeat Customers"
                  value={customerReport.repeat_customers.toLocaleString()}
                />
                <StatCard
                  title="Retention Rate"
                  value={formatPercentage(customerReport.customer_retention_rate)}
                />
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500">No customer data available</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}