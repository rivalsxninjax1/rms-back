import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: async () => (await api.get('/accounts/api/profile/')).data,
    staleTime: 60_000,
  })
}

