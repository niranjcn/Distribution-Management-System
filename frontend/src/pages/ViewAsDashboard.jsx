import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { usersAPI } from '../services/api';
import SubDistributorDashboard from './dashboards/SubDistributorDashboard';
import OperatorDashboard from './dashboards/OperatorDashboard';
import { ArrowLeft, Users, Eye } from 'lucide-react';

const ROLE_LABELS = {
  sub_distributor: 'Sub Distributor',
  sub_distribution_manager: 'Sub Distribution Manager',
  cluster: 'Cluster',
  operator: 'Operator',
  sub_distribution_employee: 'Sub Distribution Employee',
};

const ViewAsDashboard = () => {
  const { userId } = useParams();
  const [userInfo, setUserInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError(null);
    setUserInfo(null);

    const loadUser = async () => {
      try {
        const res = await usersAPI.getUser(userId);
        if (ignore) return;
        const target = res?.data || res || null;
        if (!target) throw new Error('User not found');
        const role = String(target.role || '').toLowerCase();
        if (!ROLE_LABELS[role]) {
          throw new Error('Can only view dashboards for Sub Distributors, Clusters, Operators, and Sub Distribution Managers');
        }
        setUserInfo({ ...target, role });
      } catch (err) {
        if (!ignore) setError(err.message || 'Failed to load user');
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    loadUser();
    return () => { ignore = true; };
  }, [userId]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full" />
        </div>
      </div>
    );
  }

  if (error || !userInfo) {
    return (
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-700 font-medium">{error || 'Failed to load dashboard'}</p>
          <Link to="/view-as" className="text-sm text-red-600 underline mt-2 inline-block">Back to search</Link>
        </div>
      </div>
    );
  }

  const role = String(userInfo.role || '').toLowerCase();
  const DashboardComponent = role === 'operator' ? OperatorDashboard : SubDistributorDashboard;

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <Link to="/view-as" className="text-sm text-green-600 hover:text-green-700 flex items-center gap-1 mb-2">
            <ArrowLeft className="w-4 h-4" /> Back to search
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-green-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 break-words">{userInfo.name}</h1>
              <p className="text-sm text-gray-500">{ROLE_LABELS[role]} &middot; ID: {userInfo.id}</p>
            </div>
          </div>
        </div>
        <span className="self-start sm:self-center inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 w-fit">
          <Eye className="w-4 h-4" /> Read-only preview &mdash; user&apos;s view
        </span>
      </div>

      <DashboardComponent key={userInfo.id} viewAsUser={userInfo} />
    </div>
  );
};

export default ViewAsDashboard;