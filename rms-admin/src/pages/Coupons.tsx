import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface Coupon {
  id: number
  code: string
  name: string
  discount_type: 'PERCENTAGE' | 'FIXED_AMOUNT' | 'FREE_SHIPPING' | 'BUY_X_GET_Y'
  percent?: string
  fixed_amount?: string
  minimum_order_amount?: string
  max_uses?: number | null
  max_uses_per_customer?: number | null
  times_used: number
  active: boolean
}

export default function Coupons() {
  const qc = useQueryClient()
  const coupons = useQuery({ queryKey: ['coupons'], queryFn: async () => (await api.get<Coupon[]>('/coupons/coupons/')).data })

  const [form, setForm] = useState<any>({
    code: '', name: '', discount_type: 'PERCENTAGE', percent: '10.00', fixed_amount: '0.00',
    minimum_order_amount: '0.00', max_uses: '', max_uses_per_customer: '', active: true,
  })
  const [previewOrderTotal, setPreviewOrderTotal] = useState<string>('50.00')

  const create = useMutation({
    mutationFn: async () => (await api.post('/coupons/coupons/', form)).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['coupons'] }); setForm({ code: '', name: '', discount_type: 'PERCENTAGE', percent: '10.00', fixed_amount: '0.00', minimum_order_amount: '0.00', max_uses: '', max_uses_per_customer: '', active: true }) }
  })

  const toggleActive = useMutation({
    mutationFn: async (row: Coupon) => (await api.patch(`/coupons/coupons/${row.id}/`, { active: !row.active })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupons'] })
  })

  const preview = useMutation({
    mutationFn: async (id: number) => (await api.get(`/coupons/coupons/${id}/preview/?order_total=${previewOrderTotal}`)).data,
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold">Coupons</h2></div>

      <div className="bg-white rounded border">
        <div className="px-4 py-2 border-b"><h3 className="font-medium">Create Coupon</h3></div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <input className="border rounded px-2 py-1" placeholder="Code" value={form.code} onChange={e=>setForm({ ...form, code: e.target.value.toUpperCase() })} />
          <input className="border rounded px-2 py-1" placeholder="Name" value={form.name} onChange={e=>setForm({ ...form, name: e.target.value })} />
          <select className="border rounded px-2 py-1" value={form.discount_type} onChange={e=>setForm({ ...form, discount_type: e.target.value })}>
            <option value="PERCENTAGE">Percentage</option>
            <option value="FIXED_AMOUNT">Fixed Amount</option>
          </select>
          {form.discount_type === 'PERCENTAGE' ? (
            <input className="border rounded px-2 py-1" type="number" step="0.01" placeholder="Percent" value={form.percent} onChange={e=>setForm({ ...form, percent: e.target.value })} />
          ) : (
            <input className="border rounded px-2 py-1" type="number" step="0.01" placeholder="Fixed amount" value={form.fixed_amount} onChange={e=>setForm({ ...form, fixed_amount: e.target.value })} />
          )}
          <input className="border rounded px-2 py-1" type="number" step="0.01" placeholder="Min order" value={form.minimum_order_amount} onChange={e=>setForm({ ...form, minimum_order_amount: e.target.value })} />
          <input className="border rounded px-2 py-1" type="number" placeholder="Max uses (blank=∞)" value={form.max_uses} onChange={e=>setForm({ ...form, max_uses: e.target.value })} />
          <input className="border rounded px-2 py-1" type="number" placeholder="Max / customer (blank=∞)" value={form.max_uses_per_customer} onChange={e=>setForm({ ...form, max_uses_per_customer: e.target.value })} />
          <div className="flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={e=>setForm({ ...form, active: e.target.checked })} /><span>Active</span></div>
          <div className="col-span-full">
            <button onClick={()=>create.mutate()} className="px-3 py-2 bg-blue-600 text-white rounded">Create</button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded border">
        <div className="px-4 py-2 border-b flex items-center justify-between">
          <h3 className="font-medium">Existing Coupons</h3>
          <div className="text-sm">Preview with order total: <input className="border rounded px-2 py-1 w-28" value={previewOrderTotal} onChange={e=>setPreviewOrderTotal(e.target.value)} /></div>
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          {coupons.data?.map(c => (
            <div key={c.id} className="border rounded p-3 flex items-center justify-between">
              <div>
                <div className="font-medium">{c.code} · {c.name}</div>
                <div className="text-xs text-gray-500">{c.discount_type === 'PERCENTAGE' ? `-${c.percent}%` : c.discount_type === 'FIXED_AMOUNT' ? `-$${c.fixed_amount}` : c.discount_type}</div>
                <div className="text-xs text-gray-500">Used {c.times_used}{c.max_uses ? ` / ${c.max_uses}` : ''}</div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={()=>toggleActive.mutate(c)} className={`px-2 py-1 text-xs rounded ${c.active ? 'bg-orange-100 text-orange-800' : 'bg-green-100 text-green-800'}`}>{c.active ? 'Deactivate' : 'Activate'}</button>
                <button onClick={async ()=>{
                  const r = await preview.mutateAsync(c.id)
                  alert(r.ok ? `Discount: $${r.discount_amount}` : `Not applicable: ${r.error}`)
                }} className="px-2 py-1 text-xs rounded bg-gray-100">Preview</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

