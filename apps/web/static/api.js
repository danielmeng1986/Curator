/* Curator Web Client API boundary.
 *
 * Every request is authenticated and versioned. The device token is local to
 * this browser profile; it is never embedded in source or configuration files.
 */
(function () {
  const TOKEN_KEY = 'curator.web.deviceToken';
  const BACKEND_URL_KEY = 'curator.web.backendUrl';
  const initialConfig = window.CURATOR_WEB_CONFIG || {};

  class CuratorApiError extends Error {
    constructor(code, message, status = 0) {
      super(message);
      this.name = 'CuratorApiError';
      this.code = code;
      this.status = status;
    }
  }

  function localValue(key, fallback = '') {
    try { return window.localStorage.getItem(key) || fallback; } catch { return fallback; }
  }

  function backendUrl() {
    return localValue(BACKEND_URL_KEY, initialConfig.backendUrl || '').replace(/\/$/, '');
  }

  function versionedBaseUrl() {
    const origin = backendUrl();
    return origin.endsWith('/api/v1') ? origin : `${origin}/api/v1`;
  }

  function deviceToken() {
    return localValue(TOKEN_KEY, '');
  }

  function legacyReadModel(path, data, meta) {
    if (!Array.isArray(data)) return data;
    const route = path.split('?')[0];
    const key = {
      '/albums': 'albums',
      '/models': 'models',
      '/studios': 'studios',
    }[route];
    return key ? { [key]: data, total: meta?.total ?? data.length } : data;
  }

  async function apiFetch(path, options = {}) {
    const token = deviceToken();
    if (!token) {
      throw new CuratorApiError(
        'AUTHENTICATION_MISSING_TOKEN',
        'Device access is required. Configure an approved device token before continuing.',
        401,
      );
    }

    let response;
    try {
      response = await fetch(`${versionedBaseUrl()}${path}`, {
        ...options,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...(options.headers || {}),
        },
      });
    } catch {
      throw new CuratorApiError('NETWORK_UNAVAILABLE', 'The Curator Backend is unavailable.');
    }

    let payload = {};
    try { payload = await response.json(); } catch { /* keep safe generic error below */ }
    if (!response.ok || payload.ok === false || payload.error) {
      const error = payload.error || {};
      throw new CuratorApiError(
        error.code || `HTTP_${response.status}`,
        error.message || 'The Backend rejected this request.',
        response.status,
      );
    }
    return legacyReadModel(path, payload.data, payload.meta);
  }

  const api = Object.freeze({
    get: (path) => apiFetch(path),
    post: (path, body) => apiFetch(path, { method: 'POST', body: JSON.stringify(body) }),
    put: (path, body) => apiFetch(path, { method: 'PUT', body: JSON.stringify(body) }),
    del: (path) => apiFetch(path, { method: 'DELETE' }),
    getConnection: () => ({ backendUrl: backendUrl(), hasToken: Boolean(deviceToken()) }),
    configure: ({ backendUrl: nextBackendUrl, token }) => {
      try {
        if (nextBackendUrl !== undefined) window.localStorage.setItem(BACKEND_URL_KEY, nextBackendUrl.trim());
        if (token !== undefined) window.localStorage.setItem(TOKEN_KEY, token.trim());
      } catch {
        throw new CuratorApiError('LOCAL_CONFIGURATION_UNAVAILABLE', 'This browser cannot save local connection settings.');
      }
    },
    clearToken: () => { try { window.localStorage.removeItem(TOKEN_KEY); } catch { /* no fallback */ } },
    isAuthenticationError: (error) => error instanceof CuratorApiError && (
      error.code === 'AUTHENTICATION_MISSING_TOKEN' || error.status === 401 || error.status === 403
    ),
    Error: CuratorApiError,
  });

  window.api = api;
})();
