/**
 * Theme bootstrap. Loaded synchronously in <head> so the stored theme applies before paint.
 * Dark (control-room) is the default; the choice is remembered per browser.
 */
(function () {
    var root = document.documentElement;
    var stored = null;
    try { stored = localStorage.getItem('xface-theme'); } catch (_) { /* storage blocked */ }
    if (stored === 'light' || stored === 'dark') root.dataset.theme = stored;

    function sync() {
        var dark = root.dataset.theme !== 'light';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-pressed', String(!dark));
            btn.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
            var use = btn.querySelector('use');
            if (use) use.setAttribute('href', dark ? '#i-sun' : '#i-moon');
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        sync();
        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
                try { localStorage.setItem('xface-theme', root.dataset.theme); } catch (_) { /* ignore */ }
                sync();
            });
        });
    });
})();
