import { Link } from 'react-router-dom'
import { Activity, Loader2 } from 'lucide-react'
import Card from '../ui/Card'

const RecentActivitiesList = ({ activities, loading }) => {
  return (
    <Card
      title="Recent Activities"
      icon={Activity}
      action={
        <Link to="/reports" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
          View all
        </Link>
      }
    >
      {loading ? (
        <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>
      ) : (
        <div className="space-y-4">
          {activities.slice(0, 5).map((activity) => (
            <div key={activity.id} className="flex items-start gap-3">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                <Activity className="w-4 h-4 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800">{activity.action}</p>
                <p className="text-sm text-gray-500 truncate">{activity.description}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-400">{activity.user_name || activity.user}</span>
                  <span className="text-xs text-gray-300">.</span>
                  <span className="text-xs text-gray-400">{activity.timestamp ? new Date(activity.timestamp).toLocaleString() : ''}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default RecentActivitiesList
