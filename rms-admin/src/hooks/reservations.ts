import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useLocations() {
  return useQuery({ queryKey: ['locations'], queryFn: async () => (await api.get('/core/locations/')).data })
}

export function useTableAvailability(locationId?: number, startISO?: string, endISO?: string) {
  return useQuery({
    queryKey: ['table-availability', locationId || 0, startISO || '', endISO || ''],
    queryFn: async () => {
      const loc = locationId || 1
      const qs = new URLSearchParams({ location: String(loc) })
      if (startISO) qs.set('start', startISO)
      if (endISO) qs.set('end', endISO)
      const r = await api.get(`/reservations/tables/availability/?${qs.toString()}`)
      return r.data.tables
    },
    enabled: true,
    refetchInterval: 10000,
  })
}

export function useReservations(locationId?: number, dateISO?: string, status?: string) {
  return useQuery({
    queryKey: ['reservations', locationId || 'all', dateISO || '', status || ''],
    queryFn: async () => {
      const qs = new URLSearchParams()
      if (locationId) qs.set('location', String(locationId))
      if (dateISO) qs.set('reservation_date', dateISO)
      if (status) qs.set('status', status)
      const url = `/reservations/?${qs.toString()}`
      const r = await api.get(url)
      return r.data
    },
    refetchInterval: 10000,
  })
}

export function useReservationAction(action: 'check_in'|'check_out'|'cancel'|'confirm'|'no_show'|'mark_deposit_paid'|'mark_deposit_unpaid') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.post(`/reservations/${id}/${action}/`, {}).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reservations'] })
  })
}

export function useCreateReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: any) => api.post('/reservations/', payload).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reservations'] })
  })
}
