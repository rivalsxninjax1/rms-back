import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocations, useTableAvailability, useReservations as useResv, useReservationAction, useCreateReservation } from '../hooks/reservations'
import api from '../lib/api'
import LiveDashboard from './LiveDashboard'

interface Location { id: number; name: string }
interface TableAvail { id: number; table_number: string | number; capacity: number; is_free?: boolean; is_active?: boolean; busy?: Array<{start:string;end:string;reservation_id:number}>; free?: Array<{start:string;end:string}> }
interface ReservationRow {
  id: number
  table: number
  party_size: number
  guest_name?: string
  guest_phone?: string
  status: string
  start_time: string
  end_time: string
  deposit_amount?: string
  deposit_paid?: boolean
}

export default function Reservations() {
  const queryClient = useQueryClient()
  const [locationId, setLocationId] = useState<number | undefined>(undefined)
  const [date, setDate] = useState<string>(() => new Date().toISOString().slice(0,10))
  const [startTime, setStartTime] = useState<string>(() => new Date().toISOString().slice(11,16))
  const [endTime, setEndTime] = useState<string>(() => {
    const now = new Date()
    const end = new Date(now.getTime() + 90*60000)
    return end.toISOString().slice(11,16)
  })
  const [statusFilter, setStatusFilter] = useState<string>('')
  const startISO = useMemo(()=> `${date}T${startTime}:00`, [date, startTime])
  const endISO = useMemo(()=> `${date}T${endTime}:00`, [date, endTime])
  const locations = useLocations()
  const loc = locationId || (locations.data?.[0]?.id ?? 1)
  const availability = useTableAvailability(loc, startISO, endISO)
  const reservations = useResv(locationId, date, statusFilter || undefined)
  const checkIn = useReservationAction('check_in')
  const checkOut = useReservationAction('check_out')
  const cancel = useReservationAction('cancel')
  const confirm = useReservationAction('confirm')
  const noShow = useReservationAction('no_show')
  const markPaid = useReservationAction('mark_deposit_paid')
  const markUnpaid = useReservationAction('mark_deposit_unpaid')
  const createRes = useCreateReservation()

  // Floor + selected table timeline state
  const tables: TableAvail[] = availability.data || []
  const [selectedTable, setSelectedTable] = useState<number | null>(null)
  useEffect(() => { if (!selectedTable && tables.length) setSelectedTable(tables[0].id) }, [tables, selectedTable])

  async function quickWalkIn(tableId: number, blockStartISO: string, blockEndISO?: string) {
    const defaultMinutes = blockEndISO ? Math.max(15, Math.min(360, Math.round((new Date(blockEndISO).getTime() - new Date(blockStartISO).getTime())/60000))) : 90
    const minutesRaw = window.prompt('Duration minutes:', String(defaultMinutes)) || String(defaultMinutes)
    const minutes = Math.max(15, Math.min(360, parseInt(minutesRaw || '90', 10) || 90))
    const guest = window.prompt('Guest name (optional):', '') || ''
    const phone = window.prompt('Phone (optional):', '') || ''
    try {
      await api.post('/reservations/walkin/', { table_id: tableId, minutes, guest_name: guest, phone })
      alert('Reservation created')
      queryClient.invalidateQueries({ queryKey: ['table-availability'] })
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    } catch {
      alert('Failed to create reservation (possibly conflict)')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Reservations</h2>
        <div className="flex items-center space-x-3">
          <select
            className="border rounded px-2 py-1"
            value={locationId ?? ''}
            onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)}
          >
            <option value="">All Locations</option>
            {locations.data?.map((loc: Location) => (
              <option key={loc.id} value={loc.id}>{loc.name}</option>
            ))}
          </select>
          <input type="date" className="border rounded px-2 py-1" value={date} onChange={e=>setDate(e.target.value)} />
          <input type="time" className="border rounded px-2 py-1" value={startTime} onChange={e=>setStartTime(e.target.value)} />
          <input type="time" className="border rounded px-2 py-1" value={endTime} onChange={e=>setEndTime(e.target.value)} />
          <select className="border rounded px-2 py-1" value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No Show</option>
          </select>
          <button className="px-3 py-1 bg-gray-100 rounded" onClick={() => { queryClient.invalidateQueries({ queryKey: ['table-availability'] }); queryClient.invalidateQueries({ queryKey: ['reservations'] }) }}>Refresh</button>
          <CreateReservationButton
            disabled={createRes.isPending}
            onCreate={(payload)=> createRes.mutate(payload)}
            tables={availability.data || []}
            locationId={loc}
            date={date}
            start={startISO}
            end={endISO}
          />
        </div>
      </div>

      {/* Floor + Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <div className="lg:col-span-2">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Floor / Table Map</h3>
          {availability.isLoading ? (
            <div className="text-gray-500">Loading availability…</div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-8 gap-3">
              {tables.map(t => (
                <button key={t.id} onClick={()=>setSelectedTable(t.id)} title={t.is_free ? 'Available' : 'Occupied'}
                  className={`p-3 rounded border text-center transition ${selectedTable===t.id ? 'ring-2 ring-indigo-500' : ''} ${t.is_free ? 'bg-green-50 border-green-300' : 'bg-rose-50 border-rose-300'}`}>
                  <div className="text-sm font-semibold">Table {t.table_number}</div>
                  <div className="text-xs text-gray-600">Seats: {t.capacity}</div>
                  <div className={`mt-1 inline-block px-2 py-0.5 rounded text-xs ${t.is_free ? 'bg-green-200 text-green-800' : 'bg-rose-200 text-rose-800'}`}>{t.is_free ? 'Available' : 'Occupied'}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Timeline</h3>
          <div className="text-xs text-gray-600 mb-1">{date}</div>
          <div className="border rounded p-2 bg-white">
            {availability.isLoading ? (
              <div className="text-gray-500">Loading…</div>
            ) : (
              (()=>{
                const t = tables.find(x=>x.id===selectedTable)
                if (!t) return <div className="text-gray-500">Select a table.</div>
                type Block = {start: string; end: string; type: 'free'} | {start: string; end: string; reservation_id: number; type: 'busy'}
                const freeBlocks: Block[] = (t.free||[]).map(b=> ({...b, type:'free' as const}))
                const busyBlocks: Block[] = (t.busy||[]).map(b=> ({...b, type:'busy' as const}))
                const blocks = [...freeBlocks, ...busyBlocks]
                  .sort((a,b)=> (a.start < b.start ? -1 : 1))
                if (!blocks.length) return <div className="text-gray-500">No events in window.</div>
                return (
                  <div className="space-y-2">
                    {blocks.map((b, idx:number)=> (
                      <div key={idx} className={`flex items-center justify-between px-2 py-1 rounded border ${b.type==='busy' ? 'bg-rose-50 border-rose-300' : 'bg-green-50 border-green-300'}`}
                        title={b.type==='busy' ? `Reservation ${'reservation_id' in b ? b.reservation_id : ''}` : 'Free slot'}>
                        <div className="text-xs">
                          <span className="font-medium">{b.start.slice(11,16)} - {b.end.slice(11,16)}</span>
                          {b.type==='busy' && <span className="ml-2 text-rose-700">Busy</span>}
                          {b.type==='free' && <span className="ml-2 text-green-700">Free</span>}
                        </div>
                        {b.type==='free' && (
                          <button className="text-xs px-2 py-0.5 border rounded" onClick={()=>quickWalkIn(t.id, b.start, b.end)}>Walk-in</button>
                        )}
                      </div>
                    ))}
                  </div>
                )
              })()
            )}
          </div>
        </div>
      </div>

      {/* Upcoming Reservations */}
      <div className="bg-white rounded-lg shadow border">
        <div className="px-4 py-2 border-b">
          <h3 className="text-lg font-medium text-gray-900">Upcoming</h3>
        </div>
        {reservations.isLoading ? (
          <div className="px-4 py-4 text-gray-500">Loading…</div>
        ) : reservations.data?.length ? (
          <div className="divide-y">
            {reservations.data.map((r: ReservationRow) => (
              <div key={r.id} className="px-4 py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-gray-900">#{r.id} · Table {r.table} · {new Date(r.start_time).toLocaleString()}</div>
                  <div className="text-sm text-gray-600">Party {r.party_size} · {r.guest_name || 'Guest'} {r.guest_phone ? '('+r.guest_phone+')' : ''}</div>
                  {Number(r.deposit_amount || 0) > 0 && (
                    <div className="text-xs mt-1 flex items-center gap-2">Deposit: ${Number(r.deposit_amount).toFixed(2)} · {r.deposit_paid ? 'Paid' : 'Unpaid'}
                      {r.deposit_paid
                        ? <button className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-800 rounded" onClick={() => markUnpaid.mutate(r.id)}>Mark Unpaid</button>
                        : <button className="px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded" onClick={() => markPaid.mutate(r.id)}>Mark Paid</button>
                      }
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="px-2 py-0.5 rounded text-xs bg-gray-100">{r.status}</span>
                  <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={() => confirm.mutate(r.id)} disabled={confirm.isPending}>Confirm</button>
                  <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={() => checkIn.mutate(r.id)} disabled={checkIn.isPending}>Check-in</button>
                  <button className="px-2 py-1 text-xs bg-gray-100 rounded" onClick={() => checkOut.mutate(r.id)} disabled={checkOut.isPending}>Check-out</button>
                  <button className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded" onClick={() => cancel.mutate(r.id)} disabled={cancel.isPending}>Cancel</button>
                  <button className="px-2 py-1 text-xs bg-rose-100 text-rose-800 rounded" onClick={() => noShow.mutate(r.id)} disabled={noShow.isPending}>No Show</button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-4 py-4 text-gray-500">No upcoming reservations.</div>
        )}
      </div>
      {/* Live Dashboard directly below reservations */}
      <LiveDashboard />
    </div>
  )
}

function CreateReservationButton({ disabled, onCreate, tables, locationId, date, start, end }: { disabled?: boolean; onCreate: (payload:any)=>void; tables: Array<{id:number; table_number:any; capacity:number; is_free:boolean}>; locationId:number; date:string; start:string; end:string }){
  const [open, setOpen] = useState(false)
  const [tableId, setTableId] = useState<number|''>('')
  const [party, setParty] = useState<number>(2)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const submit = () => {
    if (!tableId) return alert('Choose a table')
    const payload = {
      location: locationId,
      table: Number(tableId),
      party_size: Number(party||2),
      guest_name: name,
      guest_phone: phone,
      start_time: start,
      end_time: end,
    }
    onCreate(payload)
    setOpen(false)
  }
  return (
    <>
      <button className="px-3 py-1 bg-indigo-600 text-white rounded" disabled={disabled} onClick={()=>setOpen(true)}>New Reservation</button>
      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-[999]">
          <div className="bg-white rounded shadow-lg w-[520px] max-w-[95vw] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-lg font-semibold">Create Reservation</div>
              <button className="px-2" onClick={()=>setOpen(false)}>✕</button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-sm">Date
                <input className="mt-1 w-full border rounded px-2 py-1" type="date" value={date} readOnly />
              </label>
              <label className="text-sm">Start
                <input className="mt-1 w-full border rounded px-2 py-1" type="text" value={start.replace(':00','').split('T')[1]} readOnly />
              </label>
              <label className="text-sm">End
                <input className="mt-1 w-full border rounded px-2 py-1" type="text" value={end.replace(':00','').split('T')[1]} readOnly />
              </label>
              <label className="text-sm">Party size
                <input className="mt-1 w-full border rounded px-2 py-1" type="number" min={1} value={party} onChange={e=>setParty(Number(e.target.value||'2'))} />
              </label>
              <label className="text-sm col-span-2">Table
                <select className="mt-1 w-full border rounded px-2 py-1" value={tableId} onChange={(e)=> setTableId(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">Choose a table</option>
                  {tables.map(t=> (
                    <option key={t.id} value={t.id} disabled={!t.is_free}>Table {t.table_number} · {t.capacity} seats {t.is_free ? '' : '(busy)'}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm col-span-2">Guest name
                <input className="mt-1 w-full border rounded px-2 py-1" type="text" value={name} onChange={e=>setName(e.target.value)} placeholder="Optional" />
              </label>
              <label className="text-sm col-span-2">Guest phone
                <input className="mt-1 w-full border rounded px-2 py-1" type="tel" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="Optional" />
              </label>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button className="px-3 py-1 border rounded" onClick={()=>setOpen(false)}>Cancel</button>
              <button className="px-3 py-1 bg-indigo-600 text-white rounded" onClick={submit}>Create</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
