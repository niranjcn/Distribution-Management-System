const AUTH_USER_KEY = 'dms_user';
const LAST_PATH_KEY = 'dms-last-path';

// Only these fields are ever persisted client-side. Everything else a backend
// user object may carry (status, timestamps, login counters, lockout state,
// creator id, tokens) is dropped before it reaches sessionStorage.
const STORED_USER_FIELDS = new Set([
  'id', 'name', 'email', 'role',
  'phone', 'designation', 'address', 'pincode', 'parent_id',
  'force_email_change', 'force_password_change',
  'avatar',
]);

const hasWindow = () => typeof window !== 'undefined';

const parseUser = (raw) => {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.error('[authStorage] Failed to parse stored user:', error);
    return null;
  }
};

const stripToken = (user) => {
  if (!user || typeof user !== 'object') return user;
  const { token, access_token, ...safeUser } = user;
  return Object.fromEntries(
    Object.entries(safeUser).filter(([key]) => STORED_USER_FIELDS.has(key))
  );
};

export const getStoredUser = () => {
  if (!hasWindow()) return null;

  const sessionValue = sessionStorage.getItem(AUTH_USER_KEY);
  const sessionUser = stripToken(parseUser(sessionValue));
  if (sessionUser) return sessionUser;

  // Backward-compatible migration from legacy localStorage token storage.
  const legacyValue = localStorage.getItem(AUTH_USER_KEY);
  const legacyUser = stripToken(parseUser(legacyValue));
  if (legacyUser) {
    sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(legacyUser));
  }
  localStorage.removeItem(AUTH_USER_KEY);
  return legacyUser;
};

export const saveStoredUser = (user) => {
  if (!hasWindow()) return;
  sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(stripToken(user)));
  localStorage.removeItem(AUTH_USER_KEY);
};

export const clearStoredUser = () => {
  if (!hasWindow()) return;
  sessionStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
};

export const getLastPath = () => {
  if (!hasWindow()) return null;
  return sessionStorage.getItem(LAST_PATH_KEY);
};

export const setLastPath = (path) => {
  if (!hasWindow() || !path) return;
  sessionStorage.setItem(LAST_PATH_KEY, path);
};

export const clearLastPath = () => {
  if (!hasWindow()) return;
  sessionStorage.removeItem(LAST_PATH_KEY);
};

export const updateStoredUser = (updates) => {
  const current = getStoredUser() || {};
  const merged = { ...current, ...updates };
  saveStoredUser(merged);
  return merged;
};
