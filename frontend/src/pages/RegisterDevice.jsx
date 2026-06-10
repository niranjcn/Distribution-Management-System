import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useNotifications } from '../context/NotificationContext';
import { devicesAPI } from '../services/api';
import { Box, Save, X, Camera, XCircle, AlertCircle } from 'lucide-react';
import { Html5QrcodeScanner } from 'html5-qrcode';

const isSbType = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  return normalized === 'sb' || normalized === 'stb' || normalized === 'settopbox' || normalized === 'setupbox';
};

const RegisterDevice = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(false);
  const [showCameraScanner, setShowCameraScanner] = useState(false);
  const html5QrCodeRef = useRef(null);
  
  const [formData, setFormData] = useState({
    macAddress: '',
    serialNumber: '',
    model: '',
    manufacturer: '',
    bandType: 'single_band',
    boxType: 'HD',
    nuid: '',
    hardwareVersion: '',
    firmwareVersion: '',
    deviceType: 'ONT',
    condition: 'new',
    notes: ''
  });

  // Initialize camera scanner
  useEffect(() => {
    if (showCameraScanner && !html5QrCodeRef.current) {
      console.log('[RegisterDevice] Initializing camera scanner');
      try {
        const config = {
          fps: 10,
          qrbox: { width: 250, height: 250 },
          aspectRatio: 1.0,
          disableFlip: false,
          // Suppress error logging from the library
          verbose: false,
        };

        const scanner = new Html5QrcodeScanner('qr-reader', config, false);
        html5QrCodeRef.current = scanner;
        scanner.render(onScanSuccess, onScanError);
        console.log('[RegisterDevice] Camera scanner initialized successfully');
      } catch (error) {
        console.error('[RegisterDevice] Failed to initialize scanner:', error);
        showToast('Failed to initialize camera scanner', 'error');
        setShowCameraScanner(false);
      }
    }

    return () => {
      if (html5QrCodeRef.current) {
        console.log('[RegisterDevice] Cleaning up camera scanner');
        html5QrCodeRef.current.clear().catch(err => {
          console.error('[RegisterDevice] Failed to clear scanner on cleanup:', err);
        });
        html5QrCodeRef.current = null;
      }
    };
  }, [showCameraScanner]);

  const onScanSuccess = (decodedText, decodedResult) => {
    console.log('[RegisterDevice] Barcode/QR scan successful');
    console.log('[RegisterDevice] Scanned text:', decodedText);
    console.log('[RegisterDevice] Decoded result:', decodedResult);
    
    try {
      // Parse the scanned text for device info
      const text = decodedText.toUpperCase();
      
      // Try to extract MAC address (various formats)
      const macMatch = text.match(/([0-9A-F]{2}[:\-]?[0-9A-F]{2}[:\-]?[0-9A-F]{2}[:\-]?[0-9A-F]{2}[:\-]?[0-9A-F]{2}[:\-]?[0-9A-F]{2})/);
      if (macMatch) {
        const mac = macMatch[1].replace(/[:\-]/g, '');
        const formattedMac = mac.match(/.{2}/g)?.join(':') || mac;
        console.log('[RegisterDevice] Extracted MAC address:', formattedMac);
        setFormData(prev => ({ ...prev, macAddress: formattedMac }));
      }
      
      // Try to extract serial number
      const snMatch = text.match(/S\/?N[:\s]*([A-Z0-9\-]+)/i);
      if (snMatch) {
        console.log('[RegisterDevice] Extracted serial number:', snMatch[1]);
        setFormData(prev => ({ ...prev, serialNumber: snMatch[1] }));
      }
      
      // Try to extract model
      const modelMatch = text.match(/MODEL[:\s]*([A-Z0-9\-]+)/i);
      if (modelMatch) {
        console.log('[RegisterDevice] Extracted model:', modelMatch[1]);
        setFormData(prev => ({ ...prev, model: modelMatch[1] }));
      }
      
      // If no patterns matched, just put the scanned text in serial number
      if (!macMatch && !snMatch && !modelMatch) {
        console.log('[RegisterDevice] No patterns matched, using text as serial number');
        setFormData(prev => ({ ...prev, serialNumber: decodedText }));
      }
      
      showToast('Device scanned successfully!', 'success');
      closeCameraScanner();
    } catch (error) {
      console.error('[RegisterDevice] Error parsing scanned data:', error);
      showToast('Scanned but failed to parse data. Please enter manually.', 'warning');
      closeCameraScanner();
    }
  };

  const onScanError = (error) => {
    // The html5-qrcode library passes various types of errors
    // Convert to string safely for checking
    let errorString = '';
    try {
      if (error === null || error === undefined) {
        return; // Ignore null/undefined errors
      }
      if (typeof error === 'string') {
        errorString = error;
      } else if (error instanceof Error) {
        errorString = error.message || error.toString();
      } else if (typeof error === 'object') {
        errorString = JSON.stringify(error);
      } else {
        errorString = String(error);
      }
    } catch (e) {
      // If we can't convert the error, just ignore it
      return;
    }
    
    // Suppress common scanning errors that occur during normal operation
    // These errors are expected when no code is detected in the current frame
    if (errorString.includes('NotFoundException') || 
        errorString.includes('No MultiFormat Readers') ||
        errorString.includes('QR code parse error') ||
        errorString.includes('No barcode or QR code detected')) {
      // Silently ignore - these are normal during scanning
      return;
    }
    
    // Only log unexpected/critical errors
    console.warn('[RegisterDevice] Scanner error:', errorString);
  };

  const openCameraScanner = () => {
    console.log('[RegisterDevice] Opening camera scanner');
    setShowCameraScanner(true);
  };

  const closeCameraScanner = () => {
    console.log('[RegisterDevice] Closing camera scanner');
    try {
      if (html5QrCodeRef.current) {
        html5QrCodeRef.current.clear().catch(err => {
          console.error('[RegisterDevice] Failed to clear scanner:', err);
        });
        html5QrCodeRef.current = null;
      }
      setShowCameraScanner(false);
    } catch (error) {
      console.error('[RegisterDevice] Error closing scanner:', error);
      setShowCameraScanner(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    console.log('[RegisterDevice] Form field changed:', name, '=', value);
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const requiresNuid = isSbType(formData.deviceType);
    const requiresMacSerial = !requiresNuid;

    if (!formData.model.trim() || !formData.manufacturer.trim()) {
      showToast('Model and Vendor are required.', 'error');
      return;
    }
    if (requiresMacSerial && (!formData.macAddress.trim() || !formData.serialNumber.trim())) {
      showToast('MAC Address and Serial Number are required for non-SB devices.', 'error');
      return;
    }
    if (requiresNuid && !formData.nuid.trim()) {
      showToast('NUID is required for SB devices.', 'error');
      return;
    }
    if (requiresNuid && !['HD', 'OTT'].includes(String(formData.boxType || '').toUpperCase())) {
      showToast('Box Type must be HD or OTT for SB devices.', 'error');
      return;
    }

    setLoading(true);
    
    console.log('[RegisterDevice] Submitting device registration');
    console.log('[RegisterDevice] Form data:', formData);
    
    try {
      const deviceData = {
        device_type: formData.deviceType,
        model: formData.model.trim(),
        serial_number: requiresMacSerial ? formData.serialNumber.trim() : null,
        mac_address: requiresMacSerial ? formData.macAddress.trim() : null,
        manufacturer: formData.manufacturer.trim(),
        band_type: requiresMacSerial ? formData.bandType : null,
        box_type: requiresNuid ? String(formData.boxType || '').toUpperCase() : null,
        nuid: formData.nuid.trim() || null,
        metadata: {
          ...(requiresNuid ? { box_type: String(formData.boxType || '').toUpperCase() } : {}),
          hardware_version: formData.hardwareVersion.trim(),
          firmware_version: formData.firmwareVersion.trim(),
          condition: formData.condition,
          notes: formData.notes.trim()
        }
      };

      console.log('[RegisterDevice] Sending device data to API:', deviceData);
      const response = await devicesAPI.createDevice(deviceData);
      console.log('[RegisterDevice] Device registered successfully:', response);
      
      showToast('Device registered successfully!', 'success');
      navigate('/devices');
    } catch (error) {
      console.error('[RegisterDevice] Failed to register device:', error);
      console.error('[RegisterDevice] Error details:', {
        message: error.message,
        stack: error.stack
      });
      showToast(error.message || 'Failed to register device', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Register New Device</h1>
        <p className="text-gray-500 mt-1">Add a new device to the inventory from NOC</p>
      </div>

      {/* Camera Scanner Modal */}
      {showCameraScanner && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-auto">
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Camera className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">Camera Scanner</h3>
                    <p className="text-sm text-gray-500">Position the barcode/QR code in the frame</p>
                  </div>
                </div>
                <button
                  onClick={closeCameraScanner}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <XCircle className="w-6 h-6 text-gray-500" />
                </button>
              </div>

              <div id="qr-reader" className="rounded-lg overflow-hidden"></div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <p className="font-medium mb-1">Tips for best results:</p>
                    <ul className="space-y-1 ml-4 list-disc">
                      <li>Hold device steady and ensure good lighting</li>
                      <li>Position barcode clearly in the scanning area</li>
                      <li>Works with QR codes, barcodes, and text labels</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Scan Button */}
          <div className="flex justify-center">
            <button
              type="button"
              onClick={openCameraScanner}
              className="flex flex-col items-center gap-2 p-6 border-2 border-dashed border-gray-300 rounded-xl hover:border-blue-500 hover:bg-blue-50 transition-colors"
            >
              <Camera className="w-12 h-12 text-gray-400" />
              <span className="text-sm text-gray-600">Click to scan device barcode/QR code</span>
            </button>
          </div>

          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-4">Or enter details manually</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Device Type <span className="text-red-500">*</span>
                </label>
                <select
                  name="deviceType"
                  value={formData.deviceType}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  <option value="ONT">ONT</option>
                  <option value="ONU">ONU</option>
                  <option value="Router">Router</option>
                  <option value="Switch">Switch</option>
                  <option value="Modem">Modem</option>
                  <option value="Access Point">Access Point</option>
                  <option value="SB">SB</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {isSbType(formData.deviceType) ? 'Box Type' : 'Band Type'} {isSbType(formData.deviceType) ? <span className="text-red-500">*</span> : <span className="text-gray-400">(Optional)</span>}
                </label>
                <select
                  name={isSbType(formData.deviceType) ? 'boxType' : 'bandType'}
                  value={isSbType(formData.deviceType) ? formData.boxType : formData.bandType}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required={isSbType(formData.deviceType)}
                >
                  {isSbType(formData.deviceType) ? (
                    <>
                      <option value="HD">HD</option>
                      <option value="OTT">OTT</option>
                    </>
                  ) : (
                    <>
                      <option value="single_band">Single Band</option>
                      <option value="dual_band">Dual Band</option>
                    </>
                  )}
                </select>
              </div>

              {!isSbType(formData.deviceType) && (
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
              )}

              {!isSbType(formData.deviceType) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Serial Number <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="serialNumber"
                  value={formData.serialNumber}
                  onChange={handleChange}
                  placeholder="SN-2026-001"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Device Model <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="model"
                  value={formData.model}
                  onChange={handleChange}
                  placeholder="e.g., SI5520GWV"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Vendor <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="manufacturer"
                  value={formData.manufacturer}
                  onChange={handleChange}
                  placeholder="e.g., Syrotech"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>

              {isSbType(formData.deviceType) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    NUID <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="nuid"
                    value={formData.nuid}
                    onChange={handleChange}
                    placeholder="Enter SB NUID"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
              )}

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

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate('/devices')}
              icon={X}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={loading}
              icon={Save}
            >
              Register Device
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default RegisterDevice;
