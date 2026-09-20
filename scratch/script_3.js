
    let progressChart = null;

    function loadProgressData(range, button) {
      // Update active button
      document.querySelectorAll('[data-range]').forEach(btn => {
        btn.classList.remove('active', 'btn-primary-soft');
      });
      button.classList.add('active', 'btn-primary-soft');

      // Fetch data
      fetch(`/api/progress-data?range=${range}`)
        .then(response => response.json())
        .then(data => {
          updateChart(data.labels, data.data);
          updateStats(data.stats);
        })
        .catch(error => {
          console.error('Error loading progress data:', error);
        });
    }

    function updateChart(labels, data) {
      const ctx = document.getElementById('progressChart').getContext('2d');
      
      const computedStyle = getComputedStyle(document.documentElement);
      const accent = computedStyle.getPropertyValue('--accent').trim();
      const accentSoft = computedStyle.getPropertyValue('--accent-soft').trim();
      const textPrimary = computedStyle.getPropertyValue('--text-primary').trim();
      const textSecondary = computedStyle.getPropertyValue('--text-secondary').trim();
      const borderColor = computedStyle.getPropertyValue('--border-color').trim();
      const bgCardHover = computedStyle.getPropertyValue('--bg-card-hover').trim();

      if (progressChart) {
        progressChart.destroy();
      }

      progressChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: 'Distance (km)',
            data: data,
            borderColor: accent,
            backgroundColor: accentSoft,
            tension: 0.1,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: accent,
            pointBorderColor: textPrimary,
            pointBorderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            },
            tooltip: {
              backgroundColor: bgCardHover,
              padding: 12,
              titleColor: textPrimary,
              bodyColor: accent,
              borderColor: accent,
              borderWidth: 1,
              callbacks: {
                label: function (context) {
                  return context.parsed.y + ' km';
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: {
                color: borderColor,
                drawBorder: false
              },
              ticks: {
                color: textSecondary,
                callback: function (value) {
                  return value + ' km';
                }
              }
            },
            x: {
              grid: {
                display: false
              },
              ticks: {
                color: textSecondary
              }
            }
          },
          animation: {
            duration: 750,
            easing: 'easeInOutQuart'
          }
        }
      });
    }

    function updateChartTheme() {
      if (!progressChart) return;
      const computedStyle = getComputedStyle(document.documentElement);
      const accent = computedStyle.getPropertyValue('--accent').trim();
      const accentSoft = computedStyle.getPropertyValue('--accent-soft').trim();
      const textPrimary = computedStyle.getPropertyValue('--text-primary').trim();
      const textSecondary = computedStyle.getPropertyValue('--text-secondary').trim();
      const borderColor = computedStyle.getPropertyValue('--border-color').trim();
      const bgCardHover = computedStyle.getPropertyValue('--bg-card-hover').trim();

      const dataset = progressChart.data.datasets[0];
      dataset.borderColor = accent;
      dataset.backgroundColor = accentSoft;
      dataset.pointBackgroundColor = accent;
      dataset.pointBorderColor = textPrimary;

      const options = progressChart.options;
      options.plugins.tooltip.backgroundColor = bgCardHover;
      options.plugins.tooltip.titleColor = textPrimary;
      options.plugins.tooltip.bodyColor = accent;
      options.plugins.tooltip.borderColor = accent;

      options.scales.y.grid.color = borderColor;
      options.scales.y.ticks.color = textSecondary;
      options.scales.x.ticks.color = textSecondary;

      progressChart.update();
    }

    function updateStats(stats) {
      document.getElementById('stat-total').textContent = stats.total;
      document.getElementById('stat-average').textContent = stats.average;
      document.getElementById('stat-best').textContent = stats.best;
      document.getElementById('stat-active').textContent = stats.active_days;
    }

    // Load week data on page load
    document.addEventListener('DOMContentLoaded', function () {
      loadProgressData('week', document.querySelector('[data-range="week"]'));
    });
  