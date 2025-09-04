import { create } from 'zustand'

interface SyncState {
  online: boolean
  lastSync: number | null
  pending: number
  setOnline: (b: boolean) => void
  setLastSync: (t: number) => void
  setPending: (n: number) => void
}

export const useSyncStore = create<SyncState>((set) => ({
  online: typeof navigator !== 'undefined' ? navigator.onLine : true,
  lastSync: null,
  pending: 0,
  setOnline: (b) => set({ online: b }),
  setLastSync: (t) => set({ lastSync: t }),
  setPending: (n) => set({ pending: n }),
}))

