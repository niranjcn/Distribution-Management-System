import { useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { 
  Settings as SettingsIcon, Bell, Moon, Sun, Globe, 
  Lock, Mail, Save, ToggleLeft, ToggleRight 
} from 'lucide-react';

const Settings = () => {
  const { user, hasRole } = useAuth();
  const { addNotification } = useNotifications();

  const [settings, setSettings] = useState({
    // Notifications
    emailNotifications: true,
    pushNotifications: true,
    distributionAlerts: true,
    defectAlerts: true,
    returnAlerts: true,
    systemUpdates: false,
    
    // Appearance
    theme: 'light',
    compactMode: false,
    animationsEnabled: true,
    
    // Privacy
    showOnlineStatus: true,
    shareActivityData: false,
    
    // System (Admin only)
    maintenanceMode: false,
    debugMode: false,
    autoBackup: true,
    backupFrequency: 'daily'
  });

  const handleToggle = (key) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = () => {
    addNotification({
      type: 'success',
      title: 'Settings Saved',
      message: 'Your settings have been updated successfully.'
    });
  };

  const Toggle = ({ enabled, onChange }) => (
    <button
      onClick={onChange}
      className={`relative w-12 h-6 rounded-full transition-colors ${
        enabled ? 'bg-blue-600' : 'bg-gray-300'
      }`}
    >
      <span
        className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
          enabled ? 'translate-x-7' : 'translate-x-1'
        }`}
      />
    </button>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Settings</h1>
          <p className="text-gray-500 mt-1">Configure your application preferences</p>
        </div>
        <Button icon={Save} onClick={handleSave}>
          Save Changes
        </Button>
      </div>

      {/* Notification Settings */}
      <Card title="Notification Settings" icon={Bell}>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Email Notifications</p>
              <p className="text-sm text-gray-500">Receive notifications via email</p>
            </div>
            <Toggle 
              enabled={settings.emailNotifications} 
              onChange={() => handleToggle('emailNotifications')} 
            />
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Push Notifications</p>
              <p className="text-sm text-gray-500">Receive push notifications in browser</p>
            </div>
            <Toggle 
              enabled={settings.pushNotifications} 
              onChange={() => handleToggle('pushNotifications')} 
            />
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Distribution Alerts</p>
              <p className="text-sm text-gray-500">Get notified about new distributions</p>
            </div>
            <Toggle 
              enabled={settings.distributionAlerts} 
              onChange={() => handleToggle('distributionAlerts')} 
            />
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Defect Alerts</p>
              <p className="text-sm text-gray-500">Get notified about defect reports</p>
            </div>
            <Toggle 
              enabled={settings.defectAlerts} 
              onChange={() => handleToggle('defectAlerts')} 
            />
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Return Alerts</p>
              <p className="text-sm text-gray-500">Get notified about return requests</p>
            </div>
            <Toggle 
              enabled={settings.returnAlerts} 
              onChange={() => handleToggle('returnAlerts')} 
            />
          </div>

          <div className="flex items-center justify-between py-3">
            <div>
              <p className="font-medium text-gray-800">System Updates</p>
              <p className="text-sm text-gray-500">Get notified about system maintenance</p>
            </div>
            <Toggle 
              enabled={settings.systemUpdates} 
              onChange={() => handleToggle('systemUpdates')} 
            />
          </div>
        </div>
      </Card>

      {/* Appearance Settings */}
      <Card title="Appearance" icon={Sun}>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Theme</p>
              <p className="text-sm text-gray-500">Choose your preferred theme</p>
            </div>
            <div className="flex gap-2">
              {['light', 'dark', 'system'].map(theme => (
                <button
                  key={theme}
                  onClick={() => setSettings(prev => ({ ...prev, theme }))}
                  className={`px-3 py-2 rounded-lg capitalize transition-colors ${
                    settings.theme === theme
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {theme === 'light' && <Sun className="w-4 h-4 inline mr-1" />}
                  {theme === 'dark' && <Moon className="w-4 h-4 inline mr-1" />}
                  {theme}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Compact Mode</p>
              <p className="text-sm text-gray-500">Use smaller spacing and fonts</p>
            </div>
            <Toggle 
              enabled={settings.compactMode} 
              onChange={() => handleToggle('compactMode')} 
            />
          </div>

          <div className="flex items-center justify-between py-3">
            <div>
              <p className="font-medium text-gray-800">Animations</p>
              <p className="text-sm text-gray-500">Enable interface animations</p>
            </div>
            <Toggle 
              enabled={settings.animationsEnabled} 
              onChange={() => handleToggle('animationsEnabled')} 
            />
          </div>
        </div>
      </Card>

      {/* Privacy Settings */}
      <Card title="Privacy" icon={Lock}>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div>
              <p className="font-medium text-gray-800">Online Status</p>
              <p className="text-sm text-gray-500">Show when you're online to other users</p>
            </div>
            <Toggle 
              enabled={settings.showOnlineStatus} 
              onChange={() => handleToggle('showOnlineStatus')} 
            />
          </div>

          <div className="flex items-center justify-between py-3">
            <div>
              <p className="font-medium text-gray-800">Share Activity Data</p>
              <p className="text-sm text-gray-500">Help improve the system by sharing usage data</p>
            </div>
            <Toggle 
              enabled={settings.shareActivityData} 
              onChange={() => handleToggle('shareActivityData')} 
            />
          </div>
        </div>
      </Card>

      {/* Admin-only System Settings */}
      {hasRole(['admin']) && (
        <Card title="System Settings (Admin Only)" icon={SettingsIcon}>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="font-medium text-gray-800">Maintenance Mode</p>
                <p className="text-sm text-gray-500">Temporarily disable the system for maintenance</p>
              </div>
              <Toggle 
                enabled={settings.maintenanceMode} 
                onChange={() => handleToggle('maintenanceMode')} 
              />
            </div>

            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="font-medium text-gray-800">Debug Mode</p>
                <p className="text-sm text-gray-500">Enable detailed logging for troubleshooting</p>
              </div>
              <Toggle 
                enabled={settings.debugMode} 
                onChange={() => handleToggle('debugMode')} 
              />
            </div>

            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="font-medium text-gray-800">Auto Backup</p>
                <p className="text-sm text-gray-500">Automatically backup system data</p>
              </div>
              <Toggle 
                enabled={settings.autoBackup} 
                onChange={() => handleToggle('autoBackup')} 
              />
            </div>

            <div className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-gray-800">Backup Frequency</p>
                <p className="text-sm text-gray-500">How often to create backups</p>
              </div>
              <select
                value={settings.backupFrequency}
                onChange={(e) => setSettings(prev => ({ ...prev, backupFrequency: e.target.value }))}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          </div>
        </Card>
      )}

      {/* Regional Settings */}
      <Card title="Regional Settings" icon={Globe}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="ar">Arabic</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option value="UTC">UTC</option>
              <option value="America/New_York">Eastern Time (US)</option>
              <option value="America/Los_Angeles">Pacific Time (US)</option>
              <option value="Europe/London">London</option>
              <option value="Asia/Dubai">Dubai</option>
              <option value="Asia/Tokyo">Tokyo</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date Format</label>
            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option value="MM/DD/YYYY">MM/DD/YYYY</option>
              <option value="DD/MM/YYYY">DD/MM/YYYY</option>
              <option value="YYYY-MM-DD">YYYY-MM-DD</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Time Format</label>
            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
              <option value="12h">12 Hour (AM/PM)</option>
              <option value="24h">24 Hour</option>
            </select>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Settings;
