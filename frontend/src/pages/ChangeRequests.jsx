import { useState, useEffect, useCallback } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { changeRequestsAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react';

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
};

const TYPE_LABELS = {
  email_change: 'Email Change',
  password_reset: 'Password Reset',
  both: 'Email & Password',
  device_status_change: 'Device Status Change',
  device_edit_change: 'Device Edit Change',
  replacement_transfer_fix: 'Replacement Transfer Fix',
};

const parseDeviceEditChanges = (reason) => {
  if (!reason) return null;
  try {
    const parsed = JSON.parse(reason);
    if (parsed && typeof parsed === 'object' && parsed.changes && typeof parsed.changes === 'object') {
      return parsed.changes;
    }
    if (parsed && typeof parsed === 'object') {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
};

const ChangeRequests = ({ mode = 'password' }) => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [reviewing, setReviewing] = useState(null); // { req, action }
  const [reviewForm, setReviewForm] = useState({ review_note: '', new_email: '', new_password: '' });
  const [submitting, setSubmitting] = useState(false);
  const isEditMode = mode === 'edit';

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const res = await changeRequestsAPI.getRequests(params);
      const data = res.data || [];
      const filtered = data.filter((req) => {
        if (isEditMode) return req.request_type === 'device_edit_change';
        return req.request_type !== 'device_edit_change';
      });
      setRequests(filtered);
    } catch (err) {
      showToast('Failed to load requests', 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchRequests(); }, [fetchRequests]);

  const openReview = (req, action) => {
    setReviewing({ req, action });
    setReviewForm({ review_note: '', new_email: req.new_email || '', new_password: '' });
  };

  const submitReview = async () => {
    if (!reviewing) return;
    setSubmitting(true);
    try {
      const payload = {
        action: reviewing.action,
        review_note: reviewForm.review_note || undefined,
      };
      if (reviewing.action === 'approve') {
        if (reviewForm.new_email) payload.new_email = reviewForm.new_email;
        if (reviewForm.new_password) payload.new_password = reviewForm.new_password;
      }
      await changeRequestsAPI.review(reviewing.req.request_id, payload);
      showToast(`Request ${reviewing.action}d successfully`, 'success');
      setReviewing(null);
      fetchRequests();
    } catch (err) {
      showToast(err.message || 'Action failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">{isEditMode ? 'Edit Requests' : 'Password Change Requests'}</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {isEditMode
              ? 'Review and approve device update requests'
              : 'Review and approve account/password change requests'}
          </p>
        </div>
        <Button variant="outline" icon={RefreshCw} onClick={fetchRequests}>Refresh</Button>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2">
        {['pending', 'approved', 'rejected', 'all'].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              statusFilter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <Card>
        {loading ? (
          <div className="text-center py-12 text-gray-400">Loading...</div>
        ) : requests.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Clock className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p>No change requests found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Requester</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Type</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Requested Values</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Reason</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Date</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {requests.map(req => (
                  <tr key={req.id} className="hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="font-medium text-gray-800">{req.requested_by_name}</div>
                      <div className="text-xs text-gray-400 capitalize">{req.requested_by_role}</div>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-700">{TYPE_LABELS[req.request_type] || req.request_type}</td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {req.request_type === 'device_status_change' ? (
                        <div>
                          <div>Device ID: {req.device_id || '—'}</div>
                          <div>New Status: <span className="font-medium capitalize">{req.requested_status || '—'}</span></div>
                        </div>
                      ) : req.request_type === 'device_edit_change' ? (
                        <div>
                          <div>Device ID: {req.device_id || '—'}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            Proposed fields: {Object.keys(parseDeviceEditChanges(req.reason) || {}).length}
                          </div>
                        </div>
                      ) : req.request_type === 'replacement_transfer_fix' ? (
                        <div>
                          <div>Defect ID: {req.device_id || '—'}</div>
                          <div>Action: <span className="font-medium">Transfer fix request</span></div>
                        </div>
                      ) : (
                        <>
                          {req.new_email && <div>Email: {req.new_email}</div>}
                          {req.new_password && <div>Password: <span className="text-gray-400">••••••••</span></div>}
                        </>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-500 max-w-xs truncate">{req.reason || '—'}</td>
                    <td className="py-3 px-4 text-sm text-gray-500">
                      {new Date(req.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${STATUS_COLORS[req.status] || 'bg-gray-100 text-gray-600'}`}>
                        {req.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {req.status === 'pending' && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => openReview(req, 'approve')}
                            className="p-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
                            title="Approve"
                          >
                            <CheckCircle className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => openReview(req, 'reject')}
                            className="p-1.5 rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                            title="Reject"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                      {req.status !== 'pending' && (
                        <span className="text-xs text-gray-400">by {req.reviewed_by_name || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Review Modal */}
      {reviewing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="p-6 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-800 capitalize">
                {reviewing.action} Request
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                From: {reviewing.req.requested_by_name} ({reviewing.req.requested_by_role})
              </p>
            </div>
            <div className="p-6 space-y-4">
              {reviewing.action === 'approve' && reviewing.req.request_type === 'device_status_change' && (
                <div className="p-3 bg-blue-50 rounded-lg text-sm">
                  <p className="font-medium text-blue-800 mb-1">Device Status Change Request</p>
                  <p className="text-blue-700">Device ID: {reviewing.req.device_id}</p>
                  <p className="text-blue-700">Requested Status: <span className="font-medium capitalize">{reviewing.req.requested_status}</span></p>
                  <p className="text-blue-600 mt-1">Approving will update the device status immediately.</p>
                </div>
              )}
              {reviewing.action === 'approve' && reviewing.req.request_type === 'device_edit_change' && (
                <div className="p-3 bg-blue-50 rounded-lg text-sm">
                  <p className="font-medium text-blue-800 mb-1">Device Edit Change Request</p>
                  <p className="text-blue-700">Device ID: {reviewing.req.device_id}</p>
                  <p className="text-blue-600 mt-1">Approving will apply the requested device field updates.</p>
                </div>
              )}
              {reviewing.action === 'approve' && reviewing.req.request_type !== 'device_status_change' && reviewing.req.request_type !== 'device_edit_change' && reviewing.req.request_type !== 'replacement_transfer_fix' && (
                <>
                  <p className="text-sm text-gray-600">You can override the requested values before approving:</p>
                  {reviewing.req.request_type !== 'password_reset' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Email (leave blank to use requested value)</label>
                      <input
                        type="email"
                        value={reviewForm.new_email}
                        onChange={e => setReviewForm(p => ({ ...p, new_email: e.target.value }))}
                        placeholder={reviewing.req.new_email || 'No email change requested'}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  )}
                  {reviewing.req.request_type !== 'email_change' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Password (leave blank to use requested value)</label>
                      <input
                        type="password"
                        value={reviewForm.new_password}
                        onChange={e => setReviewForm(p => ({ ...p, new_password: e.target.value }))}
                        placeholder="Override password or leave blank"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  )}
                </>
              )}
              {reviewing.action === 'approve' && reviewing.req.request_type === 'replacement_transfer_fix' && (
                <div className="p-3 bg-amber-50 rounded-lg text-sm">
                  <p className="font-medium text-amber-800 mb-1">Replacement Transfer Fix Request</p>
                  <p className="text-amber-700">Defect ID: {reviewing.req.device_id || '—'}</p>
                  <p className="text-amber-600 mt-1">Approving will notify the operator and mark this request as approved for management processing.</p>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Note (optional)</label>
                <textarea
                  value={reviewForm.review_note}
                  onChange={e => setReviewForm(p => ({ ...p, review_note: e.target.value }))}
                  placeholder="Add a note..."
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-100 flex justify-end gap-3">
              <Button variant="outline" onClick={() => setReviewing(null)}>Cancel</Button>
              <Button
                onClick={submitReview}
                disabled={submitting}
                className={reviewing.action === 'reject' ? 'bg-red-600 hover:bg-red-700' : ''}
              >
                {submitting ? 'Processing...' : reviewing.action === 'approve' ? 'Approve' : 'Reject'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChangeRequests;
