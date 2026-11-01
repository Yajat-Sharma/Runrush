(() => {
  const modal = document.getElementById('monthlyReportModal');
  if (!modal) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  const previousFocus = { element: null };
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const now = new Date();
  const localDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const $ = (id) => document.getElementById(id);
  const formatPace = (pace) => pace == null ? '--' : `${Number(pace).toFixed(2)} min/km`;
  const formatChange = (comparison, lowerIsBetter = false) => {
    if (!comparison || comparison.percentage == null) return 'No prior data';
    const sign = comparison.percentage > 0 ? '+' : '';
    const direction = lowerIsBetter
      ? (comparison.delta < 0 ? 'improved' : comparison.delta > 0 ? 'slower' : 'unchanged')
      : (comparison.delta > 0 ? 'up' : comparison.delta < 0 ? 'down' : 'unchanged');
    return `${sign}${comparison.percentage}% - ${direction}`;
  };

  function hide() {
    modal.hidden = true;
    document.body.classList.remove('monthly-report-open');
    previousFocus.element?.focus();
  }

  function show(report) {
    const metrics = report.metrics;
    $('monthlyReportMonth').textContent = report.month_label;
    $('monthlyReportStatus').textContent = report.is_live
      ? `Live report - data through ${report.data_through}`
      : `Finalised month - includes data through ${report.data_through}`;
    $('monthlyReportHeadline').textContent = report.has_activity
      ? `${metrics.total_distance_km.toFixed(1)} km of momentum`
      : 'No valid runs logged for this month yet.';
    $('monthlyReportDistance').textContent = `${metrics.total_distance_km.toFixed(1)} km`;
    $('monthlyReportRuns').textContent = metrics.run_count;
    $('monthlyReportPace').textContent = formatPace(metrics.average_pace_min_per_km);
    $('monthlyReportLongest').textContent = `${metrics.longest_run_km.toFixed(1)} km`;
    $('monthlyReportConsistency').textContent = `${metrics.consistency_percentage}%`;
    $('monthlyReportDistanceChange').textContent = formatChange(report.comparisons.total_distance_km);
    $('monthlyReportRunsChange').textContent = formatChange(report.comparisons.run_count);
    $('monthlyReportPaceChange').textContent = formatChange(report.comparisons.average_pace_min_per_km, true);
    const best = metrics.best_run;
    $('monthlyReportBest').textContent = best
      ? `${best.distance_km.toFixed(1)} km - ${formatPace(best.pace_min_per_km)} - ${best.date.slice(0, 10)}`
      : 'No qualifying best run this month';
    previousFocus.element = document.activeElement;
    modal.hidden = false;
    document.body.classList.add('monthly-report-open');
    $('monthlyReportView').focus();
    $('monthlyReportView').onclick = () => {
      const params = new URLSearchParams({year: report.year, month: report.month, timezone, local_date: localDate});
      window.location.assign(`/monthly-report?${params.toString()}`);
    };
  }

  $('monthlyReportLater').addEventListener('click', hide);
  $('monthlyReportOptOut').addEventListener('click', async () => {
    const button = $('monthlyReportOptOut');
    button.disabled = true;
    try {
      const response = await fetch('/api/monthly-report/action', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
        body: JSON.stringify({action: 'opt_out'})
      });
      if (!response.ok) throw new Error('Could not save this preference. Please try again.');
      hide();
    } catch (error) {
      $('monthlyReportError').textContent = error.message;
      button.disabled = false;
    }
  });
  modal.addEventListener('click', (event) => { if (event.target === modal) hide(); });
  modal.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      hide();
    } else if (event.key === 'Tab') {
      const focusable = modal.querySelectorAll('button:not([disabled])');
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  const params = new URLSearchParams({timezone, local_date: localDate});
  fetch(`/api/monthly-report/prompt?${params.toString()}`, {credentials: 'same-origin'})
    .then((response) => response.ok ? response.json() : null)
    .then((data) => { if (data?.available) show(data.report); })
    .catch(() => {});
})();
