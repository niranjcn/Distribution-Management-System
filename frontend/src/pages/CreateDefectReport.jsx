import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { useNotifications } from '../context/NotificationContext';
import { devicesAPI, defectsAPI } from '../services/api';
import { getDeviceSelectLabel } from '../utils/deviceDisplay';
import { normalizeRole } from '../utils/roles';
import { useAuth } from '../context/AuthContext';
import { AlertTriangle, Save, X, Upload, Camera, Search } from 'lucide-react';

const PAGE_SIZE = 100;

const CreateDefectReport = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const isEmployee = normalizeRole(user?.role) === 'sub_distribution_employee';
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);
  const [devices, setDevices] = useState([]);
  const [activeDefectDeviceIds, setActiveDefectDeviceIds] = useState(new Set());
  const [devicePage, setDevicePage] = useState(1);
  const [hasMoreDevices, setHasMoreDevices] = useState(false);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [formData, setFormData] = useState({
    deviceId: '',
    defectType: '',
    severity: '',
    description: '',
    imageFiles: []
  });
  const [submitProgress, setSubmitProgress] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [currentSearch, setCurrentSearch] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
        if (formData.deviceId) {
          const dev = devices.find(d => String(d._id || d.id) === String(formData.deviceId));
          if (dev) {
            setSearchQuery(getDeviceSelectLabel(dev));
          }
        } else {
          setSearchQuery('');
        }
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [formData.deviceId, devices]);

  const fetchDevicesPage = async (page, search, reset) => {
    setLoadingDevices(true);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (search) {
        params.search = search;
      }
      const res = isEmployee ? await devicesAPI.getAvailableDevices(params) : await devicesAPI.getDevices(params);
      const fetchedDevices = res.data || [];
      const pagination = res.pagination || {};

      setDevices(prev => reset ? fetchedDevices : [...prev, ...fetchedDevices]);
      setDevicePage(page);
      setHasMoreDevices(page < (pagination.total_pages || 0));
    } catch (error) {
      console.error('Failed to fetch devices:', error);
    } finally {
      setLoadingDevices(false);
    }
  };

  useEffect(() => {
    const fetchInitial = async () => {
      try {
        const defectsRes = await defectsAPI.getDefects({ page_size: 10000 });
        const activeDefects = (defectsRes.data || []).filter(d =>
          d.status !== 'resolved' && d.status !== 'rejected' && d.status !== 'replaced'
        );
        setActiveDefectDeviceIds(new Set(activeDefects.map(d => String(d.device_id))));
      } catch (error) {
        console.error('Failed to fetch active defects:', error);
      }
      await fetchDevicesPage(1, '', true);
    };
    fetchInitial();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handlePhotoUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      showToast('Image size should be less than 10MB', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      setFormData(prev => ({
        ...prev,
        imageFiles: [...prev.imageFiles, { file, previewUrl: reader.result }]
      }));
    };
    reader.readAsDataURL(file);

    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemovePhoto = (index) => {
    setFormData(prev => {
      const newFiles = [...prev.imageFiles];
      newFiles.splice(index, 1);
      return { ...prev, imageFiles: newFiles };
    });
  };

  const handleSearch = () => {
    if (loadingDevices || !searchQuery.trim()) return;
    setCurrentSearch(searchQuery);
    setDropdownOpen(true);
    fetchDevicesPage(1, searchQuery, true);
  };

  const handleClearSearch = () => {
    if (loadingDevices) return;
    setSearchQuery('');
    setCurrentSearch('');
    setDropdownOpen(true);
    fetchDevicesPage(1, '', true);
  };

  const handleLoadMore = () => {
    if (loadingDevices) return;
    fetchDevicesPage(devicePage + 1, currentSearch, false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const normalizedDescription = (formData.description || '').trim();
    if (!formData.deviceId) {
      showToast('Please select a device', 'error');
      return;
    }
    if (!formData.defectType) {
      showToast('Please select a defect type', 'error');
      return;
    }
    if (!formData.severity) {
      showToast('Please select a severity', 'error');
      return;
    }
    if (normalizedDescription.length < 10) {
      showToast('Description must be at least 10 characters', 'error');
      return;
    }

    setLoading(true);

    try {
      const uploadedUrls = [];
      if (formData.imageFiles.length > 0) {
        setSubmitProgress('Uploading photos...');
        for (const item of formData.imageFiles) {
          const response = await defectsAPI.uploadDefectPhoto(item.file);
          if (response.url) uploadedUrls.push(response.url);
        }
      }

      setSubmitProgress('Submitting report...');
      const normalizedPayload = {
        device_id: String(formData.deviceId || '').trim(),
        defect_type: String(formData.defectType || '').trim().toLowerCase(),
        severity: String(formData.severity || '').trim().toLowerCase(),
        description: normalizedDescription,
        images: uploadedUrls,
      };

      await defectsAPI.createDefect(normalizedPayload);
      showToast('Defect report submitted successfully!', 'success');
      navigate('/defects');
    } catch (error) {
      showToast(error.message || 'Failed to submit defect report', 'error');
    } finally {
      setLoading(false);
      setSubmitProgress('');
    }
  };

  const availableDevices = devices.filter(d =>
    !activeDefectDeviceIds.has(String(d._id || d.id))
  );

  const selectedDevice = devices.find(d => (d._id || d.id) === formData.deviceId);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Report Defect</h1>
        <p className="text-gray-500 mt-1">
          {isEmployee ? 'Submit a defect report for approval under your sub distribution' : 'Submit a defect report for a device'}
        </p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Device Selection (Searchable) */}
          <div ref={dropdownRef} className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Device <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Search by Serial Number, MAC, or NUID..."
                value={dropdownOpen ? searchQuery : (selectedDevice ? getDeviceSelectLabel(selectedDevice) : '')}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (formData.deviceId) {
                    handleChange({ target: { name: 'deviceId', value: '' } });
                  }
                }}
                onFocus={() => {
                  setDropdownOpen(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSearch();
                  }
                }}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                required={!formData.deviceId}
              />
              <Button
                type="button"
                onClick={handleSearch}
                disabled={loadingDevices || !searchQuery.trim()}
                icon={Search}
              >
                Search
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={handleClearSearch}
                disabled={loadingDevices}
                icon={X}
              >
                Clear
              </Button>
            </div>
            {dropdownOpen && (
              <ul className="absolute z-10 w-full mt-1 max-h-60 overflow-y-auto bg-white border border-gray-300 rounded-lg shadow-lg">
                {loadingDevices && devices.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-gray-500 text-center">Loading...</li>
                ) : availableDevices.length > 0 ? (
                  availableDevices.map(device => (
                    <li
                      key={device._id || device.id}
                      onClick={() => {
                        handleChange({ target: { name: 'deviceId', value: device._id || device.id } });
                        setSearchQuery(getDeviceSelectLabel(device));
                        setDropdownOpen(false);
                      }}
                      className="px-3 py-2 cursor-pointer hover:bg-blue-50 text-sm text-gray-700 border-b border-gray-100 last:border-0"
                    >
                      {getDeviceSelectLabel(device)}
                    </li>
                  ))
                ) : (
                  <li className="px-3 py-2 text-sm text-gray-500 text-center">No devices found</li>
                )}
                {hasMoreDevices && !loadingDevices && (
                  <li className="border-t border-gray-100">
                    <button
                      type="button"
                      onClick={handleLoadMore}
                      className="w-full px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 font-medium"
                    >
                      Load More
                    </button>
                  </li>
                )}
                {loadingDevices && devices.length > 0 && (
                  <li className="border-t border-gray-100 px-3 py-2 text-sm text-gray-400 text-center">
                    Loading...
                  </li>
                )}
              </ul>
            )}
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
              {formData.imageFiles.map((item, index) => (
                <div key={index} className="relative aspect-square bg-gray-100 rounded-lg flex items-center justify-center overflow-hidden border border-gray-200">
                  <img
                    src={item.previewUrl}
                    alt={`Defect ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => handleRemovePhoto(index)}
                    className="absolute top-1 right-1 w-6 h-6 bg-red-500/80 hover:bg-red-600 text-white rounded-full flex items-center justify-center transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
              {formData.imageFiles.length < 4 && (
                <>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={handlePhotoUploadClick}
                    disabled={loading}
                    className="aspect-square border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center gap-1 hover:border-blue-500 hover:bg-blue-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Camera className="w-6 h-6 text-gray-400" />
                    <span className="text-xs text-gray-500">Add Photo</span>
                  </button>
                </>
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
            <Button variant="secondary" onClick={() => navigate('/defects')} icon={X} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" loading={loading} icon={Save}>
              {submitProgress || 'Submit Report'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default CreateDefectReport;
