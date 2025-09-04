// src/lib/db.ts
// Lightweight IndexedDB helpers for caching and offline queue

type StoreName = 'orders' | 'reservations' | 'menu' | 'queue' | 'meta'

const DB_NAME = 'rms-admin'
const DB_VERSION = 1

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      const stores: StoreName[] = ['orders', 'reservations', 'menu', 'queue', 'meta']
      stores.forEach((name) => {
        if (!db.objectStoreNames.contains(name)) {
          db.createObjectStore(name)
        }
      })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function withStore<T>(store: StoreName, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => void): Promise<T> {
  return openDB().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(store, mode)
        const st = tx.objectStore(store)
        let result: T | undefined
        tx.oncomplete = () => resolve(result as T)
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
        result = fn(st) as unknown as T
      })
  )
}

export const idb = {
  get<T = unknown>(store: StoreName, key: IDBValidKey): Promise<T | undefined> {
    return withStore<T | undefined>(store, 'readonly', (st) => {
      const req = st.get(key)
      ;(req as any).onsuccess = () => {}
      return new Promise<T | undefined>((resolve) => {
        req.onsuccess = () => resolve(req.result as T | undefined)
      }) as unknown as T | undefined
    })
  },
  set(store: StoreName, key: IDBValidKey, val: any): Promise<void> {
    return withStore<void>(store, 'readwrite', (st) => {
      st.put(val, key)
    })
  },
  del(store: StoreName, key: IDBValidKey): Promise<void> {
    return withStore<void>(store, 'readwrite', (st) => {
      st.delete(key)
    })
  },
  clear(store: StoreName): Promise<void> {
    return withStore<void>(store, 'readwrite', (st) => {
      st.clear()
    })
  },
  keys(store: StoreName): Promise<IDBValidKey[]> {
    return withStore<IDBValidKey[]>(store, 'readonly', (st) => {
      const req = st.getAllKeys()
      return new Promise<IDBValidKey[]>((resolve) => {
        req.onsuccess = () => resolve(req.result as IDBValidKey[])
      }) as unknown as IDBValidKey[]
    })
  },
  getAll<T = unknown>(store: StoreName): Promise<T[]> {
    return withStore<T[]>(store, 'readonly', (st) => {
      const req = st.getAll()
      return new Promise<T[]>((resolve) => {
        req.onsuccess = () => resolve(req.result as T[])
      }) as unknown as T[]
    })
  },
  pushQueue(job: any): Promise<void> {
    const key = `${Date.now()}_${Math.random().toString(36).slice(2)}`
    return idb.set('queue', key, job)
  },
  getQueue(): Promise<{ key: IDBValidKey; job: any }[]> {
    return withStore<{ key: IDBValidKey; job: any }[]>('queue', 'readonly', (st) => {
      const keysReq = st.getAllKeys()
      const valsReq = st.getAll()
      return new Promise((resolve) => {
        let keys: IDBValidKey[] = []
        let vals: any[] = []
        keysReq.onsuccess = () => {
          keys = keysReq.result as IDBValidKey[]
          if (vals.length) finish()
        }
        valsReq.onsuccess = () => {
          vals = valsReq.result as any[]
          if (keys.length) finish()
        }
        function finish() {
          resolve(keys.map((k, i) => ({ key: k, job: vals[i] })))
        }
      }) as unknown as { key: IDBValidKey; job: any }[]
    })
  },
  removeQueueItem(key: IDBValidKey): Promise<void> {
    return idb.del('queue', key)
  },
}

// --------- Caching helpers ---------
const API_BASE = (import.meta as any).env?.VITE_API_BASE || ''

async function fetchJSON(path: string): Promise<any> {
  const res = await fetch(API_BASE + path, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function cacheOrders(status: string): Promise<void> {
  const data = await fetchJSON(`/api/orders/?status=${encodeURIComponent(status)}`)
  await idb.set('orders', status, data)
}

export async function cacheReservationsFor(dateISO: string): Promise<void> {
  const data = await fetchJSON(`/api/reservations/?date=${encodeURIComponent(dateISO)}`)
  await idb.set('reservations', dateISO, data)
}

export async function cacheMenu(): Promise<void> {
  const [items, modifiers] = await Promise.all([
    fetchJSON('/api/menu/items/'),
    fetchJSON('/api/menu/modifiers/'),
  ])
  await idb.set('menu', 'items', items)
  await idb.set('menu', 'modifiers', modifiers)
}

// Queue a local in-house order to sync when online
export async function queueLocalOrder(payload: any): Promise<void> {
  await idb.pushQueue({ type: 'create_order', payload })
}

export async function syncQueue(onProgress?: (n: number) => void): Promise<number> {
  const list = await idb.getQueue()
  let done = 0
  for (const { key, job } of list) {
    try {
      if (job?.type === 'create_order') {
        const res = await fetch(API_BASE + '/api/orders/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(job.payload),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
      }
      await idb.removeQueueItem(key)
      done++
      onProgress?.(done)
    } catch (err) {
      // keep in queue, continue
    }
  }
  return done
}

