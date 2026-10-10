/**
 * Common utilities and background status checker for xFACE.
 */

const IS_LOGGED_IN = document.body.dataset.loggedIn === 'true';

// Escape untrusted text (subject names, notes) before inserting it into HTML
function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Inline SVG reference to the shared icon sprite (_icons.html)
function icon(name, cls = '') {
    return `<svg class="i ${cls}" aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`;
}

function initials(name) {
    return String(name || '?').trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase();
}

/* ---------- Toasts ---------- */

const TOAST_ICONS = { success: 'check', danger: 'alert', warning: 'alert', info: 'info' };

function showToast(message, type = 'info') {
    const stack = document.getElementById('toasts');
    if (!stack) return;
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    el.innerHTML = `<span class="t-icon">${icon(TOAST_ICONS[type] || 'info')}</span>
        <div class="t-msg"></div>
        <button type="button" aria-label="Dismiss">${icon('x', 'i-sm')}</button>`;
    el.querySelector('.t-msg').textContent = message;

    const dismiss = () => {
        el.classList.add('leaving');
        setTimeout(() => el.remove(), 250);
    };
    el.querySelector('button').addEventListener('click', dismiss);
    stack.appendChild(el);
    while (stack.children.length > 4) stack.firstElementChild.remove();
    setTimeout(dismiss, 4500);
}

/* ---------- Dialogs ---------- */

function openModal(id) {
    const dialog = document.getElementById(id);
    if (dialog && !dialog.open) dialog.showModal();
    return dialog;
}

function closeModal(id) {
    const dialog = typeof id === 'string' ? document.getElementById(id) : id;
    if (dialog?.open) dialog.close();
}

// Promise-based replacement for window.confirm() that matches the UI
function confirmAction({ title, message, confirmLabel = 'Delete', danger = true }) {
    return new Promise(resolve => {
        const dialog = document.createElement('dialog');
        dialog.className = 'modal';
        dialog.innerHTML = `
            <div class="modal-head ${danger ? 'danger' : ''}">
                <span class="m-icon">${icon(danger ? 'trash' : 'info')}</span>
                <div><h2></h2></div>
            </div>
            <div class="modal-body"><p class="muted"></p></div>
            <div class="modal-foot">
                <button type="button" class="btn" value="cancel">Cancel</button>
                <button type="button" class="btn ${danger ? 'btn-danger' : 'btn-primary'}" value="ok"></button>
            </div>`;
        dialog.querySelector('h2').textContent = title;
        dialog.querySelector('.modal-body p').textContent = message;
        dialog.querySelector('[value="ok"]').textContent = confirmLabel;

        let result = false;
        dialog.addEventListener('click', (e) => {
            const btn = e.target.closest('button[value]');
            if (btn) {
                result = btn.value === 'ok';
                dialog.close();
            } else if (e.target === dialog) {
                dialog.close();
            }
        });
        dialog.addEventListener('close', () => {
            dialog.remove();
            resolve(result);
        });
        document.body.appendChild(dialog);
        dialog.showModal();
        dialog.querySelector('[value="cancel"]').focus();
    });
}

/**
 * fetch() wrapper returning { ok, status, data }. Always resolves with parsed JSON
 * (or an { error } object), and sends the user to the login page when the session expired.
 */
async function apiFetch(url, options = {}) {
    let res;
    try {
        res = await fetch(url, { credentials: 'same-origin', ...options });
    } catch (err) {
        return { ok: false, status: 0, data: { error: 'Network error: the server is unreachable.' } };
    }

    let data = null;
    const contentType = res.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
        try { data = await res.json(); } catch (_) { data = null; }
    }
    if (!data) data = res.ok ? {} : { error: `HTTP ${res.status}` };

    if (res.status === 401 && IS_LOGGED_IN) {
        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    return { ok: res.ok, status: res.status, data };
}

// Temporarily replace a button's content with a spinner while an async action runs
async function withBusyButton(btn, busyLabel, action) {
    if (!btn) return action();
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>${busyLabel ? ` <span>${escapeHtml(busyLabel)}</span>` : ''}`;
    try {
        return await action();
    } finally {
        btn.disabled = false;
        btn.innerHTML = original;
    }
}

/* ---------- System health ---------- */

function setHealth(id, level, label) {
    const row = document.getElementById(id);
    if (!row) return;
    row.querySelector('.state').innerHTML = `<span class="dot ${level}"></span> ${escapeHtml(label)}`;
    row.dataset.level = level;
}

// Latest /status payload, shared with page scripts through the 'xface:status' event
let lastSystemStatus = null;

async function updateSystemStatus() {
    const { ok, data } = await apiFetch('/api/v1/system/status');
    if (!ok) {
        ['health-camera', 'health-ai', 'health-relay'].forEach(id => setHealth(id, 'bad', 'n/a'));
        document.getElementById('health-overall')?.setAttribute('class', 'dot bad');
        return;
    }
    lastSystemStatus = data;

    setHealth('health-camera', data.camera?.running ? 'live' : 'bad', data.camera?.running ? 'online' : 'offline');
    setHealth('health-ai', data.compreface?.online ? 'live' : 'warn', data.compreface?.online ? 'online' : 'offline');
    if (!data.shelly?.configured) {
        setHealth('health-relay', 'off', 'none');
    } else {
        setHealth('health-relay', data.shelly.online ? 'live' : 'bad', data.shelly.online ? 'online' : 'offline');
    }

    const levels = ['health-camera', 'health-ai', 'health-relay'].map(id => document.getElementById(id)?.dataset.level);
    const overall = levels.includes('bad') ? 'bad' : levels.includes('warn') ? 'warn' : 'live';
    document.getElementById('health-overall')?.setAttribute('class', `dot ${overall}`);

    const unlockBtn = document.getElementById('btn-manual-unlock');
    if (unlockBtn) {
        unlockBtn.disabled = !data.shelly?.configured;
        unlockBtn.title = data.shelly?.configured
            ? 'Manually trigger the door relay'
            : 'No relay configured (set SHELLY_URL)';
    }

    document.dispatchEvent(new CustomEvent('xface:status', { detail: data }));
}

/* ---------- Shell behaviour ---------- */

function timeString(date = new Date()) {
    return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function initClock() {
    const clocks = document.querySelectorAll('[data-clock]');
    if (!clocks.length) return;
    const tick = () => clocks.forEach(el => { el.textContent = timeString(); });
    tick();
    setInterval(tick, 1000);
}

function initNavDrawer() {
    const toggle = document.querySelector('[data-nav-toggle]');
    const setOpen = (open) => {
        document.body.classList.toggle('nav-open', open);
        toggle?.setAttribute('aria-expanded', String(open));
    };
    toggle?.addEventListener('click', () => setOpen(!document.body.classList.contains('nav-open')));
    document.querySelector('[data-nav-close]')?.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
}

function initDialogs() {
    // [data-open="id"] opens a dialog, [data-close] closes its dialog; clicking the backdrop closes it too
    document.addEventListener('click', (e) => {
        const opener = e.target.closest('[data-open]');
        const closer = e.target.closest('[data-close]');
        if (opener) openModal(opener.dataset.open);
        else if (closer) closer.closest('dialog')?.close();
        else if (e.target instanceof HTMLDialogElement && e.target.classList.contains('modal')) e.target.close();
    });
}

// "/" focuses the page search field
function initShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (e.key !== '/' || e.metaKey || e.ctrlKey) return;
        const tag = document.activeElement?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.querySelector('dialog[open]')) return;
        const search = document.querySelector('[data-search]');
        if (search) {
            e.preventDefault();
            search.focus();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initNavDrawer();
    initDialogs();
    initShortcuts();
    updateSystemStatus();
    setInterval(updateSystemStatus, 10000);

    const unlockBtn = document.getElementById('btn-manual-unlock');
    unlockBtn?.addEventListener('click', () => withBusyButton(unlockBtn, 'Opening…', async () => {
        const { ok, data } = await apiFetch('/api/v1/system/shelly/trigger', { method: 'POST' });
        showToast(ok ? 'Door opened.' : (data.error || 'Could not open the door.'), ok ? 'success' : 'danger');
        if (ok) document.dispatchEvent(new CustomEvent('xface:door-opened'));
    }));
});
