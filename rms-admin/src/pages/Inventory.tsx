import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface InventoryItem {
  id: number
  name: string
  sku: string
  current_stock: number
  minimum_stock: number
  unit: string
  cost_per_unit: number
  supplier?: string
  last_updated: string
}

interface StockAdjustment {
  item_id: number
  adjustment_type: 'add' | 'remove' | 'set'
  quantity: number
  reason: string
}

const ADJUSTMENT_TYPES = [
  { value: 'add', label: 'Add Stock' },
  { value: 'remove', label: 'Remove Stock' },
  { value: 'set', label: 'Set Stock Level' }
]

export default function Inventory() {
  const [showForm, setShowForm] = useState(false)
  const [showAdjustmentForm, setShowAdjustmentForm] = useState(false)
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null)
  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [stockFilter, setStockFilter] = useState<'all' | 'low' | 'out'>('all')
  
  const [itemForm, setItemForm] = useState({
    name: '',
    sku: '',
    current_stock: 0,
    minimum_stock: 0,
    unit: '',
    cost_per_unit: 0,
    supplier: ''
  })
  
  const [adjustmentForm, setAdjustmentForm] = useState<StockAdjustment>({
    item_id: 0,
    adjustment_type: 'add',
    quantity: 0,
    reason: ''
  })

  const queryClient = useQueryClient()

  const { data: inventory = [], isLoading } = useQuery({
    queryKey: ['inventory'],
    queryFn: () => api.get('/inventory/items/').then((res: any) => res.data),
    refetchInterval: 30000 // Refetch every 30 seconds
  })

  const createItemMutation = useMutation({
    mutationFn: (data: typeof itemForm) => api.post('/inventory/items/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      resetForm()
    }
  })

  const updateItemMutation = useMutation({
    mutationFn: ({ id, data }: { id: number, data: typeof itemForm }) => 
      api.put(`/inventory/items/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      resetForm()
    }
  })

  const adjustStockMutation = useMutation({
    mutationFn: (data: StockAdjustment) => api.post('/inventory/adjustments/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      setShowAdjustmentForm(false)
      setAdjustmentForm({ item_id: 0, adjustment_type: 'add', quantity: 0, reason: '' })
    }
  })

  const deleteItemMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/inventory/items/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
    }
  })

  const resetForm = () => {
    setItemForm({
      name: '',
      sku: '',
      current_stock: 0,
      minimum_stock: 0,
      unit: '',
      cost_per_unit: 0,
      supplier: ''
    })
    setEditingItem(null)
    setShowForm(false)
  }

  const startEditing = (item: InventoryItem) => {
    setEditingItem(item)
    setItemForm({
      name: item.name,
      sku: item.sku,
      current_stock: item.current_stock,
      minimum_stock: item.minimum_stock,
      unit: item.unit,
      cost_per_unit: item.cost_per_unit,
      supplier: item.supplier || ''
    })
    setShowForm(true)
  }

  const startAdjustment = (item: InventoryItem) => {
    setSelectedItem(item)
    setAdjustmentForm({
      item_id: item.id,
      adjustment_type: 'add',
      quantity: 0,
      reason: ''
    })
    setShowAdjustmentForm(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingItem) {
      updateItemMutation.mutate({ id: editingItem.id, data: itemForm })
    } else {
      createItemMutation.mutate(itemForm)
    }
  }

  const handleAdjustmentSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    adjustStockMutation.mutate(adjustmentForm)
  }

  const filteredInventory = inventory.filter((item: InventoryItem) => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         item.sku.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesFilter = stockFilter === 'all' ||
                         (stockFilter === 'low' && item.current_stock <= item.minimum_stock && item.current_stock > 0) ||
                         (stockFilter === 'out' && item.current_stock === 0)
    
    return matchesSearch && matchesFilter
  })

  const getStockStatus = (item: InventoryItem) => {
    if (item.current_stock === 0) return { status: 'Out of Stock', color: 'text-red-600 bg-red-100' }
    if (item.current_stock <= item.minimum_stock) return { status: 'Low Stock', color: 'text-yellow-600 bg-yellow-100' }
    return { status: 'In Stock', color: 'text-green-600 bg-green-100' }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Inventory Management</h1>
        <button
          onClick={() => setShowForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          Add Item
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <select
            value={stockFilter}
            onChange={(e) => setStockFilter(e.target.value as 'all' | 'low' | 'out')}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">All Items</option>
            <option value="low">Low Stock</option>
            <option value="out">Out of Stock</option>
          </select>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Item
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  SKU
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Stock
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Cost
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Updated
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredInventory.map((item: InventoryItem) => {
                const stockStatus = getStockStatus(item)
                return (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{item.name}</div>
                        {item.supplier && (
                          <div className="text-sm text-gray-500">Supplier: {item.supplier}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.sku}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.current_stock} {item.unit}
                      <div className="text-xs text-gray-500">Min: {item.minimum_stock}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${stockStatus.color}`}>
                        {stockStatus.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(item.cost_per_unit)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(item.last_updated)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                      <button
                        onClick={() => startAdjustment(item)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Adjust
                      </button>
                      <button
                        onClick={() => startEditing(item)}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this item?')) {
                            deleteItemMutation.mutate(item.id)
                          }
                        }}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add/Edit Item Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold text-gray-900 mb-4">
              {editingItem ? 'Edit Item' : 'Add New Item'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name</label>
                <input
                  type="text"
                  required
                  value={itemForm.name}
                  onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">SKU</label>
                <input
                  type="text"
                  required
                  value={itemForm.sku}
                  onChange={(e) => setItemForm({ ...itemForm, sku: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Current Stock</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={itemForm.current_stock}
                    onChange={(e) => setItemForm({ ...itemForm, current_stock: parseInt(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Minimum Stock</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={itemForm.minimum_stock}
                    onChange={(e) => setItemForm({ ...itemForm, minimum_stock: parseInt(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Unit</label>
                  <input
                    type="text"
                    required
                    value={itemForm.unit}
                    onChange={(e) => setItemForm({ ...itemForm, unit: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g., kg, pcs, lbs"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Cost per Unit</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={itemForm.cost_per_unit}
                    onChange={(e) => setItemForm({ ...itemForm, cost_per_unit: parseFloat(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Supplier (Optional)</label>
                <input
                  type="text"
                  value={itemForm.supplier}
                  onChange={(e) => setItemForm({ ...itemForm, supplier: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createItemMutation.isPending || updateItemMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {editingItem ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stock Adjustment Modal */}
      {showAdjustmentForm && selectedItem && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold text-gray-900 mb-4">
              Adjust Stock - {selectedItem.name}
            </h3>
            <div className="mb-4 p-3 bg-gray-100 rounded">
              <p className="text-sm text-gray-600">Current Stock: {selectedItem.current_stock} {selectedItem.unit}</p>
            </div>
            <form onSubmit={handleAdjustmentSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Adjustment Type</label>
                <select
                  value={adjustmentForm.adjustment_type}
                  onChange={(e) => setAdjustmentForm({ ...adjustmentForm, adjustment_type: e.target.value as 'add' | 'remove' | 'set' })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                >
                  {ADJUSTMENT_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Quantity</label>
                <input
                  type="number"
                  min="0"
                  required
                  value={adjustmentForm.quantity}
                  onChange={(e) => setAdjustmentForm({ ...adjustmentForm, quantity: parseInt(e.target.value) || 0 })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Reason</label>
                <textarea
                  required
                  value={adjustmentForm.reason}
                  onChange={(e) => setAdjustmentForm({ ...adjustmentForm, reason: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  rows={3}
                  placeholder="Reason for stock adjustment..."
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowAdjustmentForm(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adjustStockMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  Adjust Stock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}