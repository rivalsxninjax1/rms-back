import { useEffect, useState } from 'react'
import { useSyncStore } from '../lib/sync'
import { idb, syncQueue } from '../lib/db'

export default function SyncBar() {
  const online = useSyncStore((s) => s.online)
  const lastSync = useSyncStore((s) => s.lastSync)
  const pending = useSyncStore((s) => s.pending)
  const setPending = useSyncStore((s) => s.setPending)
  const setLastSync = useSyncStore((s) => s.setLastSync)

  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    // load queue size
    idb.keys('queue').then((ks) => setPending(ks.length)).catch(() => {})
  }, [setPending])

  async function doSync() {
    setSyncing(true)
    try {
      const count = await syncQueue((n) => setPending(pending - 1 + 0 * n))
      // refresh pending count
      const ks = await idb.keys('queue')
      setPending(ks.length)
      if (count > 0) setLastSync(Date.now())
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="fixed bottom-2 right-2 px-3 py-2 rounded-md shadow border bg-white text-sm flex items-center gap-3">
      <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-500' : 'bg-gray-400'}`} />
      <span>{online ? 'Online' : 'Offline'}</span>
      <span className="text-gray-500">|</span>
      <span>
        Last sync: {lastSync ? new Date(lastSync).toLocaleTimeString() : '—'}
      </span>
      <span className="text-gray-500">|</span>
      <span>Pending: {pending}</span>
      <button
        className="ml-2 px-2 py-1 border rounded disabled:opacity-50"
        onClick={doSync}
        disabled={syncing || (!online && pending === 0)}
        title={online ? 'Sync now' : 'Go online to sync'}
      >
        {syncing ? 'Syncing…' : 'Sync'}
      </button>
    </div>
  )
}

