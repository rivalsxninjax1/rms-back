import { useState } from 'react'
import { useMenuItems, useUpdateItemStock } from '../../hooks/menu'

export default function Stock() {
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState<'all' | 'in_stock' | 'low_stock' | 'out_of_stock'>('all')
  const { data: items, isLoading } = useMenuItems()
  const updateStock = useUpdateItemStock()

  const filteredItems = items?.filter((item: any) => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesFilter = filterStatus === 'all' || 
      (filterStatus === 'in_stock' && item.stock_quantity > item.low_stock_threshold) ||
      (filterStatus === 'low_stock' && item.stock_quantity <= item.low_stock_threshold && item.stock_quantity > 0) ||
      (filterStatus === 'out_of_stock' && item.stock_quantity === 0)
    return matchesSearch && matchesFilter
  }) || []

  const handleStockToggle = (itemId: number, _isAvailable: boolean) => {
    updateStock.mutate({ id: itemId, stock: items.find((item: any) => item.id === itemId)?.stock_quantity || 0 })
  }

  const handleStockUpdate = (itemId: number, quantity: number) => {
    updateStock.mutate({ id: itemId, stock: quantity })
  }

  if (isLoading) return <div className="p-4">Loading stock...</div>

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Stock Management</h3>
        <div className="flex space-x-2">
          <select 
            value={filterStatus} 
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="px-3 py-2 border border-gray-300 rounded-md"
          >
            <option value="all">All Items</option>
            <option value="in_stock">In Stock</option>
            <option value="low_stock">Low Stock</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>
        </div>
      </div>
      
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search items..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Item</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Category</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Stock</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Available</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-900">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {filteredItems.map((item: any) => {
              const stockStatus = item.stock_quantity === 0 ? 'out_of_stock' : 
                                item.stock_quantity <= item.low_stock_threshold ? 'low_stock' : 'in_stock'
              
              return (
                <tr key={item.id}>
                  <td className="px-4 py-3">
                    <div className="flex items-center">
                      {item.image && (
                        <img src={item.image} alt={item.name} className="w-10 h-10 rounded mr-3" />
                      )}
                      <div>
                        <div className="font-medium">{item.name}</div>
                        <div className="text-sm text-gray-500">${item.price}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">{item.category?.name}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      value={item.stock_quantity || 0}
                      onChange={(e) => handleStockUpdate(item.id, parseInt(e.target.value) || 0)}
                      className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                      min="0"
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Low: {item.low_stock_threshold}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 text-xs rounded ${
                      stockStatus === 'in_stock' ? 'bg-green-100 text-green-800' :
                      stockStatus === 'low_stock' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {stockStatus === 'in_stock' ? 'In Stock' :
                       stockStatus === 'low_stock' ? 'Low Stock' : 'Out of Stock'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleStockToggle(item.id, item.is_available)}
                      className={`px-3 py-1 text-xs rounded ${
                        item.is_available 
                          ? 'bg-green-100 text-green-800 hover:bg-green-200' 
                          : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                      }`}
                    >
                      {item.is_available ? 'Available' : 'Disabled'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button 
                      onClick={() => {/* Open stock adjustment modal */}}
                      className="text-blue-600 hover:text-blue-800 text-sm"
                    >
                      Adjust
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}