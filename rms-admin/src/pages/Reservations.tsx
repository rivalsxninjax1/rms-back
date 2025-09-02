import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface Table {
  id: number
  number: string
  capacity: number
  location: string
  is_available: boolean
}

interface Reservation {
  id: number
  customer_name: string
  customer_phone: string
  customer_email?: string
  table: Table
  party_size: number
  reservation_date: string
  reservation_time: string
  status: 'pending' | 'confirmed' | 'seated' | 'completed' | 'cancelled' | 'no_show'
  special_requests?: string
  created_at: string
  updated_at: string
}

const RESERVATION_STATUSES = [
  { value: 'pending', label: 'Pending', color: 'text-yellow-600 bg-yellow-100' },
  { value: 'confirmed', label: 'Confirmed', color: 'text-blue-600 bg-blue-100' },
  { value: 'seated', label: 'Seated', color: 'text-green-600 bg-green-100' },
  { value: 'completed', label: 'Completed', color: 'text-gray-600 bg-gray-100' },
  { value: 'cancelled', label: 'Cancelled', color: 'text-red-600 bg-red-100' },
  { value: 'no_show', label: 'No Show', color: 'text-red-600 bg-red-100' }
]

const TIME_SLOTS = [
  '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
  '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30',
  '19:00', '19:30', '20:00', '20:30', '21:00', '21:30', '22:00'
]

export default function Reservations() {
  const [showForm, setShowForm] = useState(false)
  const [editingReservation, setEditingReservation] = useState<Reservation | null>(null)
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchTerm, setSearchTerm] = useState('')
  
  const [reservationForm, setReservationForm] = useState({
    customer_name: '',
    customer_phone: '',
    customer_email: '',
    table_id: 0,
    party_size: 1,
    reservation_date: new Date().toISOString().split('T')[0],
    reservation_time: '19:00',
    special_requests: ''
  })

  const queryClient = useQueryClient()

  const { data: reservations = [], isLoading } = useQuery({
    queryKey: ['reservations', selectedDate],
    queryFn: () => api.get(`/reservations/?date=${selectedDate}`).then((res: any) => res.data),
    refetchInterval: 30000
  })

  const { data: tables = [] } = useQuery({
    queryKey: ['tables'],
    queryFn: () => api.get('/tables/').then((res: any) => res.data)
  })

  const createReservationMutation = useMutation({
    mutationFn: (data: typeof reservationForm) => api.post('/reservations/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
      resetForm()
    }
  })

  const updateReservationMutation = useMutation({
    mutationFn: ({ id, data }: { id: number, data: Partial<Reservation> }) => 
      api.put(`/reservations/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    }
  })

  const deleteReservationMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/reservations/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    }
  })

  const resetForm = () => {
    setReservationForm({
      customer_name: '',
      customer_phone: '',
      customer_email: '',
      table_id: 0,
      party_size: 1,
      reservation_date: new Date().toISOString().split('T')[0],
      reservation_time: '19:00',
      special_requests: ''
    })
    setEditingReservation(null)
    setShowForm(false)
  }

  const startEditing = (reservation: Reservation) => {
    setEditingReservation(reservation)
    setReservationForm({
      customer_name: reservation.customer_name,
      customer_phone: reservation.customer_phone,
      customer_email: reservation.customer_email || '',
      table_id: reservation.table.id,
      party_size: reservation.party_size,
      reservation_date: reservation.reservation_date,
      reservation_time: reservation.reservation_time,
      special_requests: reservation.special_requests || ''
    })
    setShowForm(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingReservation) {
      updateReservationMutation.mutate({ id: editingReservation.id, data: reservationForm })
    } else {
      createReservationMutation.mutate(reservationForm)
    }
  }

  const updateReservationStatus = (id: number, status: Reservation['status']) => {
    updateReservationMutation.mutate({ id, data: { status } })
  }

  const filteredReservations = reservations.filter((reservation: Reservation) => {
    const matchesSearch = reservation.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         reservation.customer_phone.includes(searchTerm)
    
    const matchesStatus = statusFilter === 'all' || reservation.status === statusFilter
    
    return matchesSearch && matchesStatus
  })

  const getStatusInfo = (status: string) => {
    return RESERVATION_STATUSES.find(s => s.value === status) || RESERVATION_STATUSES[0]
  }

  const formatTime = (time: string) => {
    return new Date(`2000-01-01T${time}`).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
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
        <h1 className="text-2xl font-bold text-gray-900">Reservations</h1>
        <button
          onClick={() => setShowForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          New Reservation
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search by customer name or phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">All Statuses</option>
            {RESERVATION_STATUSES.map(status => (
              <option key={status.value} value={status.value}>{status.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Reservations Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Customer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Table
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date & Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Party Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredReservations.map((reservation: Reservation) => {
                const statusInfo = getStatusInfo(reservation.status)
                return (
                  <tr key={reservation.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{reservation.customer_name}</div>
                        <div className="text-sm text-gray-500">{reservation.customer_phone}</div>
                        {reservation.customer_email && (
                          <div className="text-sm text-gray-500">{reservation.customer_email}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">Table {reservation.table.number}</div>
                      <div className="text-sm text-gray-500">{reservation.table.location}</div>
                      <div className="text-sm text-gray-500">Capacity: {reservation.table.capacity}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{formatDate(reservation.reservation_date)}</div>
                      <div className="text-sm text-gray-500">{formatTime(reservation.reservation_time)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {reservation.party_size} {reservation.party_size === 1 ? 'person' : 'people'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <select
                        value={reservation.status}
                        onChange={(e) => updateReservationStatus(reservation.id, e.target.value as Reservation['status'])}
                        className={`text-xs font-semibold rounded-full px-2 py-1 border-0 ${statusInfo.color}`}
                      >
                        {RESERVATION_STATUSES.map(status => (
                          <option key={status.value} value={status.value}>{status.label}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                      <button
                        onClick={() => startEditing(reservation)}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this reservation?')) {
                            deleteReservationMutation.mutate(reservation.id)
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

      {/* Add/Edit Reservation Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-10 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold text-gray-900 mb-4">
              {editingReservation ? 'Edit Reservation' : 'New Reservation'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Customer Name</label>
                <input
                  type="text"
                  required
                  value={reservationForm.customer_name}
                  onChange={(e) => setReservationForm({ ...reservationForm, customer_name: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Phone Number</label>
                <input
                  type="tel"
                  required
                  value={reservationForm.customer_phone}
                  onChange={(e) => setReservationForm({ ...reservationForm, customer_phone: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Email (Optional)</label>
                <input
                  type="email"
                  value={reservationForm.customer_email}
                  onChange={(e) => setReservationForm({ ...reservationForm, customer_email: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Table</label>
                  <select
                    required
                    value={reservationForm.table_id}
                    onChange={(e) => setReservationForm({ ...reservationForm, table_id: parseInt(e.target.value) })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value={0}>Select Table</option>
                    {tables.map((table: Table) => (
                      <option key={table.id} value={table.id}>
                        Table {table.number} ({table.capacity} seats)
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Party Size</label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    required
                    value={reservationForm.party_size}
                    onChange={(e) => setReservationForm({ ...reservationForm, party_size: parseInt(e.target.value) || 1 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Date</label>
                  <input
                    type="date"
                    required
                    value={reservationForm.reservation_date}
                    onChange={(e) => setReservationForm({ ...reservationForm, reservation_date: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Time</label>
                  <select
                    required
                    value={reservationForm.reservation_time}
                    onChange={(e) => setReservationForm({ ...reservationForm, reservation_time: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  >
                    {TIME_SLOTS.map(time => (
                      <option key={time} value={time}>{formatTime(time)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Special Requests</label>
                <textarea
                  value={reservationForm.special_requests}
                  onChange={(e) => setReservationForm({ ...reservationForm, special_requests: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  rows={3}
                  placeholder="Any special requests or notes..."
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
                  disabled={createReservationMutation.isPending || updateReservationMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {editingReservation ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}