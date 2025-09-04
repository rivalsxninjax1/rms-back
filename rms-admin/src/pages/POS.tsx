import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

type Category = { id:number; name:string }
type Item = { id:number; name:string; price:string; image_url?:string; category?: { id:number; name:string } }
type Modifier = { id:number; name:string; price:string }
type ModifierGroup = { id:number; name:string; is_required:boolean; min_select:number; max_select:number; modifiers: Modifier[] }
type Cart = { cart_uuid:string; items:Array<CartItem>; subtotal:string; tax_amount:string; total:string; delivery_option:string }
type CartItem = { id:number; menu_item:{ id:number; name:string }; quantity:number; line_total:string }
type Table = { id:number; table_number:string|number; capacity:number }

export default function POS(){
  const qc = useQueryClient()
  const [categoryId, setCategoryId] = useState<number|''>('')
  const [search, setSearch] = useState('')
  const [service, setService] = useState<'DINE_IN'|'PICKUP'|'DELIVERY'>('DINE_IN')
  const [tableId, setTableId] = useState<number|''>('')
  const categories = useQuery({ queryKey:['pos-categories'], queryFn: async()=> (await api.get('/categories/')).data })
  const items = useQuery({ 
    queryKey:['pos-items', categoryId || '', search], 
    queryFn: async()=> (await api.get(`/items/?is_available=true${categoryId?`&category=${categoryId}`:''}${search?`&search=${encodeURIComponent(search)}`:''}`)).data,
  })
  // Active cart
  const cart = useQuery({ queryKey:['pos-cart'], queryFn: async()=> (await api.get('/carts/')).data })
  // Tables for dine-in (first location by default)
  const locations = useQuery({ queryKey:['pos-locations'], queryFn: async()=> (await api.get('/core/locations/')).data })
  const locId = locations.data?.[0]?.id
  const tables = useQuery({ queryKey:['pos-tables', locId||0], enabled: !!locId, queryFn: async()=> (await api.get(`/core/tables/?location=${locId}&is_active=true`)).data })

  const addItem = useMutation({
    mutationFn: async (payload: { menu_item_id:number; quantity:number; selected_modifiers?: Array<{modifier_id:number;quantity:number}>}) => {
      return (await api.post('/carts/add_item/', payload)).data
    },
    onSuccess: ()=> qc.invalidateQueries({ queryKey:['pos-cart'] })
  })
  const patchItem = useMutation({
    mutationFn: async (payload: { cart_item_id:number; quantity:number }) => (await api.patch('/carts/update_item/', payload)).data,
    onSuccess: ()=> qc.invalidateQueries({ queryKey:['pos-cart'] })
  })
  const clearCart = useMutation({ mutationFn: async()=> (await api.delete('/carts/clear/')).data, onSuccess: ()=> qc.invalidateQueries({ queryKey:['pos-cart'] }) })
  const assignTable = useMutation({ mutationFn: async({table_id, delivery_option}:{table_id?:number; delivery_option?:string}) => (await api.post('/carts/assign_table/', { table_id, delivery_option })).data, onSuccess: ()=> qc.invalidateQueries({ queryKey:['pos-cart'] }) })
  const createOrder = useMutation({ mutationFn: async({ cart_uuid }:{ cart_uuid:string }) => (await api.post('/orders/', { cart_uuid })).data })

  const cartData: Cart|undefined = cart.data
  const cartUUID = cartData?.cart_uuid
  const [modTarget, setModTarget] = useState<{ item: Item }|undefined>(undefined)

  // Assign service/table when changed
  useEffect(()=>{ if (!cartUUID) return; assignTable.mutate({ table_id: service==='DINE_IN' && tableId ? Number(tableId) : undefined, delivery_option: service }) }, [service, tableId, cartUUID])

  return (
    <div className="grid grid-cols-[2fr_1fr] gap-4">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <input className="border rounded px-2 py-1 flex-1" placeholder="Search menu" value={search} onChange={e=>setSearch(e.target.value)} />
          <select className="border rounded px-2 py-1" value={categoryId} onChange={e=>setCategoryId(e.target.value? Number(e.target.value):'')}>
            <option value="">All</option>
            {categories.data?.map((c:Category)=>(<option key={c.id} value={c.id}>{c.name}</option>))}
          </select>
          <select className="border rounded px-2 py-1" value={service} onChange={e=>setService(e.target.value as any)}>
            <option value="DINE_IN">Dine-in</option>
            <option value="PICKUP">Pickup</option>
            <option value="DELIVERY">Delivery</option>
          </select>
          {service==='DINE_IN' && (
            <select className="border rounded px-2 py-1" value={tableId} onChange={e=>setTableId(e.target.value? Number(e.target.value):'')}>
              <option value="">Table</option>
              {tables.data?.results?.map((t:Table)=>(<option key={t.id} value={t.id}>Table {t.table_number} · {t.capacity}</option>))}
            </select>
          )}
        </div>
        {/* Items grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {(items.data?.results || items.data || []).map((it:Item)=> (
            <button key={it.id} className="p-3 rounded border text-left hover:bg-gray-50" onClick={()=> setModTarget({ item: it })}>
              <div className="font-medium">{it.name}</div>
              <div className="text-sm text-gray-600">${Number(it.price).toFixed(2)}</div>
            </button>
          ))}
        </div>
      </div>
      {/* Cart */}
      <div className="bg-white rounded-lg shadow border p-3 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="text-lg font-semibold">Cart</div>
          <button className="text-sm px-2 py-1 border rounded" onClick={()=> clearCart.mutate()} disabled={clearCart.isPending}>Clear</button>
        </div>
        <div className="flex-1 divide-y">
          {cartData?.items?.length ? cartData.items.map((ci:CartItem)=> (
            <div key={ci.id} className="py-2 flex items-center justify-between">
              <div>
                <div className="font-medium">{ci.menu_item.name}</div>
                <div className="text-xs text-gray-600">${Number(ci.line_total).toFixed(2)}</div>
              </div>
              <div className="flex items-center gap-2">
                <button className="px-2 py-1 border rounded" onClick={()=> patchItem.mutate({ cart_item_id: ci.id, quantity: ci.quantity - 1 })}>-</button>
                <div className="w-8 text-center">{ci.quantity}</div>
                <button className="px-2 py-1 border rounded" onClick={()=> patchItem.mutate({ cart_item_id: ci.id, quantity: ci.quantity + 1 })}>+</button>
              </div>
            </div>
          )) : (
            <div className="text-gray-500">No items.</div>
          )}
        </div>
        <div className="border-t pt-2 space-y-1 text-sm">
          <div className="flex items-center justify-between"><span>Subtotal</span><span>${Number(cartData?.subtotal||0).toFixed(2)}</span></div>
          <div className="flex items-center justify-between"><span>Tax</span><span>${Number(cartData?.tax_amount||0).toFixed(2)}</span></div>
          <div className="flex items-center justify-between font-semibold"><span>Total</span><span>${Number(cartData?.total||0).toFixed(2)}</span></div>
          <button className="mt-2 w-full px-3 py-2 bg-indigo-600 text-white rounded" disabled={!cartUUID || createOrder.isPending} onClick={async()=>{
            if (service==='DINE_IN' && !tableId){ alert('Choose a table for dine-in'); return }
            if (!cartUUID){ return }
            await createOrder.mutateAsync({ cart_uuid: cartUUID })
            alert('Order created')
            qc.invalidateQueries({ queryKey:['pos-cart'] })
          }}>Place Order</button>
        </div>
      </div>
      <ModifiersModal target={modTarget} onClose={()=> setModTarget(undefined)} onAdd={(payload)=> addItem.mutate(payload)} />
    </div>
  )
}

function useItemModifiers(itemId?: number){
  return useQuery({
    queryKey: ['pos-mods', itemId||0],
    enabled: !!itemId,
    queryFn: async()=> (await api.get(`/items/${itemId}/modifiers/`)).data as ModifierGroup[]
  })
}

function ModifiersModal({ target, onClose, onAdd }: { target?: { item: Item }|undefined; onClose: ()=>void; onAdd:(payload:{ menu_item_id:number; quantity:number; selected_modifiers?: Array<{modifier_id:number;quantity:number}>})=>void }){
  const item = target?.item
  const mods = useItemModifiers(item?.id)
  const [selected, setSelected] = useState<Record<number, boolean>>({})
  useEffect(()=>{ setSelected({}) }, [item?.id])
  if (!item) return null
  const groups: ModifierGroup[] = mods.data || []
  const toggle = (id:number) => setSelected(s=> ({ ...s, [id]: !s[id] }))
  const submit = () => {
    const chosen = Object.entries(selected).filter(([,v])=>v).map(([k])=>({ modifier_id: Number(k), quantity: 1 }))
    onAdd({ menu_item_id: item.id, quantity: 1, selected_modifiers: chosen })
    onClose()
  }
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-[999]">
      <div className="bg-white rounded shadow-lg w-[560px] max-w-[95vw] p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">{item.name}</div>
          <button className="px-2" onClick={onClose}>✕</button>
        </div>
        {!mods.isLoading ? (
          <div className="space-y-3 max-h-[60vh] overflow-auto">
            {groups.length ? groups.map(g=> (
              <div key={g.id}>
                <div className="font-medium text-sm">{g.name}{g.is_required ? ' *' : ''}</div>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  {g.modifiers.map(m=> (
                    <label key={m.id} className="flex items-center gap-2 text-sm border rounded px-2 py-1">
                      <input type="checkbox" checked={!!selected[m.id]} onChange={()=> toggle(m.id)} />
                      <span className="flex-1">{m.name}</span>
                      <span>${Number(m.price).toFixed(2)}</span>
                    </label>
                  ))}
                </div>
              </div>
            )) : <div className="text-gray-500 text-sm">No extras</div>}
          </div>
        ) : <div className="text-gray-500">Loading…</div>}
        <div className="flex items-center justify-end gap-2">
          <button className="px-3 py-1 border rounded" onClick={onClose}>Cancel</button>
          <button className="px-3 py-1 bg-indigo-600 text-white rounded" onClick={submit}>Add</button>
        </div>
      </div>
    </div>
  )
}
