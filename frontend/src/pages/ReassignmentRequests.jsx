import { useState, useEffect } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { reassignmentRequestsAPI, usersAPI } from '../services/api';
import {
  Loader2, RefreshCw, Check, X, Users, Network,
  ChevronDown, ChevronRight, ArrowRight, AlertTriangle
} from 'lucide-react';

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  sub_distributor: 'Sub Distributor',
  cluster: 'Cluster',
  operator: 'Operator',
  sub_distribution_manager: 'Sub Distribution Manager',
};

const ReassignmentRequests = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(null);
  const [expandedRequest, setExpandedRequest] = useState(null);
  const [reassignTargets, setReassignTargets] = useState({});
  const [targetOptions, setTargetOptions] = useState({});

  const fetchRequests = async () => {
    setLoading(true);
    try {
      const res = await reassignmentRequestsAPI.getRequests({ page_size: 100 });
      setRequests(res.data || []);
    } catch (err) {
      showToast(err.message || 'Failed to load requests', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const loadTargetOptions = async (requestId, deletedUserRole, deletedUserId) => {
    try {
      let options = [];
      if (deletedUserRole === 'sub_distributor') {
        const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: 10000 });
        options = (res.data || [])
          .filter(u => String(u.id) !== String(deletedUserId))
          .map(u => ({ ...u, targetRole: 'sub_distributor' }));
      } else if (deletedUserRole === 'cluster') {
        const res = await usersAPI.getUsers({ role: 'cluster', page_size: 10000 });
        options = (res.data || [])
          .filter(u => String(u.id) !== String(deletedUserId))
          .map(u => ({ ...u, targetRole: 'cluster' }));
      }
      setTargetOptions(prev => ({ ...prev, [requestId]: options }));
    } catch (err) {
      showToast('Failed to load target options', 'error');
    }
  };

  const handleExpand = (req) => {
    if (expandedRequest === req.id) {
      setExpandedRequest(null);
      return;
    }
    setExpandedRequest(req.id);
    if (!targetOptions[req.id]) {
      loadTargetOptions(req.id, req.deleted_user_role, req.deleted_user_id);
    }
  };

  const handleReassign = async (requestId) => {
    const targetId = reassignTargets[requestId];
    if (!targetId) {
      showToast('Please select a target to reassign to', 'error');
      return;
    }
    setSubmitting(requestId);
    try {
      const target = targetOptions[requestId]?.find(o => String(o.id) === String(targetId));
      await reassignmentRequestsAPI.reassign(requestId, {
        reassign_to_id: targetId,
        reassign_to_name: target?.name || '',
        reassign_to_role: target?.targetRole || '',
      });
      showToast('Users reassigned successfully', 'success');
      setReassignTargets(prev => ({ ...prev, [requestId]: '' }));
      setExpandedRequest(null);
      fetchRequests();
    } catch (err) {
      showToast(err.message || 'Failed to reassign', 'error');
    } finally {
      setSubmitting(null);
    }
  };

  const handleReject = async (requestId) => {
    setSubmitting(requestId);
    try {
      await reassignmentRequestsAPI.reject(requestId);
      showToast('Request rejected', 'success');
      fetchRequests();
    } catch (err) {
      showToast(err.message || 'Failed to reject', 'error');
    } finally {
      setSubmitting(null);
    }
  };

  const pendingRequests = requests.filter(r => r.status === 'pending');

  const renderChildrenList = (children) => {
    if (children.length === 0) {
      return <p className="text-sm text-gray-400 italic">No users to reassign.</p>;
    }
    // Handle both new flat format and backward-compat with old nested format
    const displayItems = children.some(c => c.children !== undefined)
      ? children  // nested: only show top-level (clusters, SDMs, not operators)
      : children; // flat: show all (which are just direct children)
    return (
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {displayItems.map((child) => (
          <div key={child.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center">
                <span className="text-xs font-medium text-gray-600">
                  {(child.name || '?').charAt(0)}
                </span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-800">{child.name}</p>
                <p className="text-xs text-gray-500">{child.email}</p>
              </div>
            </div>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              child.role === 'sub_distributor' ? 'bg-indigo-100 text-indigo-700' :
              child.role === 'sub_distribution_manager' ? 'bg-cyan-100 text-cyan-700' :
              child.role === 'cluster' ? 'bg-teal-100 text-teal-700' :
              'bg-green-100 text-green-700'
            }`}>
              {ROLE_LABELS[child.role] || child.role}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Reassignment Requests</h1>
          <p className="text-gray-500 mt-1">
            Manage pending reassignments for deleted sub-distributors and clusters
          </p>
        </div>
        <Button icon={RefreshCw} onClick={fetchRequests} disabled={loading}>
          Refresh
        </Button>
      </div>

      {/* Pending count alert */}
      {pendingRequests.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0" />
          <p className="text-amber-800 text-sm">
            <strong>{pendingRequests.length}</strong> reassignment request{pendingRequests.length !== 1 ? 's' : ''} pending action.
            Please review and assign a new parent for the orphaned users.
          </p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading requests...</span>
        </div>
      ) : requests.length === 0 ? (
        <Card>
          <div className="text-center py-10">
            <Users className="w-14 h-14 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No reassignment requests found.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {requests.map((req) => {
            const statusColors = {
              pending: 'bg-amber-100 text-amber-800',
              completed: 'bg-green-100 text-green-800',
              rejected: 'bg-red-100 text-red-800',
            };
            const isExpanded = expandedRequest === req.id;
            const children = req.children || [];

            return (
              <Card key={req.id} className="overflow-hidden">
                {/* Header */}
                <div
                  className="flex items-center justify-between cursor-pointer select-none"
                  onClick={() => handleExpand(req)}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      req.deleted_user_role === 'sub_distributor' ? 'bg-indigo-100' : 'bg-teal-100'
                    }`}>
                      <Network className={`w-5 h-5 ${
                        req.deleted_user_role === 'sub_distributor' ? 'text-indigo-600' : 'text-teal-600'
                      }`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-gray-800">{req.deleted_user_name}</p>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          req.deleted_user_role === 'sub_distributor' ? 'bg-indigo-100 text-indigo-700' : 'bg-teal-100 text-teal-700'
                        }`}>
                          {ROLE_LABELS[req.deleted_user_role] || req.deleted_user_role}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">
                        {req.request_id} &middot; {children.length} user{children.length !== 1 ? 's' : ''} to reassign
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${statusColors[req.status] || 'bg-gray-100 text-gray-800'}`}>
                      {req.status.charAt(0).toUpperCase() + req.status.slice(1)}
                    </span>
                    {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-gray-100 space-y-4">
                    {/* Children list */}
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                        <Users className="w-4 h-4" /> Users to reassign ({children.length})
                      </p>
                      {renderChildrenList(children)}
                    </div>

                    {/* Reassign section (only for pending) */}
                    {req.status === 'pending' && (
                      <div className="bg-gray-50 rounded-xl p-4 space-y-3">
                        <p className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                          <ArrowRight className="w-4 h-4" />
                          Assign to new{' '}
                          {req.deleted_user_role === 'sub_distributor' ? 'Sub Distributor' : 'Cluster'}
                        </p>
                        <div className="flex items-center gap-3">
                          <select
                            value={reassignTargets[req.id] || ''}
                            onChange={e => setReassignTargets(prev => ({ ...prev, [req.id]: e.target.value }))}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="">
                              Select {req.deleted_user_role === 'sub_distributor' ? 'Sub Distributor' : 'Cluster'}...
                            </option>
                            {(targetOptions[req.id] || []).map(opt => (
                              <option key={opt.id} value={opt.id}>
                                {opt.name} ({opt.email})
                              </option>
                            ))}
                          </select>
                          <Button
                            onClick={() => handleReassign(req.id)}
                            disabled={submitting === req.id || !reassignTargets[req.id]}
                          >
                            {submitting === req.id ? 'Assigning...' : 'Assign'}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => handleReject(req.id)}
                            disabled={submitting === req.id}
                          >
                            Reject
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Completed info */}
                    {req.status === 'completed' && req.reassigned_to_name && (
                      <div className="bg-green-50 rounded-xl p-3 flex items-center gap-3">
                        <Check className="w-5 h-5 text-green-600" />
                        <p className="text-sm text-green-800">
                          Reassigned to <strong>{req.reassigned_to_name}</strong>
                          {req.reassigned_to_role ? ` (${ROLE_LABELS[req.reassigned_to_role] || req.reassigned_to_role})` : ''}
                        </p>
                      </div>
                    )}

                    {/* Created at */}
                    <p className="text-xs text-gray-400">
                      Created: {req.created_at ? new Date(req.created_at).toLocaleString() : 'Unknown'}
                    </p>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ReassignmentRequests;
