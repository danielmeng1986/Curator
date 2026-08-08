/* Shared interaction contract for permission, error, feedback, and modal states. */
(function () {
  const activeActions = new Set();
  let returnFocus = null;
  let modalKeyHandler = null;

  const ROLE_SCOPES = Object.freeze({
    reader: Object.freeze(['read']),
    writer: Object.freeze(['read', 'write']),
    admin: Object.freeze(['read', 'write', 'admin']),
  });

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }

  function errorPresentation(error, context = 'request') {
    const code = error?.code || 'UNKNOWN_ERROR';
    const status = Number(error?.status || 0);
    const safeBackendMessage = typeof error?.message === 'string' ? error.message : '';
    const reference = error?.requestId ? `Request ${error.requestId}` : '';

    if (code === 'CLIENT_ACTION_IN_PROGRESS') {
      return { kind: 'warning', title: 'Action already in progress', message: 'Wait for the current action to finish before trying again.', reference };
    }
    if (code.includes('BOOTSTRAP_CODE')) {
      return { kind: 'validation', title: 'Bootstrap Code unavailable', message: safeBackendMessage || 'Generate a new Bootstrap Code from the Backend console.', reference };
    }
    if (status === 401 || code.startsWith('AUTHENTICATION_')) {
      return { kind: 'authentication', title: 'Authorization required', message: 'Connect with a valid approved device token, then try again.', reference };
    }
    if (status === 403 || code.startsWith('AUTHORIZATION_') || code === 'ADMIN_REQUIRED') {
      return { kind: 'authorization', title: 'Permission denied', message: 'This device does not have permission to perform this action.', reference };
    }
    if (status === 400 || code.startsWith('REQUEST_') || code === 'VALIDATION_ERROR') {
      return { kind: 'validation', title: 'Check the highlighted information', message: safeBackendMessage || 'Some information is missing or invalid.', reference };
    }
    if (status === 409 || code === 'NEEDS_REPAIR' || code.includes('CONFLICT')) {
      return { kind: 'conflict', title: code === 'NEEDS_REPAIR' ? 'Repair review required' : 'The action conflicts with current state', message: safeBackendMessage || 'Refresh the current state and review the action before trying again.', reference };
    }
    if (code === 'NETWORK_UNAVAILABLE') {
      return { kind: 'network', title: 'Backend unavailable', message: 'Check the Curator connection and try again. Your entered values have been retained.', reference };
    }
    if (status === 404) {
      return { kind: 'not-found', title: 'Record not found', message: safeBackendMessage || 'The requested record is no longer available.', reference };
    }
    return { kind: 'unexpected', title: `Unable to complete ${context}`, message: 'An unexpected error occurred. No success has been assumed.', reference };
  }

  function errorHtml(error, context) {
    const p = errorPresentation(error, context);
    return `<section class="feedback feedback-${escapeHtml(p.kind)}" role="alert" tabindex="-1">
      <h2>${escapeHtml(p.title)}</h2>
      <p>${escapeHtml(p.message)}</p>
      ${p.reference ? `<p class="feedback-reference">${escapeHtml(p.reference)}</p>` : ''}
    </section>`;
  }

  function renderPageError(element, error, context = 'this view') {
    if (!element) return;
    element.innerHTML = errorHtml(error, context);
    element.querySelector?.('[role="alert"]')?.focus?.();
  }

  function toast(message, type = 'ok', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return null;
    const node = document.createElement('div');
    const kind = ['ok', 'error', 'warning'].includes(type) ? type : 'ok';
    node.className = `toast toast-${kind}`;
    node.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    node.textContent = message;
    container.appendChild(node);
    if (duration > 0) setTimeout(() => node.remove(), duration);
    return node;
  }

  function toastError(error, context = 'action') {
    const p = errorPresentation(error, context);
    return toast(`${p.title}: ${p.message}`, p.kind === 'warning' ? 'warning' : 'error');
  }

  function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    const box = document.getElementById('modal-box');
    overlay?.classList.add('hidden');
    if (box) box.innerHTML = '';
    if (modalKeyHandler) document.removeEventListener('keydown', modalKeyHandler);
    modalKeyHandler = null;
    const target = returnFocus;
    returnFocus = null;
    target?.focus?.();
  }

  function showModal(html, { dismissible = true } = {}) {
    const overlay = document.getElementById('modal-overlay');
    const box = document.getElementById('modal-box');
    if (!overlay || !box) return;
    returnFocus = document.activeElement;
    box.innerHTML = html;
    const heading = box.querySelector('h1, h2, h3');
    if (heading && !heading.id) heading.id = 'modal-title';
    overlay.classList.remove('hidden');
    overlay.onclick = (event) => { if (dismissible && event.target === overlay) closeModal(); };
    modalKeyHandler = (event) => {
      if (event.key === 'Escape' && dismissible) { event.preventDefault(); closeModal(); return; }
      if (event.key !== 'Tab') return;
      const focusable = [...box.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter((item) => !item.disabled && !item.hidden);
      if (!focusable.length) { event.preventDefault(); box.focus(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', modalKeyHandler);
    const initial = box.querySelector('[autofocus], button, input, select, textarea, [href]');
    (initial || box).focus?.();
  }

  function confirmDialog(messageOrOptions) {
    const options = typeof messageOrOptions === 'string' ? { message: messageOrOptions } : messageOrOptions;
    const title = options.title || 'Confirm action';
    const confirmLabel = options.confirmLabel || 'Confirm';
    const danger = options.danger !== false;
    return new Promise((resolve) => {
      showModal(`
        <h3 class="modal-title" id="modal-title">${escapeHtml(title)}</h3>
        <p>${escapeHtml(options.message || '')}</p>
        <div class="modal-footer">
          <button class="btn btn-secondary" id="confirmNo">Cancel</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" id="confirmYes">${escapeHtml(confirmLabel)}</button>
        </div>
      `, { dismissible: false });
      document.getElementById('confirmYes').onclick = () => { closeModal(); resolve(true); };
      document.getElementById('confirmNo').onclick = () => { closeModal(); resolve(false); };
    });
  }

  async function runAction(key, action, { trigger = null, success = '', context = 'action' } = {}) {
    if (activeActions.has(key)) {
      const error = new window.api.Error('CLIENT_ACTION_IN_PROGRESS', 'This action is already in progress.');
      toast(errorPresentation(error, context).message, 'warning');
      return { ok: false, error };
    }
    activeActions.add(key);
    if (trigger) { trigger.disabled = true; trigger.setAttribute('aria-busy', 'true'); }
    try {
      const value = await action();
      if (success) toast(success, 'ok');
      return { ok: true, value };
    } catch (error) {
      toastError(error, context);
      return { ok: false, error };
    } finally {
      activeActions.delete(key);
      if (trigger) { trigger.disabled = false; trigger.removeAttribute('aria-busy'); }
    }
  }

  function can(role, requiredScope) {
    return Boolean(ROLE_SCOPES[role]?.includes(requiredScope));
  }

  function applyPermissions(root = document, principal = null) {
    root.querySelectorAll?.('[data-required-scope]').forEach((element) => {
      const allowed = Boolean(principal && can(principal.role, element.dataset.requiredScope));
      if (element.matches('a, [role="link"]')) {
        element.classList.toggle('hidden', !allowed);
        element.setAttribute('aria-hidden', String(!allowed));
      } else {
        element.disabled = !allowed;
        element.classList.toggle('hidden', !allowed);
      }
    });
  }

  window.ui = Object.freeze({
    ROLE_SCOPES, can, applyPermissions, escapeHtml, errorPresentation, errorHtml, renderPageError,
    toast, toastError, showModal, closeModal, confirmDialog, runAction,
  });
})();
