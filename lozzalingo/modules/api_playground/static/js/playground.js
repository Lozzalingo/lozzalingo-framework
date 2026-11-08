/**
 * API Playground Module - Interactive Request Builder
 *
 * Handles:
 * - Sidebar endpoint navigation and search
 * - Dynamic form fields from OpenAPI spec
 * - Request sending via proxy
 * - Response rendering with syntax highlighting
 * - Code generation (curl, Python, JavaScript)
 * - Theme switching
 */

(function () {
    'use strict';

    console.log('[API_PLAYGROUND] Initialising playground');

    // ---- State ----
    var state = {
        selectedEndpoint: null,
        selectedGroup: null,
        codeLang: 'curl',
    };

    // ---- DOM refs ----
    var dom = {
        nav: document.getElementById('pgNav'),
        search: document.getElementById('pgSearch'),
        server: document.getElementById('pgServer'),
        methodBadge: document.getElementById('pgMethodBadge'),
        pathInput: document.getElementById('pgPath'),
        sendBtn: document.getElementById('pgSendBtn'),
        paramsEmpty: document.getElementById('paramsEmpty'),
        paramsFields: document.getElementById('paramsFields'),
        headersFields: document.getElementById('headersFields'),
        bodyEditor: document.getElementById('pgBodyEditor'),
        codeOutput: document.getElementById('codeOutput'),
        responseMeta: document.getElementById('responseMeta'),
        responseBody: document.getElementById('responseBody'),
        addHeaderBtn: document.getElementById('addHeaderBtn'),
        copyCodeBtn: document.getElementById('copyCodeBtn'),
    };

    // ---- Theme ----
    window.toggleTheme = function () {
        var current = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('lz-theme', next);
    };

    // ---- Build sidebar nav ----
    function buildNav() {
        var html = '';
        PLAYGROUND_GROUPS.forEach(function (group) {
            html += '<div class="pg-nav-group" data-group="' + group.name + '">';
            html += '<span class="pg-nav-group-label">' + escapeHtml(group.name) + '</span>';
            group.endpoints.forEach(function (ep, idx) {
                var key = group.name + '::' + idx;
                html += '<div class="pg-nav-item" data-key="' + escapeHtml(key) + '" ';
                html += 'data-search="' + escapeHtml(ep.method + ' ' + ep.path + ' ' + ep.summary) + '">';
                html += '<span class="method-badge method-' + ep.method.toLowerCase() + '">' + ep.method + '</span>';
                html += '<span class="endpoint-path">' + escapeHtml(ep.path) + '</span>';
                html += '</div>';
            });
            html += '</div>';
        });
        dom.nav.innerHTML = html;

        // Bind click events
        dom.nav.querySelectorAll('.pg-nav-item').forEach(function (item) {
            item.addEventListener('click', function () {
                var key = item.getAttribute('data-key');
                selectEndpoint(key);
            });
        });
    }

    // ---- Select endpoint ----
    function selectEndpoint(key) {
        var parts = key.split('::');
        var groupName = parts[0];
        var epIdx = parseInt(parts[1], 10);

        var group = PLAYGROUND_GROUPS.find(function (g) { return g.name === groupName; });
        if (!group) return;

        var ep = group.endpoints[epIdx];
        if (!ep) return;

        state.selectedEndpoint = ep;
        state.selectedGroup = group;

        // Update sidebar active state
        dom.nav.querySelectorAll('.pg-nav-item').forEach(function (item) {
            item.classList.toggle('active', item.getAttribute('data-key') === key);
        });

        // Update URL bar
        dom.methodBadge.className = 'method-badge method-' + ep.method.toLowerCase();
        dom.methodBadge.textContent = ep.method;
        dom.pathInput.value = ep.path;

        // Build parameters tab
        buildParamsTab(ep);

        // Populate body editor with example
        if (ep.request_body && ep.request_body.example) {
            dom.bodyEditor.value = JSON.stringify(ep.request_body.example, null, 2);
        } else {
            dom.bodyEditor.value = '';
        }

        // Pre-populate auth headers
        if (ep.auth_types && ep.auth_types.length > 0) {
            ep.auth_types.forEach(function (auth) {
                if (auth === 'ApiKeyAuth') {
                    var apiKeyInput = dom.headersFields.querySelector('[data-header-key="X-API-Key"]');
                    if (apiKeyInput && !apiKeyInput.value) {
                        apiKeyInput.placeholder = 'Required for this endpoint';
                        apiKeyInput.style.borderColor = 'var(--lz-warning)';
                    }
                }
                if (auth === 'BearerAuth') {
                    var bearerInput = dom.headersFields.querySelector('[data-header-key="Authorization"]');
                    if (bearerInput && !bearerInput.value) {
                        bearerInput.placeholder = 'Bearer eyJ... (required)';
                        bearerInput.style.borderColor = 'var(--lz-warning)';
                    }
                }
            });
        }

        // Update code output
        updateCodeOutput();

        console.log('[API_PLAYGROUND] Selected:', ep.method, ep.path);
    }

    // ---- Build params tab ----
    function buildParamsTab(ep) {
        var params = ep.parameters || [];
        var bodyProps = (ep.request_body && ep.request_body.properties) || [];

        if (params.length === 0 && bodyProps.length === 0) {
            dom.paramsEmpty.style.display = '';
            dom.paramsFields.innerHTML = '';
            dom.paramsFields.style.display = 'none';
            return;
        }

        dom.paramsEmpty.style.display = 'none';
        dom.paramsFields.style.display = '';

        var html = '';

        // URL and query parameters
        params.forEach(function (p) {
            html += buildFieldRow(p.name, p.type, p.required, p.description, p.in, p.default, p.enum, 'param');
        });

        // Body fields
        bodyProps.forEach(function (p) {
            html += buildFieldRow(p.name, p.type, p.required, p.description, 'body', p.default, p.enum, 'body');
        });

        dom.paramsFields.innerHTML = html;

        // Sync body fields to body editor
        dom.paramsFields.querySelectorAll('[data-field-source="body"]').forEach(function (input) {
            input.addEventListener('input', syncParamsToBody);
        });

        // Sync param fields to path
        dom.paramsFields.querySelectorAll('[data-field-source="param"]').forEach(function (input) {
            input.addEventListener('input', function () {
                updatePathWithParams();
                updateCodeOutput();
            });
        });
    }

    function buildFieldRow(name, type, required, description, location, defaultVal, enumVals, source) {
        var html = '<div class="pg-field-row">';
        html += '<label>';
        html += escapeHtml(name);
        if (required) html += ' <span class="field-required">*</span>';
        html += ' <span class="field-type">' + escapeHtml(type) + '</span>';
        html += ' <span class="field-location">' + escapeHtml(location) + '</span>';
        html += '</label>';

        if (enumVals && enumVals.length) {
            html += '<select name="field_' + escapeHtml(name) + '" data-field-name="' + escapeHtml(name) + '" data-field-location="' + escapeHtml(location) + '" data-field-source="' + source + '">';
            html += '<option value="">-- select --</option>';
            enumVals.forEach(function (v) {
                var sel = (defaultVal !== undefined && defaultVal !== null && String(defaultVal) === String(v)) ? ' selected' : '';
                html += '<option value="' + escapeHtml(String(v)) + '"' + sel + '>' + escapeHtml(String(v)) + '</option>';
            });
            html += '</select>';
        } else {
            var placeholder = defaultVal !== undefined && defaultVal !== null ? String(defaultVal) : '';
            html += '<input type="text" name="field_' + escapeHtml(name) + '" data-field-name="' + escapeHtml(name) + '" data-field-location="' + escapeHtml(location) + '" data-field-source="' + source + '" placeholder="' + escapeHtml(placeholder) + '">';
        }

        if (description) {
            html += '<span class="field-description">' + escapeHtml(description) + '</span>';
        }
        html += '</div>';
        return html;
    }

    // ---- Sync param fields to body editor ----
    function syncParamsToBody() {
        var bodyFields = dom.paramsFields.querySelectorAll('[data-field-source="body"]');
        var body = {};
        bodyFields.forEach(function (input) {
            var val = input.value.trim();
            if (val) {
                var name = input.getAttribute('data-field-name');
                // Try to parse as JSON (for numbers, booleans)
                try {
                    body[name] = JSON.parse(val);
                } catch (e) {
                    body[name] = val;
                }
            }
        });

        if (Object.keys(body).length > 0) {
            dom.bodyEditor.value = JSON.stringify(body, null, 2);
        }
        updateCodeOutput();
    }

    // ---- Update path with path params ----
    function updatePathWithParams() {
        if (!state.selectedEndpoint) return;
        var path = state.selectedEndpoint.path;

        dom.paramsFields.querySelectorAll('[data-field-location="path"]').forEach(function (input) {
            var name = input.getAttribute('data-field-name');
            var val = input.value.trim();
            if (val) {
                path = path.replace('{' + name + '}', val);
            }
        });

        dom.pathInput.value = path;
    }

    // ---- Gather request data ----
    function gatherRequest() {
        var server = dom.server.value;
        var method = state.selectedEndpoint ? state.selectedEndpoint.method : 'GET';
        var path = dom.pathInput.value;

        // Query params
        var queryParams = [];
        dom.paramsFields.querySelectorAll('[data-field-location="query"]').forEach(function (input) {
            var val = input.value.trim();
            if (val) {
                queryParams.push(encodeURIComponent(input.getAttribute('data-field-name')) + '=' + encodeURIComponent(val));
            }
        });

        var fullUrl = server + path;
        if (queryParams.length) {
            fullUrl += '?' + queryParams.join('&');
        }

        // Headers
        var headers = {};
        dom.headersFields.querySelectorAll('[data-header-key]').forEach(function (input) {
            var key = input.getAttribute('data-header-key');
            var val = input.value.trim();
            if (val) {
                headers[key] = val;
            }
        });

        // Body
        var body = null;
        if (['POST', 'PUT', 'PATCH'].indexOf(method) !== -1) {
            var bodyText = dom.bodyEditor.value.trim();
            if (bodyText) {
                body = bodyText;
            }
        }

        return { url: fullUrl, method: method, headers: headers, body: body };
    }

    // ---- Send request ----
    function sendRequest() {
        var req = gatherRequest();
        if (!req.url) return;

        dom.sendBtn.classList.add('loading');
        dom.sendBtn.textContent = 'Sending...';
        dom.responseMeta.innerHTML = '';
        dom.responseBody.innerHTML = '<div class="pg-empty-tab"><p>Loading...</p></div>';

        console.log('[API_PLAYGROUND] Sending', req.method, req.url);

        var startTime = Date.now();

        // Build fetch options for proxy
        var fetchHeaders = { 'X-Target-URL': req.url };
        Object.keys(req.headers).forEach(function (k) {
            fetchHeaders[k] = req.headers[k];
        });

        var fetchOpts = {
            method: req.method,
            headers: fetchHeaders,
        };

        if (req.body) {
            fetchOpts.body = req.body;
        }

        fetch(PROXY_URL, fetchOpts)
            .then(function (resp) {
                var elapsed = Date.now() - startTime;
                var status = resp.status;
                var proxyTime = resp.headers.get('X-Proxy-Time-Ms');

                return resp.text().then(function (text) {
                    renderResponse(status, text, proxyTime || elapsed);
                });
            })
            .catch(function (err) {
                console.log('[API_PLAYGROUND] Request failed:', err);
                dom.responseMeta.innerHTML = '<span class="status-badge status-5xx">Error</span>';
                dom.responseBody.innerHTML = '<pre>' + escapeHtml(err.message || 'Request failed') + '</pre>';
            })
            .finally(function () {
                dom.sendBtn.classList.remove('loading');
                dom.sendBtn.textContent = 'Send';
            });
    }

    // ---- Render response ----
    function renderResponse(status, body, timeMs) {
        var statusClass = 'status-' + String(status).charAt(0) + 'xx';

        var metaHtml = '<span class="status-badge ' + statusClass + '">' + status + '</span>';
        metaHtml += '<span class="time-badge">' + timeMs + 'ms</span>';
        metaHtml += '<span class="size-badge">' + formatBytes(body.length) + '</span>';
        dom.responseMeta.innerHTML = metaHtml;

        // Try to pretty-print JSON
        var displayBody = body;
        try {
            var parsed = JSON.parse(body);
            displayBody = JSON.stringify(parsed, null, 2);
        } catch (e) {
            // Not JSON, show as is
        }

        dom.responseBody.innerHTML = '<pre>' + escapeHtml(displayBody) + '</pre>';
    }

    // ---- Code generation ----
    function updateCodeOutput() {
        var req = gatherRequest();
        var code = '';

        switch (state.codeLang) {
            case 'curl':
                code = generateCurl(req);
                break;
            case 'python':
                code = generatePython(req);
                break;
            case 'javascript':
                code = generateJavaScript(req);
                break;
        }

        dom.codeOutput.querySelector('code').textContent = code;
    }

    function generateCurl(req) {
        var lines = ['curl -X ' + req.method + ' \\'];
        lines.push("  '" + req.url + "' \\");

        Object.keys(req.headers).forEach(function (k) {
            lines.push("  -H '" + k + ': ' + req.headers[k] + "' \\");
        });

        if (req.body) {
            lines.push("  -d '" + req.body.replace(/'/g, "\\'") + "'");
        } else {
            // Remove trailing backslash from last line
            var last = lines[lines.length - 1];
            if (last.endsWith(' \\')) {
                lines[lines.length - 1] = last.slice(0, -2);
            }
        }

        return lines.join('\n');
    }

    function generatePython(req) {
        var lines = ['import requests', ''];
        var hasHeaders = Object.keys(req.headers).length > 0;

        if (hasHeaders) {
            lines.push('headers = {');
            Object.keys(req.headers).forEach(function (k) {
                lines.push("    '" + k + "': '" + req.headers[k] + "',");
            });
            lines.push('}');
            lines.push('');
        }

        if (req.body) {
            lines.push('data = ' + req.body);
            lines.push('');
        }

        var callArgs = ["'" + req.url + "'"];
        if (hasHeaders) callArgs.push('headers=headers');
        if (req.body) callArgs.push('json=data');

        lines.push('resp = requests.' + req.method.toLowerCase() + '(');
        callArgs.forEach(function (arg, i) {
            var comma = i < callArgs.length - 1 ? ',' : '';
            lines.push('    ' + arg + comma);
        });
        lines.push(')');
        lines.push('');
        lines.push('print(resp.status_code)');
        lines.push('print(resp.json())');

        return lines.join('\n');
    }

    function generateJavaScript(req) {
        var lines = [];
        var hasHeaders = Object.keys(req.headers).length > 0;
        var opts = [];

        opts.push("  method: '" + req.method + "',");
        if (hasHeaders) {
            opts.push('  headers: {');
            Object.keys(req.headers).forEach(function (k) {
                opts.push("    '" + k + "': '" + req.headers[k] + "',");
            });
            opts.push('  },');
        }
        if (req.body) {
            opts.push('  body: JSON.stringify(' + req.body + '),');
        }

        lines.push("const resp = await fetch('" + req.url + "', {");
        opts.forEach(function (o) { lines.push(o); });
        lines.push('});');
        lines.push('');
        lines.push('const data = await resp.json();');
        lines.push('console.log(resp.status, data);');

        return lines.join('\n');
    }

    // ---- Tab switching ----
    document.querySelectorAll('.pg-tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            var tabId = tab.getAttribute('data-tab');

            // Update active tab
            tab.closest('.pg-panel-tabs').querySelectorAll('.pg-tab').forEach(function (t) {
                t.classList.remove('active');
            });
            tab.classList.add('active');

            // Show tab content
            tab.closest('.pg-request-panel').querySelectorAll('.pg-tab-content').forEach(function (c) {
                c.classList.remove('active');
            });
            var target = document.getElementById('tab-' + tabId);
            if (target) target.classList.add('active');

            // If code tab, regenerate
            if (tabId === 'code') {
                updateCodeOutput();
            }
        });
    });

    // ---- Code language tabs ----
    document.querySelectorAll('.pg-code-tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.pg-code-tab').forEach(function (t) {
                t.classList.remove('active');
            });
            tab.classList.add('active');
            state.codeLang = tab.getAttribute('data-lang');
            updateCodeOutput();
        });
    });

    // ---- Send button ----
    dom.sendBtn.addEventListener('click', sendRequest);

    // ---- Keyboard shortcut: Ctrl+Enter to send ----
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sendRequest();
        }
    });

    // ---- Search ----
    dom.search.addEventListener('input', function () {
        var query = this.value.toLowerCase().trim();
        dom.nav.querySelectorAll('.pg-nav-item').forEach(function (item) {
            var text = (item.getAttribute('data-search') || '').toLowerCase();
            item.style.display = (!query || text.indexOf(query) !== -1) ? '' : 'none';
        });

        dom.nav.querySelectorAll('.pg-nav-group').forEach(function (group) {
            var visible = group.querySelectorAll('.pg-nav-item:not([style*="display: none"])');
            group.style.display = visible.length > 0 ? '' : 'none';
        });
    });

    // ---- Add header button ----
    dom.addHeaderBtn.addEventListener('click', function () {
        var row = document.createElement('div');
        row.className = 'pg-field-row';
        row.innerHTML = '<div style="display:flex;gap:8px;"><input type="text" placeholder="Header name" style="flex:1" class="header-key-input"><input type="text" placeholder="Value" style="flex:1" class="header-val-input"><button name="remove_header" style="background:none;border:none;color:var(--lz-danger);cursor:pointer;font-size:16px;" class="remove-header-btn">&times;</button></div>';
        dom.headersFields.appendChild(row);

        // Handle dynamic header key/value
        var keyInput = row.querySelector('.header-key-input');
        var valInput = row.querySelector('.header-val-input');
        var removeBtn = row.querySelector('.remove-header-btn');

        keyInput.addEventListener('input', function () {
            valInput.setAttribute('data-header-key', keyInput.value.trim());
        });

        removeBtn.addEventListener('click', function () {
            row.remove();
        });
    });

    // ---- Copy code button ----
    dom.copyCodeBtn.addEventListener('click', function () {
        var code = dom.codeOutput.textContent;
        navigator.clipboard.writeText(code).then(function () {
            dom.copyCodeBtn.textContent = 'Copied!';
            dom.copyCodeBtn.classList.add('copied');
            setTimeout(function () {
                dom.copyCodeBtn.textContent = 'Copy';
                dom.copyCodeBtn.classList.remove('copied');
            }, 1500);
        });
    });

    // ---- Body editor change -> update code ----
    dom.bodyEditor.addEventListener('input', function () {
        updateCodeOutput();
    });

    // ---- Helpers ----
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // ---- Init ----
    buildNav();

    // Check for pre-selected endpoint from URL params
    var urlParams = new URLSearchParams(window.location.search);
    var preMethod = urlParams.get('method');
    var prePath = urlParams.get('path');

    if (preMethod && prePath) {
        // Find matching endpoint
        PLAYGROUND_GROUPS.forEach(function (group) {
            group.endpoints.forEach(function (ep, idx) {
                if (ep.method === preMethod && ep.path === prePath) {
                    selectEndpoint(group.name + '::' + idx);
                }
            });
        });
    } else if (PLAYGROUND_GROUPS.length > 0 && PLAYGROUND_GROUPS[0].endpoints.length > 0) {
        // Select first endpoint by default
        selectEndpoint(PLAYGROUND_GROUPS[0].name + '::0');
    }

    console.log('[API_PLAYGROUND] Playground ready');
})();
