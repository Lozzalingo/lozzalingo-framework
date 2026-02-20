/* Lozzalingo Admin Theme Toggle */
(function () {
    var STORAGE_KEY = 'lz-theme';

    function getPreferred() {
        var saved = localStorage.getItem(STORAGE_KEY);
        if (saved === 'light' || saved === 'dark') return saved;
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
    }

    /* Apply immediately (runs in <head> so no FOUC) */
    apply(getPreferred());

    /* Expose global toggle */
    window.toggleTheme = function () {
        var current = document.documentElement.getAttribute('data-theme') || getPreferred();
        var next = current === 'dark' ? 'light' : 'dark';
        apply(next);
        localStorage.setItem(STORAGE_KEY, next);
    };

    /* Listen for system preference changes (only when no manual override) */
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function (e) {
        if (!localStorage.getItem(STORAGE_KEY)) {
            apply(e.matches ? 'light' : 'dark');
        }
    });
})();
