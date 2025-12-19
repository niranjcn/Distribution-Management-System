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
import CreateReturn from './pages/CreateReturn';
import Users from './pages/Users';
import Approvals from './pages/Approvals';
import Reports from './pages/Reports';
import Profile from './pages/Profile';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';
import Unauthorized from './pages/Unauthorized';

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { user, isAuthenticated, loading } = useAuth();

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

  if (allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
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
            <ProtectedRoute allowedRoles={['admin', 'manager', 'distributor']}>
              <RegisterDevice />
            </ProtectedRoute>
          } 
        />
        <Route path="devices/track" element={<TrackDevice />} />

        {/* Distributions */}
        <Route path="distributions" element={<Distributions />} />
        <Route 
          path="distributions/create" 
          element={
            <ProtectedRoute allowedRoles={['admin', 'manager', 'distributor', 'sub-distributor']}>
              <CreateDistribution />
            </ProtectedRoute>
          } 
        />

        {/* Defect Reports */}
        <Route path="defects" element={<DefectReports />} />
        <Route path="defects/create" element={<CreateDefectReport />} />

        {/* Returns */}
        <Route path="returns" element={<Returns />} />
        <Route path="returns/create" element={<CreateReturn />} />

        {/* Users (Admin/Manager only) */}
        <Route 
          path="users" 
          element={
            <ProtectedRoute allowedRoles={['admin', 'manager']}>
              <Users />
            </ProtectedRoute>
          } 
        />

        {/* Approvals */}
        <Route 
          path="approvals" 
          element={
            <ProtectedRoute allowedRoles={['admin', 'manager', 'distributor', 'sub-distributor']}>
              <Approvals />
            </ProtectedRoute>
          } 
        />

        {/* Reports (Admin/Manager/Distributor) */}
        <Route 
          path="reports" 
          element={
            <ProtectedRoute allowedRoles={['admin', 'manager', 'distributor']}>
              <Reports />
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
          <AppRoutes />
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
