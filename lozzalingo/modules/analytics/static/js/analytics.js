// analytics.js - Enhanced client-side analytics with ultra-stable fingerprinting
class AnalyticsClient {
    constructor() {
        // Initialize route tracking first (needed by collectSessionData)
        this.currentRoute = this.getCurrentRoute();
        this.routeHistory = [];

        // Persist session page count across full-page navigations using sessionStorage
        try {
            const storedCount = parseInt(sessionStorage.getItem('_lz_page_count') || '0', 10);
            this._sessionPageCount = storedCount + 1;
            sessionStorage.setItem('_lz_page_count', this._sessionPageCount.toString());
        } catch (e) {
            this._sessionPageCount = 1;
        }

        // Store fingerprint promise
        this.rateLimiterByDevice = this.generateUltraStableFingerprint();

        this.sessionData = this.collectSessionData();
        this.pageLoadTime = Date.now();

        // Visibility-aware time tracking: only count time when tab is visible
        this._activeTime = 0;           // accumulated active ms
        this._lastVisibleAt = Date.now(); // when the tab last became visible
        this._tabVisible = !document.hidden;
        this._MAX_TIME_SECONDS = 900;    // 15 min cap per page

        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Tab going hidden — bank the active time
                if (this._tabVisible) {
                    this._activeTime += Date.now() - this._lastVisibleAt;
                }
                this._tabVisible = false;
            } else {
                // Tab becoming visible — start a new active interval
                this._lastVisibleAt = Date.now();
                this._tabVisible = true;
            }
        });

        // Initialize device details from session storage if available
        this.loadDeviceDetailsFromSession();

        // Log page view when device details are ready
        this.rateLimiterByDevice.then(deviceDetails => {
            this.deviceDetails = deviceDetails;
            // Store device details for the session
            this.saveDeviceDetailsToSession(deviceDetails);

            if (!this.pageViewLogged) {
                this.logPageViewClient();
                this.pageViewLogged = true;
            }
        });

        // Set up route change listeners
        this.setupRouteTracking();

        this.setupEventListeners();
    }

    saveDeviceDetailsToSession(deviceDetails) {
        try {
            sessionStorage.setItem('analytics_device_details', JSON.stringify(deviceDetails));
        } catch (e) {
            // Session storage not available
        }
    }

    loadDeviceDetailsFromSession() {
        try {
            const stored = sessionStorage.getItem('analytics_device_details');
            if (stored) {
                this.deviceDetails = JSON.parse(stored);
                console.log('[Analytics] Loaded device details from session:', this.deviceDetails);
            }
        } catch (e) {
            // Session storage not available or invalid data
        }
    }

    /**
     * Get active (visible) time in ms since page load, capped at _MAX_TIME_SECONDS.
     */
    getActiveTimeMs() {
        let total = this._activeTime;
        if (this._tabVisible) {
            total += Date.now() - this._lastVisibleAt;
        }
        const capMs = this._MAX_TIME_SECONDS * 1000;
        return Math.min(total, capMs);
    }

    getCurrentRoute() {
        return {
            full_url: window.location.href,
            pathname: window.location.pathname,
            search: window.location.search,
            hash: window.location.hash,
            host: window.location.host,
            protocol: window.location.protocol,
            route_name: this.getRouteName(window.location.pathname),
            timestamp: new Date().toISOString()
        };
    }

    getRouteName(pathname) {
        // Define your route patterns here - customize based on your app structure
        const routePatterns = {
            '/': 'home',
            '/analytics': 'analytics',
            '/news/editor': 'new_editor',
            '/login': 'login',
            '/register': 'register'
        };

        // Check exact matches first
        if (routePatterns[pathname]) {
            return routePatterns[pathname];
        }

        // Check pattern matches for dynamic routes
        if (pathname.startsWith('/user/')) return 'user_profile';
        if (pathname.startsWith('/item/')) return 'item_detail';
        if (pathname.startsWith('/category/')) return 'category_page';
        if (pathname.startsWith('/admin/')) return 'admin_panel';
        if (pathname.match(/^\/\d+$/)) return 'numeric_id_page';
        
        // Default fallback
        return pathname.replace(/^\//, '').replace(/\//g, '_') || 'unknown_route';
    }

    setupRouteTracking() {
        // Track browser back/forward button usage
        window.addEventListener('popstate', (event) => {
            this.handleRouteChange('browser_navigation', event.state);
        });

        // Track programmatic navigation (for SPAs)
        this.interceptHistoryMethods();

        // Track hash changes
        window.addEventListener('hashchange', (event) => {
            this.handleRouteChange('hash_change', {
                oldURL: event.oldURL,
                newURL: event.newURL
            });
        });

        // Track link clicks
        document.addEventListener('click', (event) => {
            const link = event.target.closest('a');
            if (link && link.href) {
                const destination = new URL(link.href);
                // Only track internal links
                if (destination.host === window.location.host) {
                    this.logInteraction('internal_link_click', {
                        destination_url: link.href,
                        destination_route: this.getRouteName(destination.pathname),
                        link_text: link.textContent?.substring(0, 100),
                        current_route: this.currentRoute.route_name
                    });
                }
            }
        });
    }

    interceptHistoryMethods() {
        // Intercept pushState and replaceState for SPA routing
        const originalPushState = history.pushState;
        const originalReplaceState = history.replaceState;

        history.pushState = (...args) => {
            originalPushState.apply(history, args);
            setTimeout(() => this.handleRouteChange('push_state', args[0]), 0);
        };

        history.replaceState = (...args) => {
            originalReplaceState.apply(history, args);
            setTimeout(() => this.handleRouteChange('replace_state', args[0]), 0);
        };
    }

    handleRouteChange(navigationType, state = null) {
        const previousRoute = { ...this.currentRoute };
        const newRoute = this.getCurrentRoute();

        // Use visibility-aware active time (capped at 15 min)
        const timeSpent = this.getActiveTimeMs();

        // Reset active time tracking for the new route
        this._activeTime = 0;
        this._lastVisibleAt = Date.now();
        this._tabVisible = !document.hidden;

        // Update current route
        this.currentRoute = newRoute;
        
        // Add to history
        this.routeHistory.push({
            ...previousRoute,
            time_spent_ms: timeSpent,
            exit_type: navigationType
        });

        // Keep only last 10 routes in memory
        if (this.routeHistory.length > 10) {
            this.routeHistory = this.routeHistory.slice(-10);
        }

        // Log route change
        this.logRouteChange(previousRoute, newRoute, navigationType, timeSpent, state);
    }

    async logRouteChange(fromRoute, toRoute, navigationType, timeSpent, state) {
        try {
            // Wait for device details if not ready yet
            const deviceDetails = this.deviceDetails || await this.rateLimiterByDevice;
            
            const routeChangeData = {
                type: 'route_change',
                navigation_type: navigationType,
                from_route: fromRoute.route_name,
                from_url: fromRoute.full_url,
                to_route: toRoute.route_name,
                to_url: toRoute.full_url,
                time_spent_ms: timeSpent,
                time_spent_seconds: Math.round(timeSpent / 1000),
                state: state,
                route_history: this.routeHistory.slice(-3),
                deviceDetails: deviceDetails,  // Use the awaited deviceDetails
                timestamp: toRoute.timestamp,
                page_url: toRoute.full_url
            };

            await fetch('/admin/analytics/api/log-interaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(routeChangeData)
            });

            console.log(`Route change logged: ${fromRoute.route_name} -> ${toRoute.route_name} (${Math.round(timeSpent / 1000)}s)`);
        } catch (error) {
            console.warn('Route change logging failed:', error);
        }
    }

    // Enhanced page view logging with route info
    async logPageViewClient() {
        try {
            const pageViewData = {
                type: 'page_view_client',
                deviceDetails: this.deviceDetails,
                timestamp: new Date().toISOString(),
                load_time: Date.now() - this.pageLoadTime,
                route_info: this.currentRoute,
                is_returning_visitor: this.routeHistory.length > 0,
                session_page_count: this.routeHistory.length + 1,
                ...this.sessionData
            };

            await fetch('/admin/analytics/api/log-interaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pageViewData)
            });
            
            console.log('Client page view logged with route info:', this.currentRoute.route_name);
        } catch (error) {
            console.warn('Client page view logging failed:', error);
        }
    }

    // Method to manually track custom route events
    trackRouteEvent(eventName, routeData = {}) {
        this.logInteraction(`route_${eventName}`, {
            current_route: this.currentRoute.route_name,
            current_url: this.currentRoute.full_url,
            ...routeData
        });
    }

    // Get current session route analytics
    getSessionRouteAnalytics() {
        return {
            current_route: this.currentRoute,
            route_history: this.routeHistory,
            total_routes_visited: this.routeHistory.length + 1,
            total_session_time: this.routeHistory.reduce((total, route) => total + route.time_spent_ms, 0),
            unique_routes: [...new Set([...this.routeHistory.map(r => r.route_name), this.currentRoute.route_name])],
            most_visited_route: this.getMostVisitedRoute()
        };
    }

    getMostVisitedRoute() {
        const routeCounts = {};
        this.routeHistory.forEach(route => {
            routeCounts[route.route_name] = (routeCounts[route.route_name] || 0) + 1;
        });
        routeCounts[this.currentRoute.route_name] = (routeCounts[this.currentRoute.route_name] || 0) + 1;
        
        return Object.entries(routeCounts).reduce((a, b) => routeCounts[a[0]] > routeCounts[b[0]] ? a : b)[0];
    }

    // Enhanced collectSessionData with better URL parsing
    collectSessionData() {
        const urlData = this.getCurrentRoute();
        
        return {
            // ... your existing session data ...
            
            // Enhanced URL data
            ...urlData,
            referrer_route: this.getReferrerRoute(),
            entry_route: this.currentRoute.route_name,
            
            // Your existing data...
            screen_resolution: `${screen.width}x${screen.height}`,
            viewport_size: `${window.innerWidth}x${window.innerHeight}`,
            // ... rest of your existing collectSessionData code ...
        };
    }

    parseURLParameters() {
        const params = new URLSearchParams(window.location.search);
        const paramObj = {};
        for (const [key, value] of params) {
            paramObj[key] = value;
        }
        return Object.keys(paramObj).length > 0 ? paramObj : null;
    }

    getReferrerRoute() {
        if (!document.referrer) return null;
        
        try {
            const referrerURL = new URL(document.referrer);
            // Only process internal referrers
            if (referrerURL.host === window.location.host) {
                return this.getRouteName(referrerURL.pathname);
            }
            return 'external';
        } catch {
            return 'unknown';
        }
    }


    async generateUltraStableFingerprint() {
        // Get core hardware fingerprints in parallel
        const [canvasFingerprint, webGLFingerprint, audioFingerprint] = await Promise.all([
            this.generateStableCanvasFingerprint(),
            this.generateCoreWebGLFingerprint()
        ]);

        // Get hardware and essential browser info
        const hardwareFingerprint = this.getCoreHardwareFingerprint();
        const essentialBrowserFingerprint = this.getEssentialBrowserFingerprint();

        // Combine with stability weights
        const stableString = [
            `canvas:${canvasFingerprint}`,
            `webgl:${webGLFingerprint}`,
            `hardware:${hardwareFingerprint}`,
            `audio:${audioFingerprint}`,
            `browser:${essentialBrowserFingerprint}`
        ].join('||');

        const fingerprint = stableString;
        
        console.log('Ultra-stable fingerprint generated:', fingerprint.substring(0, 16) + '...');
        return fingerprint;
    }

    generateStableCanvasFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 50;
            const ctx = canvas.getContext('2d');

            // Use consistent, simple operations that depend on hardware rendering
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            
            // Simple geometric shapes - most stable across browsers
            ctx.fillStyle = '#FF0000';
            ctx.fillRect(2, 2, 96, 20);
            
            ctx.fillStyle = '#00FF00';  
            ctx.fillRect(102, 2, 96, 20);
            
            // Basic text rendering
            ctx.fillStyle = '#0000FF';
            ctx.fillText('Stable123', 4, 25);
            
            // Simple circle
            ctx.beginPath();
            ctx.arc(170, 35, 10, 0, Math.PI * 2);
            ctx.fillStyle = '#FFFF00';
            ctx.fill();

            return canvas.toDataURL();
        } catch (e) {
            return 'canvas_unavailable';
        }
    }

    async generateCoreWebGLFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            
            if (!gl) return 'webgl_unavailable';

            const stableComponents = [];

            // GPU Renderer - most stable identifier
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {
                let renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                let vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                
                // Heavily normalize for stability
                renderer = this.normalizeGPUString(renderer);
                vendor = this.normalizeGPUString(vendor);
                
                stableComponents.push(`vendor:${vendor}`, `renderer:${renderer}`);
            }

            // Core WebGL limits (hardware-dependent, very stable)
            const coreParameters = [
                gl.MAX_TEXTURE_SIZE,
                gl.MAX_CUBE_MAP_TEXTURE_SIZE, 
                gl.MAX_RENDERBUFFER_SIZE,
                gl.MAX_VERTEX_ATTRIBS,
                gl.MAX_VERTEX_UNIFORM_VECTORS,
                gl.MAX_FRAGMENT_UNIFORM_VECTORS,
                gl.MAX_VARYING_VECTORS
            ];

            coreParameters.forEach(param => {
                try {
                    const value = gl.getParameter(param);
                    stableComponents.push(Array.isArray(value) ? value.join(',') : String(value));
                } catch (e) {
                    stableComponents.push('unknown');
                }
            });

            // Only the most stable extensions
            const stableExtensions = [
                'WEBGL_debug_renderer_info',
                'OES_texture_float',
                'OES_standard_derivatives',
                'WEBGL_lose_context'
            ];
            
            const supportedExtensions = gl.getSupportedExtensions() || [];
            const hasStableExtensions = stableExtensions
                .map(ext => supportedExtensions.includes(ext))
                .join(',');
            stableComponents.push(`stable_ext:${hasStableExtensions}`);

            return stableComponents.join('|');
        } catch (e) {
            return 'webgl_error';
        }
    }

    normalizeGPUString(gpuString) {
        if (!gpuString) return 'unknown';
        
        return gpuString
            .replace(/\d+\.\d+[\d.]*\w*/g, '')
            .replace(/\([^)]*\d+[^)]*\)/g, '')
            .replace(/\d{1,2}\/\d{1,2}\/\d{2,4}/g, '')
            .replace(/\d+\.\d+\.\d+[\d.]*-?\w*/g, '')
            .replace(/rev\s*\w+/gi, '')
            .replace(/\brev\.\s*\w+/gi, '')
            .replace(/build\s*\d+/gi, '')
            .replace(/\s*-\s*\d+\.\d+\.\d+/g, '')
            .replace(/[\(\)\[\]]/g, ' ')
            .replace(/\s+/g, ' ')
            .replace(/^\s+|\s+$/g, '')
            .split(/\s+/)
            .slice(0, 3)
            .join(' ')
            .toLowerCase();
    }


    getCoreHardwareFingerprint() {
        const components = [
            screen.width,
            screen.height, 
            screen.colorDepth,
            navigator.hardwareConcurrency || 0,
            navigator.deviceMemory || 0,
            navigator.maxTouchPoints || 0,
            navigator.platform,
            Math.floor(new Date().getTimezoneOffset() / 60)
        ];
        return components.join('|');
    }

    getEssentialBrowserFingerprint() {
        let userAgent = navigator.userAgent || '';
        const browserCore = this.extractBrowserCore(userAgent);
        
        const components = [
            browserCore,
            navigator.language.split('-')[0],
            navigator.cookieEnabled,
            navigator.maxTouchPoints > 0,
            'localStorage' in window,
            'indexedDB' in window
        ];
        return components.join('|');
    }

    extractBrowserCore(userAgent) {
        if (userAgent.includes('Firefox')) return 'firefox';
        if (userAgent.includes('Chrome') && !userAgent.includes('Edge')) return 'chrome';
        if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) return 'safari';
        if (userAgent.includes('Edge')) return 'edge';
        if (userAgent.includes('Opera')) return 'opera';
        return 'unknown';
    }

    async createStableHash(input) {
        if (window.crypto && window.crypto.subtle) {
            try {
                const encoder = new TextEncoder();
                const data = encoder.encode(input);
                const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
                const hashArray = Array.from(new Uint8Array(hashBuffer));
                return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            } catch (e) {
                console.warn('SubtleCrypto unavailable, using fallback');
            }
        }
        
        let hash = 0;
        for (let i = 0; i < input.length; i++) {
            const char = input.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16).padStart(8, '0');
    }

    detectDeviceInfo() {
        const userAgent = navigator.userAgent.toLowerCase();
        let device_os = 'unknown';
        let device_brand = 'unknown';
        let device_confidence = 'low';

        // Detect OS
        if (userAgent.includes('windows')) {
            device_os = 'windows';
            device_confidence = 'high';
        } else if (userAgent.includes('mac os x') || userAgent.includes('macos')) {
            device_os = 'macos';
            device_confidence = 'high';
        } else if (userAgent.includes('android')) {
            device_os = 'android';
            device_confidence = 'high';
        } else if (userAgent.includes('linux')) {
            device_os = 'linux';
            device_confidence = 'medium';
        } else if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
            device_os = 'ios';
            device_confidence = 'high';
        }

        // Detect Brand
        if (userAgent.includes('iphone') || userAgent.includes('ipad') || userAgent.includes('macintosh') || userAgent.includes('mac os')) {
            device_brand = 'apple';
            device_confidence = 'high';
        } else if (userAgent.includes('windows')) {
            device_brand = 'microsoft';
            device_confidence = 'high';
        } else if (userAgent.includes('android')) {
            // Try to detect Android brand
            if (userAgent.includes('samsung')) {
                device_brand = 'samsung';
                device_confidence = 'high';
            } else if (userAgent.includes('huawei')) {
                device_brand = 'huawei';
                device_confidence = 'high';
            } else if (userAgent.includes('xiaomi')) {
                device_brand = 'xiaomi';
                device_confidence = 'high';
            } else if (userAgent.includes('oppo')) {
                device_brand = 'oppo';
                device_confidence = 'high';
            } else if (userAgent.includes('vivo')) {
                device_brand = 'vivo';
                device_confidence = 'high';
            } else if (userAgent.includes('oneplus')) {
                device_brand = 'oneplus';
                device_confidence = 'high';
            } else if (userAgent.includes('pixel')) {
                device_brand = 'google';
                device_confidence = 'high';
            } else {
                device_brand = 'android';
                device_confidence = 'medium';
            }
        } else if (userAgent.includes('linux')) {
            device_brand = 'linux';
            device_confidence = 'low';
        }

        return { device_os, device_brand, device_confidence };
    }

    collectSessionData() {
        const deviceInfo = this.detectDeviceInfo();

        return {
            screen_resolution: `${screen.width}x${screen.height}`,
            viewport_size: `${window.innerWidth}x${window.innerHeight}`,
            color_depth: screen.colorDepth,
            pixel_ratio: window.devicePixelRatio || 1,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            language: navigator.language,
            languages: navigator.languages ? navigator.languages.join(',') : '',
            platform: navigator.platform,
            cookie_enabled: navigator.cookieEnabled,
            online: navigator.onLine,
            do_not_track: navigator.doNotTrack || 'not_specified',
            hardware_concurrency: navigator.hardwareConcurrency || 'unknown',
            device_memory: navigator.deviceMemory || 'unknown',
            max_touch_points: navigator.maxTouchPoints || 0,
            connection_type: navigator.connection ? navigator.connection.effectiveType : 'unknown',
            connection_downlink: navigator.connection ? navigator.connection.downlink : 'unknown',
            java_enabled: navigator.javaEnabled ? navigator.javaEnabled() : false,
            pdf_viewer_enabled: navigator.pdfViewerEnabled || false,
            webdriver: navigator.webdriver || false,
            local_storage_enabled: this.testLocalStorage(),
            session_storage_enabled: this.testSessionStorage(),
            indexed_db_enabled: this.testIndexedDB(),
            page_url: window.location.href,
            page_title: document.title,
            referrer: document.referrer || null,
            protocol: window.location.protocol,
            domain: window.location.hostname,
            path: window.location.pathname,
            search_params: window.location.search,
            hash: window.location.hash,
            device_os: deviceInfo.device_os,
            device_brand: deviceInfo.device_brand,
            device_confidence: deviceInfo.device_confidence,
            session_page_count: this._sessionPageCount || 1
        };
    }

    testLocalStorage() {
        try {
            localStorage.setItem('test', 'test');
            localStorage.removeItem('test');
            return true;
        } catch (e) {
            return false;
        }
    }

    testSessionStorage() {
        try {
            sessionStorage.setItem('test', 'test');
            sessionStorage.removeItem('test');
            return true;
        } catch (e) {
            return false;
        }
    }

    testIndexedDB() {
        return 'indexedDB' in window;
    }

    async logPageViewClient() {
        try {
            const pageViewData = {
                type: 'page_view_client',
                deviceDetails: this.deviceDetails,
                timestamp: new Date().toISOString(),
                load_time: Date.now() - this.pageLoadTime,
                ...this.sessionData
            };

            await fetch('/admin/analytics/api/log-interaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pageViewData)
            });
            
            console.log('Client page view logged with ultra-stable fingerprint');
        } catch (error) {
            console.warn('Client page view logging failed:', error);
        }
    }

    async logInteraction(type, additionalData = {}) {
        try {
            const email = document.getElementById('email')?.value?.trim() || null;
            
            const payload = {
                type: type,
                deviceDetails: this.deviceDetails,
                email: email,
                timestamp: new Date().toISOString(),
                page_url: window.location.href,
                viewport_size: `${window.innerWidth}x${window.innerHeight}`,
                ...additionalData
            };

            await fetch('/admin/analytics/api/log-interaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } catch (error) {
            console.warn('Analytics logging failed:', error);
        }
    }

    setupEventListeners() {
        // Set deviceDetails in form when ready
        this.rateLimiterByDevice.then(deviceDetails => {
            const deviceDetailsInput = document.getElementById('browser_deviceDetails');
            if (deviceDetailsInput) {
                deviceDetailsInput.value = deviceDetails;
                console.log('Ultra-stable deviceDetails set in form:', deviceDetails.substring(0, 16) + '...');
            }
        });

        // Track file uploads with details
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                this.logInteraction('file_upload', {
                    has_file: file ? true : false,
                    file_name: file ? file.name : null,
                    file_size: file ? file.size : null,
                    file_type: file ? file.type : null,
                    file_last_modified: file ? new Date(file.lastModified).toISOString() : null
                });
            });
        }

        // Track form start
        let formStarted = false;
        document.addEventListener('click', (e) => {
            if (!formStarted && e.target.closest('#designForm')) {
                formStarted = true;
                this.logInteraction('form_start', {
                    click_target: e.target.tagName.toLowerCase(),
                    click_coordinates: { x: e.clientX, y: e.clientY }
                });
            }
        });

        // Track page exit
        window.addEventListener('beforeunload', async () => {
            try {
                const deviceDetails = await this.rateLimiterByDevice;
                const activeTimeMs = this.getActiveTimeMs();
                const exitData = {
                    type: 'page_exit',
                    deviceDetails: deviceDetails,
                    time_spent_seconds: Math.round(activeTimeMs / 1000),
                    url: window.location.href
                };
                
                const blob = new Blob([JSON.stringify(exitData)], {
                    type: 'application/json'
                });
                
                navigator.sendBeacon('/admin/analytics/api/log-interaction', blob);
            } catch (e) {
                console.warn('sendBeacon failed:', e);
            }
        });

        // Track errors
        window.addEventListener('error', (e) => {
            // Don't log errors from external scripts or extensions
            if (e.filename && (e.filename.includes('extension://') || e.filename.includes('chrome-extension://') || e.filename.includes('moz-extension://'))) {
                return;
            }

            this.logInteraction('javascript_error', {
                error_message: e.message,
                error_filename: e.filename || 'unknown',
                error_line: e.lineno || 0,
                error_column: e.colno || 0,
                user_agent: navigator.userAgent,
                url: window.location.href
            });
        });

        // Log form field interactions
        document.addEventListener('change', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                this.logInteraction(`field_change_${e.target.name || e.target.id}`);
            }
        });

        // Log button clicks (use closest() to handle clicks on child elements)
        document.addEventListener('click', (e) => {
            const button = e.target.closest('button, [type="submit"]');
            if (button) {
                this.logInteraction(`button_click_${button.getAttribute('name') || button.id || 'unnamed'}`);
                return;
            }
            const link = e.target.closest('a[href]');
            if (link) {
                const linkName = link.getAttribute('name') || link.id || 'unnamed_link';
                this.logInteraction(`link_click_${linkName}`);
            }
        });

        // Log prompt typing
        const promptField = document.querySelector('textarea[name="prompt"]');
        if (promptField) {
            let typingTimeout;
            promptField.addEventListener('input', (e) => {
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => {
                    this.logInteraction('prompt_typing');
                }, 1000);
            });
        }

        // Log email entry
        const emailField = document.querySelector('input[name="email"]');
        if (emailField) {
            emailField.addEventListener('blur', (e) => {
                if (e.target.value.trim()) {
                    this.logInteraction('email_entered');
                }
            });
        }
    }

    getFormCompletion() {
        const form = document.getElementById('designForm');
        if (!form) return 0;

        const requiredFields = form.querySelectorAll('[required]');
        const filledFields = Array.from(requiredFields).filter(field => field.value.trim());
        return Math.round((filledFields.length / requiredFields.length) * 100);
    }

    trackCustomEvent(eventName, data = {}) {
        this.logInteraction(eventName, data);
    }

    async validateFingerprint() {
        const newFingerprint = await this.generateUltraStableFingerprint();
        const matches = newFingerprint === this.deviceDetails;
        console.log('Fingerprint validation:', matches ? 'CONSISTENT' : 'CHANGED');
        return matches;
    }
}

// Initialize analytics when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (!window.analyticsClient) {
        window.analyticsClient = new AnalyticsClient();
    }
});

// Example usage for tracking specific route events:
/*
// Track when user reaches checkout
if (window.location.pathname === '/checkout') {
    analyticsClient.trackRouteEvent('checkout_reached', {
        checkout_step: 1,
        items_count: getCartItemCount()
    });
}

// Track route-specific form completions
analyticsClient.trackRouteEvent('form_completed', {
    form_type: 'design_request',
    completion_time: formCompletionTime
});
*/