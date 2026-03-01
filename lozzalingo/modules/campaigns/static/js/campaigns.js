/**
 * Campaigns Block Editor
 * =====================
 * Manages the block editor UI, live preview, and all CRUD actions.
 */

(function () {
    'use strict';

    const BLOCK_TYPES = [
        { value: 'heading', label: 'Heading' },
        { value: 'paragraph', label: 'Paragraph' },
        { value: 'image', label: 'Image' },
        { value: 'code_box', label: 'Code Box' },
        { value: 'button', label: 'Button' },
        { value: 'note', label: 'Note' },
        { value: 'divider', label: 'Divider' },
    ];

    let blocks = [];
    let previewTimer = null;
    const PREVIEW_DEBOUNCE = 500;

    // ── Init ──────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        console.log('[campaigns] Editor initializing');

        if (window.CAMPAIGN_DATA && window.CAMPAIGN_DATA.blocks) {
            blocks = JSON.parse(JSON.stringify(window.CAMPAIGN_DATA.blocks));
        }

        renderBlocks();
        loadVariables();
        bindActions();
        schedulePreview();

        console.log('[campaigns] Editor ready, ' + blocks.length + ' blocks loaded');
    });

    // ── Block Rendering ───────────────────────────────────────────────
    function renderBlocks() {
        var container = document.getElementById('blocks-container');
        if (!container) return;
        container.innerHTML = '';

        blocks.forEach(function (block, index) {
            var card = document.createElement('div');
            card.className = 'block-card';
            card.setAttribute('data-index', index);

            card.innerHTML = buildBlockHeader(block, index) + buildBlockFields(block, index);
            container.appendChild(card);
        });

        // Bind field change listeners
        container.querySelectorAll('input, textarea, select').forEach(function (el) {
            el.addEventListener('input', function () {
                syncBlockFromDOM();
                schedulePreview();
            });
            el.addEventListener('change', function () {
                syncBlockFromDOM();
                schedulePreview();
            });
        });
    }

    function buildBlockHeader(block, index) {
        var options = BLOCK_TYPES.map(function (t) {
            var selected = t.value === block.type ? ' selected' : '';
            return '<option value="' + t.value + '"' + selected + '>' + t.label + '</option>';
        }).join('');

        return '<div class="block-header">' +
            '<select name="block_type_' + index + '" data-field="type" data-index="' + index + '">' + options + '</select>' +
            '<div class="block-controls">' +
                '<button type="button" name="block_move_up_' + index + '" title="Move up" onclick="window._campaignMoveBlock(' + index + ',-1)">&uarr;</button>' +
                '<button type="button" name="block_move_down_' + index + '" title="Move down" onclick="window._campaignMoveBlock(' + index + ',1)">&darr;</button>' +
                '<button type="button" name="block_delete_' + index + '" class="btn-delete" title="Delete" onclick="window._campaignDeleteBlock(' + index + ')">&times;</button>' +
            '</div>' +
        '</div>';
    }

    function buildBlockFields(block, index) {
        var type = block.type || 'paragraph';
        var html = '<div class="block-fields">';

        if (type === 'heading') {
            html += fieldInput(index, 'text', 'Heading text', block.text);
            html += fieldInput(index, 'subtitle', 'Subtitle (optional)', block.subtitle);
        } else if (type === 'paragraph') {
            html += fieldTextarea(index, 'content', 'Content (use **bold**)', block.content);
        } else if (type === 'image') {
            html += fieldInput(index, 'url', 'Image URL', block.url);
            html += '<div class="field-inline">';
            html += fieldInput(index, 'alt', 'Alt text', block.alt);
            html += fieldInput(index, 'border_color', 'Border color', block.border_color);
            html += '</div>';
        } else if (type === 'code_box') {
            html += '<div class="field-inline">';
            html += fieldInput(index, 'label', 'Label', block.label);
            html += fieldInput(index, 'code', 'Code value', block.code);
            html += '</div>';
        } else if (type === 'button') {
            html += '<div class="field-inline">';
            html += fieldInput(index, 'text', 'Button text', block.text);
            html += fieldInput(index, 'url', 'URL', block.url);
            html += '</div>';
            html += '<div class="field-inline">';
            html += fieldInput(index, 'bg_color', 'Bg color', block.bg_color);
            html += fieldInput(index, 'text_color', 'Text color', block.text_color);
            html += '</div>';
        } else if (type === 'note') {
            html += '<div class="field-inline">';
            html += fieldInput(index, 'text', 'Note text', block.text);
            html += fieldInput(index, 'color', 'Color', block.color);
            html += '</div>';
        }
        // divider has no fields

        html += '</div>';
        return html;
    }

    function fieldInput(index, field, placeholder, value) {
        return '<input type="text" name="block_' + field + '_' + index + '" data-field="' + field + '" data-index="' + index +
               '" placeholder="' + placeholder + '" value="' + escapeAttr(value || '') + '">';
    }

    function fieldTextarea(index, field, placeholder, value) {
        return '<textarea name="block_' + field + '_' + index + '" data-field="' + field + '" data-index="' + index +
               '" placeholder="' + placeholder + '">' + escapeHtml(value || '') + '</textarea>';
    }

    function escapeAttr(s) {
        return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ── Sync DOM → blocks array ───────────────────────────────────────
    function syncBlockFromDOM() {
        var container = document.getElementById('blocks-container');
        if (!container) return;

        container.querySelectorAll('.block-card').forEach(function (card) {
            var idx = parseInt(card.getAttribute('data-index'), 10);
            if (idx >= blocks.length) return;

            // Sync type (may have changed)
            var typeSelect = card.querySelector('select[data-field="type"]');
            if (typeSelect && typeSelect.value !== blocks[idx].type) {
                blocks[idx] = { type: typeSelect.value };
                renderBlocks();
                return;
            }

            card.querySelectorAll('[data-field]').forEach(function (el) {
                var field = el.getAttribute('data-field');
                if (field === 'type') return;
                blocks[idx][field] = el.value;
            });
        });
    }

    // ── Block operations (exposed globally for onclick) ───────────────
    window._campaignMoveBlock = function (index, direction) {
        var newIndex = index + direction;
        if (newIndex < 0 || newIndex >= blocks.length) return;
        var temp = blocks[index];
        blocks[index] = blocks[newIndex];
        blocks[newIndex] = temp;
        renderBlocks();
        schedulePreview();
        console.log('[campaigns] Block moved: ' + index + ' -> ' + newIndex);
    };

    window._campaignDeleteBlock = function (index) {
        blocks.splice(index, 1);
        renderBlocks();
        schedulePreview();
        console.log('[campaigns] Block deleted at index ' + index);
    };

    // ── Preview ───────────────────────────────────────────────────────
    function schedulePreview() {
        if (previewTimer) clearTimeout(previewTimer);
        previewTimer = setTimeout(updatePreview, PREVIEW_DEBOUNCE);
    }

    function updatePreview() {
        if (!window.ENDPOINTS || !window.ENDPOINTS.preview) return;

        fetch(window.ENDPOINTS.preview, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ blocks: blocks })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var iframe = document.getElementById('preview-iframe');
            if (iframe && data.html) {
                iframe.srcdoc = data.html;
            }
        })
        .catch(function (err) {
            console.error('[campaigns] Preview error:', err);
        });
    }

    // ── Variables ─────────────────────────────────────────────────────
    function loadVariables() {
        if (!window.ENDPOINTS || !window.ENDPOINTS.variables) return;

        fetch(window.ENDPOINTS.variables)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var container = document.getElementById('variables-container');
                if (!container || !data.variables) return;

                container.innerHTML = '';
                data.variables.forEach(function (v) {
                    var tag = document.createElement('span');
                    tag.className = 'variable-tag';
                    tag.textContent = '{{' + v.key + '}}';
                    tag.title = v.description || '';
                    tag.setAttribute('name', 'variable_tag_' + v.key.toLowerCase());
                    tag.onclick = function () {
                        navigator.clipboard.writeText('{{' + v.key + '}}').then(function () {
                            showToast('Copied {{' + v.key + '}}', 'success');
                        });
                    };
                    container.appendChild(tag);
                });

                console.log('[campaigns] Loaded ' + data.variables.length + ' variables');
            })
            .catch(function (err) {
                console.error('[campaigns] Failed to load variables:', err);
            });
    }

    // ── Action bindings ───────────────────────────────────────────────
    function bindActions() {
        var addBtn = document.getElementById('add-block-btn');
        if (addBtn) {
            addBtn.onclick = function () {
                blocks.push({ type: 'paragraph', content: '' });
                renderBlocks();
                schedulePreview();
                console.log('[campaigns] Block added, total: ' + blocks.length);
            };
        }

        var saveBtn = document.getElementById('save-btn');
        if (saveBtn) saveBtn.onclick = saveCampaign;

        var sendTestBtn = document.getElementById('send-test-btn');
        if (sendTestBtn) sendTestBtn.onclick = sendTest;

        var sendAllBtn = document.getElementById('send-all-btn');
        if (sendAllBtn) sendAllBtn.onclick = showSendConfirm;

        var deleteBtn = document.getElementById('delete-btn');
        if (deleteBtn) deleteBtn.onclick = deleteCampaign;

        var confirmSendBtn = document.getElementById('confirm-send-btn');
        if (confirmSendBtn) confirmSendBtn.onclick = confirmSendAll;

        var confirmCancelBtn = document.getElementById('confirm-cancel-btn');
        if (confirmCancelBtn) confirmCancelBtn.onclick = function () {
            document.getElementById('confirm-overlay').style.display = 'none';
        };
    }

    // ── Save ──────────────────────────────────────────────────────────
    function saveCampaign() {
        syncBlockFromDOM();

        var payload = {
            id: window.CAMPAIGN_ID,
            name: getVal('campaign-name'),
            subject: getVal('campaign-subject'),
            trigger: getVal('campaign-trigger'),
            is_active: document.getElementById('campaign-active') ? document.getElementById('campaign-active').checked : true,
            blocks: blocks
        };

        console.log('[campaigns] Saving campaign:', payload.name);

        fetch(window.ENDPOINTS.save, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.id) {
                showToast('Campaign saved', 'success');
                // If new campaign, redirect to edit page
                if (!window.CAMPAIGN_ID) {
                    window.location.href = window.ENDPOINTS.listPage.replace(/\/$/, '') + '/editor/' + data.id;
                }
                window.CAMPAIGN_ID = data.id;
                console.log('[campaigns] Save successful, id=' + data.id);
            } else {
                showToast(data.error || 'Save failed', 'error');
            }
        })
        .catch(function (err) {
            showToast('Network error', 'error');
            console.error('[campaigns] Save error:', err);
        });
    }

    // ── Send Test ─────────────────────────────────────────────────────
    function sendTest() {
        if (!window.ENDPOINTS.sendTest) {
            showToast('Save the campaign first', 'error');
            return;
        }

        console.log('[campaigns] Sending test email');
        var btn = document.getElementById('send-test-btn');
        if (btn) btn.disabled = true;

        fetch(window.ENDPOINTS.sendTest, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            showToast(data.message || data.error, data.error ? 'error' : 'success');
            console.log('[campaigns] Test send result:', data);
        })
        .catch(function (err) {
            showToast('Network error', 'error');
            console.error('[campaigns] Test send error:', err);
        })
        .finally(function () {
            if (btn) btn.disabled = false;
        });
    }

    // ── Send All ──────────────────────────────────────────────────────
    function showSendConfirm() {
        if (!window.ENDPOINTS.sendAll) {
            showToast('Save the campaign first', 'error');
            return;
        }

        // Fetch subscriber count for confirm message
        fetch(window.ENDPOINTS.subscriberCount)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var count = data.count || 0;
                document.getElementById('confirm-message').textContent =
                    'Send "' + getVal('campaign-name') + '" to ' + count + ' active subscriber' + (count !== 1 ? 's' : '') + '?';
                document.getElementById('confirm-overlay').style.display = 'flex';
                console.log('[campaigns] Send confirm shown for ' + count + ' subscribers');
            });
    }

    function confirmSendAll() {
        document.getElementById('confirm-overlay').style.display = 'none';

        console.log('[campaigns] Sending to all subscribers');
        var btn = document.getElementById('send-all-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }

        fetch(window.ENDPOINTS.sendAll, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            showToast(data.message || data.error, data.error ? 'error' : 'success');
            console.log('[campaigns] Send all result:', data);
        })
        .catch(function (err) {
            showToast('Network error', 'error');
            console.error('[campaigns] Send all error:', err);
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = 'Send to All'; }
        });
    }

    // ── Delete ────────────────────────────────────────────────────────
    function deleteCampaign() {
        if (!window.ENDPOINTS.deleteCampaign) return;
        if (!confirm('Delete this campaign permanently?')) return;

        console.log('[campaigns] Deleting campaign ' + window.CAMPAIGN_ID);

        fetch(window.ENDPOINTS.deleteCampaign, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.message) {
                showToast('Campaign deleted', 'success');
                window.location.href = window.ENDPOINTS.listPage;
            } else {
                showToast(data.error || 'Delete failed', 'error');
            }
        })
        .catch(function (err) {
            showToast('Network error', 'error');
            console.error('[campaigns] Delete error:', err);
        });
    }

    // ── Helpers ───────────────────────────────────────────────────────
    function getVal(id) {
        var el = document.getElementById(id);
        return el ? el.value : '';
    }

    function showToast(message, type) {
        var toast = document.getElementById('status-toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = 'status-toast ' + (type || 'success');
        toast.style.display = 'block';
        setTimeout(function () { toast.style.display = 'none'; }, 3000);
    }
})();
