import { useState, useEffect } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import api from '../services/api';
import { updateStoredUser } from '../utils/authStorage';
import { User, Phone, Building, MapPin, Save } from 'lucide-react';

const fieldInputClass = 'w-full px-3.5 py-2.5 border border-gray-300 rounded-lg bg-white text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition-colors';

const FieldLabel = ({ label, icon: Icon }) => (
  <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1.5">
    {Icon && <Icon className="w-4 h-4 text-gray-400" />}
    {label}
  </label>
);

const Settings = () => {
  const { user, setUser } = useAuth();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(false);

  // Supported settings are the user fields that actually exist in the database.
  // They load from the authenticated user object, which is validated against
  // the backend (/auth/me) whenever the app loads.
  const [settings, setSettings] = useState({
    name: user?.name ?? '',
    phone: user?.phone ?? '',
    designation: user?.designation ?? '',
    address: user?.address ?? '',
    pincode: user?.pincode ?? ''
  });

  // Load supported settings from the database-backed user on mount / sign-in.
  useEffect(() => {
    if (user) {
      setSettings({
        name: user.name ?? '',
        phone: user.phone ?? '',
        designation: user.designation ?? '',
        address: user.address ?? '',
        pincode: user.pincode ?? ''
      });
    }
  }, [user]);

  const handleChange = (key) => (e) => {
    setSettings(prev => ({ ...prev, [key]: e.target.value }));
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      // Only persist settings that map to real columns on the users table.
      const updateData = {
        name: settings.name,
        phone: settings.phone,
        designation: settings.designation,
        address: settings.address,
        pincode: settings.pincode
      };

      const response = await api.users.updateUser(user.id, updateData);

      if (response.success) {
        const updatedUser = { ...user, ...response.data };
        setUser(updatedUser);
        updateStoredUser(updatedUser);

        showToast('Settings saved successfully', 'success');
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      showToast(error.message || 'Failed to save settings. Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Settings</h1>
          <p className="text-gray-500 mt-1">Configure your account details</p>
        </div>
        <Button icon={Save} onClick={handleSave} disabled={loading}>
          {loading ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      <Card
        title="Account Settings"
        subtitle="Your details as stored in the system"
        icon={User}
      >
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
            <div>
              <FieldLabel label="Full Name" icon={User} />
              <input
                type="text"
                value={settings.name}
                onChange={handleChange('name')}
                placeholder="Enter full name"
                className={fieldInputClass}
              />
            </div>

            <div>
              <FieldLabel label="Phone" icon={Phone} />
              <input
                type="tel"
                value={settings.phone}
                onChange={handleChange('phone')}
                placeholder="Enter phone number"
                className={fieldInputClass}
              />
            </div>

            <div>
              <FieldLabel label="Designation" icon={Building} />
              <input
                type="text"
                value={settings.designation}
                onChange={handleChange('designation')}
                placeholder="Enter designation"
                className={fieldInputClass}
              />
            </div>

            <div>
              <FieldLabel label="Pincode" icon={MapPin} />
              <input
                type="text"
                value={settings.pincode}
                onChange={handleChange('pincode')}
                placeholder="Enter pincode"
                className={fieldInputClass}
              />
            </div>

            <div className="md:col-span-2">
              <FieldLabel label="Address" icon={MapPin} />
              <textarea
                rows={3}
                value={settings.address}
                onChange={handleChange('address')}
                placeholder="Enter address"
                className={`${fieldInputClass} resize-none leading-relaxed`}
              />
            </div>
          </div>

          <div className="flex justify-end pt-5 mt-6 border-t border-gray-100">
            <Button type="button" icon={Save} onClick={handleSave} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Settings;
