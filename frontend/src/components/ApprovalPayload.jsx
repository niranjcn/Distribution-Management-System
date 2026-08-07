const FIELD_LABELS = {
  to_user_id: 'Recipient',
  device_ids: 'Device IDs',
  notes: 'Notes',
  date_of_distribution: 'Distribution Date',
};

const getAllowed = (payload) => {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return [];
  return Object.keys(payload).filter((k) => !['devices'].includes(k));
};

const ApprovalPayload = ({ type, payload }) => {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return (
      <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-x-auto text-xs whitespace-pre-wrap">
        {JSON.stringify(payload ?? null, null, 2)}
      </pre>
    );
  }

  const devices = Array.isArray(payload.devices) ? payload.devices : [];
  const fields = getAllowed(payload);

  return (
    <div className="space-y-3">
      {fields.length > 0 && (
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {fields.map((k) => {
            const v = payload[k];
            if (k === 'date_of_distribution' && v) {
              return (
                <div key={k} className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                  <dt className="text-xs text-gray-500">{FIELD_LABELS[k] || k}</dt>
                  <dd className="text-sm font-medium text-gray-800">{new Date(v).toLocaleString()}</dd>
                </div>
              );
            }
            return (
              <div key={k} className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <dt className="text-xs text-gray-500">{FIELD_LABELS[k] || k}</dt>
                <dd className="text-sm font-medium text-gray-800 break-words">{Array.isArray(v) ? v.join(', ') : String(v ?? '-')}</dd>
              </div>
            );
          })}
        </dl>
      )}
      {devices.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-1">Devices ({devices.length})</p>
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left px-3 py-1.5 font-medium">NUID</th>
                  <th className="text-left px-3 py-1.5 font-medium">Serial</th>
                  <th className="text-left px-3 py-1.5 font-medium">MAC</th>
                  <th className="text-left px-3 py-1.5 font-medium">Device ID</th>
                  <th className="text-left px-3 py-1.5 font-medium">Type</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d, i) => (
                  <tr key={i} className="border-t border-gray-100">
                    <td className="px-3 py-1.5 font-mono text-gray-800">{d.nuid || d.device_id || '-'}</td>
                    <td className="px-3 py-1.5 font-mono text-gray-800">{d.serial_number || '-'}</td>
                    <td className="px-3 py-1.5 font-mono text-gray-800">{d.mac_address || '-'}</td>
                    <td className="px-3 py-1.5 text-gray-800">{d.device_id || d.id || '-'}</td>
                    <td className="px-3 py-1.5 text-gray-800">{d.device_type || d.model || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApprovalPayload;