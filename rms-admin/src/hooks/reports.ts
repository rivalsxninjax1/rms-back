import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

export function useOrderAnalytics(period_days: number) {
  return useQuery({ queryKey: ['analytics','orders', period_days], queryFn: async ()=> (await api.get(`/analytics/orders/?period_days=${period_days}`)).data })
}

export function useMenuAnalytics(period_days: number) {
  return useQuery({ queryKey: ['analytics','menu', period_days], queryFn: async ()=> (await api.get(`/analytics/menu/?period_days=${period_days}`)).data })
}

export function useDailySales(params: { date_from?: string, date_to?: string }) {
  const { date_from, date_to } = params
  const key = JSON.stringify(params)
  const qs = new URLSearchParams()
  if (date_from) qs.set('date_from', date_from)
  if (date_to) qs.set('date_to', date_to)
  return useQuery({ queryKey: ['reports','daily-sales', key], queryFn: async ()=> (await api.get(`/reports/daily-sales/${qs.toString() ? `?${qs}`: ''}`)).data })
}

export function useAuditLogs(params?: Record<string,string|number|boolean>) {
  const qs = new URLSearchParams()
  Object.entries(params || {}).forEach(([k,v]) => qs.set(k, String(v)))
  return useQuery({ queryKey: ['reports','audit-logs', JSON.stringify(params||{})], queryFn: async ()=> (await api.get(`/audit-logs/${qs.toString() ? `?${qs}`: ''}`)).data })
}

