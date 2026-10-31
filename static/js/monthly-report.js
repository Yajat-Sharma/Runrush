(() => {
  const modal = document.getElementById('monthlyReportModal');
  if (!modal) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  const previousFocus = { element: null };
  let report = null;

  const $ = (id) => document.getElementById(id);
  const formatPace = (pace) => pace == null ? '—' : `${Number(pace).toFixed(2)} min/km`;
  const formatChange = (comparison, lowerIsBetter = false) => {
    if (!comparison || comparison.percentage == null) return 'No prior data';
    const sign = comparison.percentage > 0 ? '+' : '';
    const direction = lowerIsBetter
      ? (comparison.delta < 0 ? 'improved' : comparison.delta > 0 ? 'slower' : 'unchanged')
      : (comparison.delta > 0 ? 'up' : comparison.delta < 0 ? 'down' : 'unchanged');
    return `${sign}${comparison.percentage}% · ${direction}`;
  };

  function show(data) {
    report = data;
    const metrics = data.metrics;
    $('monthlyReportMonth').textContent = data.month_label;
    $('monthlyReportHeadline').textContent =
      `${metrics.total_distance_km.toFixed(1)} km of momentum`;
    $('monthlyReportDistance').textContent = `${metrics.total_distance_km.toFixed(1)} km`;
    $('monthlyReportRuns').textContent = metrics.run_count;
    $('monthlyReportPace').textContent = formatPace(metrics.average_pace_min_per_km);
    $('monthlyReportLongest').textContent = `${metrics.longest_run_km.toFixed(1)} km`;
    $('monthlyReportConsistency').textContent = `${metrics.consistency_percentage}%`;
    $('monthlyReportDistanceChange').textContent = formatChange(data.comparisons.total_distance_km);
    $('monthlyReportRunsChange').textContent = formatChange(data.comparisons.run_count);
    $('monthlyReportPaceChange').textContent = formatChange(data.comparisons.average_pace_min_per_km, true);
    const best = metrics.best_run;
    $('monthlyReportBest').textContent = best
      ? `${best.distance_km.toFixed(1)} km · ${formatPace(best.pace_min_per_km)} · ${best.date.slice(0, 10)}`
      : 'No qualifying best run this month';
    previousFocus.element = document.activeElement;
    modal.hidden = false;
    document.body.classList.add('monthly-report-open');
    $('monthlyReportView').focus();
  }

  async function action(name) {
    const response = await fetch('/api/monthly-report/action', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify({ action: name })
    });
    if (!response.ok) throw new Error('Could not save monthly report preference.');
  }

  async function close(name) {
    try {
      await action(name);
      modal.hidden = true;
      document.body.classList.remove('monthly-report-open');
      previousFocus.element?.focus();
    } catch (error) {
      $('monthlyReportError').textContent = error.message;
    }
  }

  $('monthlyReportView').addEventListener('click', () => close('view'));
  $('monthlyReportDismiss').addEventListener('click', () => close('dismiss'));
  $('monthlyReportRemind').addEventListener('click', () => close('remind'));
  modal.addEventListener('click', (event) => {
    if (event.target === modal) close('dismiss');
  });
  modal.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close('dismiss');
    } else if (event.key === 'Tab') {
      const focusable = modal.querySelectorAll('button:not([disabled])');
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  fetch('/api/monthly-report/prompt', { credentials: 'same-origin' })
    .then((response) => response.ok ? response.json() : null)
    .then((data) => {
      if (data?.available) show(data.report);
    })
    .catch(() => {});
})();
