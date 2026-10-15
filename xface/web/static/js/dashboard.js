/**
 * Dashboard Controller for Subject and Face Enrollment management.
 */

let allSubjectsData = {};

document.addEventListener('DOMContentLoaded', () => {
    loadSubjects();

    document.getElementById('btn-refresh-subjects')?.addEventListener('click', loadSubjects);

    document.getElementById('subject-search-input')?.addEventListener('input', (e) => {
        renderSubjects(e.target.value.trim().toLowerCase());
    });

    document.querySelectorAll('[data-photo-form]').forEach(initPhotoPicker);

    document.getElementById('form-add-subject')?.addEventListener('submit', handleAddSubject);
    document.getElementById('form-add-photo')?.addEventListener('submit', handleAddExtraPhoto);
    document.getElementById('form-rename-subject')?.addEventListener('submit', handleRenameSubject);

    document.getElementById('subjects-grid')?.addEventListener('click', onSubjectAction);
    // Samples that cannot be fetched (engine offline, deleted upstream) fall back to a placeholder
    ['subjects-grid', 'gallery-images-container'].forEach(id => {
        document.getElementById(id)?.addEventListener('error', (e) => {
            if (e.target.tagName !== 'IMG') return;
            const placeholder = document.createElement('div');
            placeholder.className = 'portrait-placeholder';
            placeholder.innerHTML = icon('face-id');
            e.target.replaceWith(placeholder);
        }, true);
    });
    document.getElementById('gallery-images-container')?.addEventListener('click', onGalleryAction);
    document.getElementById('btn-gallery-add')?.addEventListener('click', () => {
        const name = document.getElementById('gallery-images-container').dataset.subject;
        closeModal('modalSubjectGallery');
        openAddPhotoModal(name);
    });

    initSystemControls();
});

/* ---------- Photo picker (file upload or webcam capture) ---------- */

function initPhotoPicker(form) {
    const dialog = form.closest('dialog');
    const fileInput = form.querySelector('[data-photo-file]');
    const filePreview = form.querySelector('[data-photo-file-preview]');
    const dropzone = form.querySelector('[data-dropzone]');
    const prompt = form.querySelector('[data-dropzone-prompt]');
    const liveImg = form.querySelector('[data-webcam-live]');
    const captureBtn = form.querySelector('[data-webcam-capture]');

    const setSource = (source) => {
        form.dataset.photoSource = source;
        form.querySelectorAll('[data-photo-pane]').forEach(pane => {
            pane.hidden = pane.dataset.photoPane !== source;
        });
        // Only stream video while the webcam pane is visible
        if (liveImg) {
            if (source === 'webcam' && dialog?.open) liveImg.src = `/video/stream?t=${Date.now()}`;
            else liveImg.removeAttribute('src');
        }
    };

    form.querySelectorAll('[data-photo-source]').forEach(radio => {
        radio.addEventListener('change', () => radio.checked && setSource(radio.value));
    });

    const showFilePreview = (file) => {
        if (filePreview.src) URL.revokeObjectURL(filePreview.src);
        if (file) {
            filePreview.src = URL.createObjectURL(file);
            filePreview.hidden = false;
            prompt.hidden = true;
            dropzone.classList.add('has-image');
        } else {
            filePreview.removeAttribute('src');
            filePreview.hidden = true;
            prompt.hidden = false;
            dropzone.classList.remove('has-image');
        }
    };

    fileInput?.addEventListener('change', () => showFilePreview(fileInput.files[0]));
    ['dragenter', 'dragover'].forEach(type => dropzone?.addEventListener(type, () => dropzone.classList.add('dragging')));
    ['dragleave', 'drop'].forEach(type => dropzone?.addEventListener(type, () => dropzone.classList.remove('dragging')));

    captureBtn?.addEventListener('click', () => withBusyButton(captureBtn, 'Capturing…', async () => {
        const { ok, data } = await apiFetch('/video/frame_base64');
        if (ok && data.frame) {
            form.dataset.capturedB64 = data.frame;
            form.querySelector('[data-webcam-captured]').src = `data:image/jpeg;base64,${data.frame}`;
            form.querySelector('[data-webcam-result]').hidden = false;
        } else {
            showToast(data.error || 'No frame available from the camera.', 'warning');
        }
    }));

    form.resetPhotoPicker = () => {
        form.reset();
        delete form.dataset.capturedB64;
        const result = form.querySelector('[data-webcam-result]');
        if (result) result.hidden = true;
        showFilePreview(null);
        setSource('file');
    };
    dialog?.addEventListener('close', () => form.resetPhotoPicker());
    setSource('file');
}

// Append the selected photo to formData. Returns false (and warns) if none was chosen.
function appendSelectedPhoto(form, formData) {
    if (form.dataset.photoSource === 'webcam') {
        if (!form.dataset.capturedB64) {
            showToast('Capture a frame from the camera first.', 'warning');
            return false;
        }
        formData.append('photo_data', form.dataset.capturedB64);
        return true;
    }
    const file = form.querySelector('[data-photo-file]')?.files[0];
    if (!file) {
        showToast('Choose an image file first.', 'warning');
        return false;
    }
    formData.append('image', file);
    return true;
}

/* ---------- Subjects grid ---------- */

function imageUrl(imageId) {
    return `/api/v1/proxy/images/${encodeURIComponent(imageId)}`;
}

async function loadSubjects() {
    const grid = document.getElementById('subjects-grid');
    if (!grid) return;

    const { ok, data } = await apiFetch('/api/v1/subjects');
    if (!ok) {
        allSubjectsData = {};
        document.getElementById('stat-total-subjects').textContent = '—';
        document.getElementById('stat-total-photos').textContent = '—';
        grid.innerHTML = `
            <div class="empty error">
                <div class="empty-icon">${icon('alert')}</div>
                <h3>Could not load subjects</h3>
                <p>${escapeHtml(data.error)}</p>
                <p class="hint">Check that CompreFace is running and that <code>API_KEY</code> is set in <code>.env</code>.</p>
            </div>`;
        return;
    }

    allSubjectsData = data;
    const names = Object.keys(allSubjectsData);
    const totalPhotos = names.reduce((sum, name) => sum + (allSubjectsData[name] || []).length, 0);
    document.getElementById('stat-total-subjects').textContent = names.length;
    document.getElementById('stat-total-photos').textContent = totalPhotos;
    document.getElementById('stat-samples-note').textContent = names.length
        ? `Avg. ${(totalPhotos / names.length).toFixed(1)} per subject`
        : 'No samples yet';

    renderSubjects(document.getElementById('subject-search-input')?.value.trim().toLowerCase() || '');
}

function renderSubjects(query = '') {
    const grid = document.getElementById('subjects-grid');
    if (!grid) return;

    const names = Object.keys(allSubjectsData).sort((a, b) => a.localeCompare(b));
    const filtered = query ? names.filter(n => n.toLowerCase().includes(query)) : names;
    const count = document.getElementById('subject-count');
    if (count) count.textContent = query ? `${filtered.length} of ${names.length}` : `${names.length} total`;

    if (filtered.length === 0) {
        grid.innerHTML = names.length
            ? `<div class="empty">
                   <div class="empty-icon">${icon('search')}</div>
                   <h3>No matching subjects</h3>
                   <p>Nobody matches “${escapeHtml(query)}”.</p>
               </div>`
            : `<div class="empty">
                   <div class="empty-icon">${icon('scan-face')}</div>
                   <h3>No one enrolled yet</h3>
                   <p>Enroll the first person to start recognising faces at the door.</p>
                   <button class="btn btn-primary" type="button" data-open="modalAddSubject">${icon('user-plus')} New subject</button>
               </div>`;
        return;
    }

    grid.innerHTML = filtered.map((name, idx) => {
        const images = allSubjectsData[name] || [];
        const photoCount = images.length;
        const safeName = escapeHtml(name);
        const portrait = images[0]
            ? `<img src="${imageUrl(images[0])}" alt="${safeName}" loading="lazy">`
            : `<div class="portrait-placeholder">${icon('face-id')}</div>`;

        return `
            <article class="subject-card" data-subject="${safeName}">
                <div class="portrait reticle">
                    <span class="r-t"></span><span class="r-b"></span>
                    ${portrait}
                    <span class="scanline"></span>
                    <span class="portrait-badge">${icon('fingerprint')} ID-${String(idx + 1).padStart(3, '0')}</span>
                </div>
                <div class="subject-body">
                    <div class="subject-title">
                        <h3 title="${safeName}">${safeName}</h3>
                        <span class="dot ${photoCount ? 'live' : 'warn'}" title="${photoCount ? 'Enrolled' : 'No samples'}"></span>
                    </div>
                    <div class="subject-meta">
                        <span>${icon('face-id', 'i-sm')} ${photoCount} ${photoCount === 1 ? 'sample' : 'samples'}</span>
                        <span>${icon('shield', 'i-sm')} ${photoCount ? 'Active' : 'Incomplete'}</span>
                    </div>
                    <div class="subject-actions">
                        <button class="btn btn-sm" data-action="gallery" type="button">${icon('gallery', 'i-sm')} Samples</button>
                        <button class="btn btn-sm btn-icon" data-action="add-photo" type="button" title="Add sample" aria-label="Add sample for ${safeName}">${icon('plus', 'i-sm')}</button>
                        <button class="btn btn-sm btn-icon" data-action="rename" type="button" title="Rename" aria-label="Rename ${safeName}">${icon('pen', 'i-sm')}</button>
                        <button class="btn btn-sm btn-icon btn-danger" data-action="delete" type="button" title="Delete subject" aria-label="Delete ${safeName}">${icon('trash', 'i-sm')}</button>
                    </div>
                </div>
            </article>`;
    }).join('');
}

function onSubjectAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const name = btn.closest('[data-subject]')?.dataset.subject;
    if (name === undefined) return;

    switch (btn.dataset.action) {
        case 'add-photo': openAddPhotoModal(name); break;
        case 'gallery': openGalleryModal(name); break;
        case 'rename': openRenameModal(name); break;
        case 'delete': deleteSubject(name, btn); break;
    }
}

/* ---------- Create / add photo / rename / delete ---------- */

async function handleAddSubject(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const name = document.getElementById('new-subject-name').value.trim();
    if (!name) {
        showToast('Enter the subject name.', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('subject', name);
    if (!appendSelectedPhoto(form, formData)) return;

    await withBusyButton(document.getElementById('btn-save-subject'), 'Enrolling…', async () => {
        const { ok, data } = await apiFetch('/api/v1/subjects', { method: 'POST', body: formData });
        if (ok) {
            showToast(`Subject "${name}" enrolled.`, 'success');
            closeModal('modalAddSubject');
            loadSubjects();
        } else {
            showToast(data.error || 'Could not create the subject.', 'danger');
        }
    });
}

function openAddPhotoModal(name) {
    document.getElementById('add-photo-subject-name').value = name;
    document.getElementById('add-photo-subject-title').textContent = `For ${name}`;
    openModal('modalAddPhoto');
}

async function handleAddExtraPhoto(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const name = document.getElementById('add-photo-subject-name').value;

    const formData = new FormData();
    if (!appendSelectedPhoto(form, formData)) return;

    await withBusyButton(document.getElementById('btn-submit-photo'), 'Uploading…', async () => {
        const { ok, data } = await apiFetch(`/api/v1/subjects/${encodeURIComponent(name)}/images`, {
            method: 'POST',
            body: formData
        });
        if (ok) {
            showToast(`New sample added for ${name}.`, 'success');
            closeModal('modalAddPhoto');
            loadSubjects();
        } else {
            showToast(data.error || 'Could not add the photo.', 'danger');
        }
    });
}

function openRenameModal(name) {
    document.getElementById('rename-old-name').value = name;
    const input = document.getElementById('rename-new-name');
    input.value = name;
    openModal('modalRenameSubject');
    input.select();
}

async function handleRenameSubject(e) {
    e.preventDefault();
    const oldName = document.getElementById('rename-old-name').value;
    const newName = document.getElementById('rename-new-name').value.trim();
    if (!newName) return;

    await withBusyButton(document.getElementById('btn-rename-subject'), 'Saving…', async () => {
        const { ok, data } = await apiFetch(`/api/v1/subjects/${encodeURIComponent(oldName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: newName })
        });
        if (ok) {
            showToast(data.message || 'Subject renamed.', 'success');
            closeModal('modalRenameSubject');
            loadSubjects();
        } else {
            showToast(data.error || 'Could not rename the subject.', 'danger');
        }
    });
}

async function deleteSubject(name, btn) {
    const confirmed = await confirmAction({
        title: `Delete ${name}?`,
        message: 'This permanently removes the subject and all of their face samples from the recognition engine.',
        confirmLabel: 'Delete subject',
    });
    if (!confirmed) return;

    await withBusyButton(btn, '', async () => {
        const { ok, data } = await apiFetch(`/api/v1/subjects/${encodeURIComponent(name)}`, { method: 'DELETE' });
        if (ok) {
            showToast(`Subject "${name}" deleted.`, 'success');
            loadSubjects();
        } else {
            showToast(data.error || 'Could not delete the subject.', 'danger');
        }
    });
}

/* ---------- Gallery ---------- */

function openGalleryModal(name) {
    document.getElementById('gallery-subject-name').textContent = name;
    renderGallery(name);
    openModal('modalSubjectGallery');
}

function renderGallery(name) {
    const container = document.getElementById('gallery-images-container');
    const images = allSubjectsData[name] || [];
    container.dataset.subject = name;
    document.getElementById('gallery-subject-meta').textContent =
        `${images.length} face ${images.length === 1 ? 'sample' : 'samples'} enrolled`;

    if (images.length === 0) {
        container.innerHTML = `
            <div class="empty">
                <div class="empty-icon">${icon('image')}</div>
                <h3>No samples yet</h3>
                <p>Add at least one photo so this person can be recognised.</p>
            </div>`;
        return;
    }

    container.innerHTML = images.map((imgId, i) => {
        const safeId = escapeHtml(imgId);
        return `
            <figure>
                <img src="${imageUrl(imgId)}" alt="Face sample ${i + 1}" loading="lazy">
                <figcaption><span>SAMPLE ${String(i + 1).padStart(2, '0')}</span>${icon('check', 'i-sm')}</figcaption>
                <button class="btn btn-danger btn-icon btn-sm" type="button" data-image-id="${safeId}" title="Delete this sample" aria-label="Delete sample ${i + 1}">
                    ${icon('trash', 'i-sm')}
                </button>
            </figure>`;
    }).join('');
}

async function onGalleryAction(e) {
    const btn = e.target.closest('[data-image-id]');
    if (!btn) return;
    const imageId = btn.dataset.imageId;
    const name = e.currentTarget.dataset.subject;

    const confirmed = await confirmAction({
        title: 'Delete this face sample?',
        message: `The sample is removed from ${name}'s biometric profile. This cannot be undone.`,
        confirmLabel: 'Delete sample',
    });
    if (!confirmed) return;

    await withBusyButton(btn, '', async () => {
        const { ok, data } = await apiFetch(`/api/v1/images/${encodeURIComponent(imageId)}`, { method: 'DELETE' });
        if (ok) {
            showToast('Face sample deleted.', 'success');
            allSubjectsData[name] = (allSubjectsData[name] || []).filter(id => id !== imageId);
            renderGallery(name);
            loadSubjects();
        } else {
            showToast(data.error || 'Could not delete the photo.', 'danger');
        }
    });
}

/* ---------- Recognition engine & camera controls ---------- */

function initSystemControls() {
    const toggle = document.getElementById('toggle-recognition');
    const badge = document.getElementById('stat-recognition-badge');
    const details = document.getElementById('stat-recognition-details');

    const render = (active) => {
        badge.className = `tag ${active ? 'ok' : 'neutral'}`;
        badge.innerHTML = `${icon(active ? 'activity' : 'pause')} ${active ? 'Active' : 'Paused'}`;
        toggle.checked = active;
    };

    document.addEventListener('xface:status', (e) => {
        const rec = e.detail.recognition || {};
        toggle.disabled = false;
        render(Boolean(rec.active));
        if (rec.interval !== undefined) details.textContent = `every ${rec.interval}s`;
        if (rec.similarity_threshold !== undefined) {
            const pct = rec.similarity_threshold * 100;
            document.getElementById('stat-threshold').textContent = `${pct.toFixed(0)}%`;
            const bar = document.getElementById('stat-threshold-bar');
            bar.style.width = `${pct}%`;
            bar.style.background = 'var(--warn)';
        }
    });

    toggle?.addEventListener('change', async () => {
        toggle.disabled = true;
        const { ok, data } = await apiFetch('/api/v1/system/recognition/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: toggle.checked })
        });
        toggle.disabled = false;
        if (ok) {
            render(data.recognition_active);
            showToast(data.recognition_active ? 'Recognition resumed.' : 'Recognition paused.', 'info');
        } else {
            render(!toggle.checked);
            showToast(data.error || 'Could not change the recognition state.', 'danger');
        }
    });

    const restartBtn = document.getElementById('btn-restart-camera');
    restartBtn?.addEventListener('click', () => withBusyButton(restartBtn, 'Restarting…', async () => {
        const { ok, data } = await apiFetch('/api/v1/system/camera/restart', { method: 'POST' });
        showToast(ok ? data.message : (data.error || 'Camera restart failed.'), ok ? 'success' : 'warning');
        updateSystemStatus();
    }));
}
