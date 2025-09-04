import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useMenuCategories() {
  return useQuery({ queryKey: ['menu','categories'], queryFn: async () => (await api.get('/menu/categories/')).data })
}

export function useMenuItems(params?: string) {
  return useQuery({ queryKey: ['menu','items', params || ''], queryFn: async () => (await api.get(`/menu/items/${params || ''}`)).data })
}

export function useCreateItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (form: FormData) => api.post('/menu/items/', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','items'] })
  })
}

export function useUpdateItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, form }: { id: number, form: FormData }) => api.patch(`/menu/items/${id}/`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','items'] })
  })
}

export function useDeleteItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/menu/items/${id}/`).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','items'] })
  })
}

// Modifier hooks
export function useMenuModifiers() {
  return useQuery({ queryKey: ['menu','modifiers'], queryFn: async () => (await api.get('/menu/modifiers/')).data })
}

export function useCreateModifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (form: FormData) => api.post('/menu/modifiers/', form).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','modifiers'] })
  })
}

export function useUpdateModifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, form }: { id: number, form: FormData }) => api.patch(`/menu/modifiers/${id}/`, form).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','modifiers'] })
  })
}

export function useDeleteModifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/menu/modifiers/${id}/`).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','modifiers'] })
  })
}

// Stock management hooks
export function useUpdateItemStock() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, stock }: { id: number, stock: number }) => api.patch(`/menu/items/${id}/stock/`, { stock }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['menu','items'] })
  })
}

