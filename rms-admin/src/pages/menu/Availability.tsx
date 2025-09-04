import { useState } from 'react'
import { useMenuItems, useUpdateItem } from '../../hooks/menu'

export default function Availability() {
  const [searchTerm, setSearchTerm] = useState('')
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const { data: items, isLoading } = useMenuItems()
  const updateItem = useUpdateItem()

  const filteredItems = items?.filter((item: any) => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesCategory = filterCategory === 'all' || item.category?.id.toString() === filterCategory
    return matchesSearch && matchesCategory
  }) || []

  const categories = [...new Set(items?.map((item: any) => item.category).filter((cat: any) => cat != null))]

  const handleAvailabilityToggle = (itemId: number, isAvailable: boolean) => {
    const formData = new FormData()
    formData.append('is_available', (!isAvailable).toString())
    updateItem.mutate({ id: itemId, form: formData })
  }

  const handleScheduleUpdate = (itemId: number, schedule: any) => {
    const formData = new FormData()
    formData.append('availability_schedule', JSON.stringify(schedule))
    updateItem.mutate({ id: itemId, form: formData })
  }

  if (isLoading) return <div className="p-4">Loading availability...</div>

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Menu Availability</h3>
        <div className="flex space-x-2">
          <select 
            value={filterCategory} 
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md"
          >
            <option value="all">All Categories</option>
            {categories.map((category: any) => (
              <option key={category.id} value={category.id.toString()}>
                {category.name}
              </option>
            ))}
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

      <div className="grid gap-4">
        {filteredItems.map((item: any) => (
          <div key={item.id} className="bg-white p-4 rounded-lg border">
            <div className="flex justify-between items-start">
              <div className="flex items-center space-x-3">
                {item.image && (
                  <img src={item.image} alt={item.name} className="w-12 h-12 rounded" />
                )}
                <div>
                  <h4 className="font-medium">{item.name}</h4>
                  <p className="text-sm text-gray-600">{item.category?.name} • ${item.price}</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => handleAvailabilityToggle(item.id, item.is_available)}
                  className={`px-4 py-2 rounded text-sm font-medium ${
                    item.is_available 
                      ? 'bg-green-100 text-green-800 hover:bg-green-200' 
                      : 'bg-red-100 text-red-800 hover:bg-red-200'
                  }`}
                >
                  {item.is_available ? 'Available' : 'Unavailable'}
                </button>
              </div>
            </div>
            
            <div className="mt-4 pt-4 border-t">
              <h5 className="text-sm font-medium mb-3">Availability Schedule</h5>
              <div className="grid grid-cols-7 gap-2">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => {
                  const daySchedule = item.availability_schedule?.[index] || { enabled: true, start: '00:00', end: '23:59' }
                  
                  return (
                    <div key={day} className="text-center">
                      <div className="text-xs font-medium text-gray-700 mb-1">{day}</div>
                      <div className="space-y-1">
                        <label className="flex items-center justify-center">
                          <input
                            type="checkbox"
                            checked={daySchedule.enabled}
                            onChange={(e) => {
                              const newSchedule = [...(item.availability_schedule || Array(7).fill({ enabled: true, start: '00:00', end: '23:59' }))]
                              newSchedule[index] = { ...daySchedule, enabled: e.target.checked }
                              handleScheduleUpdate(item.id, newSchedule)
                            }}
                            className="w-3 h-3"
                          />
                        </label>
                        {daySchedule.enabled && (
                          <div className="space-y-1">
                            <input
                              type="time"
                              value={daySchedule.start}
                              onChange={(e) => {
                                const newSchedule = [...(item.availability_schedule || Array(7).fill({ enabled: true, start: '00:00', end: '23:59' }))]
                                newSchedule[index] = { ...daySchedule, start: e.target.value }
                                handleScheduleUpdate(item.id, newSchedule)
                              }}
                              className="w-full text-xs px-1 py-1 border rounded"
                            />
                            <input
                              type="time"
                              value={daySchedule.end}
                              onChange={(e) => {
                                const newSchedule = [...(item.availability_schedule || Array(7).fill({ enabled: true, start: '00:00', end: '23:59' }))]
                                newSchedule[index] = { ...daySchedule, end: e.target.value }
                                handleScheduleUpdate(item.id, newSchedule)
                              }}
                              className="w-full text-xs px-1 py-1 border rounded"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}