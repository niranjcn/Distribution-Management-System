import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { notificationsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import { Bell, Clock3, Loader2, CheckCheck, AlertTriangle, Info, CheckCircle2, ExternalLink } from 'lucide-react';

const PAGE_SIZE = 20;
const VALID_BASE_ROUTES = new Set([
  '/',
  '/devices',
  '/devices/register',
  '/devices/track',
  '/devices/bulk-import',
  '/devices/edit-requests',
  '/distributions',
  '/distributions/create',
  '/defects',
  '/defects/create',
  '/replacements',
  '/returns',
  '/pending-dues',
  '/users',
  '/users/hierarchy',
  '/approvals',
  '/delivery-confirmations',
  '/replacement-confirmation',
  '/reports',
  '/notifications',
  '/change-requests',
  '/profile',
]);

const getRelatedId = (notification) => {
  const metadata = notification?.metadata || {};
  const directKeys = [
    'device_id',
    'defect_id',
    'return_id',
    'distribution_id',
    'request_id',
    'entity_id',
  ];

  for (const key of directKeys) {
    if (metadata[key]) return String(metadata[key]);
  }

  if (notification?.link) {
    const tail = String(notification.link).split('/').filter(Boolean).pop();
    if (tail && !tail.includes('?')) {
      return tail;
    }
  }

  return '-';
};

const getStatusLabel = (notification) => {
  const metadata = notification?.metadata || {};
  const action = String(metadata.action || '').toLowerCase();
  const text = `${notification?.title || ''} ${notification?.message || ''}`.toLowerCase();
  const actionable = ['approval', 'distribution', 'return', 'defect'].includes(notification?.category);

  if (
    action.includes('approved') ||
    action.includes('resolved') ||
    text.includes('approved') ||
    text.includes('resolved') ||
    text.includes('completed') ||
    text.includes('confirmed receipt')
  ) {
    return 'Completed';
  }

  if (
    actionable &&
    !notification?.is_read &&
    (action.includes('request') || action.includes('pending') || text.includes('pending') || text.includes('action required'))
  ) {
    return 'Pending';
  }

  if (actionable && !notification?.is_read) {
    return 'Pending';
  }

  return 'Informational';
};

const getSection = (notification) => {
  if (notification?.category === 'approval') return 'requests';

  const message = `${notification?.title || ''} ${notification?.message || ''}`.toLowerCase();
  if (message.includes('request') || message.includes('approval') || message.includes('confirm')) {
    return 'requests';
  }

  return 'activities';
};

const getNotificationIcon = (type) => {
  if (type === 'error') return <AlertTriangle className="w-4 h-4 text-red-600" />;
  if (type === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-600" />;
  if (type === 'success') return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
  return <Info className="w-4 h-4 text-blue-600" />;
};

const statusStyle = {
  Pending: 'bg-amber-100 text-amber-800 border-amber-300',
  Completed: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  Informational: 'bg-blue-100 text-blue-800 border-blue-300',
};

const normalizeNotificationLink = (link) => {
  if (!link) return null;

  let url;
  try {
    url = new URL(String(link), 'http://local');
  } catch {
    return null;
  }

  let path = url.pathname || '';
  const query = url.search || '';

  // Legacy alias used in some older UI handlers.
  if (path === '/track-device') {
    return `/devices/track${query}`;
  }

  const defectsDetail = path.match(/^\/defects\/(\d+)$/);
  if (defectsDetail) {
    return `/defects?defectId=${defectsDetail[1]}`;
  }

  const returnsDetail = path.match(/^\/returns\/(\d+)$/);
  if (returnsDetail) {
    return `/returns?returnId=${returnsDetail[1]}`;
  }

  const distributionsDetail = path.match(/^\/distributions\/(\d+)$/);
  if (distributionsDetail) {
    return `/distributions?distributionId=${distributionsDetail[1]}`;
  }

  const devicesDetail = path.match(/^\/devices\/(\d+)$/);
  if (devicesDetail) {
    return `/devices?deviceId=${devicesDetail[1]}`;
  }

  if (VALID_BASE_ROUTES.has(path)) {
    return `${path}${query}`;
  }

  // Graceful fallback for unknown deep links under known modules.
  if (path.startsWith('/defects/')) return '/defects';
  if (path.startsWith('/returns/')) return '/returns';
  if (path.startsWith('/distributions/')) return '/distributions';
  if (path.startsWith('/devices/')) return '/devices';

  return null;
};

const isAuthorizedForPath = (role, path) => {
  if (path.startsWith('/devices/edit-requests')) {
    return ['super_admin', 'manager'].includes(role);
  }
  if (path.startsWith('/change-requests')) {
    return ['super_admin', 'manager'].includes(role);
  }
  if (path.startsWith('/reports')) {
    return ['super_admin', 'manager', 'pdic_staff'].includes(role);
  }
  if (path.startsWith('/delivery-confirmations')) {
    return ['sub_distributor', 'cluster', 'operator'].includes(role);
  }
  if (path.startsWith('/replacement-confirmation')) {
    return ['operator', 'cluster', 'sub_distributor', 'sub_distribution_employee'].includes(role);
  }
  if (path.startsWith('/approvals')) {
    return ['super_admin', 'manager', 'pdic_staff', 'sub_distributor'].includes(role);
  }
  return true;
};

const resolveNotificationLink = (notification, userRole) => {
  const metadata = notification?.metadata || {};
  const action = String(metadata.action || '').toLowerCase();

  // Prefer explicit action routing for replacement confirmation workflows.
  if (
    ['operator', 'cluster', 'sub_distributor', 'sub_distribution_employee'].includes(userRole) &&
    (action.includes('replacement') || action.includes('transfer_fix') || action.includes('transfer'))
  ) {
    return '/replacement-confirmation';
  }

  const normalizedLink = normalizeNotificationLink(notification?.link);
  if (normalizedLink) {
    if (isAuthorizedForPath(userRole, normalizedLink)) {
      return normalizedLink;
    }
    return '/notifications';
  }

  const categoryFallback = (() => {
    if (notification?.category === 'approval') {
      if (action.includes('device_edit_change') || action.includes('device_edit_request')) {
        return '/devices/edit-requests';
      }
      return '/change-requests';
    }
    if (notification?.category === 'distribution') return '/distributions';
    if (notification?.category === 'return') return '/returns';
    if (notification?.category === 'defect') {
      return ['operator', 'cluster', 'sub_distributor', 'sub_distribution_employee'].includes(userRole) &&
        action.includes('replacement')
        ? '/replacement-confirmation'
        : '/defects';
    }
    return null;
  })();

  if (categoryFallback) {
    return isAuthorizedForPath(userRole, categoryFallback) ? categoryFallback : '/notifications';
  }

  return null;
};

const NotificationRow = ({ notification, onOpen }) => {
  const status = getStatusLabel(notification);
  const relatedId = getRelatedId(notification);

  return (
    <button
      type="button"
      onClick={() => onOpen(notification)}
      className={`w-full text-left p-4 border rounded-lg transition-colors hover:bg-gray-50 ${
        notification.is_read ? 'border-gray-200 bg-white' : 'border-blue-200 bg-blue-50/60'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{getNotificationIcon(notification.type)}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <p className="font-medium text-gray-900">{notification.title}</p>
            {!notification.is_read && <span className="w-2.5 h-2.5 rounded-full bg-blue-600 mt-1.5" />}
          </div>
          <p className="text-sm text-gray-600 mt-1">{notification.message}</p>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 text-gray-700 border border-gray-200">
              <Clock3 className="w-3 h-3" />
              {new Date(notification.created_at).toLocaleString()}
            </span>
            <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 border border-gray-200">
              Related ID: {relatedId}
            </span>
            <span className={`px-2 py-1 rounded-md border ${statusStyle[status]}`}>
              {status}
            </span>
          </div>
        </div>
        <ExternalLink className="w-4 h-4 text-gray-400 mt-1" />
      </div>
    </button>
  );
};

const Notifications = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { showToast, refreshUnreadCount } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [totalCount, setTotalCount] = useState(0);

  const loadNotifications = useCallback(async (targetPage = 1) => {
    setLoading(true);
    try {
      const response = await notificationsAPI.getNotifications({
        page: targetPage,
        page_size: PAGE_SIZE,
      });

      const incoming = response?.data || [];
      const pagination = response?.pagination || {};

      setItems(incoming);
      setPage(targetPage);
      setTotalCount(Number(pagination.total || incoming.length || 0));
      setHasNext(Boolean(pagination.has_next));
      await refreshUnreadCount();
    } catch (error) {
      showToast(error.message || 'Failed to load notifications', 'error');
    } finally {
      setLoading(false);
    }
  }, [refreshUnreadCount, showToast]);

  useEffect(() => {
    loadNotifications(1);
  }, [loadNotifications]);

  const orderedItems = useMemo(
    () => [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [items]
  );

  const activities = orderedItems.filter((n) => getSection(n) === 'activities');
  const requests = orderedItems.filter((n) => getSection(n) === 'requests');

  const openNotification = async (notification) => {
    try {
      if (!notification.is_read) {
        await notificationsAPI.markAsRead(notification.id);
        setItems((prev) => prev.map((n) => (String(n.id) === String(notification.id) ? { ...n, is_read: true } : n)));
        await refreshUnreadCount();
      }

      const target = resolveNotificationLink(notification, user?.role);
      if (target) {
        const separator = target.includes('?') ? '&' : '?';
        const withContext = `${target}${separator}notificationId=${notification.id}`;

        // Force meaningful navigation when the base target equals current location.
        if (`${location.pathname}${location.search}` === target) {
          navigate(withContext, { replace: true });
        } else {
          navigate(withContext);
        }
      } else {
        showToast('This notification has no valid destination route', 'info');
      }
    } catch (error) {
      showToast(error.message || 'Failed to open notification', 'error');
    }
  };

  const handleMarkAllRead = async () => {
    setMarkingAll(true);
    try {
      await notificationsAPI.markAllAsRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      await refreshUnreadCount();
      showToast('All notifications marked as read', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to mark all notifications as read', 'error');
    } finally {
      setMarkingAll(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="text-sm text-gray-500 mt-1">All alerts and request updates in chronological order.</p>
        </div>
        <Button onClick={handleMarkAllRead} disabled={markingAll} icon={CheckCheck}>
          {markingAll ? 'Marking...' : 'Mark All Read'}
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-gray-600">
        <p>
          Page {page} of {Math.ceil(totalCount / PAGE_SIZE) || 1} &mdash; {totalCount} notifications
        </p>
      </div>

      {loading ? (
        <Card>
          <div className="py-10 flex items-center justify-center gap-2 text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading notifications...
          </div>
        </Card>
      ) : orderedItems.length === 0 ? (
        <Card>
          <div className="py-10 text-center text-gray-500">
            <Bell className="w-10 h-10 mx-auto mb-2 text-gray-300" />
            No notifications yet.
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card title="Activities / Alerts">
            <div className="space-y-3">
              {activities.length === 0 ? (
                <p className="text-sm text-gray-500">No activity alerts.</p>
              ) : (
                activities.map((notification) => (
                  <NotificationRow
                    key={notification.id}
                    notification={notification}
                    onOpen={openNotification}
                  />
                ))
              )}
            </div>
          </Card>

          <Card title="Requests / Approvals">
            <div className="space-y-3">
              {requests.length === 0 ? (
                <p className="text-sm text-gray-500">No request notifications.</p>
              ) : (
                requests.map((notification) => (
                  <NotificationRow
                    key={notification.id}
                    notification={notification}
                    onOpen={openNotification}
                  />
                ))
              )}
            </div>
          </Card>
        </div>
      )}

      {!loading && (
        <div className="flex items-center justify-center gap-4">
          <Button variant="outline" disabled={page <= 1} onClick={() => loadNotifications(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-gray-500">Page {page}</span>
          <Button variant="outline" disabled={!hasNext} onClick={() => loadNotifications(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
};

export default Notifications;

