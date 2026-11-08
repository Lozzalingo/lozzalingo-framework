/**
 * API Docs Module - Interactive Features
 * Handles sidebar toggling, endpoint expand/collapse, search, copy buttons,
 * and theme switching.
 */

(function () {
    'use strict';

    console.log('[API_DOCS] Initialising docs UI');

    // ---- Theme toggle ----
    window.toggleTheme = function () {
        var current = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('lz-theme', next);
        console.log('[API_DOCS] Theme switched to', next);
    };

    // ---- Mobile sidebar toggle ----
    var menuBtn = document.getElementById('mobileMenuBtn');
    var sidebar = document.getElementById('docsSidebar');

    if (menuBtn && sidebar) {
        menuBtn.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });

        // Close sidebar when clicking a link on mobile
        sidebar.querySelectorAll('.sidebar-link').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth <= 900) {
                    sidebar.classList.remove('open');
                }
            });
        });
    }

    // ---- Sidebar group toggle ----
    document.querySelectorAll('.sidebar-group-toggle').forEach(function (btn) {
        var group = btn.closest('.sidebar-group');

        btn.addEventListener('click', function () {
            group.classList.toggle('open');
        });

        // Open all groups by default
        group.classList.add('open');
    });

    // ---- Endpoint expand/collapse ----
    document.querySelectorAll('.endpoint-header').forEach(function (header) {
        header.addEventListener('click', function () {
            var card = header.closest('.endpoint-card');
            card.classList.toggle('expanded');
        });
    });

    // ---- Search ----
    var searchInput = document.getElementById('endpointSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var query = this.value.toLowerCase().trim();
            var links = document.querySelectorAll('.endpoint-link');
            var groups = document.querySelectorAll('.sidebar-group');

            links.forEach(function (link) {
                var searchText = (link.getAttribute('data-search') || '').toLowerCase();
                var matches = !query || searchText.indexOf(query) !== -1;
                link.style.display = matches ? '' : 'none';
            });

            // Show/hide groups based on visible links
            groups.forEach(function (group) {
                var visibleLinks = group.querySelectorAll('.endpoint-link[style=""], .endpoint-link:not([style])');
                var hasVisible = false;
                visibleLinks.forEach(function (l) {
                    if (l.style.display !== 'none') hasVisible = true;
                });

                group.style.display = hasVisible ? '' : 'none';

                // Auto-open groups when searching
                if (query && hasVisible) {
                    group.classList.add('open');
                }
            });
        });
    }

    // ---- Copy buttons ----
    document.querySelectorAll('.copy-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var targetId = btn.getAttribute('data-copy-target');
            var target = document.getElementById(targetId);
            if (!target) return;

            var text = target.textContent;
            navigator.clipboard.writeText(text).then(function () {
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(function () {
                    btn.textContent = 'Copy';
                    btn.classList.remove('copied');
                }, 1500);
            }).catch(function () {
                console.log('[API_DOCS] Clipboard write failed');
            });
        });
    });

    // ---- Smooth scroll to anchor ----
    if (window.location.hash) {
        var target = document.querySelector(window.location.hash);
        if (target) {
            setTimeout(function () {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Expand the card if it's an endpoint
                var card = target.closest('.endpoint-card');
                if (card) card.classList.add('expanded');
            }, 100);
        }
    }

    // ---- Active sidebar link tracking ----
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                var id = entry.target.id;
                document.querySelectorAll('.sidebar-link').forEach(function (link) {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }, { rootMargin: '-20% 0px -70% 0px' });

    document.querySelectorAll('.endpoint-card[id], .docs-section[id]').forEach(function (el) {
        observer.observe(el);
    });

    console.log('[API_DOCS] Docs UI ready');
})();
