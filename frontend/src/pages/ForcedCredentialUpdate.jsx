import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { AlertCircle, ShieldCheck } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { isForcedCredentialUpdateRequired } from '../utils/roles';

const ForcedCredentialUpdate = () => {
  const { user, completeForcedCredentialUpdate } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!isForcedCredentialUpdateRequired(user)) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match');
      return;
    }

    setLoading(true);
    try {
      const result = await completeForcedCredentialUpdate(currentPassword, newEmail, newPhone, newPassword);
      if (!result.success) {
        setError(result.error || 'Failed to complete update');
        return;
      }

      window.location.href = '/';
    } catch (updateError) {
      setError(updateError.message || 'Failed to complete update');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg rounded-2xl border border-cyan-500/30 bg-slate-900 p-8 shadow-xl">
        <div className="flex items-center gap-3 text-cyan-200 mb-6">
          <ShieldCheck className="w-6 h-6" />
          <h1 className="text-xl font-semibold">First Login Security Update Required</h1>
        </div>

        <p className="text-slate-300 text-sm mb-6">
          This account is using seeded credentials. You must change both email and password before accessing the application.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-400/40 bg-red-950/30 p-3 text-red-200 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-200 mb-1">Current Password</label>
            <input
              type="password"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-200 mb-1">New Email</label>
            <input
              type="email"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-200 mb-1">New Phone Number</label>
            <input
              type="tel"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100"
              value={newPhone}
              onChange={(event) => setNewPhone(event.target.value)}
              placeholder="Enter your phone number"
              required
              minLength={10}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-200 mb-1">New Password</label>
            <input
              type="password"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-200 mb-1">Confirm New Password</label>
            <input
              type="password"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white py-2.5 font-medium"
          >
            {loading ? 'Updating...' : 'Update Credentials'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ForcedCredentialUpdate;
