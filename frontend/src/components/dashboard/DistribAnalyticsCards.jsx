const DistribAnalyticsCards = ({ data }) => {
  if (!data) return null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slideUp">
      <div className="bg-gradient-to-br from-blue-50 to-white border border-blue-200 rounded-xl p-4 shadow-sm">
        <p className="text-xs font-semibold text-blue-500 uppercase tracking-wider">Sent to Distribution</p>
        <p className="text-2xl font-bold text-blue-700 mt-1">{data.total_sent_to_distribution ?? 0}</p>
        <p className="text-xs text-blue-400 mt-0.5">Devices distributed/in use</p>
      </div>
      <div className="bg-gradient-to-br from-green-50 to-white border border-green-200 rounded-xl p-4 shadow-sm">
        <p className="text-xs font-semibold text-green-500 uppercase tracking-wider">Remaining Available</p>
        <p className="text-2xl font-bold text-green-700 mt-1">{data.remaining_available_devices ?? 0}</p>
        <p className="text-xs text-green-400 mt-0.5">In stock</p>
      </div>
      {(data.sent_by_type || []).map((item, i) => (
        <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{item.device_type}</p>
          <div className="flex items-center justify-between gap-4">
            <div className="text-center flex-1">
              <p className="text-lg font-bold text-indigo-700">{item.sent}</p>
              <p className="text-[10px] text-indigo-400 font-medium uppercase tracking-wide mt-0.5">Distributed</p>
            </div>
            <div className="w-px h-10 bg-gray-200" />
            <div className="text-center flex-1">
              <p className="text-lg font-bold text-emerald-700">{item.remaining}</p>
              <p className="text-[10px] text-emerald-400 font-medium uppercase tracking-wide mt-0.5">Remaining</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default DistribAnalyticsCards
