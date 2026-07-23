import { Link } from 'react-router-dom'
import { UserCog, ArrowRight } from 'lucide-react'
import Card from '../ui/Card'
import StatusBadge from '../ui/StatusBadge'

const RecentUsersList = ({ users }) => {
  return (
    <Card
      title="Recent Users"
      icon={UserCog}
      action={
        <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
          Manage users <ArrowRight className="w-4 h-4" />
        </Link>
      }
    >
      <div className="space-y-3">
        {users.slice(0, 5).map((user) => (
          <div key={user.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <span className="text-sm font-medium text-blue-600">{user.name.split(' ').map((n) => n[0]).join('')}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-800">{user.name}</p>
                <p className="text-xs text-gray-500">{user.email}</p>
              </div>
            </div>
            <StatusBadge status={user.role} size="sm" />
          </div>
        ))}
      </div>
    </Card>
  )
}

export default RecentUsersList
