/**
 * Live Entrance Monitor controller for Kiosks and Totems with SSE real-time streaming.
 * Draws face boxes from recognition events over the MJPEG feed.
 */

const DOOR_OPEN_MS = 5000;
const MAX_FEED_ITEMS = 12;

let cooldownSeconds = 10;
let threshold = null;
let frameSize = { w: 640, h: 480 };

const STATES = {
    idle: { icon: 'scan-face', title: 'Ready', message: 'Please look at the camera' },
    authorized: { icon: 'check', title: null, message: 'Access granted' },
    denied: { icon: 'x', title: 'Access denied', message: 'Similarity below the access threshold. Please contact the administrator.' },
    unknown: { icon: 'user-unknown', title: 'Not recognised', message: 'This face is not enrolled. Please contact the administrator.' },
    paused: { icon: 'pause', title: 'Recognition paused', message: 'Automatic access is temporarily disabled' },
};

const FEED_META = {
    GRANTED: { icon: 'check', label: 'Access granted' },
    DENIED: { icon: 'x', label: 'Below threshold' },
    UNKNOWN: { icon: 'user-unknown', label: 'Unknown face' },
    MANUAL_OPEN: { icon: 'hand', label: 'Manual open' },
};

document.addEventListener('DOMContentLoaded', () => {
    initStream();
    initSSE();
    initFullscreen();
    initKioskMode();

    document.addEventListener('xface:status', (e) => {
        const cam = e.detail.camera || {};
        const badge = document.getElementById('badge-stream-fps');
        if (badge && cam.resolution) badge.textContent = `${cam.resolution} · ${cam.target_fps} FPS`;
        if (cam.resolution) {
            const [w, h] = cam.resolution.split('x').map(Number);
            if (w && h) {
                frameSize = { w, h };
                document.getElementById('face-overlay')?.setAttribute('viewBox', `0 0 ${w} ${h}`);
            }
        }
        document.getElementById('stream-offline').hidden = Boolean(cam.running);
        const rec = e.detail.recognition || {};
        if (rec.cooldown_seconds) cooldownSeconds = rec.cooldown_seconds;
        if (rec.similarity_threshold !== undefined) setThreshold(rec.similarity_threshold);
    });

    document.addEventListener('xface:door-opened', () => {
        openDoor();
        addFeedItem('Operator', null, 'MANUAL_OPEN');
    });
});

// Reload the MJPEG stream if it breaks (camera unplugged, server restarted...)
function initStream() {
    const img = document.getElementById('live-stream-img');
    const offline = document.getElementById('stream-offline');
    if (!img) return;
    const baseSrc = img.getAttribute('src');
    let retryTimer = null;

    img.addEventListener('error', () => {
        offline.hidden = false;
        clearTimeout(retryTimer);
        retryTimer = setTimeout(() => { img.src = `${baseSrc}?t=${Date.now()}`; }, 3000);
    });
    img.addEventListener('load', () => { offline.hidden = true; });
}

function initSSE() {
    let idleTimeout = null;
    const scheduleIdle = (ms) => {
        clearTimeout(idleTimeout);
        idleTimeout = setTimeout(() => {
            showState('idle');
            drawFaces([]);
        }, ms);
    };

    const eventSource = new EventSource('/api/v1/system/events');

    eventSource.onmessage = (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error('SSE parsing error:', e);
            return;
        }
        const faces = data.faces || [];
        drawFaces(faces);

        if (data.status === 'AUTHORIZED') {
            const face = faces.find(f => f.status === 'AUTHORIZED') || {};
            showState('authorized', face);
            if (face.access_logged) {
                addFeedItem(face.subject, face.similarity, 'GRANTED');
                startCooldown();
                if (face.relay_triggered) openDoor();
            }
            scheduleIdle(5000);
        } else if (data.status === 'DENIED' || data.status === 'UNKNOWN') {
            const face = faces.find(f => f.status === data.status) || {};
            showState(data.status === 'DENIED' ? 'denied' : 'unknown', face);
            if (face.access_logged) addFeedItem(null, face.similarity, data.status);
            scheduleIdle(4000);
        } else if (data.status === 'PAUSED') {
            clearTimeout(idleTimeout);
            showState('paused');
        }
        // NO_FACES / IDLE: keep the current card until the idle timer resets it
    };

    eventSource.onerror = () => {
        console.warn('SSE connection interrupted. The browser will reconnect automatically.');
    };
}

function setThreshold(value) {
    threshold = value;
    const mark = document.getElementById('ring-threshold');
    if (!mark) return;
    mark.style.strokeDashoffset = String(-(value * 100 - 0.7));
    mark.style.opacity = '.75';
}

function showState(state, face = {}) {
    const card = document.getElementById('card-access-status');
    const cfg = STATES[state] || STATES.idle;
    const sim = face.similarity ? face.similarity * 100 : null;
    const showScore = sim !== null && state !== 'idle' && state !== 'paused';

    card.dataset.state = state;
    // Restart the entry animation even when the state repeats
    const core = card.querySelector('.ring-core');
    core.style.animation = 'none';
    void core.offsetWidth;
    core.style.animation = '';

    document.getElementById('status-icon').querySelector('use').setAttribute('href', `#i-${cfg.icon}`);
    document.getElementById('status-subject-name').textContent =
        state === 'authorized' ? `Welcome, ${face.subject || 'guest'}` : cfg.title;
    document.getElementById('status-message').textContent = cfg.message;

    document.getElementById('status-similarity-pill').hidden = !showScore;
    if (showScore) document.getElementById('status-similarity-val').textContent = `${sim.toFixed(1)}%`;
    document.getElementById('ring-value').style.strokeDasharray = `${showScore ? sim : 0} 100`;
}

/* ---------- Face boxes over the video ---------- */

const SVG_NS = 'http://www.w3.org/2000/svg';
// The stage is always dark, so overlay colours stay fixed across themes
const FACE_COLORS = { AUTHORIZED: '#3ddc97', DENIED: '#ff5d6e', UNKNOWN: '#ffb547' };

function drawFaces(faces) {
    const svg = document.getElementById('face-overlay');
    const counter = document.querySelector('#badge-faces span');
    if (!svg) return;
    svg.replaceChildren();
    if (counter) counter.textContent = `${faces.length} ${faces.length === 1 ? 'face' : 'faces'}`;

    faces.forEach(face => {
        const b = face.box || {};
        if (b.x_max === undefined) return;
        const x = b.x_min, y = b.y_min, w = b.x_max - b.x_min, h = b.y_max - b.y_min;
        const c = Math.min(w, h) * 0.22;
        const color = FACE_COLORS[face.status] || '#5ce1ff';

        const g = document.createElementNS(SVG_NS, 'g');
        g.setAttribute('class', 'face-box');
        g.style.color = color;

        const rect = document.createElementNS(SVG_NS, 'rect');
        Object.entries({ x, y, width: w, height: h, rx: 6, class: 'box', stroke: 'currentColor', 'stroke-opacity': 0.45 })
            .forEach(([k, v]) => rect.setAttribute(k, v));

        const corners = document.createElementNS(SVG_NS, 'path');
        corners.setAttribute('class', 'corner');
        corners.setAttribute('stroke', 'currentColor');
        corners.setAttribute('d', [
            `M${x} ${y + c}V${y}H${x + c}`, `M${x + w - c} ${y}H${x + w}V${y + c}`,
            `M${x + w} ${y + h - c}V${y + h}H${x + w - c}`, `M${x + c} ${y + h}H${x}V${y + h - c}`,
        ].join(''));

        const label = face.status === 'AUTHORIZED'
            ? `${face.subject} · ${(face.similarity * 100).toFixed(1)}%`
            : face.status === 'DENIED'
                ? `NO MATCH · ${(face.similarity * 100).toFixed(1)}%`
                : 'UNKNOWN';
        const fontSize = Math.max(12, frameSize.w / 48);
        const tagW = label.length * fontSize * 0.62 + 16;
        const tagY = y - fontSize - 12 < 0 ? y + h + 6 : y - fontSize - 12;

        const tag = document.createElementNS(SVG_NS, 'rect');
        Object.entries({ x, y: tagY, width: tagW, height: fontSize + 10, rx: 5, fill: 'currentColor' })
            .forEach(([k, v]) => tag.setAttribute(k, v));
        const text = document.createElementNS(SVG_NS, 'text');
        Object.entries({ x: x + 8, y: tagY + fontSize + 2, fill: '#03131c', 'font-size': fontSize })
            .forEach(([k, v]) => text.setAttribute(k, v));
        text.textContent = label;

        g.append(rect, corners, tag, text);
        svg.appendChild(g);
    });
}

/* ---------- Door & cooldown ---------- */

let doorTimeout = null;
function openDoor() {
    const panel = document.getElementById('door-panel');
    const badge = document.getElementById('relay-status-badge');
    const text = document.getElementById('relay-status-text');
    const gateUse = document.querySelector('#gate-icon use');
    const setDoor = (open) => {
        panel.classList.toggle('open', open);
        text.textContent = open ? 'Unlocked' : 'Locked';
        gateUse.setAttribute('href', open ? '#i-door-open' : '#i-door-closed');
        badge.className = `tag ${open ? 'ok' : 'neutral'}`;
        badge.innerHTML = open ? `${icon('unlock')} Open` : `${icon('lock')} Secured`;
    };
    setDoor(true);
    clearTimeout(doorTimeout);
    doorTimeout = setTimeout(() => setDoor(false), DOOR_OPEN_MS);
}

let cooldownTimer = null;
function startCooldown() {
    const bar = document.getElementById('cooldown-progress');
    const text = document.getElementById('cooldown-timer-text');
    if (!bar || !text) return;

    const end = Date.now() + cooldownSeconds * 1000;
    clearInterval(cooldownTimer);
    const tick = () => {
        const remaining = Math.max(0, end - Date.now());
        bar.style.width = `${100 - (remaining / (cooldownSeconds * 1000)) * 100}%`;
        bar.style.background = remaining ? 'var(--warn)' : 'var(--ok)';
        text.textContent = remaining ? `${(remaining / 1000).toFixed(1)}s` : 'Ready';
        if (!remaining) clearInterval(cooldownTimer);
    };
    tick();
    cooldownTimer = setInterval(tick, 100);
}

/* ---------- Event feed ---------- */

function addFeedItem(name, similarity, status) {
    const feed = document.getElementById('recent-access-feed');
    if (!feed) return;

    feed.querySelector('[data-placeholder]')?.remove();

    const meta = FEED_META[status] || FEED_META.UNKNOWN;
    const sim = similarity ? `${(similarity * 100).toFixed(1)}%` : '';
    const label = name || (status === 'DENIED' ? 'Not authorised' : 'Unknown face');

    const li = document.createElement('li');
    li.className = `feed-item ${status.toLowerCase()}`;
    li.innerHTML = `
        <span class="f-icon">${icon(meta.icon)}</span>
        <div style="min-width:0"><strong>${escapeHtml(label)}</strong><small>${meta.label}${sim ? ` · ${sim}` : ''}</small></div>
        <time>${escapeHtml(timeString())}</time>`;
    feed.prepend(li);

    while (feed.children.length > MAX_FEED_ITEMS) feed.lastElementChild.remove();
    const count = document.getElementById('feed-count');
    if (count) count.textContent = String(Number(count.textContent) + 1);
}

/* ---------- Fullscreen & kiosk ---------- */

function setKiosk(on) {
    document.body.classList.toggle('kiosk-mode', on);
    const btn = document.getElementById('btn-kiosk');
    if (btn) btn.setAttribute('aria-pressed', String(on));
}

function initKioskMode() {
    document.getElementById('btn-kiosk')?.addEventListener('click', () => {
        setKiosk(true);
        showToast('Kiosk mode on. Press Esc to exit.', 'info');
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !document.fullscreenElement) setKiosk(false);
    });
}

function initFullscreen() {
    const btn = document.getElementById('btn-fullscreen');
    if (!btn) return;

    const render = () => {
        const fs = Boolean(document.fullscreenElement);
        btn.innerHTML = fs
            ? `${icon('compress', 'i-sm')} <span>Exit</span>`
            : `${icon('expand', 'i-sm')} <span>Fullscreen</span>`;
        setKiosk(fs);
    };

    btn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen?.().catch(err => {
                showToast(`Fullscreen not available: ${err.message}`, 'warning');
            });
        } else {
            document.exitFullscreen?.();
        }
    });
    // Also covers leaving fullscreen with the Esc key
    document.addEventListener('fullscreenchange', render);
}
