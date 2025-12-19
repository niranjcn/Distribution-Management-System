import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useNotifications } from '../context/NotificationContext';
import { Box, Save, X, QrCode } from 'lucide-react';

const RegisterDevice = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    macAddress: '',
    serialNumber: '',
    model: '',
    manufacturer: '',
    hardwareVersion: '',
    firmwareVersion: '',
    condition: 'new',
    notes: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    showToast('Device registered successfully!', 'success');
    navigate('/devices');
    setLoading(false);
  };

  const handleScan = () => {
    // Simulate QR/Barcode scan
    setFormData(prev => ({
      ...prev,
      macAddress: 'AA:BB:CC:DD:EE:' + Math.random().toString(16).slice(2, 4).toUpperCase(),
      serialNumber: 'SN-2024-' + Math.floor(Math.random() * 1000).toString().padStart(3, '0')
    }));
    showToast('Device scanned successfully!', 'info');
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Register New Device</h1>
        <p className="text-gray-500 mt-1">Add a new device to the inventory from NOC</p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Scan Button */}
          <div className="flex justify-center">
            <button
              type="button"
              onClick={handleScan}
              className="flex flex-col items-center gap-2 p-6 border-2 border-dashed border-gray-300 rounded-xl hover:border-blue-500 hover:bg-blue-50 transition-colors"
            >
              <QrCode className="w-12 h-12 text-gray-400" />
              <span className="text-sm text-gray-600">Click to scan device barcode/QR code</span>
            </button>
          </div>

          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-4">Or enter details manually</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  MAC Address <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="macAddress"
                  value={formData.macAddress}
                  onChange={handleChange}
                  placeholder="AA:BB:CC:DD:EE:FF"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Serial Number <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="serialNumber"
                  value={formData.serialNumber}
                  onChange={handleChange}
                  placeholder="SN-2024-001"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Device Model <span className="text-red-500">*</span>
                </label>
                <select
                  name="model"
                  value={formData.model}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  <option value="">Select model</option>
                  <option value="Router X500">Router X500</option>
                  <option value="Router X700">Router X700</option>
                  <option value="Switch S200">Switch S200</option>
                  <option value="Switch S300">Switch S300</option>
                  <option value="Modem M100">Modem M100</option>
                  <option value="Modem M200">Modem M200</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Manufacturer <span className="text-red-500">*</span>
                </label>
                <select
                  name="manufacturer"
                  value={formData.manufacturer}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  <option value="">Select manufacturer</option>
                  <option value="NetGear">NetGear</option>
                  <option value="Cisco">Cisco</option>
                  <option value="TP-Link">TP-Link</option>
                  <option value="Linksys">Linksys</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Hardware Version
                </label>
                <input
                  type="text"
                  name="hardwareVersion"
                  value={formData.hardwareVersion}
                  onChange={handleChange}
                  placeholder="2.0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Firmware Version
                </label>
                <input
                  type="text"
                  name="firmwareVersion"
                  value={formData.firmwareVersion}
                  onChange={handleChange}
                  placeholder="5.1.2"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Condition <span className="text-red-500">*</span>
                </label>
                <select
                  name="condition"
                  value={formData.condition}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  <option value="new">New</option>
                  <option value="refurbished">Refurbished</option>
                </select>
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Additional Notes
              </label>
              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                rows={3}
                placeholder="Any additional information about the device..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={() => navigate('/devices')} icon={X}>
              Cancel
            </Button>
            <Button type="submit" loading={loading} icon={Save}>
              Register Device
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default RegisterDevice;
