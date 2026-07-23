async function apiFetch(path, options = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const api = {
  get:  (path)       => apiFetch(path),
  post: (path, body) => apiFetch(path, { method: 'POST', body: JSON.stringify(body) }),
  put:  (path, body) => apiFetch(path, { method: 'PUT',  body: JSON.stringify(body) }),
  del:  (path)       => apiFetch(path, { method: 'DELETE' }),
};
