import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, DEMO_USERS } from '../context/AuthContext';
import { 
  Box, 
  Eye, 
  EyeOff, 
  LogIn, 
  AlertCircle,
  Truck,
  Users,
  Shield,
  Package
} from 'lucide-react';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);
    
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleDemoLogin = async (user) => {
    setEmail(user.email);
    setPassword(user.password);
    setLoading(true);
    
    const result = await login(user.email, user.password);
    if (result.success) {
      navigate('/');
    }
    setLoading(false);
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'admin': return <Shield className="w-4 h-4" />;
      case 'manager': return <Users className="w-4 h-4" />;
      case 'distributor': return <Truck className="w-4 h-4" />;
      case 'sub-distributor': return <Package className="w-4 h-4" />;
      case 'operator': return <Box className="w-4 h-4" />;
      default: return null;
    }
  };

  const getRoleColor = (role) => {
    switch (role) {
      case 'admin': return 'bg-purple-100 text-purple-700 border-purple-200';
      case 'manager': return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'distributor': return 'bg-green-100 text-green-700 border-green-200';
      case 'sub-distributor': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'operator': return 'bg-gray-100 text-gray-700 border-gray-200';
      default: return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50 flex">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-blue-600 to-blue-800 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center">
              <Truck className="w-7 h-7 text-blue-600" />
            </div>
            <span className="text-2xl font-bold text-white">DMS</span>
          </div>
        </div>
        
        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Distribution<br />Management<br />System
          </h1>
          <p className="text-blue-100 text-lg max-w-md">
            Track devices from NOC through the entire distribution chain. 
            Manage distributions, approvals, returns, and defects all in one place.
          </p>
          
          <div className="grid grid-cols-2 gap-4 pt-6">
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <div className="text-3xl font-bold text-white">5000+</div>
              <div className="text-blue-200 text-sm">Devices Tracked</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <div className="text-3xl font-bold text-white">150+</div>
              <div className="text-blue-200 text-sm">Distributors</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <div className="text-3xl font-bold text-white">98%</div>
              <div className="text-blue-200 text-sm">Approval Rate</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <div className="text-3xl font-bold text-white">24/7</div>
              <div className="text-blue-200 text-sm">Support</div>
            </div>
          </div>
        </div>
        
        <div className="text-blue-200 text-sm">
          © 2024 Distribution Management System. All rights reserved.
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-8">
            <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
              <Truck className="w-7 h-7 text-white" />
            </div>
            <span className="text-2xl font-bold text-gray-800">DMS</span>
          </div>

          <div className="text-center lg:text-left">
            <h2 className="text-3xl font-bold text-gray-900">Welcome back</h2>
            <p className="mt-2 text-gray-600">Please sign in to your account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                placeholder="Enter your email"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors pr-12"
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input type="checkbox" className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" />
                <span className="ml-2 text-sm text-gray-600">Remember me</span>
              </label>
              <a href="#" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                Forgot password?
              </a>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  Sign In
                </>
              )}
            </button>
          </form>

          {/* Demo Accounts */}
          <div className="border-t border-gray-200 pt-6">
            <p className="text-sm text-gray-500 text-center mb-4">Demo Accounts (Click to Login)</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {DEMO_USERS.map((user) => (
                <button
                  key={user.id}
                  onClick={() => handleDemoLogin(user)}
                  disabled={loading}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all hover:shadow-md disabled:opacity-50 ${getRoleColor(user.role)}`}
                >
                  {getRoleIcon(user.role)}
                  <span className="capitalize">{user.role.replace('-', ' ')}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 text-center mt-3">
              Password for all demo accounts follows the pattern: role + 123
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
