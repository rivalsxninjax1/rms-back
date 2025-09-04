import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useOrders(params?: string) {
  return useQuery({
    queryKey: ['orders', params || 'all'],
    queryFn: async () => (await api.get(`/orders/${params || ''}`)).data,
    refetchInterval: 5000,
  })
}

export function useOrderUpdateStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: number, status: string }) => api.patch(`/orders/${id}/`, { status: status.toUpperCase() }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] })
  })
}

export function useOrderCancel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: number, reason: string }) => api.post(`/orders/${id}/cancel/`, { reason }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] })
  })
}

export function useOrderRefund() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, amount, reason }: { id: number, amount: string, reason?: string }) => api.post(`/orders/${id}/refund/`, { refund_amount: amount, reason: reason || '' }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] })
  })
}

