import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useLoyaltyRanks() {
  return useQuery({ queryKey: ['loyalty','ranks'], queryFn: async ()=> (await api.get('/loyalty/ranks/')).data })
}

export function useLoyaltyProfiles() {
  return useQuery({ queryKey: ['loyalty','profiles'], queryFn: async ()=> (await api.get('/loyalty/profiles/')).data })
}

export function useAdjustPoints() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, delta, reason, reference }:{ id:number, delta:number, reason:string, reference?:string}) =>
      api.post(`/loyalty/profiles/${id}/adjust/`, { delta, reason, reference }).then(r=>r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loyalty'] })
  })
}

