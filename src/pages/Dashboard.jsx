import { useAuth } from '../context/AuthContext';
import AdminDashboard from './dashboards/AdminDashboard';
import ManagerDashboard from './dashboards/ManagerDashboard';
import DistributorDashboard from './dashboards/DistributorDashboard';
import SubDistributorDashboard from './dashboards/SubDistributorDashboard';
import OperatorDashboard from './dashboards/OperatorDashboard';

const Dashboard = () => {
  const { user } = useAuth();

  const dashboardComponents = {
    admin: AdminDashboard,
    manager: ManagerDashboard,
    distributor: DistributorDashboard,
    'sub-distributor': SubDistributorDashboard,
    operator: OperatorDashboard,
  };

  const DashboardComponent = dashboardComponents[user?.role] || AdminDashboard;

  return <DashboardComponent />;
};

export default Dashboard;
