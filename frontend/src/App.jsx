import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
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
import Backup from './pages/Backup';
import Activities from './pages/Activities';
import Notifications from './pages/Notifications';
import ExternalInventory from './pages/ExternalInventory';
import Profile from './pages/Profile';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';
import Unauthorized from './pages/Unauthorized';
import ForcedCredentialUpdate from './pages/ForcedCredentialUpdate';
import ChangeRequests from './pages/ChangeRequests';


import DeliveryConfirmations from './pages/DeliveryConfirmations';
import ReplacementConfirmation from './pages/ReplacementConfirmation';
import Replacements from './pages/Replacements';
import PendingReplacements from './pages/PendingReplacements';
import PendingDues from './pages/PendingDues';

import BulkImportDevices from './pages/BulkImportDevices';
import BulkImportDistribution from './pages/BulkImportDistribution';
import { normalizeRole, isForcedCredentialUpdateRequired } from './utils/roles';

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { user, isAuthenticated, loading } = useAuth();
  const normalizedUserRole = normalizeRole(user?.role);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
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

// Public Route Component (redirect to dashboard if already logged in)
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
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
              <ExternalInventory />
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

        {/* Profile & Settings */}
        <Route path="profile" element={<Profile />} />
        <Route path="settings" element={<Settings />} />
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
          <div className="ops-theme min-h-screen">
            <AppRoutes />
          </div>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

