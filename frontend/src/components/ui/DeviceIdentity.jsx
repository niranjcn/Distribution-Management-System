import { getDeviceMac, getDeviceModel, getDeviceNuid, getDeviceSerial, getDeviceType, isSbDevice } from '../../utils/deviceDisplay';

const DeviceIdentity = ({ device, className = '' }) => {
  const model = getDeviceModel(device);
  const serial = getDeviceSerial(device);
  const mac = getDeviceMac(device);
  const nuid = getDeviceNuid(device);
  const isSb = isSbDevice(device);
  const type = getDeviceType(device);

  return (
    <div className={`flex items-start justify-between gap-3 ${className}`}>
      <div className="min-w-0">
        <p className="font-medium text-gray-800 break-words">{model}</p>
        {isSb ? (
          <p className="text-xs text-gray-500">NUID: {nuid}</p>
        ) : (
          <>
            <p className="text-xs text-gray-500">SN: {serial}</p>
            <p className="text-xs text-gray-500 break-all">MAC: {mac}</p>
          </>
        )}
      </div>
      <span className="px-2 py-1 text-[10px] uppercase tracking-wide rounded-full bg-gray-100 text-gray-600 border border-gray-200 whitespace-nowrap">
        {type}
      </span>
    </div>
  );
};

export default DeviceIdentity;
