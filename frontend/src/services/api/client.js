import { clearStoredUser } from '../../utils/authStorage';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';
const isDev = import.meta.env.DEV;
const log = isDev ? console.log : () => {};
const logError = isDev ? console.error : () => {};

log('[API] Initialized with base URL:', API_BASE_URL);

let _refreshing = false;
let _refreshPromise = null;

const getCookieValue = (name) => {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

// Attempt to refresh the access token using the httpOnly refresh-token cookie.
// Uses a deduplication guard so concurrent 401s only trigger one refresh request.
const attemptTokenRefresh = async () => {
  if (_refreshing) {
    // Another refresh is already in flight — wait for it
    return _refreshPromise;
  }

  _refreshing = true;
  _refreshPromise = (async () => {
    try {
      const csrfToken = getCookieValue('csrftoken');
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
      });
      if (res.ok) {
        log('[API] Token refresh succeeded');
        return true;
      }
      logError('[API] Token refresh failed with status:', res.status);
      return false;
    } catch (err) {
      logError('[API] Token refresh request error:', err.message);
      return false;
    } finally {
      _refreshing = false;
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
};

const isUnsafeMethod = (method) => !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase());

const buildCsrfHeader = (method) => {
  const csrfToken = getCookieValue('csrftoken');
  return csrfToken && isUnsafeMethod(method) ? { 'X-CSRFToken': csrfToken } : {};
};

// 401 indicates an invalid/expired session (token refresh then logout).
// 403 is a genuine permission error (authenticated but not allowed) and must
// NOT clear the session, otherwise any "forbidden" API error logs the user out.
const AUTH_FAILURE_STATUSES = new Set([401]);
const AUTH_FAILURE_ALLOWLIST = new Set([
  '/auth/login',
  '/auth/refresh',
  '/auth/complete-forced-update',
]);

const handleAuthFailure = (endpoint, message) => {
  if (AUTH_FAILURE_ALLOWLIST.has(endpoint)) return;

  logError('[API] Auth failure detected, clearing session:', { endpoint, message });
  clearStoredUser();

  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};

const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();

  log('[API] Making request:', {
    method: options.method || 'GET',
    endpoint,
    url
  });

  const headers = {
    'Content-Type': 'application/json',
    ...buildCsrfHeader(method),
    ...options.headers,
  };

  try {
    const fetchOptions = {
      ...options,
      credentials: 'include',
      headers,
    };

    const response = await fetch(url, fetchOptions);

    log('[API] Response received:', {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      endpoint
    });

    const raw = await response.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { message: raw || 'API request failed' };
    }

    if (!response.ok) {
      let errorMessage =
        data?.message ||
        data?.detail ||
        (typeof data?.error?.details === 'string' ? data.error.details : null) ||
        'API request failed';

      if (
        response.status === 422 &&
        data?.error?.code === 'VALIDATION_ERROR' &&
        Array.isArray(data?.error?.details) &&
        data.error.details.length > 0
      ) {
        const first = data.error.details[0];
        const field = first?.field ? String(first.field).replace('body.', '') : 'field';
        const message = first?.message || 'Invalid value';
        errorMessage = `${field}: ${message}`;
      }

      if (
        response.status === 400 &&
        Array.isArray(data?.error?.details) &&
        data.error.details.length > 0
      ) {
        const first = data.error.details[0];
        errorMessage = first?.message || errorMessage;
      }

      if (response.status === 401 && !AUTH_FAILURE_ALLOWLIST.has(endpoint)) {
        const refreshed = await attemptTokenRefresh();
        if (refreshed) return apiRequest(endpoint, options);
      }

      if (AUTH_FAILURE_STATUSES.has(response.status)) {
        handleAuthFailure(endpoint, errorMessage);
      }

      logError('[API] Request failed:', {
        endpoint,
        status: response.status,
        error: errorMessage,
        data
      });
      throw new Error(errorMessage);
    }

    log('[API] Request successful:', endpoint);

    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method) && !endpoint.startsWith('/auth/')) {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('appDataMutation'));
      }
    }

    return data;
  } catch (error) {
    logError('[API] Request error:', {
      endpoint,
      error: error.message,
      stack: error.stack
    });
    throw error;
  }
};

// Downloads a bulk operation error report (CSV) via the cookie-authenticated
// API. Returns nothing on success and throws on failure.
const downloadBulkReport = async (reportId, filename = 'bulk-report.csv') => {
  const response = await fetch(`${API_BASE_URL}/bulk-reports/${reportId}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to download report');
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

export { API_BASE_URL, apiRequest, buildCsrfHeader, getCookieValue, isDev, log, logError, downloadBulkReport };
