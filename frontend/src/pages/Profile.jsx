import { useState, useEffect, useRef } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { authAPI, usersAPI, adminUpdateCredentials } from '../services/api';
import { updateStoredUser } from '../utils/authStorage';
import { 
  User, Mail, Phone, Building, MapPin, Lock, 
  Save, Eye, EyeOff
} from 'lucide-react';

const fieldInputClass = 'w-full px-3.5 py-2.5 border border-gray-300 rounded-lg bg-white text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-600 transition-colors';
const fieldReadOnlyClass = 'w-full px-3.5 py-2.5 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 cursor-not-allowed text-sm';

const FieldLabel = ({ label, icon: Icon }) => (
  <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1.5">
    {Icon && <Icon className="w-4 h-4 text-gray-400" />}
    {label}
  </label>
);

const AutoResizeTextarea = ({ value, onChange, className = '', ...props }) => {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={onChange}
      rows={3}
      className={`w-full px-3.5 py-2.5 border border-gray-300 rounded-lg bg-white text-gray-800 placeholder:text-gray-400 text-sm leading-relaxed resize-none overflow-hidden focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-600 transition-colors ${className}`}
      {...props}
    />
  );
};

const Profile = () => {
  const { user, setUser, logout } = useAuth();
  const { showToast } = useNotifications();
  
  const [activeTab, setActiveTab] = useState('profile');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    designation: user?.designation || '',
    address: user?.address || '',
    pincode: user?.pincode || '',
  });

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  const [emailData, setEmailData] = useState({
    newEmail: ''
  });

  const [phoneData, setPhoneData] = useState({
    newPhone: user?.phone || ''
  });

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: profileData.name,
        designation: profileData.designation,
        address: profileData.address,
        pincode: profileData.pincode,
      };

      const response = await usersAPI.updateUser(user.id, payload);
      // Update auth context with new user data
      const updatedUser = { ...user, ...response.data };
      setUser(updatedUser);
      updateStoredUser(updatedUser);
      showToast('Profile updated successfully', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to update profile', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handlePhoneChange = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const response = await usersAPI.updateUser(user.id, { phone: phoneData.newPhone });
      const updatedUser = { ...user, ...(response.data || {}), phone: phoneData.newPhone };
      setUser(updatedUser);
      updateStoredUser(updatedUser);
      showToast('Phone number updated successfully', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to update phone number', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      showToast('New passwords do not match', 'error');
      return;
    }
    if (passwordData.newPassword.length < 6) {
      showToast('Password must be at least 6 characters', 'error');
      return;
    }

    setSaving(true);
    try {
      await authAPI.changePassword(passwordData.currentPassword, passwordData.newPassword);
      showToast('Password changed successfully', 'success');
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (err) {
      showToast(err.message || 'Failed to change password', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleEmailChange = async (e) => {
    e.preventDefault();

    const nextEmail = String(emailData.newEmail || '').trim().toLowerCase();
    if (!nextEmail) {
      showToast('Please enter a new email address', 'error');
      return;
    }
    if (nextEmail === String(user?.email || '').toLowerCase()) {
      showToast('New email must be different from current email', 'error');
      return;
    }

    setSaving(true);
    try {
      const response = await adminUpdateCredentials(user.id, { email: nextEmail });
      const updatedUser = { ...user, ...(response.data || {}), email: nextEmail };
      setUser(updatedUser);
      updateStoredUser(updatedUser);
      showToast('Email updated successfully', 'success');

      setEmailData({ newEmail: '' });
    } catch (err) {
      showToast(err.message || 'Failed to process email change', 'error');
    } finally {
      setSaving(false);
    }
  };

  const getRoleBadgeColor = (role) => {
    switch (role) {
      case 'super_admin': return 'bg-red-100 text-red-800';
      case 'manager': return 'bg-purple-100 text-purple-800';
      case 'pdic_staff': return 'bg-blue-100 text-blue-800';
      case 'sub_distributor': return 'bg-indigo-100 text-indigo-800';
      case 'cluster': return 'bg-teal-100 text-teal-800';
      case 'operator': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">My Profile</h1>
        <p className="text-gray-500 mt-1">Manage your account settings and preferences</p>
      </div>

      {/* Profile Header */}
      <Card>
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center">
            <span className="text-3xl font-bold text-blue-600">
              {user?.name?.split(' ').map(n => n[0]).join('') || 'U'}
            </span>
          </div>
          <div className="text-center sm:text-left">
            <h2 className="text-xl font-bold text-gray-800">{user?.name}</h2>
            <p className="text-gray-500">{user?.email}</p>
            <span className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-medium capitalize ${getRoleBadgeColor(user?.role)}`}>
              {user?.role?.replace(/[-_]/g, ' ')}
            </span>
          </div>
        </div>
      </Card>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('profile')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'profile'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Profile Information
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'security'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Security
        </button>
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <Card
          icon={User}
          title="Profile Information"
          subtitle="Your personal details as shown across the system"
        >
          <form onSubmit={handleProfileUpdate}>
            <div className="space-y-6">
              {/* Basic Details */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-4">
                  Basic Details
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                  <div>
                    <FieldLabel label="Full Name" icon={User} />
                    <input
                      type="text"
                      value={profileData.name}
                      onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                      placeholder="Enter full name"
                      className={fieldInputClass}
                    />
                  </div>

                  <div>
                    <FieldLabel label="Designation" icon={Building} />
                    <input
                      type="text"
                      value={profileData.designation}
                      onChange={(e) => setProfileData({ ...profileData, designation: e.target.value })}
                      placeholder="Enter designation"
                      className={fieldInputClass}
                    />
                  </div>
                </div>
              </div>

              {/* Contact & Location */}
              <div className="border-t border-gray-100 pt-6">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-4">
                  Contact &amp; Location
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                  <div className="md:col-span-2">
                    <FieldLabel label="Address" icon={MapPin} />
                    <AutoResizeTextarea
                      value={profileData.address}
                      onChange={(e) => setProfileData({ ...profileData, address: e.target.value })}
                      placeholder="Enter address"
                    />
                  </div>

                  <div>
                    <FieldLabel label="Pincode" icon={MapPin} />
                    <input
                      type="text"
                      value={profileData.pincode}
                      onChange={(e) => setProfileData({ ...profileData, pincode: e.target.value })}
                      placeholder="Enter pincode"
                      className={fieldInputClass}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-5 mt-6 border-t border-gray-200">
              <Button type="submit" icon={Save} disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          <Card
            icon={Mail}
            title="Email Address"
            subtitle="Your email is used for signing in and receiving system notifications."
          >
            <form onSubmit={handleEmailChange}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                <div>
                  <FieldLabel label="Current Email" icon={Mail} />
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300" />
                    <input
                      type="email"
                      value={user?.email || ''}
                      disabled
                      className={`${fieldReadOnlyClass} pl-9`}
                    />
                  </div>
                </div>

                <div>
                  <FieldLabel label="New Email" icon={Mail} />
                  <input
                    type="email"
                    value={emailData.newEmail}
                    onChange={(e) => setEmailData({ newEmail: e.target.value })}
                    placeholder="Enter new email"
                    className={fieldInputClass}
                    required
                  />
                  <p className="text-xs text-gray-400 mt-1.5">Your email will be updated immediately when you save.</p>
                </div>
              </div>

              <div className="flex justify-end pt-5 mt-6 border-t border-gray-200">
                <Button type="submit" icon={Mail} disabled={saving}>
                  {saving ? 'Submitting...' : 'Change Email'}
                </Button>
              </div>
            </form>
          </Card>

          <Card
            icon={Phone}
            title="Phone Number"
            subtitle="Your phone number is used for contact and account recovery."
          >
            <form onSubmit={handlePhoneChange}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                <div>
                  <FieldLabel label="Current Phone" icon={Phone} />
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300" />
                    <input
                      type="tel"
                      value={user?.phone || ''}
                      disabled
                      className={`${fieldReadOnlyClass} pl-9`}
                    />
                  </div>
                </div>

                <div>
                  <FieldLabel label="New Phone Number" icon={Phone} />
                  <input
                    type="tel"
                    value={phoneData.newPhone}
                    onChange={(e) => setPhoneData({ newPhone: e.target.value })}
                    placeholder="Enter new phone number"
                    className={fieldInputClass}
                    required
                    minLength={10}
                  />
                  <p className="text-xs text-gray-400 mt-1.5">Your phone number will be updated immediately when you save.</p>
                </div>
              </div>

              <div className="flex justify-end pt-5 mt-6 border-t border-gray-200">
                <Button type="submit" icon={Phone} disabled={saving}>
                  {saving ? 'Submitting...' : 'Change Phone'}
                </Button>
              </div>
            </form>
          </Card>

          <Card
            icon={Lock}
            title="Password"
            subtitle="Use at least 6 characters. Choose something you don't use elsewhere."
          >
            <form onSubmit={handlePasswordChange}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                <div className="md:col-span-2">
                  <FieldLabel label="Current Password" icon={Lock} />
                  <div className="relative max-w-md">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type={showCurrentPassword ? 'text' : 'password'}
                      value={passwordData.currentPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                      className={`${fieldInputClass} pl-9 pr-10`}
                      required
                    />
                    <button type="button" onClick={() => setShowCurrentPassword(!showCurrentPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                      {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <FieldLabel label="New Password" icon={Lock} />
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      value={passwordData.newPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                      className={`${fieldInputClass} pl-9 pr-10`}
                      required
                      minLength={6}
                    />
                    <button type="button" onClick={() => setShowNewPassword(!showNewPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 mt-1.5">Must be at least 6 characters</p>
                </div>

                <div>
                  <FieldLabel label="Confirm New Password" icon={Lock} />
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="password"
                      value={passwordData.confirmPassword}
                      onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                      className={`${fieldInputClass} pl-9`}
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-5 mt-6 border-t border-gray-200">
                <Button type="submit" icon={Lock} disabled={saving}>
                  {saving ? 'Updating...' : 'Update Password'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};

export default Profile;

