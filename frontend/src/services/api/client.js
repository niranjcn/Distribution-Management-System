import { clearStoredUser } from '../../utils/authStorage';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';
const isDev = import.meta.env.DEV;
const log = isDev ? console.log : () => {};
const logError = isDev ? console.error : () => {};

log('[API] Initialized with base URL:', API_BASE_URL);

const getCookieValue = (name) => {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

const isUnsafeMethod = (method) => !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase());

const buildCsrfHeader = (method) => {
  const csrfToken = getCookieValue('csrftoken');
  return csrfToken && isUnsafeMethod(method) ? { 'X-CSRFToken': csrfToken } : {};
};

const AUTH_FAILURE_STATUSES = new Set([401, 403]);
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

    if (method === 'GET' || method === 'HEAD') {
      fetchOptions.cache = 'no-store';
    }

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
      setTimeout(() => {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('appDataMutation'));
        }
      }, 500);
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

export { API_BASE_URL, apiRequest, buildCsrfHeader, getCookieValue, isDev, log, logError };
