import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Button from '../components/ui/Button';
import { ShieldX, Home, LogOut } from 'lucide-react';

const Unauthorized = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center max-w-md">
        <div className="mb-8">
          <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <ShieldX className="w-10 h-10 text-red-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Access Denied</h1>
          <p className="text-gray-500">
            You don't have permission to access this page. 
            Your current role ({user?.role || 'unknown'}) doesn't have the required privileges.
          </p>
        </div>

        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-8">
          <p className="text-sm text-yellow-800">
            If you believe you should have access to this page, please contact your administrator.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/">
            <Button icon={Home}>
              Go to Dashboard
            </Button>
          </Link>
          <Button variant="outline" icon={LogOut} onClick={logout}>
            Switch Account
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Unauthorized;
