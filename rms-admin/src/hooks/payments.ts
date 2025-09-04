import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function usePaymentAnalytics() {
  return useQuery({
    queryKey: ['payments','analytics'],
    queryFn: async () => (await api.get('/payments/analytics/')).data,
    staleTime: 30_000,
  })
}

export function usePaymentIntents(params?: { q?: string }) {
  // If no list endpoint, reuse analytics data for now
  return useQuery({
    queryKey: ['payments','intents', params?.q || ''],
    queryFn: async () => (await api.get('/payments/analytics/')).data?.intents || [],
  })
}

export function useRefund() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ payment_intent_id, amount_cents }: { payment_intent_id: string, amount_cents: number|null }) =>
      api.post(`/payments/refund/${payment_intent_id}/`, amount_cents ? { amount_cents } : {}).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payments'] })
  })
}

export function useCancelPaymentIntent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payment_intent_id: string) => api.post(`/payments/payment-intent/${payment_intent_id}/cancel/`).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payments'] })
  })
}

export function useReceiptLink(orderId: number) {
  return `/api/payments/receipt/${orderId}/`
}

export function useWebhookEvents() {
  return useQuery({
    queryKey: ['payments','events'],
    queryFn: async () => (await api.get('/payments/analytics/')).data?.events || [],
  })
}

export function usePayments() {
  return useQuery({
    queryKey: ['payments','list'],
    queryFn: async () => (await api.get('/payments/')).data,
  })
}

export function useRefunds() {
  return useQuery({
    queryKey: ['payments','refunds'],
    queryFn: async () => (await api.get('/payments/refunds/')).data,
  })
}

