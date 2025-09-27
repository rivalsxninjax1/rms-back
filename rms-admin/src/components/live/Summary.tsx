// no explicit React import needed with new TS/JSX runtime

export function Summary({ active, pending, preparing, ready, wsConnected } : {
  active: number
  pending: number
  preparing: number
  ready: number
  wsConnected: boolean
}) {
  return (
    <div className="bg-white rounded-lg shadow border">
      <div className="px-4 py-2 border-b flex items-center justify-between">
        <div className="font-medium">Live Online Orders</div>
        <div className="text-xs text-gray-500">{wsConnected ? 'Live updates on' : 'Live updates: disconnected'}</div>
      </div>
      <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
        <div><div className="text-2xl font-semibold">{active}</div><div className="text-xs text-gray-600">Active</div></div>
        <div><div className="text-2xl font-semibold">{pending}</div><div className="text-xs text-gray-600">Pending</div></div>
        <div><div className="text-2xl font-semibold">{preparing}</div><div className="text-xs text-gray-600">Preparing</div></div>
        <div><div className="text-2xl font-semibold">{ready}</div><div className="text-xs text-gray-600">Ready</div></div>
      </div>
    </div>
  )
}
