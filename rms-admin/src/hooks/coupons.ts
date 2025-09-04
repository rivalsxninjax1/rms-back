import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useCoupons() {
  return useQuery({ queryKey: ['coupons'], queryFn: async () => (await api.get('/coupons/coupons/')).data })
}

export function useCreateCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (form: any) => api.post('/coupons/coupons/', form).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupons'] })
  })
}

export function useToggleCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (row: any) => api.patch(`/coupons/coupons/${row.id}/`, { active: !row.active }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupons'] })
  })
}

export function usePreviewCoupon() {
  return useMutation({
    mutationFn: ({ id, order_total, item_count, user_id, first }:{ id:number, order_total:string, item_count?:number, user_id?:number, first?:boolean }) =>
      api.get(`/coupons/coupons/${id}/preview/`, { params: { order_total, item_count, user_id, first } }).then(r=>r.data)
  })
}

