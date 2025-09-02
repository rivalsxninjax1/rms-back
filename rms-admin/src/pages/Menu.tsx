import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import type { MenuCategory, MenuItem } from '../types/menu'

interface MenuItemForm {
  name: string
  description: string
  price: number
  category: number
  is_available: boolean
}

interface CategoryForm {
  name: string
  description: string
  is_active: boolean
}

export default function Menu() {
  const [showItemForm, setShowItemForm] = useState(false)
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null)
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<number | 'all'>('all')
  const queryClient = useQueryClient()

  const [itemForm, setItemForm] = useState<MenuItemForm>({
    name: '',
    description: '',
    price: 0,
    category: 0,
    is_available: true
  })

  const [categoryForm, setCategoryForm] = useState<CategoryForm>({
    name: '',
    description: '',
    is_active: true
  })

  const categories = useQuery({
    queryKey: ['menu', 'categories'],
    queryFn: async () => {
      const response = await api.get<MenuCategory[]>('/menu/categories/')
      return response.data
    },
  })

  const items = useQuery({
    queryKey: ['menu', 'items', selectedCategory],
    queryFn: async () => {
      const params = selectedCategory !== 'all' ? `?category=${selectedCategory}` : ''
      const response = await api.get<MenuItem[]>(`/menu/items/${params}`)
      return response.data
    },
  })

  const createItem = useMutation({
    mutationFn: async (data: MenuItemForm) => {
      const response = await api.post('/menu/items/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'items'] })
      setShowItemForm(false)
      setItemForm({ name: '', description: '', price: 0, category: 0, is_available: true })
    },
  })

  const updateItem = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<MenuItemForm> }) => {
      const response = await api.patch(`/menu/items/${id}/`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'items'] })
      setEditingItem(null)
    },
  })

  const deleteItem = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/menu/items/${id}/`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'items'] })
    },
  })

  const createCategory = useMutation({
    mutationFn: async (data: CategoryForm) => {
      const response = await api.post('/menu/categories/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'categories'] })
      setShowCategoryForm(false)
      setCategoryForm({ name: '', description: '', is_active: true })
    },
  })

  const updateCategory = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<CategoryForm> }) => {
      const response = await api.patch(`/menu/categories/${id}/`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'categories'] })
      setEditingCategory(null)
    },
  })

  const deleteCategory = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/menu/categories/${id}/`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['menu', 'categories'] })
    },
  })

  const handleItemSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingItem) {
      updateItem.mutate({ id: editingItem.id, data: itemForm })
    } else {
      createItem.mutate(itemForm)
    }
  }

  const handleCategorySubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingCategory) {
      updateCategory.mutate({ id: editingCategory.id, data: categoryForm })
    } else {
      createCategory.mutate(categoryForm)
    }
  }

  const startEditingItem = (item: MenuItem) => {
    setEditingItem(item)
    setItemForm({
      name: item.name,
      description: item.description || '',
      price: item.price,
      category: item.category,
      is_available: item.is_available ?? true
    })
    setShowItemForm(true)
  }

  const startEditingCategory = (category: MenuCategory) => {
    setEditingCategory(category)
    setCategoryForm({
      name: category.name,
      description: category.description || '',
      is_active: category.is_active ?? true
    })
    setShowCategoryForm(true)
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Menu Management</h2>
        <div className="flex space-x-3">
          <button
            onClick={() => setShowCategoryForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add Category
          </button>
          <button
            onClick={() => setShowItemForm(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            Add Menu Item
          </button>
        </div>
      </div>

      {/* Category Filter */}
      <div className="flex space-x-2 overflow-x-auto">
        <button
          onClick={() => setSelectedCategory('all')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedCategory === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          All Items
        </button>
        {categories.data?.map((category) => (
          <button
            key={category.id}
            onClick={() => setSelectedCategory(category.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              selectedCategory === category.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {category.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Categories Section */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Categories</h3>
            </div>
            <div className="p-6">
              {categories.isLoading ? (
                <div className="text-center text-gray-500">Loading categories...</div>
              ) : categories.data?.length === 0 ? (
                <div className="text-center text-gray-500">No categories found</div>
              ) : (
                <div className="space-y-3">
                  {categories.data?.map((category) => (
                    <div key={category.id} className="p-3 border rounded-lg hover:bg-gray-50">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">{category.name}</h4>
                          <p className="text-sm text-gray-600 mt-1">{category.description}</p>
                        </div>
                        <div className="flex space-x-1 ml-2">
                          <button
                            onClick={() => startEditingCategory(category)}
                            className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => deleteCategory.mutate(category.id)}
                            className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Menu Items Section */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">
                Menu Items
                {items.data && (
                  <span className="ml-2 text-sm text-gray-500">({items.data.length})</span>
                )}
              </h3>
            </div>
            <div className="p-6">
              {items.isLoading ? (
                <div className="text-center text-gray-500">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                  Loading menu items...
                </div>
              ) : items.data?.length === 0 ? (
                <div className="text-center text-gray-500">No menu items found</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {items.data?.map((item) => (
                    <div key={item.id} className="p-4 border rounded-lg hover:bg-gray-50">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium text-gray-900">{item.name}</h4>
                            {!item.is_available && (
                              <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">
                                Unavailable
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 mt-1">{item.description}</p>
                          <p className="text-lg font-semibold text-green-600 mt-2">
                            {formatCurrency(item.price)}
                          </p>
                        </div>
                        <div className="flex space-x-1 ml-2">
                          <button
                            onClick={() => updateItem.mutate({ 
                              id: item.id, 
                              data: { is_available: !item.is_available } 
                            })}
                            className={`p-1 transition-colors ${
                              item.is_available 
                                ? 'text-gray-400 hover:text-orange-600' 
                                : 'text-gray-400 hover:text-green-600'
                            }`}
                          >
                            {item.is_available ? (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            )}
                          </button>
                          <button
                            onClick={() => startEditingItem(item)}
                            className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => deleteItem.mutate(item.id)}
                            className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Item Form Modal */}
      {showItemForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              {editingItem ? 'Edit Menu Item' : 'Add Menu Item'}
            </h3>
            <form onSubmit={handleItemSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={itemForm.name}
                  onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={itemForm.description}
                  onChange={(e) => setItemForm({ ...itemForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Price</label>
                <input
                  type="number"
                  step="0.01"
                  value={itemForm.price}
                  onChange={(e) => setItemForm({ ...itemForm, price: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select
                  value={itemForm.category}
                  onChange={(e) => setItemForm({ ...itemForm, category: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value={0}>Select a category</option>
                  {categories.data?.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_available"
                  checked={itemForm.is_available}
                  onChange={(e) => setItemForm({ ...itemForm, is_available: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="is_available" className="ml-2 block text-sm text-gray-900">
                  Available
                </label>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowItemForm(false)
                    setEditingItem(null)
                    setItemForm({ name: '', description: '', price: 0, category: 0, is_available: true })
                  }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createItem.isPending || updateItem.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {editingItem ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Category Form Modal */}
      {showCategoryForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              {editingCategory ? 'Edit Category' : 'Add Category'}
            </h3>
            <form onSubmit={handleCategorySubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={categoryForm.name}
                  onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={categoryForm.description}
                  onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={categoryForm.is_active}
                  onChange={(e) => setCategoryForm({ ...categoryForm, is_active: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="is_active" className="ml-2 block text-sm text-gray-900">
                  Active
                </label>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowCategoryForm(false)
                    setEditingCategory(null)
                    setCategoryForm({ name: '', description: '', is_active: true })
                  }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createCategory.isPending || updateCategory.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {editingCategory ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}