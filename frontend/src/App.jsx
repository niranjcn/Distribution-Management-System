import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import { getLastPath, setLastPath } from './utils/authStorage';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Devices from './pages/Devices';
import RegisterDevice from './pages/RegisterDevice';
import TrackDevice from './pages/TrackDevice';
import Distributions from './pages/Distributions';
import CreateDistribution from './pages/CreateDistribution';
import DefectReports from './pages/DefectReports';
import CreateDefectReport from './pages/CreateDefectReport';
import Returns from './pages/Returns';
import Users from './pages/Users';
import UserHierarchy from './pages/UserHierarchy';
import Approvals from './pages/Approvals';
import Reports from './pages/Reports';
import SubDistributionReport from './pages/SubDistributionReport';
import ClusterReport from './pages/ClusterReport';
import OperatorReport from './pages/OperatorReport';
import Backup from './pages/Backup';
import Activities from './pages/Activities';
import InstallBanner from './components/ui/InstallBanner';
import Notifications from './pages/Notifications';
import ExternalInventory from './pages/ExternalInventory';
import Profile from './pages/Profile';
import NotFound from './pages/NotFound';
import Unauthorized from './pages/Unauthorized';
import ForcedCredentialUpdate from './pages/ForcedCredentialUpdate';
import ChangeRequests from './pages/ChangeRequests';
import EditRequests from './pages/EditRequests';
import ReassignmentRequests from './pages/ReassignmentRequests';
import UserSearch from './pages/UserSearch';
import ViewAsDashboard from './pages/ViewAsDashboard';


import DeliveryConfirmations from './pages/DeliveryConfirmations';
import ReplacementConfirmation from './pages/ReplacementConfirmation';
import Replacements from './pages/Replacements';
import PendingReplacements from './pages/PendingReplacements';
import PendingDues from './pages/PendingDues';

import BulkImportDevices from './pages/BulkImportDevices';
import BulkImportDistribution from './pages/BulkImportDistribution';
import BulkUploadUsers from './pages/BulkUploadUsers';
import ExternalBulkDistribution from './pages/ExternalBulkDistribution';
import { normalizeRole, isForcedCredentialUpdateRequired } from './utils/roles';
import ErrorBoundary from './components/ui/ErrorBoundary';
import { AlertTriangle } from 'lucide-react';

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { user, isAuthenticated, loading } = useAuth();
  const normalizedUserRole = normalizeRole(user?.role);

  if (loading) {
    return (
      <div className="full-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isForcedCredentialUpdateRequired(user) && window.location.pathname !== '/force-update-credentials') {
    return <Navigate to="/force-update-credentials" replace />;
  }

  if (allowedRoles.length > 0 && !allowedRoles.map(normalizeRole).includes(normalizedUserRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

// Public Route Component (redirect to dashboard or last page if already logged in)
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="full-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={getLastPath() || '/'} replace />;
  }

  return children;
};

// Remembers the last authenticated page so an authenticated visit to /login
// (or a fresh tab with a live session) can return the user where they were.
const RouteTracker = () => {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (
      isAuthenticated &&
      location.pathname !== '/login' &&
      location.pathname !== '/unauthorized' &&
      location.pathname !== '/force-update-credentials'
    ) {
      setLastPath(location.pathname + location.search);
    }
  }, [location, isAuthenticated]);

  return null;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      <Route path="/unauthorized" element={<Unauthorized />} />
      <Route
        path="/force-update-credentials"
        element={
          <ProtectedRoute>
            <ForcedCredentialUpdate />
          </ProtectedRoute>
        }
      />

      {/* Protected Routes with Layout */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        {/* Dashboard */}
        <Route index element={<Dashboard />} />

        {/* Devices */}
        <Route path="devices" element={<Devices />} />
        <Route 
          path="devices/register" 
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <RegisterDevice />
            </ProtectedRoute>
          } 
        />
        <Route path="devices/track" element={<TrackDevice />} />
        <Route
          path="devices/bulk-import"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <BulkImportDevices />
            </ProtectedRoute>
          }
        />

        {/* Distributions */}
        <Route path="distributions" element={<Distributions />} />
        <Route 
          path="distributions/create" 
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff', 'sub_distributor', 'cluster', 'operator']}>
              <CreateDistribution />
            </ProtectedRoute>
          } 
        />
        <Route
          path="distributions/bulk-upload"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff', 'sub_distributor', 'cluster', 'operator']}>
              <BulkImportDistribution />
            </ProtectedRoute>
          }
        />

        {/* Defect Reports */}
        <Route path="defects" element={<DefectReports />} />
        <Route
          path="defects/create"
          element={
            <ProtectedRoute allowedRoles={['operator', 'sub_distributor', 'cluster']}>
              <CreateDefectReport />
            </ProtectedRoute>
          }
        />
        <Route
          path="replacements"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <Replacements />
            </ProtectedRoute>
          }
        />
        <Route
          path="replacements/pending"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <PendingReplacements />
            </ProtectedRoute>
          }
        />
        <Route
          path="pending-dues"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <PendingDues />
            </ProtectedRoute>
          }
        />

        {/* Returns */}
        <Route
          path="returns"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <Returns />
            </ProtectedRoute>
          }
        />

        {/* Users - not for staff */}
        <Route 
          path="users" 
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'sub_distribution_manager', 'sub_distributor', 'cluster']}>
              <Users />
            </ProtectedRoute>
          } 
        />
        <Route
          path="users/hierarchy"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'sub_distribution_manager', 'sub_distributor', 'cluster']}>
              <UserHierarchy />
            </ProtectedRoute>
          }
        />
        <Route
          path="users/bulk-upload"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'sub_distribution_manager', 'sub_distributor', 'cluster']}>
              <BulkUploadUsers />
            </ProtectedRoute>
          }
        />

        {/* Approvals */}
        <Route 
          path="approvals" 
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <Approvals />
            </ProtectedRoute>
          } 
        />

        {/* Delivery Confirmations */}
        <Route
          path="delivery-confirmations"
          element={
            <ProtectedRoute allowedRoles={['sub_distributor', 'cluster', 'operator']}>
              <DeliveryConfirmations />
            </ProtectedRoute>
          }
        />

        {/* Replacement Confirmations */}
        <Route
          path="replacement-confirmation"
          element={
            <ProtectedRoute allowedRoles={['operator', 'cluster', 'sub_distributor']}>
              <ReplacementConfirmation />
            </ProtectedRoute>
          }
        />

        {/* Reports (Admin/Manager/Distributor) */}
        <Route 
          path="reports" 
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff']}>
              <Reports />
            </ProtectedRoute>
          } 
        />

        <Route
          path="reports/sub-distribution"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff']}>
              <SubDistributionReport />
            </ProtectedRoute>
          }
        />

        <Route
          path="reports/cluster"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor']}>
              <ClusterReport />
            </ProtectedRoute>
          }
        />

        <Route
          path="reports/operator"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster']}>
              <OperatorReport />
            </ProtectedRoute>
          }
        />

        <Route
          path="backup"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager']}>
              <Backup />
            </ProtectedRoute>
          }
        />

        <Route
          path="activities"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director']}>
              <Activities />
            </ProtectedRoute>
          }
        />

        <Route
          path="external-inventory"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <ExternalInventory tab="items" />
            </ProtectedRoute>
          }
        />

        <Route
          path="external-inventory/distribution"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <ExternalInventory tab="distribution" />
            </ProtectedRoute>
          }
        />

        <Route
          path="external-inventory/bulk"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <ExternalBulkDistribution />
            </ProtectedRoute>
          }
        />

        <Route
          path="external-inventory/distributed"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff']}>
              <ExternalInventory tab="distributed" />
            </ProtectedRoute>
          }
        />

        <Route
          path="notifications"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator']}>
              <Notifications />
            </ProtectedRoute>
          }
        />

        {/* Change Requests */}
        <Route
          path="change-requests"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager']}>
              <ChangeRequests />
            </ProtectedRoute>
          }
        />
        <Route
          path="reassignment-requests"
          element={
            <ProtectedRoute allowedRoles={['super_admin']}>
              <ReassignmentRequests />
            </ProtectedRoute>
          }
        />
        <Route
          path="view-as"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager']}>
              <UserSearch />
            </ProtectedRoute>
          }
        />
        <Route
          path="view-as/:userId"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'md_director', 'manager']}>
              <ViewAsDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="devices/edit-requests"
          element={
            <ProtectedRoute allowedRoles={['super_admin', 'manager']}>
              <EditRequests />
            </ProtectedRoute>
          }
        />

        {/* Profile */}
        <Route path="profile" element={<Profile />} />
      </Route>

      {/* 404 Not Found */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
          <div className="ops-theme full-screen">
            <ErrorBoundary
              name="Page"
              fallback={
                <div className="full-screen flex items-center justify-center bg-gray-50 p-4">
                  <div className="bg-white rounded-xl shadow-sm border border-red-200 p-8 max-w-md w-full text-center">
                    <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center border border-red-200 mx-auto mb-4">
                      <AlertTriangle className="w-6 h-6 text-red-500" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-800 mb-2">Something went wrong</h2>
                    <p className="text-sm text-gray-500 mb-6">An unexpected error occurred while loading this page.</p>
                    <button
                      onClick={() => window.location.reload()}
                      className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Reload Page
                    </button>
                  </div>
                </div>
              }
            >
              <RouteTracker />
              <AppRoutes />
            </ErrorBoundary>
            <InstallBanner />
          </div>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

