import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Eye,
  EyeOff,
  LogIn,
  AlertCircle
} from 'lucide-react';
import kvLogo from '../kv_logo.webp';

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

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-green-700 via-green-800 to-green-900 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-4">
            <div className="w-32 h-32 bg-white/20 backdrop-blur rounded-2xl flex items-center justify-center shadow-lg">
              <img
                src={kvLogo}
                alt="KannurVision"
                className="w-32 h-32 object-contain"
              />
            </div>
            <span className="text-2xl font-bold text-white">KannurVision PDIC</span>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Distribution<br />Management<br />System
          </h1>
          <p className="text-green-100 text-lg max-w-md">
            Track devices from NOC through the entire distribution chain.
            Manage distributions, approvals, returns, and defects all in one place.
          </p>

          <div className="grid grid-cols-2 gap-4 pt-6">
            <div className="bg-white/10 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="text-3xl font-bold text-white">5000+</div>
              <div className="text-green-100 text-sm">Devices Tracked</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="text-3xl font-bold text-white">150+</div>
              <div className="text-green-100 text-sm">Distributors</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="text-3xl font-bold text-white">98%</div>
              <div className="text-green-100 text-sm">Approval Rate</div>
            </div>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4 border border-white/20">
              <div className="text-3xl font-bold text-white">24/7</div>
              <div className="text-green-100 text-sm">Support</div>
            </div>
          </div>
        </div>

        <div className="text-green-200 text-sm">
          © 2026 KannurVision PDIC. All rights reserved.
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8 bg-white rounded-2xl p-8 border border-gray-200 shadow-lg">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-4 mb-8">
            <div className="w-16 h-16 bg-green-700 rounded-2xl flex items-center justify-center">
              <img
                src={kvLogo}
                alt="KannurVision"
                className="w-12 h-12 object-contain"
              />
            </div>
            <span className="text-2xl font-bold text-gray-800">PDIC</span>
          </div>

          <div className="text-center lg:text-left">
            <h2 className="text-3xl font-bold text-gray-900">Welcome back</h2>
            <p className="mt-2 text-gray-500">Please sign in to your account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500/20 focus:border-green-600 transition-colors bg-white text-gray-800"
                placeholder="Enter your email"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500/20 focus:border-green-600 transition-colors pr-12 bg-white text-gray-800"
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input type="checkbox" className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500" />
                <span className="ml-2 text-sm text-gray-500">Remember me</span>
              </label>
              <a href="#" className="text-sm text-green-700 hover:text-green-800 font-medium">
                Forgot password?
              </a>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-700 hover:bg-green-800 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
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
        </div>
      </div>
    </div>
  );
};

export default Login;
