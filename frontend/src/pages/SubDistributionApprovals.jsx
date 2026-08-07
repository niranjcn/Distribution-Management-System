import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { approvalRequestsAPI } from '../services/api';
import ApprovalPayload from '../components/ApprovalPayload';
import { ShieldAlert, Eye, Check, X, ClipboardCheck } from 'lucide-react';

const TYPE_LABELS = {
  distribution: 'Distribution',
  defect: 'Defect Report',
  cluster: 'Create Cluster',
  operator: 'Create Operator',
};

const SubDistributionApprovals = () => {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [detail, setDetail] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [decision, setDecision] = useState('');
  const [note, setNote] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!hasRole(['sub_distribution_manager', 'sub_distributor'])) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <ShieldAlert className="w-16 h-16 text-red-500 mb-4" />
        <h1 className="text-xl font-bold text-gray-800 text-center">Access Denied</h1>
        <p className="text-gray-500 mt-2 text-center">Only sub distribution managers and sub distributors can approve requests.</p>
        <Button className="mt-4" onClick={() => navigate('/')}>Back to Dashboard</Button>
      </div>
    );
  }

  const load = useCallback(async (targetStatus) => {
    setLoading(true);
    try {
      const params = { page: 1, page_size: 100 };
      if (targetStatus) params.status = targetStatus;
      const res = await approvalRequestsAPI.getPending(params);
      setRows(Array.isArray(res?.data) ? res.data : []);
    } catch (error) {
      showToast(error.message || 'Failed to load requests', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load(statusFilter);
  }, [statusFilter, load]);

  const openDetail = async (row) => {
    try {
      const res = await approvalRequestsAPI.getDetail(row.request_id);
      setDetail(res?.data || row);
      setNote('');
      setDecision('');
      setShowDetail(true);
    } catch (error) {
      showToast(error.message || 'Failed to load request details', 'error');
    }
  };

  const openDecision = (action) => {
    if (action === 'reject' && !note.trim()) {
      showToast('Please enter a reason for rejection', 'error');
      return;
    }
    setDecision(action);
    setShowConfirm(true);
  };

  const submitDecision = async () => {
    setSubmitting(true);
    try {
      const res = await approvalRequestsAPI.decide(detail.request_id, { action: decision, review_note: note || undefined });
      showToast(res?.message || `Request ${decision}d`, decision === 'approve' ? 'success' : 'info');
      setShowConfirm(false);
      setShowDetail(false);
      load(statusFilter);
    } catch (error) {
      showToast(error.message || 'Failed to submit decision', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    { key: 'request_id', label: 'Request ID' },
    {
      key: 'request_type', label: 'Type',
      render: (value) => <span className="text-gray-700">{TYPE_LABELS[value] || value}</span>,
    },
    { key: 'summary', label: 'Summary', render: (v) => <span className="text-gray-600 truncate block max-w-[280px]">{v || '-'}</span> },
    { key: 'requested_by_name', label: 'Requested By', render: (v) => <span className="text-gray-700">{v || '-'}</span> },
    {
      key: 'status', label: 'Status',
      render: (value) => <StatusBadge status={value} />,
    },
    {
      key: 'created_at', label: 'Submitted',
      render: (value) => <span className="text-gray-500">{value ? new Date(value).toLocaleString() : '-'}</span>,
    },
    {
      key: 'actions', label: 'Actions',
      render: (_, row) => (
        <Button size="sm" variant="outline" icon={Eye} onClick={() => openDetail(row)}>View</Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Sub Distribution Approvals</h1>
        <p className="text-gray-500 mt-1 text-sm sm:text-base">
          Approve or reject employee proposals under your sub distribution.
        </p>
      </div>

      <Card icon={ClipboardCheck}>
        <div className="mb-4 flex flex-wrap gap-2">
          {['pending', 'approved', 'rejected'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border transition-colors ${
                statusFilter === s
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {s[0].toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <DataTable
          columns={columns}
          data={rows}
          pagination={false}
          exportable={false}
          searchable={false}
          loading={loading}
        />
      </Card>

      <Modal isOpen={showDetail} onClose={() => setShowDetail(false)} title="Request Details" size="lg">
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="flex items-center gap-3">
              <span className="font-mono font-semibold text-gray-800">{detail.request_id}</span>
              <StatusBadge status={detail.status} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <p><span className="text-gray-500">Type:</span> <span className="font-medium">{TYPE_LABELS[detail.request_type] || detail.request_type}</span></p>
              <p><span className="text-gray-500">Requested by:</span> <span className="font-medium">{detail.requested_by_name}</span></p>
              <p><span className="text-gray-500">Summary:</span> <span className="font-medium">{detail.summary || '-'}</span></p>
              <p><span className="text-gray-500">Forum roles:</span> <span className="font-medium">{(detail.required_roles || []).join(', ') || '-'}</span></p>
            </div>
            <div>
              <p className="text-gray-500 mb-1">Payload</p>
              <ApprovalPayload type={detail.request_type} payload={detail.payload} />
            </div>
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg p-2">
              Approved proposals are revalidated before being applied. If any detail is now invalid, the request will be returned for correction.
            </p>

            {detail.status === 'pending' ? (
              <div className="space-y-3 border-t border-gray-200 pt-4">
                <label className="block text-sm font-medium text-gray-700">Review note</label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Optional note / rejection reason..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" icon={X} onClick={() => openDecision('reject')}>Reject</Button>
                  <Button icon={Check} onClick={() => openDecision('approve')}>Approve</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 border-t border-gray-200 pt-4">
                {(detail.approvals || []).map((a, i) => (
                  <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-2">
                    <p className="text-gray-700">
                      {a.user_name} ({a.role}) — <span className="capitalize">{a.decision}</span>
                      {a.note ? ` — ${a.note}` : ''}
                    </p>
                  </div>
                ))}
                {detail.status === 'rejected' && detail.rejection_reason && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-2">
                    <p className="font-medium text-red-700">Reason</p>
                    <p className="text-red-600">{detail.rejection_reason}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        isOpen={showConfirm}
        onClose={() => setShowConfirm(false)}
        title={decision === 'approve' ? 'Confirm Approval' : 'Confirm Rejection'}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Cancel</Button>
            <Button
              variant={decision === 'approve' ? 'primary' : 'danger'}
              loading={submitting}
              onClick={submitDecision}
            >
              Confirm {decision}
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-700">
          {decision === 'approve'
            ? 'Submitting this will record your approval. The request is applied once all required approvers approve.'
            : 'Submitting this will reject the employee request.'}
        </p>
        {note && <p className="text-sm text-gray-500 mt-2">Note: {note}</p>}
      </Modal>
    </div>
  );
};

export default SubDistributionApprovals;