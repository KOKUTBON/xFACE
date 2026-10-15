/**
 * Access Logs & Historical Audit Trail Controller.
 */

let currentPage = 1;
const perPage = 25;
let currentLogs = [];

const STATUS_TAGS = {
    GRANTED: ['granted', 'check', 'Granted'],
    DENIED: ['denied', 'x', 'Denied'],
    UNKNOWN: ['unknown', 'user-unknown', 'Unknown'],
    MANUAL_OPEN: ['manual_open', 'hand', 'Manual'],
};
const SCORE_COLORS = { GRANTED: 'var(--ok)', DENIED: 'var(--bad)', UNKNOWN: 'var(--warn)' };

document.addEventListener('DOMContentLoaded', () => {
    refreshAll();

    document.getElementById('btn-refresh-logs')?.addEventListener('click', () => refreshAll(currentPage));

    document.getElementById('filter-logs-form')?.addEventListener('submit', (e) => {
        e.preventDefault();
        loadLogs(1);
    });

    document.getElementById('filter-status')?.addEventListener('change', () => loadLogs(1));

    document.getElementById('btn-reset-filters')?.addEventListener('click', () => {
        document.getElementById('filter-logs-form').reset();
        loadLogs(1);
    });

    document.getElementById('pagination-nav')?.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-page]');
        if (btn && !btn.disabled) loadLogs(Number(btn.dataset.page));
    });

    document.getElementById('logs-table-body')?.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-log-index]');
        if (btn) openSnapshotModal(currentLogs[Number(btn.dataset.logIndex)]);
    });

    document.getElementById('modalSnapshotPreview')?.addEventListener('close', () => {
        document.getElementById('snapshot-preview-img').removeAttribute('src');
    });
});

function refreshAll(page = 1) {
    loadLogsStats();
    loadLogs(page);
}

function formatDate(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString(undefined, {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

function formatParts(isoString) {
    if (!isoString) return { time: '—', date: '' };
    const d = new Date(isoString);
    return {
        time: d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        date: d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' }),
    };
}

// Convert the <input type="date"> values (local days) to UTC instants for the API
function buildFilterParams() {
    const params = new URLSearchParams();
    const subject = document.getElementById('filter-subject')?.value.trim();
    const status = document.getElementById('filter-status')?.value;
    const startDate = document.getElementById('filter-start-date')?.value;
    const endDate = document.getElementById('filter-end-date')?.value;

    if (subject) params.set('subject', subject);
    if (status) params.set('status', status);
    if (startDate) params.set('start_date', new Date(`${startDate}T00:00:00`).toISOString());
    if (endDate) params.set('end_date', new Date(`${endDate}T23:59:59.999`).toISOString());
    return params;
}

async function loadLogsStats() {
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const { ok, data } = await apiFetch(`/api/v1/logs/stats?today_start=${encodeURIComponent(todayStart.toISOString())}`);
    if (!ok) return;

    const total = data.today_accesses;
    const granted = data.granted_today;
    const rejected = data.unknown_today;
    const other = Math.max(0, total - granted - rejected);
    const pct = (n) => (total ? (n / total) * 100 : 0);

    document.getElementById('stat-today-total').textContent = total;
    document.getElementById('stat-today-granted').textContent = granted;
    document.getElementById('stat-today-unknown').textContent = rejected;
    document.getElementById('stat-all-time-total').textContent = data.total_accesses;
    document.getElementById('stat-granted-rate').textContent = total ? `${pct(granted).toFixed(0)}% of today's events` : 'No events yet today';
    document.getElementById('stat-subjects-total').textContent = `${data.total_subjects} known subjects`;

    document.getElementById('donut-ok').setAttribute('stroke-dasharray', `${pct(granted)} 100`);
    const bad = document.getElementById('donut-bad');
    bad.setAttribute('stroke-dasharray', `${pct(rejected)} 100`);
    bad.setAttribute('stroke-dashoffset', String(-pct(granted)));
    document.getElementById('donut-rate').textContent = total ? `${pct(granted).toFixed(0)}%` : '—';
    document.getElementById('legend-ok').textContent = granted;
    document.getElementById('legend-bad').textContent = rejected;
    document.getElementById('legend-other').textContent = other;

    const top = data.top_subjects || [];
    const max = Math.max(1, ...top.map(t => t.count));
    document.getElementById('top-subjects').innerHTML = top.length
        ? top.map((t, i) => `
            <li>
                <span class="pos">${String(i + 1).padStart(2, '0')}</span>
                <span class="who"><span class="avatar">${escapeHtml(initials(t.subject))}</span><span>${escapeHtml(t.subject)}</span></span>
                <span class="n">${t.count}</span>
                <span class="bar"><span style="width:${(t.count / max) * 100}%"></span></span>
            </li>`).join('')
        : '<li class="muted">No granted accesses yet.</li>';
}

async function loadLogs(page = 1) {
    currentPage = page;
    const tbody = document.getElementById('logs-table-body');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" class="state-cell"><span class="spinner" style="display:inline-block;vertical-align:middle"></span>&nbsp; Loading events…</td></tr>`;

    const filters = buildFilterParams();
    // Keep the CSV export in sync with what is on screen
    const exportBtn = document.getElementById('btn-export-csv');
    if (exportBtn) exportBtn.href = `/api/v1/logs/export${filters.toString() ? `?${filters}` : ''}`;

    const params = new URLSearchParams(filters);
    params.set('page', page);
    params.set('per_page', perPage);

    const { ok, data } = await apiFetch(`/api/v1/logs?${params.toString()}`);
    if (!ok) {
        tbody.innerHTML = `
            <tr><td colspan="7" class="state-cell" style="color:var(--bad)">
                ${icon('alert')} Could not load logs: ${escapeHtml(data.error)}
            </td></tr>`;
        return;
    }

    renderLogsTable(data.logs);
    renderPagination(data.page, data.total_pages, data.total);
}

function statusTag(status) {
    const [cls, ic, label] = STATUS_TAGS[status] || ['neutral', 'info', status];
    return `<span class="tag ${cls}">${icon(ic)}${escapeHtml(label)}</span>`;
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logs-table-body');
    currentLogs = logs || [];

    if (currentLogs.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="7" class="state-cell">
                <div class="empty" style="padding:8px">
                    <div class="empty-icon">${icon('audit')}</div>
                    <h3>No events found</h3>
                    <p>Nothing matches the current filters.</p>
                </div>
            </td></tr>`;
        return;
    }

    tbody.innerHTML = currentLogs.map((item, index) => {
        const when = formatParts(item.timestamp);
        const hasSim = item.similarity !== null && item.similarity !== undefined;
        const simPct = hasSim ? item.similarity * 100 : 0;
        const similarity = hasSim
            ? `<div class="score"><span>${simPct.toFixed(1)}%</span><span class="meter"><span style="width:${simPct}%;background:${SCORE_COLORS[item.status] || 'var(--accent)'}"></span></span></div>`
            : '<span class="muted">—</span>';
        const subject = item.subject_name
            ? `<div class="who"><span class="avatar">${escapeHtml(initials(item.subject_name))}</span><div class="cell-stack"><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.device_name || '')}</small></div></div>`
            : `<div class="who"><span class="avatar unknown">${icon('user-unknown', 'i-sm')}</span><div class="cell-stack"><span class="muted">Unidentified</span><small>${escapeHtml(item.device_name || '')}</small></div></div>`;
        const relay = item.relay_triggered
            ? `<span class="relay-yes">${icon('door-open', 'i-sm')} Opened</span>`
            : `<span class="relay-no">${icon('lock', 'i-sm')} Locked</span>`;
        const snapshotBtn = item.snapshot_filename
            ? `<button class="btn btn-sm" type="button" data-log-index="${index}">${icon('image', 'i-sm')} View</button>`
            : '<span class="muted">—</span>';
        const notes = escapeHtml(item.notes || '');

        return `
            <tr>
                <td><div class="cell-stack"><span class="mono">${escapeHtml(when.time)}</span><small class="mono">#${item.id} · ${escapeHtml(when.date)}</small></div></td>
                <td>${subject}</td>
                <td>${statusTag(item.status)}</td>
                <td>${similarity}</td>
                <td>${relay}</td>
                <td>${snapshotBtn}</td>
                <td class="notes-cell" title="${notes}">${notes || '—'}</td>
            </tr>`;
    }).join('');
}

function renderPagination(current, totalPages, totalCount) {
    const info = document.getElementById('pagination-info');
    const nav = document.getElementById('pagination-nav');

    if (info) {
        const from = (current - 1) * perPage + 1;
        const to = Math.min(current * perPage, totalCount);
        info.textContent = totalCount ? `Showing ${from}–${to} of ${totalCount} ${totalCount === 1 ? 'event' : 'events'}` : '';
    }

    if (!nav) return;
    if (totalPages <= 1) {
        nav.innerHTML = '';
        return;
    }

    const pageBtn = (page, label, { disabled = false, active = false, aria = '' } = {}) =>
        `<button type="button" data-page="${page}" ${disabled ? 'disabled' : ''} ${active ? 'aria-current="page"' : ''} ${aria ? `aria-label="${aria}"` : ''}>${label}</button>`;

    let html = pageBtn(current - 1, icon('chevron-left', 'i-sm'), { disabled: current <= 1, aria: 'Previous page' });
    for (let p = Math.max(1, current - 2); p <= Math.min(totalPages, current + 2); p++) {
        html += pageBtn(p, p, { active: p === current });
    }
    html += pageBtn(current + 1, icon('chevron-right', 'i-sm'), { disabled: current >= totalPages, aria: 'Next page' });
    nav.innerHTML = html;
}

function openSnapshotModal(item) {
    if (!item) return;
    document.getElementById('snapshot-preview-img').src = `/video/snapshots/${encodeURIComponent(item.snapshot_filename)}`;
    document.getElementById('snapshot-preview-sub').textContent = formatDate(item.timestamp);
    const sim = item.similarity !== null && item.similarity !== undefined ? `${(item.similarity * 100).toFixed(1)}%` : '—';
    document.getElementById('snapshot-preview-details').innerHTML = `
        <div><small>Subject</small><strong>${escapeHtml(item.subject_name || 'Unidentified')}</strong></div>
        <div><small>Decision</small><strong>${statusTag(item.status)}</strong></div>
        <div><small>Similarity</small><strong class="mono">${sim}</strong></div>
        <div><small>Device</small><strong>${escapeHtml(item.device_name || '—')}</strong></div>`;
    openModal('modalSnapshotPreview');
}
