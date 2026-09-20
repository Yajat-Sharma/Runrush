
    let paceTrendChart = null;

    // Format decimal pace (min/km) → "MM:SS /km"
    function fmtPace(decPace) {
      const mins = Math.floor(decPace);
      const secs = Math.round((decPace - mins) * 60);
      return `${mins}:${String(secs).padStart(2, '0')} /km`;
    }

    function loadPaceTrend() {
      fetch('/api/analytics/pace-trend', { cache: 'no-cache' })
        .then(r => r.json())
        .then(data => {
          const cs = getComputedStyle(document.documentElement);
          const accent      = cs.getPropertyValue('--accent').trim();
          const accentLime  = cs.getPropertyValue('--accent-lime').trim() || '#b0ff4f';
          const borderColor = cs.getPropertyValue('--border-color').trim();
          const textSec     = cs.getPropertyValue('--text-secondary').trim();
          const bgCard      = cs.getPropertyValue('--bg-card').trim();
          const danger      = cs.getPropertyValue('--danger').trim() || '#ff6b6b';

          // Update trend badge with magnitude and data-sufficiency guard
          const badge = document.getElementById('paceTrendBadge');
          if (!data.labels || data.labels.length === 0) {
            badge.textContent = 'Not enough data for a trend';
            badge.style.background = 'rgba(255,255,255,0.06)';
            badge.style.border = '1px solid rgba(255,255,255,0.12)';
            badge.style.color = textSec;
            return;
          }

          // Need at least 3 data points and a meaningful slope to state a conclusion
          const n = data.n || 0;
          const slopeSecPerRun = data.slope_sec_per_km || 0; // sec/km change per run-index step
          const isSignificant  = Math.abs(slopeSecPerRun) >= 0.5; // ≥ 0.5 sec/km per run

          if (n < 3) {
            badge.textContent = 'Not enough data for a trend';
            badge.style.background = 'rgba(255,255,255,0.06)';
            badge.style.border = '1px solid rgba(255,255,255,0.12)';
            badge.style.color = textSec;
          } else if (data.improving) {
            if (isSignificant) {
              const secDisplay = Math.abs(slopeSecPerRun).toFixed(1);
              badge.textContent = `Getting Faster · ~${secDisplay} sec/km per run`;
            } else {
              badge.textContent = 'Pace Holding Steady (slight improvement)';
            }
            badge.style.background = 'rgba(176,255,79,0.12)';
            badge.style.border = '1px solid rgba(176,255,79,0.3)';
            badge.style.color = accentLime;
          } else {
            if (isSignificant) {
              const secDisplay = Math.abs(slopeSecPerRun).toFixed(1);
              badge.textContent = `Pace Slowing · ~${secDisplay} sec/km per run`;
            } else {
              badge.textContent = 'Pace Holding Steady (slight slowdown)';
            }
            badge.style.background = 'rgba(255,107,107,0.12)';
            badge.style.border = '1px solid rgba(255,107,107,0.3)';
            badge.style.color = danger;
          }

          const trendColor = data.improving ? accentLime : danger;

          const ctx = document.getElementById('paceTrendChart').getContext('2d');
          if (paceTrendChart) paceTrendChart.destroy();

          paceTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
              labels: data.labels,
              datasets: [
                {
                  label: 'Actual Pace',
                  data: data.paces,
                  borderColor: accent,
                  backgroundColor: 'rgba(0,242,255,0.07)',
                  tension: 0.1,
                  fill: true,
                  pointRadius: data.paces.length > 30 ? 2 : 4,
                  pointHoverRadius: 6,
                  pointBackgroundColor: accent,
                  borderWidth: 2,
                },
                {
                  label: 'Trend',
                  data: data.trend,
                  borderColor: trendColor,
                  borderWidth: 2,
                  borderDash: [6, 4],
                  pointRadius: 0,
                  fill: false,
                  tension: 0,
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
                  filter: item => item.datasetIndex === 0, // Only show tooltip for actual pace
                  callbacks: {
                    label: ctx => `Pace: ${fmtPace(ctx.parsed.y)}`
                  }
                }
              },
              scales: {
                y: {
                  reverse: false,
                  grid: { color: borderColor, drawBorder: false },
                  ticks: {
                    color: textSec,
                    callback: v => fmtPace(v)
                  }
                },
                x: {
                  grid: { display: false },
                  ticks: {
                    color: textSec,
                    maxTicksLimit: 10,
                    maxRotation: 45,
                  }
                }
              },
              animation: { duration: 700, easing: 'easeOutQuart' }
            }
          });
        })
        .catch(err => console.error('Pace trend error:', err));
    }
  