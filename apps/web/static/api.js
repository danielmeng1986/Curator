/* Curator Web Client API boundary.
 *
 * Every request is authenticated and versioned. The device token is local to
 * this browser profile; it is never embedded in source or configuration files.
 */
(function () {
  const TOKEN_KEY = 'curator.web.deviceToken';
  const BACKEND_URL_KEY = 'curator.web.backendUrl';
  const DEVICE_IDENTITY_KEY = 'curator.web.deviceIdentity';
  const ENROLLMENT_KEY = 'curator.web.pendingEnrollment';
  const initialConfig = window.CURATOR_WEB_CONFIG || {};

  class CuratorApiError extends Error {
    constructor(code, message, status = 0, { details = null, requestId = null } = {}) {
      super(message);
      this.name = 'CuratorApiError';
      this.code = code;
      this.status = status;
      this.details = details;
      this.requestId = requestId;
    }
  }

  const inFlightMutations = new Set();

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

  function deviceIdentity() {
    const existing = localValue(DEVICE_IDENTITY_KEY, '');
    if (existing) return existing;
    const generated = window.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try { window.localStorage.setItem(DEVICE_IDENTITY_KEY, generated); } catch { /* session-only fallback */ }
    return generated;
  }

  async function publicAuthFetch(path, options = {}) {
    let response;
    try {
      response = await fetch(`${backendUrl()}${path}`, {
        ...options,
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(options.headers || {}) },
      });
    } catch {
      throw new CuratorApiError('NETWORK_UNAVAILABLE', 'The Curator Backend is unavailable.');
    }
    let payload = {};
    try { payload = await response.json(); } catch { /* safe generic error below */ }
    if (!response.ok || payload.error) {
      const error = payload.error || {};
      throw new CuratorApiError(
        error.code || `HTTP_${response.status}`,
        error.message || 'The Backend rejected this request.',
        response.status,
        { details: error.details || null, requestId: payload.meta?.request_id || null },
      );
    }
    return payload.data;
  }

  async function validateConnection({ backendUrl: candidateBackendUrl = '', token }) {
    const origin = String(candidateBackendUrl || '').replace(/\/$/, '');
    let response;
    try {
      response = await fetch(`${origin}/api/v1/auth/me`, {
        headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
      });
    } catch {
      throw new CuratorApiError('NETWORK_UNAVAILABLE', 'The Curator Backend is unavailable.');
    }
    let payload = {};
    try { payload = await response.json(); } catch { /* safe generic error below */ }
    if (!response.ok || payload.error) {
      const error = payload.error || {};
      throw new CuratorApiError(
        error.code || `HTTP_${response.status}`,
        error.message || 'The Backend rejected this request.',
        response.status,
        { details: error.details || null, requestId: payload.meta?.request_id || null },
      );
    }
    return payload.data.principal;
  }

  function randomCredential(byteLength = 32) {
    const bytes = new Uint8Array(byteLength);
    window.crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async function sha256Hex(value) {
    const digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
    return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  }

  async function requestDeviceAccess({ deviceName, role, registrationProof }) {
    if (!['reader', 'writer'].includes(role)) throw new CuratorApiError('REQUEST_INVALID_ROLE', 'Only Reader or Writer access may be requested.');
    const token = randomCredential(32), enrollmentProof = randomCredential(32);
    const scopes = role === 'writer' ? ['read', 'write'] : ['read'];
    const data = await publicAuthFetch('/api/auth/registrations', { method: 'POST', body: JSON.stringify({
      device_name: deviceName, device_identity: deviceIdentity(), requested_role: role,
      requested_scopes: scopes, registration_proof: registrationProof,
      candidate_token_hash: await sha256Hex(token), enrollment_proof: enrollmentProof,
    }) });
    const pending = { registrationUuid: data.registration.uuid, enrollmentProof, token, role, deviceName };
    try { window.localStorage.setItem(ENROLLMENT_KEY, JSON.stringify(pending)); }
    catch { throw new CuratorApiError('LOCAL_CONFIGURATION_UNAVAILABLE', 'This browser cannot save the pending enrollment.'); }
    return data.registration;
  }

  function pendingEnrollment() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(ENROLLMENT_KEY) || 'null');
      if (!saved || typeof saved !== 'object') return null;
      // Accept both the current browser shape and early snake_case builds so
      // an enrollment already approved by an Administrator remains recoverable.
      const pending = {
        registrationUuid: saved.registrationUuid || saved.registration_uuid,
        enrollmentProof: saved.enrollmentProof || saved.enrollment_proof,
        token: saved.token,
        role: saved.role || saved.requested_role,
        deviceName: saved.deviceName || saved.device_name,
      };
      return pending.registrationUuid && pending.enrollmentProof && pending.token ? pending : null;
    } catch { return null; }
  }

  async function enrollmentStatus() {
    const pending = pendingEnrollment();
    if (!pending) return null;
    const data = await publicAuthFetch(`/api/auth/registrations/${encodeURIComponent(pending.registrationUuid)}/status`, {
      method: 'POST', body: JSON.stringify({ enrollment_proof: pending.enrollmentProof }),
    });
    if (data.registration.status === 'Approved') {
      const principal = await validateConnection({ backendUrl: backendUrl(), token: pending.token });
      try {
        window.localStorage.setItem(TOKEN_KEY, pending.token);
        window.localStorage.removeItem(ENROLLMENT_KEY);
      } catch { throw new CuratorApiError('LOCAL_CONFIGURATION_UNAVAILABLE', 'This browser cannot save the approved Token.'); }
      return { ...data.registration, principal };
    }
    return data.registration;
  }

  function legacyReadModel(path, data, meta) {
    if (!Array.isArray(data)) return data;
    const route = path.split('?')[0];
    if (route === '/operations') return { operations: data, meta: meta || {} };
    if (route === '/work-dispatch/candidates' || route === '/work-dispatch/groups') {
      return { items: data, meta: meta || {}, total: meta?.pagination?.total ?? meta?.total ?? data.length,
        limit: meta?.pagination?.limit ?? data.length };
    }
    const key = {
      '/albums': 'albums',
      '/models': 'models',
      '/studios': 'studios',
    }[route];
    return key ? { [key]: data, total: meta?.pagination?.total ?? meta?.total ?? data.length } : data;
  }

  async function performFetch(path, options, token) {
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
        { details: error.details || null, requestId: payload.meta?.request_id || null },
      );
    }
    return legacyReadModel(path, payload.data, payload.meta);
  }

  async function performBlobFetch(path, token) {
    let response;
    try {
      response = await fetch(`${versionedBaseUrl()}${path}`, {
        headers: { Accept: 'image/*', Authorization: `Bearer ${token}` }, cache:'no-store',
      });
    } catch {
      throw new CuratorApiError('NETWORK_UNAVAILABLE', 'The Curator Backend is unavailable.');
    }
    if (!response.ok) {
      let payload={};try{payload=await response.json();}catch{/* generic error below */}
      const error=payload.error||{};
      throw new CuratorApiError(error.code||`HTTP_${response.status}`,error.message||'The image is unavailable.',response.status,
        {details:error.details||null,requestId:payload.meta?.request_id||null});
    }
    return response.blob();
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

    const method = (options.method || 'GET').toUpperCase();
    const mutationKey = method === 'GET' ? null : `${method} ${path}`;
    if (mutationKey && inFlightMutations.has(mutationKey)) {
      throw new CuratorApiError(
        'CLIENT_ACTION_IN_PROGRESS',
        'This action is already in progress.',
        0,
      );
    }
    if (mutationKey) inFlightMutations.add(mutationKey);
    try {
      return await performFetch(path, options, token);
    } finally {
      if (mutationKey) inFlightMutations.delete(mutationKey);
    }
  }

  const api = Object.freeze({
    get: (path) => apiFetch(path),
    getBlob: (path) => {
      const token=deviceToken();
      if(!token)throw new CuratorApiError('AUTHENTICATION_MISSING_TOKEN','Device access is required.',401);
      return performBlobFetch(path,token);
    },
    post: (path, body) => apiFetch(path, { method: 'POST', body: JSON.stringify(body) }),
    put: (path, body) => apiFetch(path, { method: 'PUT', body: JSON.stringify(body) }),
    del: (path) => apiFetch(path, { method: 'DELETE' }),
    getConnection: () => ({ backendUrl: backendUrl(), hasToken: Boolean(deviceToken()) }),
    getDeviceIdentity: deviceIdentity,
    validateConnection,
    bootstrapStatus: () => publicAuthFetch('/api/auth/bootstrap/status'),
    completeBootstrap: (body) => publicAuthFetch('/api/auth/bootstrap/complete', { method: 'POST', body: JSON.stringify(body) }),
    requestDeviceAccess,
    getPendingEnrollment: pendingEnrollment,
    enrollmentStatus,
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
      error.code === 'AUTHENTICATION_MISSING_TOKEN' || error.status === 401
    ),
    isAuthorizationError: (error) => error instanceof CuratorApiError && error.status === 403,
    isActionInProgressError: (error) => error instanceof CuratorApiError && error.code === 'CLIENT_ACTION_IN_PROGRESS',
    Error: CuratorApiError,
  });

  window.api = api;
})();
