import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import { devicesAPI, defectsAPI } from '../services/api';
import { getDeviceSelectLabel } from '../utils/deviceDisplay';
import { AlertTriangle, Save, X, Upload, Camera, Loader2 } from 'lucide-react';

const CreateDefectReport = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(false);
  const [myDevices, setMyDevices] = useState([]);
  const [formData, setFormData] = useState({
    deviceId: '',
    defectType: '',
    severity: '',
    description: '',
    reportTarget: 'manager_admin',
    images: []
  });

  const isOperator = user?.role === 'operator';

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const response = await devicesAPI.getDevices();
        setMyDevices(response.data || []);
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      }
    };
    fetchDevices();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handlePhotoUpload = () => {
    // Simulate photo upload
    setFormData(prev => ({
      ...prev,
      images: [...prev.images, `photo_${prev.images.length + 1}.jpg`]
    }));
    showToast('Photo added', 'info');
  };

  const handleRemovePhoto = (index) => {
    setFormData(prev => ({
      ...prev,
      images: prev.images.filter((_, i) => i !== index)
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const normalizedDescription = (formData.description || '').trim();
    const normalizedPayload = {
      device_id: String(formData.deviceId || '').trim(),
      defect_type: String(formData.defectType || '').trim().toLowerCase(),
      severity: String(formData.severity || '').trim().toLowerCase(),
      description: normalizedDescription,
      images: formData.images || [],
      ...(isOperator ? { report_target: formData.reportTarget } : {})
    };

    if (!normalizedPayload.device_id) {
      showToast('Please select a device', 'error');
      return;
    }
    if (!normalizedPayload.defect_type) {
      showToast('Please select a defect type', 'error');
      return;
    }
    if (!normalizedPayload.severity) {
      showToast('Please select a severity', 'error');
      return;
    }
    if (normalizedDescription.length < 10) {
      showToast('Description must be at least 10 characters', 'error');
      return;
    }

    setLoading(true);
    
    try {
      await defectsAPI.createDefect(normalizedPayload);
      showToast('Defect report submitted successfully!', 'success');
      navigate('/defects');
    } catch (error) {
      showToast(error.message || 'Failed to submit defect report', 'error');
    } finally {
      setLoading(false);
    }
  };

  const selectedDevice = myDevices.find(d => (d._id || d.id) === formData.deviceId);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Report Defect</h1>
        <p className="text-gray-500 mt-1">Submit a defect report for a device</p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Device Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Device <span className="text-red-500">*</span>
            </label>
            <select
              name="deviceId"
              value={formData.deviceId}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">Select a device...</option>
              {myDevices.map(device => (
                <option key={device._id || device.id} value={device._id || device.id}>
                  {getDeviceSelectLabel(device)}
                </option>
              ))}
            </select>
          </div>

          {/* Selected Device Info */}
          {selectedDevice && (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-blue-600" />
                </div>
                <DeviceIdentity device={selectedDevice} />
                <div className="ml-auto">
                  <StatusBadge status={selectedDevice.status} />
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Defect Type <span className="text-red-500">*</span>
              </label>
              <select
                name="defectType"
                value={formData.defectType}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select type...</option>
                <option value="hardware">Hardware</option>
                <option value="software">Software</option>
                <option value="physical_damage">Physical Damage</option>
                <option value="performance">Performance</option>
                <option value="connectivity">Connectivity</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Severity <span className="text-red-500">*</span>
              </label>
              <select
                name="severity"
                value={formData.severity}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select severity...</option>
                <option value="critical">Critical - Device unusable</option>
                <option value="high">High - Major functionality affected</option>
                <option value="medium">Medium - Some functionality affected</option>
                <option value="low">Low - Minor issue</option>
              </select>
            </div>

            {isOperator && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Report To <span className="text-red-500">*</span>
                </label>
                <select
                  name="reportTarget"
                  value={formData.reportTarget}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="manager_admin">Manager/Admin</option>
                  <option value="sub_distributor">Sub Distributor</option>
                </select>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows={4}
              minLength={10}
              placeholder="Describe the defect in detail..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
            <p className="text-xs text-gray-500 mt-1">Minimum 10 characters.</p>
          </div>

          {/* Photo Upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Photos (Optional)
            </label>
            <div className="grid grid-cols-4 gap-3">
              {formData.images.map((photo, index) => (
                <div key={index} className="relative aspect-square bg-gray-100 rounded-lg flex items-center justify-center">
                  <span className="text-xs text-gray-500">{photo}</span>
                  <button
                    type="button"
                    onClick={() => handleRemovePhoto(index)}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs"
                  >
                    ×
                  </button>
                </div>
              ))}
              {formData.images.length < 4 && (
                <button
                  type="button"
                  onClick={handlePhotoUpload}
                  className="aspect-square border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center gap-1 hover:border-blue-500 hover:bg-blue-50 transition-colors"
                >
                  <Camera className="w-6 h-6 text-gray-400" />
                  <span className="text-xs text-gray-500">Add Photo</span>
                </button>
              )}
            </div>
          </div>

          {/* Severity Warning */}
          {formData.severity === 'critical' && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-red-800">Critical Defect</p>
                <p className="text-sm text-red-600">
                  Critical defects will be prioritized and may qualify for immediate device replacement.
                </p>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={() => navigate('/defects')} icon={X}>
              Cancel
            </Button>
            <Button type="submit" loading={loading} icon={Save}>
              Submit Report
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default CreateDefectReport;
