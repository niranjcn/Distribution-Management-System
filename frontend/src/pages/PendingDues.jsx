import { useEffect, useMemo, useState } from 'react';
import Card from '../components/ui/Card';
import DataTable from '../components/ui/DataTable';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import { Loader2, Receipt, DollarSign } from 'lucide-react';

const PendingDues = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const role = String(user?.role || '').toLowerCase();
  const isOperatorView = role === 'operator';
  const isHierarchyView = !isOperatorView;
  const canConfirmPayment = ['super_admin', 'manager', 'pdic_staff'].includes(role);

  const fetchUsers = async () => {
    try {
      setLoadingUsers(true);
      if (isHierarchyView) {
        const response = await defectsAPI.getPendingDueUsers();
        const rows = response.data || [];
        setUsers(rows);
        if (rows.length > 0) {
          await loadUserDetails(rows[0].user_id, rows[0]);
        } else {
          setSelectedUser(null);
          setDetails(null);
        }
      } else {
        setUsers([]);
        setSelectedUser(null);
        setLoadingDetails(true);
        const response = await defectsAPI.getMyPendingDues();
        setDetails(response.data || null);
      }
    } catch (error) {
      showToast(error.message || 'Failed to load pending dues', 'error');
    } finally {
      setLoadingUsers(false);
      setLoadingDetails(false);
    }
  };

  const loadUserDetails = async (userId, userRow = null) => {
    try {
      setLoadingDetails(true);
      const response = await defectsAPI.getPendingDuesForUser(userId);
      setDetails(response.data || null);
      setSelectedUser(userRow || users.find((u) => String(u.user_id) === String(userId)) || null);
    } catch (error) {
      showToast(error.message || 'Failed to load due details', 'error');
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [isHierarchyView]);

  const totalOutstanding = useMemo(
    () => users.reduce((acc, row) => acc + Number(row.total_due || 0), 0),
    [users]
  );

  const userColumns = [
    { key: 'user_name', label: 'User' },
    {
      key: 'user_role',
      label: 'Role',
      render: (value) => String(value || '-').replace(/_/g, ' '),
    },
    {
      key: 'parent_name',
      label: 'Parent',
      render: (value) => value || '-',
    },
    { key: 'due_count', label: 'Pending Defects' },
    {
      key: 'total_due',
      label: 'Total Due',
      render: (value) => <span className="font-semibold text-amber-700">{Number(value || 0).toFixed(2)}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">{isHierarchyView ? 'Pending Dues' : 'Pending Payments'}</h1>
        <p className="text-gray-500 mt-1">
          {isHierarchyView
            ? 'Track unpaid dues in your hierarchy branch by role.'
            : 'View all pending payments awaiting confirmation for your defective device returns.'}
        </p>
      </div>

      <div className={`grid grid-cols-1 ${isHierarchyView ? 'md:grid-cols-3' : 'md:grid-cols-2'} gap-4`}>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">{isHierarchyView ? 'Users with Dues' : 'Pending Items'}</p>
          <p className="text-2xl font-bold text-gray-800">{isHierarchyView ? users.length : Number(details?.count || 0)}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Outstanding Amount</p>
          <p className="text-2xl font-bold text-amber-700">{(isHierarchyView ? totalOutstanding : Number(details?.total_due || 0)).toFixed(2)}</p>
        </Card>
        {isHierarchyView && (
          <Card className="!p-4">
            <p className="text-sm text-gray-500">Pending Items</p>
            <p className="text-2xl font-bold text-blue-700">{users.reduce((acc, row) => acc + Number(row.due_count || 0), 0)}</p>
          </Card>
        )}
      </div>

      <div className={`grid grid-cols-1 ${isHierarchyView ? 'lg:grid-cols-5' : ''} gap-6`}>
        {isHierarchyView && (
          <div className="lg:col-span-2">
            <Card title="Users" icon={DollarSign}>
              {loadingUsers ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading users...
                </div>
              ) : (
                <DataTable
                  columns={userColumns}
                  data={users}
                  onRowClick={(row) => loadUserDetails(row.user_id, row)}
                />
              )}
            </Card>
          </div>
        )}

        <div className={isHierarchyView ? 'lg:col-span-3' : ''}>
          <Card title={selectedUser ? `Due Details - ${selectedUser.user_name}` : 'Due Details'} icon={Receipt}>
            {loadingDetails ? (
              <div className="flex items-center justify-center py-10 text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading details...
              </div>
            ) : !details || !details.items || details.items.length === 0 ? (
              <p className="text-gray-500">{isHierarchyView ? 'No pending due items for the selected user.' : 'No pending payments right now.'}</p>
            ) : (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900">
                  {isHierarchyView ? 'Outstanding for this user:' : 'Your total pending amount:'}{' '}
                  <span className="font-semibold">{Number(details.total_due || 0).toFixed(2)}</span>
                </div>

                {details.items.map((item) => (
                  <div key={item.id} className="p-4 rounded-lg border border-gray-200 bg-white space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-gray-800">{item.report_id} • {item.device_model || item.device_type || 'Device'}</p>
                        <p className="text-sm text-gray-500">Serial: {item.device_serial || 'N/A'} • Return: {item.return_id || item.auto_return_id || 'N/A'}</p>
                      </div>
                      <StatusBadge status={item.return_status || item.status || 'pending'} size="sm" />
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <p><span className="text-gray-500">Received At PDIC:</span> {item.received_date ? new Date(item.received_date).toLocaleDateString() : 'N/A'}</p>
                      <p><span className="text-gray-500">Due Amount:</span> <span className="font-semibold text-amber-700">{Number(item.return_amount || 0).toFixed(2)}</span></p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {item.payment_bill_url && (
                        <Button
                          variant="secondary"
                          onClick={async () => {
                            try {
                              const { blob } = await defectsAPI.fetchPaymentBillBlob(item.payment_bill_url);
                              const blobUrl = URL.createObjectURL(blob);
                              window.open(blobUrl, '_blank', 'noopener,noreferrer');
                              setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
                            } catch (error) {
                              showToast(error.message || 'Failed to open bill', 'error');
                            }
                          }}
                        >
                          View Bill
                        </Button>
                      )}
                      {canConfirmPayment && (
                        <Button
                          onClick={async () => {
                            try {
                              await defectsAPI.confirmPayment(item.id, 'Confirmed from Pending Dues page');
                              showToast('Payment confirmed', 'success');
                              await fetchUsers();
                            } catch (error) {
                              showToast(error.message || 'Failed to confirm payment', 'error');
                            }
                          }}
                        >
                          Confirm Payment
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PendingDues;
