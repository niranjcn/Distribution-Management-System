const normalizeType = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  if (normalized === 'settopbox' || normalized === 'setupbox' || normalized === 'sb' || normalized === 'stb') {
    return 'SB';
  }
  return value;
};

export const isSbDevice = (device) => {
  const type = normalizeType(
    device?.device_type ||
    device?.defective_device?.device_type ||
    device?.replacement_device?.device_type ||
    ''
  );
  return type === 'SB';
};

export const getDeviceNuid = (device) =>
  device?.nuid ||
  device?.device_nuid ||
  device?.defective_device_nuid ||
  device?.source_device_nuid ||
  device?.defective_device?.nuid ||
  device?.replacement_device?.nuid ||
  'N/A';

export const getDeviceModel = (device) => {
  const directModel = device?.model || device?.device_model || device?.defective_device?.model || device?.replacement_device?.model;
  if (directModel) return directModel;

  // Some APIs send a generic device_name that may duplicate device_type; avoid using type as model text.
  const deviceName = device?.device_name;
  if (deviceName && String(deviceName).toLowerCase() !== String(device?.device_type || '').toLowerCase()) {
    return deviceName;
  }

  return 'Unknown Model';
};

export const getDeviceSerial = (device) => {
  if (isSbDevice(device)) return 'N/A';
  return device?.serial_number || device?.device_serial || device?.defective_device?.serial_number || 'N/A';
};

export const getDeviceMac = (device) => {
  if (isSbDevice(device)) return 'N/A';
  return device?.mac_address || device?.defective_device?.mac_address || 'N/A';
};

export const getDeviceType = (device) =>
  normalizeType(
    device?.device_type ||
    device?.defective_device?.device_type ||
    device?.replacement_device?.device_type ||
    'Unknown Type'
  );

export const getDeviceSelectLabel = (device) => {
  const model = getDeviceModel(device);
  const type = getDeviceType(device);
  if (isSbDevice(device)) {
    return `${model} | NUID: ${getDeviceNuid(device)} | Type: ${type}`;
  }
  const serial = getDeviceSerial(device);
  const mac = getDeviceMac(device);
  return `${model} | SN: ${serial} | MAC: ${mac} | Type: ${type}`;
};
