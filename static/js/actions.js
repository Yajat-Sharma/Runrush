/**
 * RunRush Actions Dispatcher (CSP Event Delegation)
 *
 * Dispatches DOM events to registered actions in window.RR_ACTIONS.
 * Eliminates all inline on*= attributes for CSP compliance.
 *
 * Rules:
 *  - Never uses eval(), new Function(), or window[name] lookup from attributes.
 *  - Dispatches only to explicit functions in window.RR_ACTIONS.
 *  - Reads data-action, data-click-action, data-change-action, data-input-action,
 *    data-keydown-action, data-submit-action.
 *  - Reads arguments from data-args (JSON-safe array or string).
 *  - Binds `this` to the triggering element.
 */

window.RR_ACTIONS = window.RR_ACTIONS || {};

(function () {
  'use strict';

  function parseArgs(el) {
    var raw = el.getAttribute('data-args');
    if (!raw) return null;
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch (e) {
      return [raw];
    }
  }

  function dispatch(event, eventType) {
    var target = event.target;
    if (!target || typeof target.closest !== 'function') return;

    var specificAttr = 'data-' + eventType + '-action';
    var el = target.closest('[' + specificAttr + '], [data-action]');
    if (!el) return;

    var actionName = el.getAttribute(specificAttr) || el.getAttribute('data-action');
    if (!actionName) return;

    var handler = window.RR_ACTIONS[actionName];
    if (typeof handler !== 'function') {
      console.warn('[RR_ACTIONS] Unknown action:', actionName, 'on element:', el);
      return;
    }

    var args = parseArgs(el);
    if (args !== null) {
      return handler.apply(el, args.concat([event]));
    } else {
      return handler.call(el, event, el);
    }
  }

  // Delegated event listeners on document
  document.addEventListener('click', function (e) {
    dispatch(e, 'click');
  });

  document.addEventListener('change', function (e) {
    dispatch(e, 'change');
  });

  document.addEventListener('input', function (e) {
    dispatch(e, 'input');
  });

  document.addEventListener('keydown', function (e) {
    dispatch(e, 'keydown');
  });

  document.addEventListener('submit', function (e) {
    var res = dispatch(e, 'submit');
    if (res === false) {
      e.preventDefault();
    }
  });

  // Image load error fallback (capture phase because error events on <img> do not bubble)
  document.addEventListener('error', function (e) {
    var target = e.target;
    if (target && target.tagName === 'IMG') {
      var fallback = target.getAttribute('data-fallback-src') || target.getAttribute('data-error-src');
      if (fallback && target.src !== fallback && !target.dataset.hasFailed) {
        target.dataset.hasFailed = 'true';
        target.src = fallback;
      } else {
        var actionName = target.getAttribute('data-error-action') || target.getAttribute('data-action');
        if (actionName && typeof window.RR_ACTIONS[actionName] === 'function') {
          window.RR_ACTIONS[actionName].call(target, e);
        }
      }
    }
  }, true);

})();
