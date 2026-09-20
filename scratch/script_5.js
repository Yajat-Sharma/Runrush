
    let monthlyCompareChart = null;

    function loadMonthlyComparison() {
      fetch('/api/analytics/monthly-comparison', { cache: 'no-cache' })
        .then(r => r.json())
        .then(data => {
          const cs = getComputedStyle(document.documentElement);
          const accent      = cs.getPropertyValue('--accent').trim();
          const borderColor = cs.getPropertyValue('--border-color').trim();
          const textSec     = cs.getPropertyValue('--text-secondary').trim();
          const bgCard      = cs.getPropertyValue('--bg-card').trim();

          // Update legend labels
          document.getElementById('thisMonthLegend').textContent = data.this_month_name + ' (this month)';
          document.getElementById('lastMonthLegend').textContent = data.last_month_name + ' (last month)';

          // Update delta badge
          const badge = document.getElementById('monthlyDeltaBadge');
          const delta = data.delta;
          const absDelta = Math.abs(delta).toFixed(1);
          if (delta > 0) {
            badge.textContent = `+${absDelta} km vs ${data.last_month_name}`;
            badge.style.background = 'rgba(176,255,79,0.12)';
            badge.style.border = '1px solid rgba(176,255,79,0.3)';
            badge.style.color = '#b0ff4f';
          } else if (delta < 0) {
            badge.textContent = `−${absDelta} km vs ${data.last_month_name}`;
            badge.style.background = 'rgba(255,107,107,0.12)';
            badge.style.border = '1px solid rgba(255,107,107,0.3)';
            badge.style.color = '#ff6b6b';
          } else {
            badge.textContent = `Same as ${data.last_month_name}`;
            badge.style.background = 'rgba(255,255,255,0.06)';
            badge.style.border = '1px solid rgba(255,255,255,0.12)';
            badge.style.color = textSec;
          }

          // Update totals line below the badge
          const totalsEl = document.getElementById('monthlyTotalsLine');
          if (totalsEl) {
            totalsEl.textContent = `${data.this_month_name}: ${data.this_total} km • ${data.last_month_name}: ${data.last_total} km`;
          }

          const ctx = document.getElementById('monthlyCompareChart').getContext('2d');
          if (monthlyCompareChart) monthlyCompareChart.destroy();

          monthlyCompareChart = new Chart(ctx, {
            type: 'bar',
            data: {
              labels: data.labels,
              datasets: [
                {
                  label: data.this_month_name,
                  data: data.this_month,
                  backgroundColor: 'rgba(0,242,255,0.65)',
                  borderColor: 'rgba(0,242,255,0.9)',
                  borderWidth: 1.5,
                  borderRadius: 6,
                  borderSkipped: false,
                },
                {
                  label: data.last_month_name,
                  data: data.last_month,
                  backgroundColor: 'rgba(255,255,255,0.12)',
                  borderColor: 'rgba(255,255,255,0.25)',
                  borderWidth: 1.5,
                  borderRadius: 6,
                  borderSkipped: false,
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false },
                tooltip: {
                  backgroundColor: bgCard || '#1a1f2e',
                  padding: 12,
                  titleColor: '#fff',
                  bodyColor: accent,
                  borderColor: accent,
                  borderWidth: 1,
                  callbacks: {
                    label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y} km`
                  }
                }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  grid: { color: borderColor, drawBorder: false },
                  ticks: {
                    color: textSec,
                    callback: v => v + ' km'
                  }
                },
                x: {
                  grid: { display: false },
                  ticks: { color: textSec }
                }
              },
              animation: { duration: 700, easing: 'easeOutQuart' }
            }
          });
        })
        .catch(err => console.error('Monthly comparison error:', err));
    }
  