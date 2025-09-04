import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface Rank { id:number; code:string; name:string; tip_cents:number; earn_points_per_currency:string; burn_cents_per_point:number; is_active:boolean }
interface Profile { id:number; user:number; rank?:Rank; points:number; notes?:string }


export default function Loyalty() {
  const qc = useQueryClient()
  // const ranks = useQuery({ queryKey:['loyalty','ranks'], queryFn: async ()=> (await api.get<Rank[]>('/loyalty/ranks/')).data })
  const profiles = useQuery({ queryKey:['loyalty','profiles'], queryFn: async ()=> (await api.get<Profile[]>('/loyalty/profiles/')).data })

  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null)
  const [delta, setDelta] = useState<string>('10')
  const [reason, setReason] = useState<string>('Manual adjustment')
  const [reference, setReference] = useState<string>('')

  const adjust = useMutation({
    mutationFn: async (id:number)=> (await api.post(`/loyalty/profiles/${id}/adjust/`, { delta: Number(delta), reason, reference })).data,
    onSuccess: ()=> { qc.invalidateQueries({ queryKey:['loyalty','profiles'] }); setSelectedProfile(null) }
  })

  // const [previewTotal, setPreviewTotal] = useState<string>('50.00')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold">Loyalty</h2></div>

      <div className="bg-white rounded border">
        <div className="px-4 py-2 border-b"><h3 className="font-medium">Profiles</h3></div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          {profiles.data?.map(p => (
            <div key={p.id} className="border rounded p-3 flex items-center justify-between">
              <div>
                <div className="font-medium">User #{p.user} · {p.rank?.name || 'No Rank'}</div>
                <div className="text-sm text-gray-600">Points: {p.points}</div>
              </div>
              <div className="flex items-center gap-2">
                <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={()=>setSelectedProfile(p)}>Adjust</button>
                <a className="px-2 py-1 text-xs bg-white border rounded" href="/api/loyalty/profiles/export_csv/">Export CSV</a>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedProfile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded p-4 w-full max-w-md">
            <h3 className="font-medium mb-2">Adjust Points · Profile #{selectedProfile.id}</h3>
            <div className="space-y-2">
              <input className="w-full border rounded px-2 py-1" type="number" value={delta} onChange={e=>setDelta(e.target.value)} placeholder="Delta (e.g., 10 or -10)" />
              <input className="w-full border rounded px-2 py-1" value={reason} onChange={e=>setReason(e.target.value)} placeholder="Reason" />
              <input className="w-full border rounded px-2 py-1" value={reference} onChange={e=>setReference(e.target.value)} placeholder="Reference (optional)" />
            </div>
            <div className="mt-3 flex items-center justify-end gap-2">
              <button className="px-3 py-1 bg-gray-100 rounded" onClick={()=>setSelectedProfile(null)}>Cancel</button>
              <button className="px-3 py-1 bg-blue-600 text-white rounded" onClick={()=>adjust.mutate(selectedProfile.id)} disabled={adjust.isPending}>Apply</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

