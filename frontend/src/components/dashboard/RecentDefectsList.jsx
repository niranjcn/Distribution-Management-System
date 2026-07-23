import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import Card from '../ui/Card'
import StatusBadge from '../ui/StatusBadge'

const RecentDefectsList = ({ defects }) => {
  return (
    <Card
      title="Recent Defect Reports"
      icon={AlertTriangle}
      action={
        <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
          View all <ArrowRight className="w-4 h-4" />
        </Link>
      }
    >
      <div className="space-y-3">
        {defects.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">No defect reports yet</p>
        ) : defects.slice(0, 4).map((defect) => (
          <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-800">{defect.device_type || 'Unknown'}</p>
                <StatusBadge status={defect.severity} size="sm" />
              </div>
              <p className="text-xs text-gray-500 mt-0.5">{defect.device_serial || defect.report_id}</p>
              <p className="text-xs text-gray-400 mt-0.5 truncate">{defect.description}</p>
            </div>
            <StatusBadge status={defect.status} size="sm" />
          </div>
        ))}
      </div>
    </Card>
  )
}

export default RecentDefectsList
