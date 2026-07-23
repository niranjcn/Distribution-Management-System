import { Link } from 'react-router-dom'
import { Clock } from 'lucide-react'
import Card from '../ui/Card'
import StatusBadge from '../ui/StatusBadge'

const CriticalAlertsCard = ({ alerts, pendingReassignments, replacementSuccessRate }) => {
  return (
    <Card title="Critical Ops Alerts" icon={Clock}>
      <div className="space-y-3">
        {pendingReassignments > 0 && (
          <Link
            to="/reassignment-requests"
            className="block rounded-lg border border-amber-200 bg-amber-50 p-3 hover:bg-amber-100 transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-amber-800">Reassignment Requests</p>
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-800">
                {pendingReassignments} pending
              </span>
            </div>
            <p className="text-xs text-amber-700 mt-1">
              Users need reassignment before deletion can complete.
            </p>
          </Link>
        )}
        {alerts.length === 0 ? (
          <p className="text-sm text-gray-500">No active alerts right now.</p>
        ) : alerts.map((alert, idx) => (
          <Link
            key={`${alert.title}-${idx}`}
            to={alert.link || '/dashboard'}
            className="block rounded-lg border border-gray-200 p-3 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-gray-800">{alert.title}</p>
              <StatusBadge status={alert.type === 'error' ? 'critical' : 'pending'} size="sm" />
            </div>
            <p className="text-xs text-gray-600 mt-1">{alert.message}</p>
          </Link>
        ))}
        <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
          <p className="text-sm font-semibold text-slate-700">Replacement Success</p>
          <p className="text-2xl font-bold text-slate-900">{replacementSuccessRate ?? 0}%</p>
          <p className="text-xs text-slate-500 mt-1">Confirmed replacement completion ratio</p>
        </div>
      </div>
    </Card>
  )
}

export default CriticalAlertsCard
