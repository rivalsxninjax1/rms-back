import { useState } from 'react'
import { useMenuModifiers, useDeleteModifier } from '../../hooks/menu'

export default function Modifiers() {
  const [searchTerm, setSearchTerm] = useState('')
  const { data: modifiers, isLoading } = useMenuModifiers()
  // const createModifier = useCreateModifier()
  // const updateModifier = useUpdateModifier()
  const deleteModifier = useDeleteModifier()

  const filteredModifiers = modifiers?.filter((mod: any) => 
    mod.name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || []

  if (isLoading) return <div className="p-4">Loading modifiers...</div>

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Menu Modifiers</h3>
        <button 
          onClick={() => {/* Open create modal */}}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Add Modifier Group
        </button>
      </div>
      
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search modifiers..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>

      <div className="grid gap-4">
        {filteredModifiers.map((modifier: any) => (
          <div key={modifier.id} className="bg-white p-4 rounded-lg border">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-medium">{modifier.name}</h4>
                <p className="text-sm text-gray-600">{modifier.description}</p>
                <div className="mt-2">
                  <span className={`px-2 py-1 text-xs rounded ${
                    modifier.required ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                  }`}>
                    {modifier.required ? 'Required' : 'Optional'}
                  </span>
                  <span className="ml-2 text-sm text-gray-500">
                    {modifier.selection_type} • Max: {modifier.max_selections}
                  </span>
                </div>
              </div>
              <div className="flex space-x-2">
                <button 
                  onClick={() => {/* Open edit modal */}}
                  className="text-blue-600 hover:text-blue-800"
                >
                  Edit
                </button>
                <button 
                  onClick={() => deleteModifier.mutate(modifier.id)}
                  className="text-red-600 hover:text-red-800"
                >
                  Delete
                </button>
              </div>
            </div>
            
            {modifier.options && modifier.options.length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <h5 className="text-sm font-medium mb-2">Options:</h5>
                <div className="grid grid-cols-2 gap-2">
                  {modifier.options.map((option: any) => (
                    <div key={option.id} className="flex justify-between text-sm">
                      <span>{option.name}</span>
                      <span className="font-medium">${option.price}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}