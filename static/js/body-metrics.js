/**
 * Height (ft/in or cm) + weight (kg) fields with a live BMI check.
 *
 * Markup contract (see templates/onboarding.html and settings.html):
 *   [data-body-metrics] or ="required"     wrapper ("required": height must be filled)
 *     input[type=hidden][data-height-cm]    submitted value, always in cm
 *     [data-height-unit="ft"|"cm"] buttons  unit switch
 *     [data-height-mode="ft"] > [data-height-ft], [data-height-in]
 *     [data-height-mode="cm"] > [data-height-cm-input]
 *     input[data-weight-kg]                 weight, kg
 *     [data-bmi-preview]                    live BMI / warning
 *
 * The server only ever sees centimetres; feet is just the default way to type it.
 */
(function () {
  'use strict';

  var UNIT_KEY = 'runrush-height-unit';
  var LIMITS = { minCm: 100, maxCm: 250, minKg: 25, maxKg: 300, minBmi: 10, maxBmi: 70 };

  function num(el) {
    var v = parseFloat(el && el.value);
    return isNaN(v) ? null : v;
  }

  function category(bmi) {
    if (bmi < 18.5) return { label: 'Underweight', tone: 'warn' };
    if (bmi < 25) return { label: 'Healthy', tone: 'good' };
    if (bmi < 30) return { label: 'Overweight', tone: 'warn' };
    return { label: 'Obese', tone: 'warn' };
  }

  function init(root) {
    var hidden = root.querySelector('[data-height-cm]');
    var ft = root.querySelector('[data-height-ft]');
    var inch = root.querySelector('[data-height-in]');
    var cmInput = root.querySelector('[data-height-cm-input]');
    var weight = root.querySelector('[data-weight-kg]');
    var preview = root.querySelector('[data-bmi-preview]');
    var unit = 'ft';
    try { unit = localStorage.getItem(UNIT_KEY) === 'cm' ? 'cm' : 'ft'; } catch (e) {}

    function heightCm() {
      if (unit === 'cm') return num(cmInput);
      var f = num(ft), i = num(inch);
      if (f === null && i === null) return null;
      return Math.round(((f || 0) * 30.48 + (i || 0) * 2.54) * 10) / 10;
    }

    function fillFromCm(cm) {
      if (cm === null || cm === undefined || cm === '') return;
      cm = parseFloat(cm);
      if (isNaN(cm)) return;
      cmInput.value = Math.round(cm * 10) / 10;  // keep e.g. 175.3 exact when switching units
      var totalIn = Math.round(cm / 2.54);
      ft.value = Math.floor(totalIn / 12);
      inch.value = totalIn % 12;
    }

    function setUnit(next) {
      var cm = heightCm();
      unit = next;
      try { localStorage.setItem(UNIT_KEY, unit); } catch (e) {}
      root.querySelectorAll('[data-height-unit]').forEach(function (b) {
        var on = b.dataset.heightUnit === unit;
        b.classList.toggle('active', on);
        b.setAttribute('aria-pressed', String(on));
      });
      root.querySelectorAll('[data-height-mode]').forEach(function (g) {
        g.style.display = g.dataset.heightMode === unit ? '' : 'none';
      });
      // Only the visible height box may be required (a hidden required field blocks the form)
      var required = root.dataset.bodyMetrics === 'required';
      ft.required = required && unit === 'ft';
      cmInput.required = required && unit === 'cm';
      fillFromCm(cm);  // keep the same height when switching units
      update();
    }

    // Returns null when OK (or when nothing to check yet), otherwise a message
    function problem() {
      var cm = heightCm(), kg = num(weight);
      if (cm === null || kg === null) return null;
      var bmi = kg / Math.pow(cm / 100, 2);
      if (cm < LIMITS.minCm || cm > LIMITS.maxCm || kg < LIMITS.minKg || kg > LIMITS.maxKg ||
          bmi < LIMITS.minBmi || bmi > LIMITS.maxBmi) {
        return "These numbers don't look right. Please check your height and weight and enter the correct values.";
      }
      return null;
    }

    function update() {
      var cm = heightCm(), kg = num(weight);
      hidden.value = cm === null ? '' : cm;
      if (!preview) return;
      var err = problem();
      if (cm === null || kg === null) {
        preview.className = 'bmi-preview';
        preview.innerHTML = '<i class="fa-solid fa-calculator"></i> Enter your height and weight to see your BMI.';
      } else if (err) {
        preview.className = 'bmi-preview bad';
        preview.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + err;
      } else {
        var bmi = kg / Math.pow(cm / 100, 2), c = category(bmi);
        preview.className = 'bmi-preview ' + c.tone;
        preview.innerHTML = '<i class="fa-solid fa-heart-pulse"></i> Your BMI is <b>' + bmi.toFixed(1) + '</b> · ' + c.label;
      }
    }

    root.querySelectorAll('[data-height-unit]').forEach(function (b) {
      b.addEventListener('click', function () { setUnit(b.dataset.heightUnit); });
    });
    [ft, inch, cmInput, weight].forEach(function (el) { el && el.addEventListener('input', update); });

    fillFromCm(hidden.value);
    setUnit(unit);

    root.bodyMetrics = {
      // true if OK to submit; otherwise shows the warning and focuses the height field
      validate: function () {
        update();
        if (!problem()) return true;
        (unit === 'cm' ? cmInput : ft).focus();
        if (preview) preview.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return false;
      },
      heightCm: heightCm
    };
  }

  function initAll() {
    document.querySelectorAll('[data-body-metrics]').forEach(init);
  }

  window.BodyMetrics = {
    validate: function (scope) {
      var roots = (scope || document).querySelectorAll('[data-body-metrics]');
      for (var i = 0; i < roots.length; i++) {
        if (roots[i].bodyMetrics && !roots[i].bodyMetrics.validate()) return false;
      }
      return true;
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();
