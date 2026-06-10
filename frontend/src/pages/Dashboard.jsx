import { useAuth } from '../context/AuthContext';
import AdminDashboard from './dashboards/AdminDashboard';
import ManagerDashboard from './dashboards/ManagerDashboard';
import SubDistributorDashboard from './dashboards/SubDistributorDashboard';
import OperatorDashboard from './dashboards/OperatorDashboard';
import { normalizeRole } from '../utils/roles';

const Dashboard = () => {
  const { user } = useAuth();
  const role = normalizeRole(user?.role);

  const dashboardComponents = {
    super_admin: AdminDashboard,
    md_director: AdminDashboard,
    manager: ManagerDashboard,
    pdic_staff: ManagerDashboard,
    sub_distribution_manager: SubDistributorDashboard,
    sub_distributor: SubDistributorDashboard,
    cluster: SubDistributorDashboard,
    operator: OperatorDashboard,
  };

  const DashboardComponent = dashboardComponents[role] || AdminDashboard;

  return <DashboardComponent />;
};

export default Dashboard;
