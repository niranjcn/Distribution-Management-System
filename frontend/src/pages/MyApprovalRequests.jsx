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
import { ShieldAlert, Eye, XCircle, ClipboardList } from 'lucide-react';

const TYPE_LABELS = {
  distribution: 'Distribution',
  defect: 'Defect Report',
  cluster: 'Create Cluster',
  operator: 'Create Operator',
};

const MyApprovalRequests = () => {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [detail, setDetail] = useState(null);
  const [showDetail, setShowDetail] = useState(false);

  if (!hasRole(['sub_distribution_employee'])) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <ShieldAlert className="w-16 h-16 text-red-500 mb-4" />
        <h1 className="text-xl font-bold text-gray-800 text-center">Access Denied</h1>
        <p className="text-gray-500 mt-2 text-center">Only sub distribution employees can view their requests here.</p>
        <Button className="mt-4" onClick={() => navigate('/')}>Back to Dashboard</Button>
      </div>
    );
  }

  const load = useCallback(async (targetPage, targetStatus) => {
    setLoading(true);
    try {
      const params = { page: targetPage, page_size: 100 };
      if (targetStatus) params.status = targetStatus;
      const res = await approvalRequestsAPI.getMy(params);
      const data = Array.isArray(res?.data) ? res.data : [];
      setRows(data);
      setTotal(data.length);
      setPage(targetPage);
    } catch (error) {
      showToast(error.message || 'Failed to load your requests', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load(1, statusFilter);
  }, [statusFilter, load]);

  const openDetail = async (row) => {
    try {
      const res = await approvalRequestsAPI.getDetail(row.request_id);
      setDetail(res?.data || row);
      setShowDetail(true);
    } catch (error) {
      showToast(error.message || 'Failed to load request details', 'error');
    }
  };

  const handleCancel = async (row) => {
    if (!window.confirm(`Cancel request ${row.request_id}?`)) return;
    try {
      await approvalRequestsAPI.cancel(row.request_id);
      showToast('Request cancelled', 'success');
      load(1, statusFilter);
    } catch (error) {
      showToast(error.message || 'Failed to cancel request', 'error');
    }
  };

  const columns = [
    { key: 'request_id', label: 'Request ID' },
    {
      key: 'request_type', label: 'Type',
      render: (value) => <span className="text-gray-700">{TYPE_LABELS[value] || value}</span>,
    },
    { key: 'summary', label: 'Summary', render: (v) => <span className="text-gray-600 truncate block max-w-[300px]">{v || '-'}</span> },
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
        <div className="flex gap-2">
          <Button size="sm" variant="outline" icon={Eye} onClick={() => openDetail(row)}>View</Button>
          {row.status === 'pending' && (
            <Button size="sm" variant="danger" icon={XCircle} onClick={() => handleCancel(row)}>Cancel</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">My Approval Requests</h1>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">
            Proposals you submitted for approval under your sub distribution.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/distributions/create')}>Create Distribution</Button>
          <Button variant="outline" onClick={() => navigate('/defects/create')}>Report Defect</Button>
        </div>
      </div>

      <Card icon={ClipboardList}>
        <div className="mb-4 flex flex-wrap gap-2">
          {['', 'pending', 'approved', 'rejected', 'cancelled'].map((s) => (
            <button
              key={s || 'all'}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border transition-colors ${
                statusFilter === s
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              {s ? s[0].toUpperCase() + s.slice(1) : 'All'}
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

      <Modal
        isOpen={showDetail}
        onClose={() => setShowDetail(false)}
        title="Request Details"
        size="lg"
      >
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="flex items-center gap-3">
              <span className="font-mono font-semibold text-gray-800">{detail.request_id}</span>
              <StatusBadge status={detail.status} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <p><span className="text-gray-500">Type:</span> <span className="font-medium">{TYPE_LABELS[detail.request_type] || detail.request_type}</span></p>
              <p><span className="text-gray-500">Submitted:</span> <span className="font-medium">{detail.created_at ? new Date(detail.created_at).toLocaleString() : '-'}</span></p>
              <p><span className="text-gray-500">Summary:</span> <span className="font-medium">{detail.summary || '-'}</span></p>
              <p><span className="text-gray-500">Forum roles:</span> <span className="font-medium">{(detail.required_roles || []).join(', ') || '-'}</span></p>
            </div>
            <div>
              <p className="text-gray-500 mb-1">Payload</p>
              <ApprovalPayload type={detail.request_type} payload={detail.payload} />
            </div>
            {detail.status === 'rejected' && detail.rejection_reason && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="font-medium text-red-700">Reason</p>
                <p className="text-red-600">{detail.rejection_reason}</p>
              </div>
            )}
            {(detail.approvals || []).length > 0 && (
              <div>
                <p className="text-gray-500 mb-1">Approval trail</p>
                <div className="space-y-1">
                  {(detail.approvals || []).map((a, i) => (
                    <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-2">
                      <p className="text-gray-700">
                        {a.user_name} ({a.role}) — <span className="capitalize">{a.decision}</span>
                        {a.note ? ` — ${a.note}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default MyApprovalRequests;