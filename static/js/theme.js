/**
 * RunRush unified theme system.
 *
 * Canonical mechanism: <html data-theme="light|dark"> plus
 * <html data-theme-preference="system|light|dark">. The *preference* is
 * what the user actually chose (defaults to "system"); the *resolved*
 * theme is what's actually applied after resolving "system" against
 * matchMedia. Everything in the app should read data-theme for styling
 * and only this module should ever write it.
 *
 * Resolution order (matches the brief): explicit stored preference ->
 * system preference if set to "system" -> server-rendered fallback for
 * a first-ever visit on this device -> "dark".
 *
 * The actual FIRST paint is handled by a tiny inline script in
 * templates/partials/_theme_init.html (included in every page's <head>,
 * before any CSS/JS loads) so there is never a flash of the wrong theme
 * -- this file runs after that, and is responsible for: live switching
 * without reload, reacting to OS theme changes while the preference is
 * "system", and persisting a new preference (localStorage instantly,
 * server on a short debounce for logged-in users).
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'runrush-theme-preference';
  var VALID = ['system', 'light', 'dark'];

  function resolve(preference) {
    if (preference === 'system') {
      return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    return preference;
  }

  function apply(preference) {
    if (VALID.indexOf(preference) === -1) preference = 'system';
    var resolved = resolve(preference);
    var root = document.documentElement;
    root.setAttribute('data-theme', resolved);
    root.setAttribute('data-theme-preference', preference);

    // Legacy compatibility: settings.html's own (pre-Phase-1) CSS still
    // keys off body.light-theme. Mirroring it here keeps that page
    // looking correct without touching its CSS in this foundation pass
    // -- removed once settings.html's own styles migrate to data-theme
    // directly in a later phase.
    if (document.body) {
      document.body.classList.toggle('light-theme', resolved === 'light');
    }

    var themeColorMeta = document.getElementById('themeColorMeta') || document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
      themeColorMeta.setAttribute('content', resolved === 'light' ? '#F0F4F8' : '#0B0B0D');
    }

    document.dispatchEvent(new CustomEvent('runrush:theme-changed', {
      detail: { preference: preference, resolved: resolved }
    }));
  }

  function getCsrfToken() {
    // Not every page uses the same CSRF pattern: most set a
    // <meta name="csrf-token">, but e.g. settings.html only has hidden
    // <input name="csrf_token"> fields inside its forms. Check both.
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : null;
  }

  function persistToServer(preference) {
    // Best-effort, fire-and-forget -- never blocks the UI and never throws if
    // the user is logged out (the endpoint just no-ops via its login check).
    // Sent immediately with keepalive: the account value is what every page
    // loads, so it must land even if the user navigates away right after.
    (function () {
      try {
        var csrfToken = getCsrfToken();
        var body = new URLSearchParams({ theme: preference });
        fetch('/settings/theme', {
          method: 'POST',
          headers: Object.assign(
            { 'Content-Type': 'application/x-www-form-urlencoded' },
            csrfToken ? { 'X-CSRFToken': csrfToken } : {}
          ),
          body: body.toString(),
          credentials: 'same-origin',
          keepalive: true
        }).catch(function () { /* offline / logged out -- fine, localStorage still holds it */ });
      } catch (e) { /* never let theme persistence break the UI */ }
    })();
  }

  function setPreference(preference) {
    if (VALID.indexOf(preference) === -1) return;
    try { localStorage.setItem(STORAGE_KEY, preference); } catch (e) { /* private mode etc. */ }
    apply(preference);
    persistToServer(preference);
  }

  function getPreference() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (VALID.indexOf(stored) !== -1) return stored;
    } catch (e) { /* ignore */ }
    return document.documentElement.getAttribute('data-theme-preference') || 'system';
  }

  // Live-update if the preference is "system" and the OS theme changes
  // while the tab is open.
  var mq = window.matchMedia('(prefers-color-scheme: light)');
  var onSystemChange = function () {
    if (getPreference() === 'system') apply('system');
  };
  if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
  else if (mq.addListener) mq.addListener(onSystemChange); // Safari < 14

  window.RunRushTheme = {
    setPreference: setPreference,
    getPreference: getPreference,
    getResolved: function () { return document.documentElement.getAttribute('data-theme'); }
  };
})();
