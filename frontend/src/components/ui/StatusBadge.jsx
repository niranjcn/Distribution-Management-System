/**
 * StatusBadge — KannurVision PDIC
 * Colored dot + label. Every status from the API is covered.
 */
const StatusBadge = ({ status, size = 'md' }) => {
  const normalizeStatusLabel = (rawStatus) => {
    const normalized = String(rawStatus || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
    if (['sb', 'stb', 'settopbox', 'setupbox'].includes(normalized)) return 'SB';
    return String(rawStatus || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  const statusConfig = {
    // ── Device availability statuses (from API) ────────────────
    'available':      { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Available' },
    'distributed':    { dot: 'bg-blue-500',     bg: 'bg-blue-50',    text: 'text-blue-700',   label: 'Distributed' },
    'in_use':         { dot: 'bg-indigo-500',   bg: 'bg-indigo-50',  text: 'text-indigo-700', label: 'In Use' },
    'in-use':         { dot: 'bg-indigo-500',   bg: 'bg-indigo-50',  text: 'text-indigo-700', label: 'In Use' },
    'maintenance':    { dot: 'bg-amber-500',    bg: 'bg-amber-50',   text: 'text-amber-700',  label: 'Maintenance' },
    'defective':      { dot: 'bg-red-500',      bg: 'bg-red-50',     text: 'text-red-700',    label: 'Defective' },
    'replaced':       { dot: 'bg-gray-400',     bg: 'bg-gray-100',   text: 'text-gray-500',   label: 'Replaced' },
    'returned':       { dot: 'bg-orange-500',   bg: 'bg-orange-50',  text: 'text-orange-700', label: 'Returned' },
    'stored':         { dot: 'bg-purple-500',   bg: 'bg-purple-50',  text: 'text-purple-700', label: 'Stored' },

    // ── Device active/inactive ─────────────────────────────────
    'active':         { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Active' },
    'inactive':       { dot: 'bg-gray-400',    bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Inactive' },

    // ── Online / Offline (network status) ─────────────────────
    'online':         { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Online' },
    'offline':        { dot: 'bg-red-500',     bg: 'bg-red-50',     text: 'text-red-700',    label: 'Offline' },

    // ── Distribution statuses ──────────────────────────────────
    'pending':                          { dot: 'bg-amber-500',   bg: 'bg-amber-50',   text: 'text-amber-700',  label: 'Pending' },
    'pending_receipt':                  { dot: 'bg-orange-500',  bg: 'bg-orange-50',  text: 'text-orange-700', label: 'Awaiting Receipt' },
    'in-transit':                       { dot: 'bg-blue-500',    bg: 'bg-blue-50',    text: 'text-blue-700',   label: 'In Transit' },
    'in_transit':                       { dot: 'bg-blue-500',    bg: 'bg-blue-50',    text: 'text-blue-700',   label: 'In Transit' },
    'delivered':                        { dot: 'bg-indigo-500',  bg: 'bg-indigo-50',  text: 'text-indigo-700', label: 'Delivered' },
    'approved':                         { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Confirmed' },
    'rejected':                         { dot: 'bg-red-500',     bg: 'bg-red-50',     text: 'text-red-700',    label: 'Rejected' },
    'disputed':                         { dot: 'bg-red-400',     bg: 'bg-red-50',     text: 'text-red-700',    label: 'Disputed' },
    'completed':                        { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Completed' },
    'cancelled':                        { dot: 'bg-gray-400',    bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Cancelled' },
    'replacement_pending_confirmation': { dot: 'bg-amber-500',   bg: 'bg-amber-50',   text: 'text-amber-700',  label: 'Pending Confirmation' },
    'replacement_waiting_for_device':   { dot: 'bg-orange-500',  bg: 'bg-orange-50',  text: 'text-orange-700', label: 'Waiting For Device' },

    // ── Defect / Return statuses ───────────────────────────────
    'open':           { dot: 'bg-amber-500',   bg: 'bg-amber-50',   text: 'text-amber-700',  label: 'Open' },
    'under_review':   { dot: 'bg-blue-500',    bg: 'bg-blue-50',    text: 'text-blue-700',   label: 'Under Review' },
    'under-review':   { dot: 'bg-blue-500',    bg: 'bg-blue-50',    text: 'text-blue-700',   label: 'Under Review' },
    'resolved':       { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Resolved' },
    'closed':         { dot: 'bg-gray-400',    bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Closed' },
    'received':       { dot: 'bg-teal-500',    bg: 'bg-teal-50',    text: 'text-teal-700',   label: 'Received' },

    // ── Journey / Timeline statuses ────────────────────────────
    'current':        { dot: 'bg-green-500',   bg: 'bg-green-50',   text: 'text-green-700',  label: 'Current' },

    // ── Severity ───────────────────────────────────────────────
    'critical': { dot: 'bg-red-600',    bg: 'bg-red-50',     text: 'text-red-700',    label: 'Critical' },
    'high':     { dot: 'bg-orange-500', bg: 'bg-orange-50',  text: 'text-orange-700', label: 'High' },
    'medium':   { dot: 'bg-amber-500',  bg: 'bg-amber-50',   text: 'text-amber-700',  label: 'Medium' },
    'low':      { dot: 'bg-green-400',  bg: 'bg-green-50',   text: 'text-green-700',  label: 'Low' },

    // ── Condition ──────────────────────────────────────────────
    'new':          { dot: 'bg-green-500',  bg: 'bg-green-50',  text: 'text-green-700',  label: 'New' },
    'refurbished':  { dot: 'bg-blue-500',   bg: 'bg-blue-50',   text: 'text-blue-700',   label: 'Refurbished' },

    // ── Replacement markers ────────────────────────────────────
    'replacement':       { dot: 'bg-green-500', bg: 'bg-green-50',  text: 'text-green-700',  label: 'Replacement Device' },
    'defective_device':  { dot: 'bg-red-500',   bg: 'bg-red-50',    text: 'text-red-700',    label: 'Defective Device' },
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3 py-1.5 text-sm gap-1.5',
  };

  const dotSizes = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-2 h-2',
  };

  const normalizedStatus = String(status || '').toLowerCase().trim();
  const cfg = statusConfig[normalizedStatus] || {
    dot: 'bg-gray-400',
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    label: normalizeStatusLabel(status),
  };

  return (
    <span className={`inline-flex items-center font-medium rounded-full ${cfg.bg} ${cfg.text} ${sizeClasses[size]}`}>
      <span className={`rounded-full flex-shrink-0 ${dotSizes[size]} ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
};

export default StatusBadge;
