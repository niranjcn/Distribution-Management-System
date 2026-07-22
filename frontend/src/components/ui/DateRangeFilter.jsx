import { useState, useRef, useEffect } from 'react';
import { Calendar, ChevronDown } from 'lucide-react';

const PRESETS = [
  { label: 'Today', value: 'today' },
  { label: 'Last 7 Days', value: 'last7' },
  { label: 'Last 30 Days', value: 'last30' },
  { label: 'Last 60 Days', value: 'last60' },
  { label: 'Last 90 Days', value: 'last90' },
  { label: 'This Year', value: 'thisYear' },
  { label: 'All Time', value: 'all' },
  { label: 'Custom Range', value: 'custom' },
];

export const formatDateParam = (date) => {
  if (!date) return null;
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

export const buildDateParams = (range) => {
  const params = {};
  if (range.startDate) params.start_date = formatDateParam(range.startDate);
  if (range.endDate) params.end_date = formatDateParam(range.endDate);
  return params;
};

const buildPresetRange = (preset) => {
  const now = new Date();
  const end = new Date(now);
  end.setHours(23, 59, 59, 999);

  if (preset === 'today') {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  if (preset === 'last7') {
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  if (preset === 'last30') {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  if (preset === 'last60') {
    const start = new Date(now);
    start.setDate(start.getDate() - 59);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  if (preset === 'last90') {
    const start = new Date(now);
    start.setDate(start.getDate() - 89);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  if (preset === 'thisYear') {
    const start = new Date(now.getFullYear(), 0, 1);
    start.setHours(0, 0, 0, 0);
    return { startDate: start, endDate: end };
  }
  return { startDate: null, endDate: null };
};

const formatDate = (date) => {
  if (!date) return '';
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

const DateRangeFilter = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const currentPreset = value?.range || 'all';
  const presetLabel = PRESETS.find((p) => p.value === currentPreset)?.label || 'All Time';

  const handlePreset = (preset) => {
    if (preset === 'custom') {
      onChange({ range: 'custom', startDate: null, endDate: null });
      return;
    }
    const range = buildPresetRange(preset);
    onChange({ range: preset, startDate: range.startDate, endDate: range.endDate });
    setOpen(false);
  };

  const handleCustomApply = () => {
    const start = customStart ? new Date(customStart + 'T00:00:00') : null;
    const end = customEnd ? new Date(customEnd + 'T23:59:59') : null;
    onChange({ range: 'custom', startDate: start, endDate: end });
    setOpen(false);
  };

  const displayLabel = currentPreset === 'custom' && value?.startDate
    ? `${formatDate(value.startDate)} - ${formatDate(value.endDate)}`
    : presetLabel;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 hover:border-gray-400 transition-colors"
      >
        <Calendar className="w-4 h-4 text-gray-500" />
        <span className="min-w-[100px] text-left">{displayLabel}</span>
        <ChevronDown className="w-4 h-4 text-gray-500" />
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="p-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.value}
                onClick={() => handlePreset(preset.value)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  currentPreset === preset.value
                    ? 'bg-green-50 text-green-700 font-medium'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {currentPreset === 'custom' && (
            <div className="border-t border-gray-200 p-3 space-y-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Start Date</label>
                <input
                  type="date"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">End Date</label>
                <input
                  type="date"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                />
              </div>
              <button
                onClick={handleCustomApply}
                disabled={!customStart || !customEnd}
                className="w-full px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Apply
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DateRangeFilter;
