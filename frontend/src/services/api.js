import {
  API_BASE_URL as _API_BASE_URL,
  apiRequest as _apiRequest,
  buildCsrfHeader as _buildCsrfHeader,
  getCookieValue as _getCookieValue,
  isDev as _isDev,
  log as _log,
  logError as _logError,
  authAPI as _authAPI,
  usersAPI as _usersAPI,
  adminUpdateCredentials as _adminUpdateCredentials,
  devicesAPI as _devicesAPI,
  distributionsAPI as _distributionsAPI,
  defectsAPI as _defectsAPI,
  returnsAPI as _returnsAPI,
  notificationsAPI as _notificationsAPI,
  externalInventoryAPI as _externalInventoryAPI,
  reportsAPI as _reportsAPI,
  dashboardAPI as _dashboardAPI,
  changeRequestsAPI as _changeRequestsAPI,
  reassignmentRequestsAPI as _reassignmentRequestsAPI,
  digitalIdsAPI as _digitalIdsAPI,
  approvalsAPI as _approvalsAPI,
} from './api/index.js';

export const API_BASE_URL = _API_BASE_URL;
export const apiRequest = _apiRequest;
export const buildCsrfHeader = _buildCsrfHeader;
export const getCookieValue = _getCookieValue;
export const isDev = _isDev;
export const log = _log;
export const logError = _logError;
export const authAPI = _authAPI;
export const usersAPI = _usersAPI;
export const adminUpdateCredentials = _adminUpdateCredentials;
export const devicesAPI = _devicesAPI;
export const distributionsAPI = _distributionsAPI;
export const defectsAPI = _defectsAPI;
export const returnsAPI = _returnsAPI;
export const notificationsAPI = _notificationsAPI;
export const externalInventoryAPI = _externalInventoryAPI;
export const reportsAPI = _reportsAPI;
export const dashboardAPI = _dashboardAPI;
export const changeRequestsAPI = _changeRequestsAPI;
export const reassignmentRequestsAPI = _reassignmentRequestsAPI;
export const digitalIdsAPI = _digitalIdsAPI;
export const approvalsAPI = _approvalsAPI;

const api = {
  auth: _authAPI,
  users: _usersAPI,
  devices: _devicesAPI,
  distributions: _distributionsAPI,
  defects: _defectsAPI,
  returns: _returnsAPI,
  notifications: _notificationsAPI,
  externalInventory: _externalInventoryAPI,
  reports: _reportsAPI,
  dashboard: _dashboardAPI,
  changeRequests: _changeRequestsAPI,
  reassignmentRequests: _reassignmentRequestsAPI,
  digitalIds: _digitalIdsAPI,
  approvals: _approvalsAPI,
};

export default api;
