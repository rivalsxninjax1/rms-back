// no explicit React import needed with new TS/JSX runtime

export function Controls({ mute, setMute, count } : { mute: boolean, setMute: (v: boolean)=>void, count: number }) {
  return (
    <div className="bg-white rounded-lg shadow border">
      <div className="px-4 py-2 border-b flex items-center justify-between">
        <div className="font-medium">Controls</div>
        <div className="text-xs text-gray-500">{count} shown</div>
      </div>
      <div className="p-3">
        <button onClick={()=> setMute(!mute)} className="px-3 py-1 border rounded text-sm">
          {mute ? 'Unmute' : 'Mute'}
        </button>
      </div>
    </div>
  )
}
