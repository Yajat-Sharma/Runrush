/* --- New Script Block --- */
(function() {
      const storedTheme = localStorage.getItem('theme');
      const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
      const theme = storedTheme || (prefersLight ? 'light' : 'dark');
      document.documentElement.setAttribute('data-theme', theme);
      if (theme === 'light') {
        document.getElementById('themeColorMeta').setAttribute('content', '#F0F4F8');
      }
    })();

/* --- New Script Block --- */


/* --- New Script Block --- */
document.getElementById('weeklyLeaderboardCard').addEventListener('click', function () {
          const rest = document.getElementById('lb-rest');
          const chevron = document.getElementById('lbChevron');
          if (rest) {
            rest.classList.toggle('d-none');
            chevron.classList.toggle('rotated');
          }
        });

/* --- New Script Block --- */


/* --- New Script Block --- */


/* --- New Script Block --- */
const body = document.body;
    const themeToggleBtn = document.getElementById("themeToggle");
    const runsTable = document.getElementById("runsTable");

    // ── SIDEBAR NAVIGATION HELPER ──
    // Opens the target collapse section and smoothly scrolls to it
    function navToSection(sectionId) {
      // Close offcanvas first
      const offcanvasEl = document.getElementById('appMenu');
      const offcanvasInstance = bootstrap.Offcanvas.getInstance(offcanvasEl);
      if (offcanvasInstance) offcanvasInstance.hide();

      // Wait for offcanvas close animation, then open collapse & scroll
      setTimeout(() => {
        const target = document.getElementById(sectionId);
        if (!target) return;

        // If it's a Bootstrap collapse, open it
        if (target.classList.contains('collapse')) {
          const bsCollapse = bootstrap.Collapse.getOrCreateInstance(target, { toggle: false });
          bsCollapse.show();
          // Update chevron icon on the toggle button
          const toggleBtn = document.querySelector(`[data-bs-target="#${sectionId}"]`);
          if (toggleBtn) {
            const chevron = toggleBtn.querySelector('.chevron-icon');
            if (chevron) chevron.classList.add('rotated');
          }
        }

        // Scroll to the section (or its preceding toggle button)
        const scrollTarget = target.previousElementSibling || target;
        scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 350);
    }

    // ── THEME SYSTEM ──
    function applyTheme(theme) {
      if (theme === "light") {
        body.classList.add("light-theme");
        body.classList.remove("text-dark", "bg-light");
        if (runsTable) runsTable.classList.remove("table-dark");
        if (themeToggleBtn) themeToggleBtn.textContent = "🌙 Dark mode";
      } else {
        body.classList.remove("light-theme", "bg-light", "text-dark");
        if (runsTable) runsTable.classList.add("table-dark");
        if (themeToggleBtn) themeToggleBtn.textContent = "☀️ Light mode";
      }
      localStorage.setItem("theme", theme);
    }

    const savedTheme = localStorage.getItem("theme") || "dark";
    applyTheme(savedTheme);

    if (themeToggleBtn) {
      themeToggleBtn.addEventListener("click", () => {
        const current = localStorage.getItem("theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
      });
    }

    // Chevron rotation toggle on collapse events
    document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(button => {
      const target = button.getAttribute('data-bs-target');
      const chevron = button.querySelector('.chevron-icon');
      if (target && chevron) {
        const targetEl = document.querySelector(target);
        if (!targetEl) return;
        targetEl.addEventListener('show.bs.collapse', () => chevron.classList.add('rotated'));
        targetEl.addEventListener('hide.bs.collapse', () => chevron.classList.remove('rotated'));
      }
    });

    // Show run count
    const runCountEl = document.getElementById('runCount');
    if (runCountEl) {
      runCountEl.textContent = document.querySelectorAll('#runsTable tbody tr').length;
    }

    // Pace live calculation and hints
    function updatePaceDisplay() {
      const d = parseFloat(document.getElementById('distanceInput')?.value);
      const t = parseFloat(document.getElementById('minutes')?.value);
      if (!isNaN(d) && d > 0 && !isNaN(t) && t > 0) {
        const pace = (t / d).toFixed(2);
        const minutes = Math.floor(pace);
        const seconds = Math.round((pace - minutes) * 60);
        document.getElementById('paceDisplay').textContent =
          `${minutes}:${String(seconds).padStart(2, '0')} min/km`;
      }
    }

    const distanceInput = document.getElementById('distanceInput');
    const minutesInput = document.getElementById('minutes');

    if (distanceInput) {
      distanceInput.addEventListener('input', () => {
        const distance = parseFloat(distanceInput.value);
        const hint = document.getElementById('distanceHint');
        if (!isNaN(distance) && distance > 0) {
          if (distance < 2) hint.textContent = 'Short shakeout run';
          else if (distance < 5) hint.textContent = 'Solid daily run';
          else if (distance < 10) hint.textContent = 'Long run vibes';
          else hint.textContent = 'Big session!';
        } else {
          hint.textContent = '';
        }
        updatePaceDisplay();
      });
    }

    if (minutesInput) {
      minutesInput.addEventListener('input', updatePaceDisplay);
    }

    // Form validation
    const addRunForm = document.getElementById('addRunForm');
    if (addRunForm) {
      addRunForm.addEventListener('submit', async function (e) {
        const dateInput = document.getElementById('dateInput');
        const distanceInput = document.getElementById('distanceInput');
        const minutesInput = document.getElementById('minutes');
        const notesInput = document.querySelector('textarea[name="notes"]');
        const formError = document.getElementById('formError');

        // Get today's date in YYYY-MM-DD format
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayStr = today.toISOString().split('T')[0];

        // Validate date
        if (dateInput && dateInput.value) {
          const selectedDate = new Date(dateInput.value + 'T00:00:00');
          if (selectedDate > today) {
            e.preventDefault();
            formError.textContent = 'You cannot log runs for future dates.';
            formError.style.display = 'block';
            dateInput.focus();
            return;
          }
        }

        // Validate distance (positive)
        const distance = parseFloat(distanceInput?.value);
        if (isNaN(distance) || distance <= 0) {
          e.preventDefault();
          formError.textContent = 'Distance must be greater than 0 km.';
          formError.style.display = 'block';
          distanceInput.focus();
          return;
        }

        // Validate duration (positive)
        const duration = parseFloat(minutesInput?.value);
        if (isNaN(duration) || duration <= 0) {
          e.preventDefault();
          formError.textContent = 'Duration must be greater than 0 minutes.';
          formError.style.display = 'block';
          minutesInput.focus();
          return;
        }

        // Validate pace (realistic - max 30 min/km for walking)
        const pace = duration / distance;
        if (pace > 30) {
          e.preventDefault();
          formError.textContent = 'Pace seems unrealistic. Please check your distance and time.';
          formError.style.display = 'block';
          return;
        }

        // Validate pace (realistic - min 2 min/km for world record)
        if (pace < 2) {
          e.preventDefault();
          formError.textContent = 'Pace seems too fast. Please check your distance and time.';
          formError.style.display = 'block';
          return;
        }

        // Check if offline — intercept and save to IndexedDB instead
        if (!navigator.onLine) {
          e.preventDefault();
          const date = dateInput?.value || todayStr;
          const notes = notesInput?.value || '';
          try {
            await saveOfflineRun({ date: date, distance: distance, time: duration, notes: notes });
            formError.className = 'alert alert-success';
            formError.textContent = 'Run saved offline. Will sync when online.';
            formError.style.display = 'block';
            await updateOfflineRunsUI();
            setTimeout(() => {
              const modal = bootstrap.Modal.getInstance(document.getElementById('addRunModal'));
              if (modal) modal.hide();
              document.getElementById('addRunForm').reset();
              formError.style.display = 'none';
              formError.className = 'alert alert-danger';
            }, 2000);
          } catch (error) {
            console.error('Error saving offline run:', error);
            formError.textContent = 'Failed to save offline run: ' + error.message;
            formError.style.display = 'block';
          }
          return;
        }

        // Online — allow normal form submission to POST /add
        formError.style.display = 'none';
      });

      // Real-time date validation
      const dateInput = document.getElementById('dateInput');
      if (dateInput) {
        dateInput.addEventListener('change', function () {
          const dateError = document.getElementById('dateError');
          const today = new Date();
          today.setHours(0, 0, 0, 0);

          if (this.value) {
            const selectedDate = new Date(this.value + 'T00:00:00');
            if (selectedDate > today) {
              dateError.style.display = 'block';
              this.value = '';
            } else {
              dateError.style.display = 'none';
            }
          }
        });
      }
    }
    // ── RUN TYPE SELECTOR HIGHLIGHT ──
    document.querySelectorAll('#runTypeSelector label').forEach(label => {
      label.addEventListener('click', () => {
        document.querySelectorAll('#runTypeSelector label').forEach(l => l.style.outline = '');
        label.style.outline = '2px solid white';
        label.style.outlineOffset = '2px';
        // Suggest run type based on pace
        suggestRunType();
      });
    });

    function suggestRunType() {
      const d = parseFloat(document.getElementById('distanceInput')?.value);
      const t = parseFloat(document.getElementById('minutes')?.value);
      const hint = document.getElementById('runTypePaceSuggestion');
      if (!isNaN(d) && d > 0 && !isNaN(t) && t > 0) {
        const pace = t / d;
        let suggestion = '';
        if (pace < 4)        suggestion = 'Elite speed pace — Race or Interval?';
        else if (pace < 4.5) suggestion = 'Threshold pace — Tempo or Race?';
        else if (pace < 5.5) suggestion = 'Solid pace — Tempo or Long Run?';
        else if (pace < 7)   suggestion = 'Aerobic pace — Easy or Long Run?';
        else                 suggestion = 'Recovery pace — Easy day?';
        if (hint) hint.textContent = suggestion;
      }
    }

    // ── PACE ZONE BADGES ──
    function getPaceZone(pace) {
      if (pace <= 0) return null;
      if (pace < 4)   return { cls: 'pz-5', label: 'Z5 Speed' };
      if (pace < 5)   return { cls: 'pz-4', label: 'Z4 Threshold' };
      if (pace < 6)   return { cls: 'pz-3', label: 'Z3 Tempo' };
      if (pace < 7)   return { cls: 'pz-2', label: 'Z2 Aerobic' };
      return               { cls: 'pz-1', label: 'Z1 Easy' };
    }
    document.querySelectorAll('.pz-badge').forEach(span => {
      const pace = parseFloat(span.dataset.pace);
      const zone = getPaceZone(pace);
      if (zone) {
        span.classList.add(zone.cls);
        span.textContent = zone.label;
      } else {
        span.remove();
      }
    });

/* --- New Script Block --- */


/* --- New Script Block --- */
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

/* --- New Script Block --- */
function loadInsights() {
      const container = document.getElementById('insightsContainer');
      const loading = document.getElementById('insightsLoading');
      const empty = document.getElementById('insightsEmpty');
      if (!container) return;

      // Show loading state
      if (loading) loading.style.display = '';
      if (empty) empty.style.display = 'none';

      fetch('/api/analytics/insights')
        .then(r => r.json())
        .then(data => {
          if (loading) loading.style.display = 'none';
          const insights = data.insights || [];
          if (insights.length === 0) {
            container.innerHTML = '';
            if (empty) empty.style.display = '';
            return;
          }
          if (empty) empty.style.display = 'none';
          container.innerHTML = insights.map(i => `
            <div class="col-12 col-md-6">
              <div class="insight-item d-flex align-items-start gap-2">
                <span class="insight-icon">${i.icon}</span>
                <div>
                  <div class="insight-title">${i.title}</div>
                  <div class="insight-desc">${i.description}</div>
                </div>
              </div>
            </div>
          `).join('');
        })
        .catch(() => {
          if (loading) loading.style.display = 'none';
          container.innerHTML = '<div class="col-12 text-center text-muted py-2">Could not load insights.</div>';
        });
    }

/* --- New Script Block --- */
let monthlyCompareChart = null;

    function loadMonthlyComparison() {
      fetch('/api/analytics/monthly-comparison')
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

/* --- New Script Block --- */
let paceTrendChart = null;

    // Format decimal pace (min/km) → "MM:SS /km"
    function fmtPace(decPace) {
      const mins = Math.floor(decPace);
      const secs = Math.round((decPace - mins) * 60);
      return `${mins}:${String(secs).padStart(2, '0')} /km`;
    }

    function loadPaceTrend() {
      fetch('/api/analytics/pace-trend')
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

/* --- New Script Block --- */


/* --- New Script Block --- */


/* --- New Script Block --- */


/* --- New Script Block --- */
// ──────────────────────────────────────────────
  // FEATURE 3: MOTIVATIONAL QUOTE OF THE DAY
  // ──────────────────────────────────────────────
  const QUOTES = [
    { text: "The miracle isn't that I finished. The miracle is that I had the courage to start.", author: "– John Bingham" },
    { text: "Run when you can, walk if you have to, crawl if you must; just never give up.", author: "– Dean Karnazes" },
    { text: "Most people never run far enough on their first wind to find out they've got a second.", author: "– William James" },
    { text: "If you run, you are a runner. It doesn't matter how fast or how far.", author: "– John Bingham" },
    { text: "Pain is inevitable. Suffering is optional.", author: "– Haruki Murakami" },
    { text: "The obsession with running is really an obsession with the potential for more and more life.", author: "– George Sheehan" },
    { text: "Every morning in Africa, a gazelle wakes up knowing it must run faster than the fastest lion.", author: "– African Proverb" },
    { text: "Running is the greatest metaphor for life, because you get out of it what you put into it.", author: "– Oprah Winfrey" },
    { text: "Ask yourself: Can I give more? The answer is usually: Yes.", author: "– Paul Tergat" },
    { text: "It's very hard in the beginning to understand that the whole idea is not to beat the other runners... Eventually you learn that the competition is against the little voice inside you.", author: "– George Sheehan" },
    { text: "Running is nothing more than a series of arguments between the part of your brain that wants to stop and the part that wants to keep going.", author: "– Anonymous" },
    { text: "Don't dream of winning, train for it!", author: "– Mo Farah" },
    { text: "Your body will argue that there is no justifiable reason to continue. Your only recourse is to call on your spirit.", author: "– Tim Noakes" },
    { text: "If you're tired of starting over, stop giving up.", author: "– Anonymous" },
    { text: "The road to victory is paved with miles.", author: "– Anonymous" },
    { text: "Believe that you can run farther or faster. Believe that you're young enough, old enough, strong enough.", author: "– John Bingham" },
    { text: "Champions are not made in gyms. Champions are made from something they have deep inside them — a desire, a dream, a vision.", author: "– Muhammad Ali" },
    { text: "You don't have to go fast. You just have to go.", author: "– Anonymous" },
    { text: "Strive for progress, not perfection.", author: "– Anonymous" },
    { text: "The only bad run is the one that didn't happen.", author: "– Anonymous" },
  ];

  (function initQuote() {
    const today = new Date().toDateString();
    const idx = [...today].reduce((acc, c) => acc + c.charCodeAt(0), 0) % QUOTES.length;
    const q = QUOTES[idx];
    document.getElementById('quoteText').textContent = '\u201c' + q.text + '\u201d';
    document.getElementById('quoteAuthor').textContent = q.author;
    if (document.getElementById('drawerQuoteText')) {
      document.getElementById('drawerQuoteText').textContent = '\u201c' + q.text + '\u201d';
      document.getElementById('drawerQuoteAuthor').textContent = q.author;
    }
  })();

  // ──────────────────────────────────────────────
  // FEATURE 6: LIVE STOPWATCH
  // ──────────────────────────────────────────────
  let swInterval = null;
  let swRunning = false;
  let swSeconds = 0;

  function toggleStopwatch() {
    const btn = document.getElementById('swToggleBtn');
    const panel = document.getElementById('swPanel');
    const minutesInput = document.getElementById('minutes');

    if (!swRunning) {
      // Start
      swRunning = true;
      swSeconds = 0;
      panel.style.display = 'block';
      btn.textContent = 'Stop Timer';
      btn.style.borderColor = 'rgba(255,107,107,0.5)';
      btn.style.color = '#ff6b6b';
      swInterval = setInterval(() => {
        swSeconds++;
        const mm = String(Math.floor(swSeconds / 60)).padStart(2, '0');
        const ss = String(swSeconds % 60).padStart(2, '0');
        document.getElementById('swDisplay').textContent = mm + ':' + ss;
      }, 1000);
    } else {
      // Stop
      swRunning = false;
      clearInterval(swInterval);
      btn.textContent = 'Start Timer';
      btn.style.borderColor = '';
      btn.style.color = '';
      // Auto-fill minutes field
      const mins = (swSeconds / 60).toFixed(2);
      if (minutesInput) {
        minutesInput.value = mins;
        minutesInput.dispatchEvent(new Event('input'));
      }
    }
  }

  // Reset stopwatch when modal closes
  document.getElementById('addRunModal')?.addEventListener('hidden.bs.modal', () => {
    if (swRunning) toggleStopwatch();
    swSeconds = 0;
    document.getElementById('swDisplay').textContent = '00:00';
    document.getElementById('swPanel').style.display = 'none';
  });

  // ──────────────────────────────────────────────
  // FEATURE 4: GITHUB-STYLE HEATMAP
  // ──────────────────────────────────────────────
  function buildHeatmap(days) {
    const grid = document.getElementById('heatmapGrid');
    const monthsEl = document.getElementById('heatmapMonths');
    if (!grid) return;
    grid.innerHTML = '';
    monthsEl.innerHTML = '';

    // Pad so first day aligns to Sunday=0
    const firstDate = new Date(days[0].date + 'T00:00:00');
    const firstDow = firstDate.getDay(); // Sun=0

    let week = document.createElement('div');
    week.className = 'heatmap-week';

    // Empty cells before first day
    for (let i = 0; i < firstDow; i++) {
      const empty = document.createElement('div');
      empty.className = 'heatmap-cell';
      empty.style.visibility = 'hidden';
      week.appendChild(empty);
    }

    let weekNum = 0;
    let lastMonth = -1;
    const monthLabels = [];

    days.forEach((d, i) => {
      const dt = new Date(d.date + 'T00:00:00');
      const dow = dt.getDay(); // Sun=0

      // Month label tracking
      if (dt.getMonth() !== lastMonth) {
        monthLabels.push({ weekIdx: weekNum, name: dt.toLocaleString('en', { month: 'short' }) });
        lastMonth = dt.getMonth();
      }

      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      const km = d.km;
      if      (km >= 6) cell.classList.add('hm-4');
      else if (km >= 3) cell.classList.add('hm-3');
      else if (km >= 1) cell.classList.add('hm-2');
      else if (km > 0)  cell.classList.add('hm-1');

      cell.title = d.date + (km > 0 ? ' — ' + km + ' km' : ' — rest day');
      week.appendChild(cell);

      if (dow === 6) {
        grid.appendChild(week);
        week = document.createElement('div');
        week.className = 'heatmap-week';
        weekNum++;
      }
    });
    // Last partial week
    if (week.children.length > 0) grid.appendChild(week);

    // Month labels
    const totalWeeks = weekNum + 1;
    const cellW = 15; // 12px + 3px gap
    monthLabels.forEach((ml, i) => {
      // If the NEXT month label is less than 3 weeks away, skip THIS label.
      // This ensures we skip the partial starting month rather than the first full month.
      if (i < monthLabels.length - 1 && monthLabels[i + 1].weekIdx - ml.weekIdx < 3) {
        return;
      }
      const span = document.createElement('span');
      span.textContent = ml.name;
      span.style.paddingLeft = (ml.weekIdx * cellW) + 'px';
      span.style.position = 'absolute';
      monthsEl.appendChild(span);
    });
    monthsEl.style.position = 'relative';
    monthsEl.style.height = '16px';
  }

  fetch('/api/heatmap-data')
    .then(r => r.json())
    .then(data => buildHeatmap(data.days))
    .catch(() => {});

  // ──────────────────────────────────────────────
  // FEATURE 5: MILESTONE RINGS
  // ──────────────────────────────────────────────
  const MILESTONES = [
    { label: '5K',          dist: 5,    color: '#b0ff4f', emoji: '🟢' },
    { label: '10K',         dist: 10,   color: '#00f2ff', emoji: '🔵' },
    { label: 'Half (21K)', dist: 21.1,  color: '#c084fc', emoji: '🟣' },
    { label: 'Marathon',   dist: 42.2,  color: '#ff6e3a', emoji: '🟠' },
    { label: 'Ultra 50K',  dist: 50,    color: '#ff5858', emoji: '🔴' },
  ];

  async function fetchPrediction() {
    try {
      const res = await fetch('/api/predict-next-run');
      const data = await res.json();
      
      const valEl = document.getElementById('predictionValue');
      const msgEl = document.getElementById('predictionMessage');
      
      if (!valEl || !msgEl) return;
      
      if (data.error) {
        valEl.textContent = '-- km';
        msgEl.textContent = 'Prediction temporarily unavailable';
        return;
      }
      
      if (data.prediction_km === null) {
        valEl.textContent = '-- km';
        msgEl.textContent = 'Log more runs to unlock predictions';
        return;
      }
      
      valEl.textContent = data.prediction_km + ' km';
      if (data.method === 'ml') {
        const mae = data.confidence_mae !== null ? data.confidence_mae : 0;
        msgEl.textContent = 'Based on your training pattern (±' + mae + ' km)';
      } else {
        msgEl.textContent = 'Estimate based on recent runs — log a few more for AI predictions';
      }
    } catch (e) {
      console.error('Error fetching prediction:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', fetchPrediction);

  function buildMilestoneRings(allTimeDist) {
    const container = document.getElementById('milestoneRings');
    if (!container) return;
    container.innerHTML = '';

    MILESTONES.forEach(m => {
      const pct = Math.min(100, (allTimeDist / m.dist) * 100);
      const unlocked = allTimeDist >= m.dist;
      const r = 30, cx = 38, cy = 38, strokeW = 6;
      const circumference = 2 * Math.PI * r;
      const offset = circumference - (pct / 100) * circumference;

      const wrap = document.createElement('div');
      wrap.className = 'milestone-ring-wrap';
      wrap.innerHTML = `
        <svg class="ring-svg" width="76" height="76" viewBox="0 0 76 76">
          <circle class="ring-bg" cx="${cx}" cy="${cy}" r="${r}" stroke-width="${strokeW}"/>
          <circle class="ring-fill" cx="${cx}" cy="${cy}" r="${r}"
            stroke="${unlocked ? m.color : 'rgba(255,255,255,0.15)' }"
            stroke-width="${strokeW}"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"
            transform="rotate(-90 ${cx} ${cy})"/>
          <text x="${cx}" y="${cy+2}" text-anchor="middle" dominant-baseline="middle"
            fill="${unlocked ? m.color : 'rgba(255,255,255,0.3)'}"
            font-size="11" font-weight="700">${unlocked ? '✓' : Math.round(pct) + '%'}</text>
        </svg>
        <span class="milestone-label" style="color:${unlocked ? m.color : 'var(--text-tertiary)'}">${m.emoji} ${m.label}</span>
        <span class="milestone-sub">${allTimeDist >= m.dist ? 'Completed!' : m.dist + ' km'}</span>
      `;
      container.appendChild(wrap);
    });
  }

  // Fetch badge progress for milestone rings
  fetch('/api/badges/progress')
    .then(r => r.json())
    .then(data => buildMilestoneRings(data.total_distance || 0))
    .catch(() => buildMilestoneRings(0));

  // ──────────────────────────────────────────────
  // FEATURE 1: ACHIEVEMENTS / BADGES SHOWCASE
  // ──────────────────────────────────────────────
  const BADGE_DEFS = {
    'FIRST_5K':      { icon: '🏅', name: 'First 5K',         desc: 'Complete a 5K run' },
    'FIRST_10K':     { icon: '🥇', name: 'First 10K',        desc: 'Complete a 10K run' },
    'TOTAL_50KM':    { icon: '🚀', name: '50 KM Club',       desc: 'Run 50km total' },
    'TOTAL_100KM':   { icon: '💯', name: '100 KM Legend',    desc: 'Run 100km total' },
    'STREAK_7DAY':   { icon: '🔥', name: 'Week Warrior',     desc: '7 day running streak' },
    'STREAK_30DAY':  { icon: '⚡', name: 'Month of Miles',   desc: '30 day running streak' },
  };

  // Fallback badge definitions if server has no rows
  const HARDCODED_BADGES = Object.entries(BADGE_DEFS).map(([key, def]) => ({
    key, ...def,
    is_unlocked: false,
    progress: 0, current: 0,
    target: key.includes('5K') ? 5 : key.includes('10K') ? 10 : key.includes('50') ? 50 : key.includes('100') ? 100 : key.includes('7') ? 7 : 30,
    criteria_type: key.startsWith('STREAK') ? 'STREAK' : key.startsWith('TOTAL') ? 'ACCUMULATIVE_DISTANCE' : 'SINGLE_DISTANCE',
  }));

  function renderBadges(badges) {
    const grid = document.getElementById('badgeGrid');
    if (!grid) return;
    if (!badges.length) {
      grid.innerHTML = '<div class="col-12 text-muted text-center small py-3">No badges defined yet. Keep running!</div>';
      return;
    }
    grid.innerHTML = '';
    badges.forEach(b => {
      const def = BADGE_DEFS[b.key] || { icon: '🎖️', name: b.name || b.key, desc: b.description || '' };
      const col = document.createElement('div');
      col.className = 'col-6 col-md-4 col-lg-2';
      const pct = b.progress || 0;
      col.innerHTML = `
        <div class="badge-card ${b.is_unlocked ? 'unlocked' : 'locked'}">
          ${b.is_unlocked ? '<div class="badge-glow"></div>' : ''}
          <span class="badge-icon">${def.icon}</span>
          <div class="badge-name">${def.name}</div>
          <div class="badge-desc">${def.desc}</div>
          <div class="badge-prog">
            <div class="progress" style="height:4px;margin-top:6px;">
              <div class="progress-bar bg-info" style="width:${pct}%"></div>
            </div>
            <small class="text-muted" style="font-size:0.6rem;">${b.current || 0} / ${b.target || '?'} ${b.criteria_type === 'STREAK' ? 'days' : 'km'}</small>
          </div>
          ${b.is_unlocked ? '<div style="position:absolute;top:6px;right:8px;font-size:0.65rem;color:var(--accent);">Unlocked</div>' : ''}
        </div>
      `;
      grid.appendChild(col);
    });
  }

  fetch('/api/badges')
    .then(r => r.json())
    .then(data => {
      if (data.badges && data.badges.length) {
        renderBadges(data.badges);
      } else {
        // No DB badges seeded — show hardcoded with progress from stats
        fetch('/api/badges/progress')
          .then(r => r.json())
          .then(stats => {
            HARDCODED_BADGES.forEach(b => {
              if (b.criteria_type === 'ACCUMULATIVE_DISTANCE') {
                b.current = Math.round(stats.total_distance || 0);
                b.progress = Math.min(100, (b.current / b.target) * 100);
                b.is_unlocked = b.current >= b.target;
              } else if (b.criteria_type === 'STREAK') {
                b.current = stats.current_streak || 0;
                b.progress = Math.min(100, (b.current / b.target) * 100);
                b.is_unlocked = b.current >= b.target;
              }
            });
            renderBadges(HARDCODED_BADGES);
          });
      }
    })
    .catch(() => renderBadges(HARDCODED_BADGES));

  // ──────────────────────────────────────────────
  // CONFETTI on badge unlock
  // ──────────────────────────────────────────────
  function launchConfetti() {
    const colors = ['#00f2ff','#b0ff4f','#ff6e3a','#ff6b6b','#c084fc','#ffffff'];
    for (let i = 0; i < 60; i++) {
      const p = document.createElement('div');
      p.className = 'confetti-piece';
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[Math.floor(Math.random() * colors.length)];
      p.style.animationDuration = (1.5 + Math.random() * 2) + 's';
      p.style.animationDelay = (Math.random() * 0.8) + 's';
      p.style.width = (6 + Math.random() * 6) + 'px';
      p.style.height = (10 + Math.random() * 10) + 'px';
      p.style.transform = 'rotate(' + (Math.random() * 360) + 'deg)';
      document.body.appendChild(p);
      p.addEventListener('animationend', () => p.remove());
    }
  }

  // Check for new badges after page load
  {% if new_badges %}
  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      launchConfetti();
      const badgesWon = {{ new_badges | tojson }};
      if (badgesWon.length) {
        const names = { 'FIRST_5K':'First 5K','FIRST_10K':'First 10K','TOTAL_50KM':'50 KM Club','TOTAL_100KM':'100 KM Legend','STREAK_7DAY':'Week Warrior','STREAK_30DAY':'Month of Miles' };
        const earned = badgesWon.map(k => names[k] || k).join(', ');
        const toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.9);border:1px solid #00f2ff;border-radius:14px;padding:1rem 1.5rem;color:#fff;z-index:9999;text-align:center;animation:slideIn 0.4s ease;max-width:90vw;';
        toast.innerHTML = '<div style="font-size:1.5rem;margin-bottom:0.3rem">Badge Unlocked!</div><div style="color:#00f2ff;font-weight:700;">' + earned + '</div>';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
      }
    }, 600);
  });
  {% endif %}

/* --- New Script Block --- */
// ==========================================
    // DASHBOARD WIDGET SYSTEM
    // ==========================================
    let dashboardSortable = null;
    let dashboardLayout = [];
    
    async function loadDashboardLayout() {
      try {
        const res = await fetch('/api/dashboard-layout');
        if (!res.ok) return;
        dashboardLayout = await res.json();
        renderDashboardLayout();
      } catch (e) {
        console.error("Failed to load dashboard layout", e);
      }
    }
    
    function renderDashboardLayout(editMode = false) {
      const container = document.getElementById('dashboardWidgetContainer');
      const widgets = Array.from(container.children);
      
      // Detach all widgets temporarily
      widgets.forEach(w => w.remove());
      
      // Reattach based on layout order
      dashboardLayout.forEach(item => {
        const widgetEl = widgets.find(w => w.dataset.widget === item.widget_type);
        if (widgetEl) {
          container.appendChild(widgetEl);
          const toggle = widgetEl.querySelector('.widget-toggle');
          if (toggle) toggle.checked = item.visible;
          
          if (editMode) {
            widgetEl.style.display = 'block';
            widgetEl.querySelector('.widget-edit-controls').style.display = 'flex';
            // Optionally hide content for compact sorting
            // widgetEl.querySelector('.widget-content').style.display = 'none';
          } else {
            widgetEl.style.display = (item.visible || item.widget_type === 'quick_start') ? 'block' : 'none';
            widgetEl.querySelector('.widget-edit-controls').style.display = 'none';
            widgetEl.querySelector('.widget-content').style.display = 'block';
          }
        }
      });
      
      // Reattach any widgets not in layout at the bottom (fallback)
      widgets.forEach(w => {
        if (!dashboardLayout.find(item => item.widget_type === w.dataset.widget)) {
          container.appendChild(w);
          if (!editMode) w.style.display = (w.dataset.widget === 'quick_start') ? 'block' : 'none';
        }
      });
    }
    
    function toggleDashboardEditMode() {
      document.querySelector('.edit-dashboard-btn-container').style.display = 'none';
      document.querySelector('.edit-dashboard-actions').style.display = 'block';
      
      renderDashboardLayout(true);
      
      const container = document.getElementById('dashboardWidgetContainer');
      if (!dashboardSortable) {
        dashboardSortable = new Sortable(container, {
          handle: '.drag-handle',
          animation: 150,
          ghostClass: 'sortable-ghost'
        });
      }
    }
    
    function cancelDashboardEditMode() {
      document.querySelector('.edit-dashboard-btn-container').style.display = 'block';
      document.querySelector('.edit-dashboard-actions').style.display = 'none';
      
      if (dashboardSortable) {
        dashboardSortable.destroy();
        dashboardSortable = null;
      }
      
      // Revert to saved layout without saving
      renderDashboardLayout(false);
    }
    
    async function saveDashboardLayout() {
      const container = document.getElementById('dashboardWidgetContainer');
      const widgets = Array.from(container.children);
      
      const newLayout = widgets.map((w, index) => {
        const toggle = w.querySelector('.widget-toggle');
        return {
          widget_type: w.dataset.widget,
          visible: toggle ? toggle.checked : true,
          order: index
        };
      });
      
      try {
        const res = await fetch('/api/dashboard-layout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value
          },
          body: JSON.stringify(newLayout)
        });
        
        if (res.ok) {
          dashboardLayout = newLayout;
          cancelDashboardEditMode(); // exits mode & re-renders
        } else {
          alert('Failed to save layout.');
        }
      } catch (e) {
        console.error(e);
        alert('Error saving layout.');
      }
    }
    
    // Call load on startup
    document.addEventListener('DOMContentLoaded', () => {
      loadDashboardLayout();
    });

/* --- New Script Block --- */
async function handleRunSubmit(event) {
      const dateInput = document.getElementById('dateInput');
      const distanceInput = document.getElementById('distanceInput');
      const minutesInput = document.getElementById('minutes');
      const notesInput = document.querySelector('textarea[name="notes"]');
      const formError = document.getElementById('formError');

      // Get values
      const date = dateInput?.value || new Date().toISOString().split('T')[0];
      const distance = parseFloat(distanceInput?.value);
      const time = parseFloat(minutesInput?.value);
      const notes = notesInput?.value || '';

      // Client-side validation (same as before)
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (dateInput && dateInput.value) {
        const selectedDate = new Date(dateInput.value + 'T00:00:00');
        if (selectedDate > today) {
          event.preventDefault();
          formError.textContent = 'You cannot log runs for future dates.';
          formError.style.display = 'block';
          return false;
        }
      }

      if (isNaN(distance) || distance <= 0) {
        event.preventDefault();
        formError.textContent = 'Distance must be greater than 0 km.';
        formError.style.display = 'block';
        return false;
      }

      if (isNaN(time) || time <= 0) {
        event.preventDefault();
        formError.textContent = 'Duration must be greater than 0 minutes.';
        formError.style.display = 'block';
        return false;
      }

      const pace = time / distance;
      if (pace > 30 || pace < 2) {
        event.preventDefault();
        formError.textContent = 'Pace seems unrealistic. Please check your distance and time.';
        formError.style.display = 'block';
        return false;
      }

      // Check if offline
      if (!navigator.onLine) {
        event.preventDefault();

        try {
          // Save to IndexedDB
          const offlineRun = await saveOfflineRun({
            date: date,
            distance: distance,
            time: time,
            notes: notes
          });

          // Show success message
          formError.className = 'text-success mt-2';
          formError.textContent = 'Run saved offline. Will sync when online.';
          formError.style.display = 'block';

          // Update UI
          await updateOfflineRunsUI();

          // Close modal after 2 seconds
          setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('addRunModal'));
            if (modal) modal.hide();

            // Reset form
            document.getElementById('addRunForm').reset();
            formError.style.display = 'none';
            formError.className = 'text-danger mt-2';
          }, 2000);

        } catch (error) {
          console.error('Error saving offline run:', error);
          formError.textContent = 'Failed to save offline run: ' + error.message;
          formError.style.display = 'block';
        }

        return false;
      }

      // Online - allow normal form submission
      formError.style.display = 'none';
      return true;
    }

/* --- New Script Block --- */
(function () {
      const savedTheme = localStorage.getItem('theme') || '{{ theme }}' || 'dark';
      if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
      }
      window.setTheme = function(theme) {
        localStorage.setItem('theme', theme);
        document.body.classList.toggle('light-theme', theme === 'light');
        if (theme === 'light') {
          document.body.classList.remove('bg-light', 'text-dark');
        }
      };
      window.currentTheme = savedTheme;
    })();

/* --- New Script Block --- */
(function () {
    const notesTextarea = document.querySelector('textarea[name="notes"]');
    if (!notesTextarea) return;

    let dropdown = null;
    let debounceTimer = null;
    let activeIndex = -1;
    let currentItems = [];
    let mentionStart = -1;  // caret position where '@' was typed

    // ── Create dropdown element ──
    function createDropdown() {
      if (dropdown) dropdown.remove();
      dropdown = document.createElement('div');
      dropdown.className = 'mention-dropdown';
      document.body.appendChild(dropdown);
    }

    // ── Position dropdown near caret ──
    function positionDropdown() {
      if (!dropdown) return;
      const rect = notesTextarea.getBoundingClientRect();
      dropdown.style.top  = (rect.bottom + window.scrollY + 4) + 'px';
      dropdown.style.left = (rect.left  + window.scrollX)      + 'px';
    }

    // ── Render suggestions ──
    function renderDropdown(users) {
      if (!dropdown) return;
      dropdown.innerHTML = '';
      activeIndex = -1;
      currentItems = users;

      if (!users.length) {
        closeDropdown();
        return;
      }

      users.forEach((u, i) => {
        const item = document.createElement('div');
        item.className = 'mention-dropdown-item';
        item.innerHTML =
          `<span>👤 <strong>${escHtml(u.display_name)}</strong></span>` +
          `<span class="mdi-username">@${escHtml(u.username)}</span>`;
        item.addEventListener('mousedown', (e) => {
          e.preventDefault();  // prevent textarea blur
          insertMention(u.username);
        });
        dropdown.appendChild(item);
      });

      positionDropdown();
    }

    // ── Insert @username into textarea ──
    function insertMention(username) {
      const val   = notesTextarea.value;
      const caret = notesTextarea.selectionStart;
      // Replace from '@' position to caret with '@username '
      const before = val.slice(0, mentionStart);
      const after  = val.slice(caret);
      const insert = '@' + username + ' ';
      notesTextarea.value = before + insert + after;
      // Move caret after the inserted mention
      const newPos = mentionStart + insert.length;
      notesTextarea.setSelectionRange(newPos, newPos);
      notesTextarea.focus();
      closeDropdown();
    }

    // ── Close dropdown ──
    function closeDropdown() {
      if (dropdown) { dropdown.remove(); dropdown = null; }
      currentItems = [];
      activeIndex = -1;
      mentionStart = -1;
    }

    // ── HTML-escape helper (prevents XSS in dropdown) ──
    function escHtml(str) {
      return (str || '').replace(/[&<>"']/g, c =>
        ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
    }

    // ── Fetch matching users from API (debounced, 300ms) ──
    function searchUsers(query) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetch(`/api/users/search?q=${encodeURIComponent(query)}`)
          .then(r => r.ok ? r.json() : { users: [] })
          .then(data => renderDropdown(data.users || []))
          .catch(() => closeDropdown());
      }, 300);
    }

    // ── Main input handler ──
    notesTextarea.addEventListener('input', function () {
      const val   = this.value;
      const caret = this.selectionStart;

      // Find the last '@' before the caret that starts a word
      let atPos = -1;
      for (let i = caret - 1; i >= 0; i--) {
        const ch = val[i];
        if (ch === '@') { atPos = i; break; }
        // Stop if we hit whitespace without finding '@'
        if (/\s/.test(ch)) break;
      }

      if (atPos === -1) { closeDropdown(); return; }

      const fragment = val.slice(atPos + 1, caret);  // text between '@' and caret
      if (/\s/.test(fragment) || fragment.length === 0) { closeDropdown(); return; }

      mentionStart = atPos;

      // Only create dropdown on first need
      if (!dropdown) createDropdown();
      searchUsers(fragment);
    });

    // ── Keyboard navigation within dropdown ──
    notesTextarea.addEventListener('keydown', function (e) {
      if (!dropdown || !currentItems.length) return;
      const items = dropdown.querySelectorAll('.mention-dropdown-item');

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % items.length;
        items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + items.length) % items.length;
        items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (activeIndex >= 0 && currentItems[activeIndex]) {
          e.preventDefault();
          insertMention(currentItems[activeIndex].username);
        }
      } else if (e.key === 'Escape') {
        closeDropdown();
      }
    });

    // Close on outside click
    document.addEventListener('mousedown', function (e) {
      if (dropdown && !dropdown.contains(e.target) && e.target !== notesTextarea) {
        closeDropdown();
      }
    });

    // Reposition on scroll/resize
    window.addEventListener('scroll', positionDropdown, { passive: true });
    window.addEventListener('resize', positionDropdown, { passive: true });
  })();

/* --- New Script Block --- */
(function () {
    // Server passes whether the user has run today
    const ranToday = {{ ran_today | tojson }};
    const REMINDER_KEY        = 'rr_reminder_enabled';
    const LAST_NOTIFIED_KEY   = 'rr_last_notified';
    const REMINDER_HOUR       = 20;  // 8 PM local time

    const toggle = document.getElementById('reminderToggle');
    if (!toggle) return;

    // ── Load saved preference ──
    const isEnabled = localStorage.getItem(REMINDER_KEY) === 'true';
    toggle.checked = isEnabled;

    // ── Toggle handler ──
    toggle.addEventListener('change', function () {
      const enable = this.checked;
      if (enable) {
        // Request permission first
        if (!('Notification' in window)) {
          alert('Your browser does not support notifications.');
          this.checked = false;
          return;
        }
        Notification.requestPermission().then(perm => {
          if (perm === 'granted') {
            localStorage.setItem(REMINDER_KEY, 'true');
            scheduleReminder();
          } else {
            this.checked = false;
            alert('Notification permission denied. Please allow notifications in your browser settings.');
          }
        });
      } else {
        localStorage.setItem(REMINDER_KEY, 'false');
      }
    });

    // ── Schedule the 8pm check ──
    function scheduleReminder() {
      if (localStorage.getItem(REMINDER_KEY) !== 'true') return;
      if (!('Notification' in window) || Notification.permission !== 'granted') return;

      const now      = new Date();
      const target   = new Date();
      target.setHours(REMINDER_HOUR, 0, 0, 0);

      // If 8pm already passed today, don't schedule (would be tomorrow)
      const msUntil8pm = target - now;
      if (msUntil8pm <= 0) return;

      setTimeout(() => {
        // Re-check at the moment the timer fires
        if (localStorage.getItem(REMINDER_KEY) !== 'true') return;

        // Avoid duplicate notifications on the same day
        const today       = new Date().toDateString();
        const lastNotified = localStorage.getItem(LAST_NOTIFIED_KEY);
        if (lastNotified === today) return;

        // Only notify if user hasn't run today
        // ranToday reflects state at page load; if they ran after load, no big deal
        if (ranToday) return;

        try {
          const n = new Notification('⚡ RunRush Reminder', {
            body: "Don't break your streak! Log today's run before midnight.",
            icon: '/static/favicon.png',
            tag:  'runrush-streak',     // prevents duplicate system notifications
            requireInteraction: false
          });
          n.onclick = () => { window.focus(); n.close(); };
          localStorage.setItem(LAST_NOTIFIED_KEY, today);
        } catch (e) {
          // Silently fail (e.g. notification blocked)
        }
      }, msUntil8pm);
    }

    // Auto-schedule on page load if reminders are enabled
    if (isEnabled && 'Notification' in window && Notification.permission === 'granted') {
      scheduleReminder();
    }
  })();

/* --- New Script Block --- */
document.querySelectorAll('.run-notes-preview').forEach(el => {
    el.addEventListener('click', function () {
      const full = this.dataset.full || '';
      if (this.dataset.expanded === 'true') {
        const short = full.slice(0, 60) + (full.length > 60 ? '\u2026' : '');
        this.textContent = short;
        this.dataset.expanded = 'false';
      } else {
        this.textContent = full;
        this.dataset.expanded = 'true';
      }
    });
  });

/* --- New Script Block --- */
let currentParsedData = null;

    function handleCsvFileSelected(input) {
      const file = input?.files[0];
      const fnEl = document.getElementById('selectedFileName');
      const errEl = document.getElementById('parseErrorAlert');
      if (file) {
        fnEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        fnEl.style.display = 'block';
        if (errEl) errEl.style.display = 'none';
      } else {
        if (fnEl) fnEl.style.display = 'none';
      }
    }

    async function uploadAndParseCsv() {
      const input = document.getElementById('stravaCsvInput');
      const file = input?.files[0];
      const errorEl = document.getElementById('parseErrorAlert');
      const parseBtn = document.getElementById('parseCsvBtn');

      if (!file) {
        errorEl.textContent = 'Please select a CSV file first.';
        errorEl.style.display = 'block';
        return;
      }

      const formData = new FormData();
      formData.append('file', file);

      parseBtn.disabled = true;
      parseBtn.textContent = 'Parsing...';
      errorEl.style.display = 'none';

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/parse-import', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: formData
        });
        const res = await resp.json();

        parseBtn.disabled = false;
        parseBtn.textContent = 'Parse & Preview';

        if (!resp.ok || !res.success) {
          errorEl.textContent = `${res.error || 'Failed to parse file'}`;
          errorEl.style.display = 'block';
          return;
        }

        currentParsedData = res.data;
        renderImportPreview(currentParsedData);

      } catch (err) {
        parseBtn.disabled = false;
        parseBtn.textContent = 'Parse & Preview';
        errorEl.textContent = `Network/Server error: ${err.message}`;
        errorEl.style.display = 'block';
      }
    }

    function renderImportPreview(data) {
      document.getElementById('importStepUpload').style.display = 'none';
      document.getElementById('importStepPreview').style.display = 'block';
      document.getElementById('parseCsvBtn').style.display = 'none';
      document.getElementById('importBackBtn').style.display = 'inline-block';
      
      const confirmBtn = document.getElementById('confirmImportBtn');
      confirmBtn.style.display = 'inline-block';

      document.getElementById('cntTotal').textContent = data.total_rows;
      document.getElementById('cntValid').textContent = data.valid_count;
      document.getElementById('cntDup').textContent = data.duplicate_count;
      document.getElementById('cntSkipped').textContent = data.skipped_non_run_count + data.invalid_count;

      const tbody = document.getElementById('importPreviewTbody');
      tbody.innerHTML = '';

      if (data.valid_count === 0) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'No Valid Runs to Import';
      } else {
        confirmBtn.disabled = false;
        confirmBtn.textContent = `Import ${data.valid_count} Valid Run(s)`;
      }

      data.valid_runs.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${r.date}</td>
          <td>${escapeHtml(r.name)}</td>
          <td>${r.distance} km</td>
          <td>${r.time} min</td>
          <td>${r.pace} min/km</td>
          <td><span class="badge bg-success">Ready</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.duplicates.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-secondary opacity-75';
        tr.innerHTML = `
          <td>${r.date}</td>
          <td>${escapeHtml(r.name)}</td>
          <td>${r.distance} km</td>
          <td>${r.time} min</td>
          <td>${r.pace} min/km</td>
          <td><span class="badge bg-warning text-dark">Duplicate</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.skipped.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-dark opacity-50';
        tr.innerHTML = `
          <td>-</td>
          <td>${escapeHtml(r.name)}</td>
          <td colspan="3"><small class="text-muted">${escapeHtml(r.reason)}</small></td>
          <td><span class="badge bg-secondary">Skipped</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.invalids.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-danger opacity-75';
        tr.innerHTML = `
          <td>-</td>
          <td>${escapeHtml(r.name)}</td>
          <td colspan="3"><small class="text-danger">${escapeHtml(r.reason)}</small></td>
          <td><span class="badge bg-danger">Invalid</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function resetImportModal() {
      document.getElementById('importStepUpload').style.display = 'block';
      document.getElementById('importStepPreview').style.display = 'none';
      document.getElementById('parseCsvBtn').style.display = 'inline-block';
      document.getElementById('importBackBtn').style.display = 'none';
      document.getElementById('confirmImportBtn').style.display = 'none';
      document.getElementById('stravaCsvInput').value = '';
      const fnEl = document.getElementById('selectedFileName');
      if (fnEl) fnEl.style.display = 'none';
      const pErr = document.getElementById('parseErrorAlert');
      if (pErr) pErr.style.display = 'none';
      const cErr = document.getElementById('importConfirmAlert');
      if (cErr) cErr.style.display = 'none';
      currentParsedData = null;
    }

    async function confirmBatchImport() {
      if (!currentParsedData || !currentParsedData.valid_runs || currentParsedData.valid_runs.length === 0) {
        return;
      }

      const confirmBtn = document.getElementById('confirmImportBtn');
      const alertEl = document.getElementById('importConfirmAlert');

      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      alertEl.style.display = 'none';

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/confirm-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ runs: currentParsedData.valid_runs })
        });

        const res = await resp.json();

        if (!resp.ok || !res.success) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = `Import ${currentParsedData.valid_runs.length} Valid Run(s)`;
          alertEl.textContent = `${res.error || 'Import failed'}`;
          alertEl.style.display = 'block';
          return;
        }

        alertEl.className = 'alert alert-success mt-3';
        alertEl.textContent = `${res.message || 'Import successful!'}`;
        alertEl.style.display = 'block';

        setTimeout(() => {
          window.location.reload();
        }, 1500);

      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = `Import ${currentParsedData.valid_runs.length} Valid Run(s)`;
        alertEl.textContent = `Network/Server error: ${err.message}`;
        alertEl.style.display = 'block';
      }
    }

/* --- New Script Block --- */
let pendingImportTab = 'csv';

    // ── Open import modal and store target tab to initialize on show ──
    function openImportTab(tab) {
      pendingImportTab = tab;
    }

    document.addEventListener('DOMContentLoaded', () => {

      // Auto-load on initial view
      loadWeeklyGoal();

      const importModal = document.getElementById('importRunsModal');
      if (importModal) {
        importModal.addEventListener('show.bs.modal', () => {
          const targetTab = pendingImportTab || 'csv';
          const csvBtn = document.getElementById('csvTabBtn');
          const ssBtn = document.getElementById('screenshotTabBtn');
          const csvPane = document.getElementById('csvTabPane');
          const ssPane = document.getElementById('screenshotTabPane');

          if (targetTab === 'screenshot') {
            csvBtn.classList.remove('active');
            csvBtn.setAttribute('aria-selected', 'false');
            ssBtn.classList.add('active');
            ssBtn.setAttribute('aria-selected', 'true');

            csvPane.classList.remove('show', 'active');
            ssPane.classList.add('show', 'active');

            resetScreenshotModal();
          } else {
            ssBtn.classList.remove('active');
            ssBtn.setAttribute('aria-selected', 'false');
            csvBtn.classList.add('active');
            csvBtn.setAttribute('aria-selected', 'true');

            ssPane.classList.remove('show', 'active');
            csvPane.classList.add('show', 'active');

            resetImportModal();
          }
        });
      }

      // ── Drag & Drop Event Handlers ──
      setupDragAndDrop('csvDropZone', 'stravaCsvInput', handleCsvFileSelected);
      setupDragAndDrop('screenshotDropZone', 'screenshotInput', handleScreenshotSelected);
    });

    function setupDragAndDrop(zoneId, inputId, onFileSelected) {
      const zone = document.getElementById(zoneId);
      const input = document.getElementById(inputId);
      if (!zone || !input) return;

      ['dragenter', 'dragover'].forEach(eventName => {
        zone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.add('drag-active');
        }, false);
      });

      ['dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.remove('drag-active');
        }, false);
      });

      zone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
          input.files = files;
          onFileSelected(input);
        }
      }, false);
    }

    // ── Screenshot step state ──
    function ssShowStep(step) {
      // steps: 'upload' | 'loading' | 'preview' | 'error'
      ['ssStepUpload','ssStepLoading','ssStepPreview','ssStepError'].forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
      document.getElementById('ssStep' + step.charAt(0).toUpperCase() + step.slice(1)).style.display = '';
    }

    function handleScreenshotSelected(input) {
      const file = input?.files[0];
      const el   = document.getElementById('ssSelectedFileName');
      const errEl = document.getElementById('ssUploadError');
      if (file) {
        el.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        el.style.display = 'block';
        if (errEl) errEl.style.display = 'none';
      } else {
        el.style.display = 'none';
      }
    }

    async function uploadAndParseScreenshot() {
      const input = document.getElementById('screenshotInput');
      const file  = input?.files[0];
      const errEl = document.getElementById('ssUploadError');

      if (!file) {
        errEl.textContent = 'Please select an image file first.';
        errEl.style.display = 'block';
        return;
      }

      const parseBtn = document.getElementById('ssParseBtn');
      parseBtn.disabled = true;
      parseBtn.textContent = 'Uploading...';
      ssShowStep('loading');

      const formData = new FormData();
      formData.append('file', file);

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/parse-screenshot', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: formData
        });
        const res = await resp.json();

        parseBtn.disabled = false;
        parseBtn.textContent = 'Analyse Screenshot';

        if (!resp.ok || !res.success) {
          document.getElementById('ssErrorMsg').textContent = res.error || 'Failed to analyse screenshot.';
          ssShowStep('error');
          return;
        }

        // Populate editable preview form
        const d = res.data;
        document.getElementById('ssDistanceKm').value = d.distance_km ?? '';
        document.getElementById('ssTimeMin').value     = d.time_min    ?? '';
        document.getElementById('ssDate').value        = d.date        ?? '';
        document.getElementById('ssPace').value        = d.pace_per_km ?? '';
        document.getElementById('ssCalories').value   = d.calories     ?? '';
        document.getElementById('ssHeartRate').value  = d.average_heart_rate ?? '';
        document.getElementById('ssElevation').value  = d.elevation_gain_m   ?? '';
        document.getElementById('ssSourceApp').value  = d.source_app   ?? 'unknown';

        ssShowStep('preview');
        document.getElementById('ssBackBtn').style.display    = 'inline-block';
        document.getElementById('ssParseBtn').style.display   = 'none';
        document.getElementById('ssConfirmBtn').style.display = 'inline-block';

      } catch (err) {
        parseBtn.disabled = false;
        parseBtn.textContent = 'Analyse Screenshot';
        document.getElementById('ssErrorMsg').textContent = `Network/Server error: ${err.message}`;
        ssShowStep('error');
      }
    }

    async function confirmScreenshotImport() {
      const confirmBtn = document.getElementById('ssConfirmBtn');
      const alertEl   = document.getElementById('ssConfirmError');

      const distance_km = parseFloat(document.getElementById('ssDistanceKm').value);
      const time_min    = parseFloat(document.getElementById('ssTimeMin').value);

      if (!distance_km || !time_min || distance_km <= 0 || time_min <= 0) {
        alertEl.textContent = 'Distance and Duration are required.';
        alertEl.style.display = 'block';
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      alertEl.style.display = 'none';

      const payload = {
        distance_km,
        time_min,
        date:        document.getElementById('ssDate').value        || null,
        run_type:    document.getElementById('ssRunType').value      || 'easy',
        notes:       document.getElementById('ssNotes').value        || '',
        source_app:  document.getElementById('ssSourceApp').value   || 'unknown',
      };

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/confirm-screenshot-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify(payload)
        });
        const res = await resp.json();

        if (!resp.ok || !res.success) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Import This Run';
          alertEl.textContent = `${res.error || 'Import failed'}`;
          alertEl.style.display = 'block';
          return;
        }

        alertEl.className = 'alert alert-success mt-3';
        alertEl.textContent = `${res.message || 'Run imported!'}`;
        alertEl.style.display = 'block';

        setTimeout(() => { window.location.reload(); }, 1500);

      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Import This Run';
        alertEl.textContent = `Network/Server error: ${err.message}`;
        alertEl.style.display = 'block';
      }
    }

    function resetScreenshotModal() {
      document.getElementById('screenshotInput').value = '';
      document.getElementById('ssSelectedFileName').style.display = 'none';
      document.getElementById('ssUploadError').style.display     = 'none';
      document.getElementById('ssConfirmError').style.display    = 'none';
      document.getElementById('ssBackBtn').style.display         = 'none';
      document.getElementById('ssParseBtn').style.display        = 'inline-block';
      document.getElementById('ssParseBtn').disabled             = false;
      document.getElementById('ssParseBtn').textContent          = 'Analyse Screenshot';
      document.getElementById('ssConfirmBtn').style.display      = 'none';
      ssShowStep('upload');
    }

/* --- New Script Block --- */
[
            {% for r in runs %}
              {"date": "{{ r['date'] }}", "distance_km": {{ r['distance_km'] }}, "pace": {{ r['pace'] }}}
              {% if not loop.last %},{% endif %}
            {% endfor %}
            ]

/* --- New Script Block --- */
document.addEventListener('DOMContentLoaded', () => {

      // Auto-load on initial view
      loadWeeklyGoal();
    });

    // ==========================================
    // THEME TOGGLE
    // ==========================================
    function toggleTheme() {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
      
      const meta = document.getElementById('themeColorMeta');
      if (meta) {
        meta.setAttribute('content', newTheme === 'light' ? '#F0F4F8' : '#1a1a1e');
      }

      const btn = document.getElementById('themeToggleBtn');
      if (btn) {
        btn.innerHTML = newTheme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode';
      }

      // Phase 3 trigger prep
      if (typeof updateChartTheme === 'function') {
        updateChartTheme();
      }
    }

    // Initialize button text based on load
    window.addEventListener('DOMContentLoaded', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const btn = document.getElementById('themeToggleBtn');
      if (btn) {
        btn.innerHTML = currentTheme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode';
      }
    });

    function switchTab(tabId, el) {
      if (el) {
        // Remove active class from all nav items
        document.querySelectorAll('.tab-nav-item').forEach(i => i.classList.remove('active'));
        // Add active class to the specific data-tab items (both mobile and desktop)
        document.querySelectorAll(`.tab-nav-item[data-tab="${tabId}"]`).forEach(i => i.classList.add('active'));
      }

      ['homeView', 'runsView', 'leaderboardView', 'analyticsView', 'achievementsView'].forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
      document.getElementById(tabId + 'View').style.display = 'block';


      
      // Trigger resize event for charts if they need to redraw
      setTimeout(() => window.dispatchEvent(new Event('resize')), 50);

      if (tabId === 'home') {
        loadWeeklyGoal();
      }

      // Auto-load analytics charts when switching to analytics tab
      if (tabId === 'analytics') {
        loadInsights();
        loadMonthlyComparison();
        loadPaceTrend();
      }

      if (tabId === 'achievements') {
        loadAchievements();
      }
    }

    // ──────────────────────────────────────────────
    // ACHIEVEMENTS TAB
    // ──────────────────────────────────────────────
    let currentAchievementTab = 'personalBests';
    
    function switchAchievementTab(tabId) {
      currentAchievementTab = tabId;
      document.querySelectorAll('.achievement-nav-pill').forEach(btn => btn.classList.remove('active'));
      document.getElementById('btn' + tabId.charAt(0).toUpperCase() + tabId.slice(1)).classList.add('active');
      
      document.querySelectorAll('.achievement-tab-content').forEach(content => content.style.display = 'none');
      document.getElementById(tabId + 'Content').style.display = 'block';
      
      if (tabId === 'personalBests') {
        loadPersonalBests();
      } else if (tabId === 'badges') {
        loadBadges();
      } else if (tabId === 'challenges') {
        loadChallenges();
      } else if (tabId === 'personalGoals') {
        loadPersonalGoals();
      }
    }

    function loadAchievements() {
      // Called when clicking the main Achievements nav
      switchAchievementTab(currentAchievementTab);
    }
    
    function createRecordCard(title, icon, valueText, dateStr) {
      if (valueText === null) {
        return `
          <div class="col-12 col-md-6 col-lg-4">
            <div class="metric-card p-3 border-0 h-100 unachieved-record d-flex flex-column align-items-center justify-content-center text-center">
              <i class="${icon} mb-2" style="font-size:1.5rem; color:var(--text-muted);"></i>
              <h6 class="fw-bold mb-1" style="color:var(--text-muted);">${title}</h6>
              <div class="small" style="color:var(--text-faint);">Not yet achieved</div>
            </div>
          </div>
        `;
      }
      
      const parsedDate = new Date(dateStr);
      const displayDate = parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      
      return `
        <div class="col-12 col-md-6 col-lg-4">
          <div class="metric-card p-3 border-0 h-100 position-relative" style="background:var(--premium-surface); border:1px solid var(--premium-border) !important;">
            <div class="d-flex align-items-start gap-3">
              <div class="d-flex justify-content-center align-items-center" style="width:40px;height:40px;border-radius:10px;background:rgba(22, 131, 247, 0.1);color:var(--cyan-accent);font-size:1.2rem;">
                <i class="${icon}"></i>
              </div>
              <div class="flex-grow-1">
                <h6 class="fw-bold mb-1" style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px;">${title}</h6>
                <div class="fw-bold mb-1" style="color:var(--text-main); font-size:1.25rem;">${valueText}</div>
                <div class="small" style="color:var(--text-faint);"><i class="fas fa-calendar-alt me-1"></i> ${displayDate}</div>
              </div>
            </div>
          </div>
        </div>
      `;
    }
    
    function loadPersonalBests() {
      const grid = document.getElementById('personalBestsGrid');
      grid.innerHTML = '<div class="col-12 text-center text-secondary py-5"><i class="fa-solid fa-spinner fa-spin fa-2x mb-3"></i><br>Loading records...</div>';
      
      fetch('/api/personal-bests')
        .then(res => res.json())
        .then(data => {
           let html = '';
           html += createRecordCard("Fastest 5K", "fas fa-bolt", data.fastest_5k ? data.fastest_5k.time_min + " min" : null, data.fastest_5k ? data.fastest_5k.date : null);
           html += createRecordCard("Fastest 10K", "fas fa-tachometer-alt", data.fastest_10k ? data.fastest_10k.time_min + " min" : null, data.fastest_10k ? data.fastest_10k.date : null);
           html += createRecordCard("Longest Run", "fas fa-route", data.longest_distance ? data.longest_distance.distance_km + " km" : null, data.longest_distance ? data.longest_distance.date : null);
           html += createRecordCard("Longest Duration", "fas fa-stopwatch", data.longest_duration ? data.longest_duration.time_min + " min" : null, data.longest_duration ? data.longest_duration.date : null);
           html += createRecordCard("Best Pace", "fas fa-wind", data.best_pace ? data.best_pace.pace.toFixed(2) + " min/km" : null, data.best_pace ? data.best_pace.date : null);
           html += createRecordCard("Most Calories", "fas fa-fire-alt", data.highest_calories ? data.highest_calories.calories + " kcal" : null, data.highest_calories ? data.highest_calories.date : null);
           grid.innerHTML = html;
        })
        .catch(err => {
           console.error('Error loading personal bests:', err);
           grid.innerHTML = '<div class="col-12 text-center text-danger py-5">Failed to load records.</div>';
        });
    }

    function loadBadges() {
      const grid = document.getElementById('achievementsGrid');
      grid.innerHTML = '<div class="col-12 text-center text-secondary py-5"><i class="fa-solid fa-spinner fa-spin fa-2x mb-3"></i><br>Loading achievements...</div>';
      
      fetch('/api/badges')
        .then(res => res.json())
        .then(data => {
          if (data.status === 'success' && data.badges.length > 0) {
            grid.innerHTML = '';
            data.badges.forEach(b => {
              const cardClass = 'metric-card h-100 p-4 border-0';
              const iconStyle = b.earned ? 'font-size: 2.5rem;' : 'font-size: 2.5rem; filter: grayscale(1); opacity: 0.5;';
              const dateText = b.earned ? `<div class="mt-3 small fw-bold text-success"><i class="fa-solid fa-check-circle me-1"></i> Unlocked ${new Date(b.unlocked_at).toLocaleDateString()}</div>` : '';
              
              grid.innerHTML += `
                <div class="col-12 col-md-4 col-lg-4">
                  <div class="${cardClass}" style="border-radius: var(--border-radius-lg); ${!b.earned ? 'opacity: 0.6; filter: grayscale(1);' : ''}">
                    <div class="d-flex flex-column align-items-center text-center">
                      <div class="mb-3" style="${iconStyle}">${b.icon}</div>
                      <h5 class="fw-bold mb-2">${b.name}</h5>
                      <p class="text-secondary small mb-0">${b.description}</p>
                      ${dateText}
                    </div>
                  </div>
                </div>
              `;
            });
          } else {
            grid.innerHTML = '<div class="col-12 text-center text-secondary py-5">No achievements found.</div>';
          }
        })
        .catch(err => {
          console.error('Error loading achievements:', err);
          grid.innerHTML = '<div class="col-12 text-center text-danger py-5">Failed to load achievements.</div>';
        });
    }

    // ──────────────────────────────────────────────
    // CHALLENGES TAB
    // ──────────────────────────────────────────────
    function loadChallenges() {
      const list = document.getElementById('challengesList');
      list.innerHTML = '<div class="text-center text-secondary py-5"><i class="fa-solid fa-spinner fa-spin fa-2x mb-3"></i><br>Loading challenges...</div>';

      fetch('/api/challenges')
        .then(res => res.json())
        .then(data => {
          if (!data.challenges || data.challenges.length === 0) {
            list.innerHTML = `
              <div class="text-center py-5">
                <div class="d-inline-flex justify-content-center align-items-center mb-3"
                     style="width:64px;height:64px;border-radius:16px;background:var(--premium-surface);border:1px solid var(--premium-border);color:var(--text-faint);font-size:1.5rem;">
                  <i class="fas fa-flag-checkered"></i>
                </div>
                <h5 class="fw-bold" style="color:var(--text-main);">No Active Challenges</h5>
                <p style="color:var(--text-muted);">New challenges will appear at the start of each month.</p>
              </div>`;
            return;
          }

          let html = '<div class="d-flex flex-column gap-3">';
          data.challenges.forEach(c => {
            const isComplete = c.completed;
            const pct = c.percent_complete;
            const goalLabel = c.goal_type === 'run_count'
              ? `${Math.min(c.current_progress, c.goal_value).toFixed(0)} / ${c.goal_value.toFixed(0)} runs`
              : `${Math.min(c.current_progress, c.goal_value).toFixed(1)} / ${c.goal_value.toFixed(1)} km`;

            const completedBadge = isComplete
              ? `<span class="ms-auto d-flex align-items-center gap-1" style="color:#22c55e;font-size:0.85rem;font-weight:600;">
                   <i class="fas fa-check-circle"></i> Completed
                 </span>`
              : '';

            const rewardPill = c.reward_badge_name
              ? `<div class="challenge-reward-pill">
                   ${isComplete ? '<i class="fas fa-award"></i>' : '<i class="fas fa-gift"></i>'}
                   ${isComplete ? 'Earned: ' : 'Reward: '} ${c.reward_badge_icon} ${c.reward_badge_name}
                 </div>`
              : '';

            html += `
              <div class="challenge-card ${isComplete ? 'challenge-complete' : ''}">
                <div class="d-flex align-items-start gap-3">
                  <div class="d-flex justify-content-center align-items-center flex-shrink-0"
                       style="width:40px;height:40px;border-radius:10px;
                              background:${isComplete ? 'rgba(34,197,94,0.12)' : 'rgba(22,131,247,0.1)'};
                              color:${isComplete ? '#22c55e' : 'var(--cyan-accent)'};font-size:1.1rem;">
                    <i class="${c.icon}"></i>
                  </div>
                  <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-items-center flex-wrap gap-2 mb-1">
                      <h6 class="fw-bold mb-0" style="color:var(--text-main);">${c.name}</h6>
                      ${completedBadge}
                    </div>
                    <p class="small mb-1" style="color:var(--text-muted);">${c.description}</p>
                    <div class="d-flex align-items-center justify-content-between mb-1">
                      <span class="small" style="color:var(--text-faint);">${goalLabel}</span>
                      <span class="small fw-semibold" style="color:${isComplete ? '#22c55e' : 'var(--cyan-accent)'};">${pct}%</span>
                    </div>
                    <div class="challenge-progress-track">
                      <div class="challenge-progress-fill" style="width:${pct}%;"></div>
                    </div>
                    ${rewardPill}
                  </div>
                </div>
              </div>`;
          });
          html += '</div>';
          list.innerHTML = html;
        })
        .catch(err => {
          console.error('Error loading challenges:', err);
          list.innerHTML = '<div class="text-center text-danger py-5">Failed to load challenges.</div>';
        });
    }

    // ──────────────────────────────────────────────
    // WEEKLY GOAL
    // ──────────────────────────────────────────────
    function loadWeeklyGoal() {
      fetch('/api/weekly-goal-progress')
        .then(res => res.json())
        .then(data => {
          document.getElementById('goalLoading').style.display = 'none';
          
          if (data.error || data.goal_km === null) {
            document.getElementById('goalSetup').style.display = 'block';
            document.getElementById('goalProgressContainer').style.display = 'none';
            document.getElementById('editGoalBtn').style.display = 'none';
            if (data.goal_km === null) {
                document.getElementById('goalInput').value = '';
            }
          } else {
            document.getElementById('goalSetup').style.display = 'none';
            document.getElementById('goalProgressContainer').style.display = 'block';
            document.getElementById('editGoalBtn').style.display = 'block';
            
            // Populate progress
            document.getElementById('goalCurrent').innerText = data.current_km.toFixed(1);
            document.getElementById('goalTarget').innerText = data.goal_km.toFixed(1);
            document.getElementById('goalPercent').innerText = Math.round(data.percent_complete) + '%';
            
            let daysText = data.days_remaining_in_week === 1 ? '1 day remaining' : data.days_remaining_in_week + ' days remaining';
            if (data.days_remaining_in_week === 0) daysText = 'Last day';
            document.getElementById('goalDaysLeft').innerText = daysText;
            
            // Set bar percentage
            setTimeout(() => {
              document.getElementById('goalProgressBar').style.width = `${data.percent_complete}%`;
              document.getElementById('goalProgressBar').setAttribute('aria-valuenow', data.percent_complete);
            }, 100);
            
            // Status text
            const statusEl = document.getElementById('goalStatusText');
            const barEl = document.getElementById('goalProgressBar');
            const percentEl = document.getElementById('goalPercent');
            
            if (data.percent_complete >= 100) {
              let over = (data.current_km - data.goal_km).toFixed(1);
              statusEl.innerHTML = `🎉 Goal smashed! <span style="font-size: 0.8rem; font-weight: normal; color: var(--accent);">+${over} km</span>`;
              barEl.style.backgroundColor = '#b0ff4f'; // Green for completion
              percentEl.style.color = '#b0ff4f';
            } else {
              statusEl.innerText = 'Keep it up!';
              barEl.style.backgroundColor = 'var(--accent)';
              percentEl.style.color = 'var(--accent)';
            }
          }
        })
        .catch(err => {
          console.error('Goal load error', err);
          document.getElementById('goalLoading').innerText = 'Error loading goal';
        });
    }

    function toggleGoalEdit(e) {
      if (e) e.preventDefault();
      document.getElementById('goalSetup').style.display = 'block';
      document.getElementById('goalProgressContainer').style.display = 'none';
      document.getElementById('editGoalBtn').style.display = 'none';
      
      const targetTxt = document.getElementById('goalTarget').innerText;
      if (targetTxt && targetTxt !== '0.0') {
          document.getElementById('goalInput').value = targetTxt;
      }
    }

    function saveWeeklyGoal() {
      const val = parseFloat(document.getElementById('goalInput').value);
      if (isNaN(val) || val <= 0 || val > 500) {
        showToast('Please enter a valid goal (0.1 - 500)', 'danger');
        return;
      }
      
      const btn = document.getElementById('saveGoalBtn');
      const originalText = btn.innerText;
      btn.innerText = 'Saving...';
      btn.disabled = true;
      
      fetch('/api/weekly-goal', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
        },
        body: JSON.stringify({ goal_km: val })
      })
      .then(res => res.json())
      .then(data => {
        btn.innerText = originalText;
        btn.disabled = false;
        
        if (data.success) {
          showToast('Goal saved!', 'success');
          loadWeeklyGoal();
        } else {
          showToast(data.error || 'Failed to save goal', 'danger');
        }
      })
      .catch(err => {
        console.error(err);
        btn.innerText = originalText;
        btn.disabled = false;
        showToast('Network error', 'danger');
      });
    }

    // ──────────────────────────────────────────────
    // SHARE RUN CARD
    // ──────────────────────────────────────────────
    let _shareCardData = null;
    let _shareCardBlob = null;

    const SC_RUNTYPE_STYLES = {
      easy:     { bg: 'rgba(176,255,79,0.15)',  color: '#b0ff4f', border: 'rgba(176,255,79,0.3)' },
      tempo:    { bg: 'rgba(255,110,58,0.15)',  color: '#ff6e3a', border: 'rgba(255,110,58,0.3)' },
      long:     { bg: 'rgba(0,242,255,0.12)',   color: '#00f2ff', border: 'rgba(0,242,255,0.25)' },
      interval: { bg: 'rgba(180,100,255,0.15)', color: '#c084fc', border: 'rgba(180,100,255,0.3)' },
      race:     { bg: 'rgba(255,107,107,0.15)', color: '#ff6b6b', border: 'rgba(255,107,107,0.3)' },
    };

    function formatShareDate(dateStr) {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function formatDuration(minutes) {
      if (!minutes) return '00:00';
      let m = Math.floor(minutes);
      let s = Math.round((minutes - m) * 60);
      if (s === 60) {
        m += 1;
        s = 0;
      }
      return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function openShareCard(data) {
      _shareCardData = data;
      _shareCardBlob = null;

      // Populate card fields
      document.getElementById('sc-distance').textContent = data.distance_km;
      document.getElementById('sc-duration').textContent = formatDuration(data.time_min);
      document.getElementById('sc-pace').textContent = data.pace;
      document.getElementById('sc-calories').textContent = data.calories;
      document.getElementById('sc-date').textContent = '📅 ' + formatShareDate(data.date);
      // Display name removed in redesign, only username is shown
      document.getElementById('sc-username').textContent = '@' + data.username;

      // Run type badge (design image shows it as plain text without the pill border)
      const rt = data.run_type || 'easy';
      const rtBadge = document.getElementById('sc-runtype-badge');
      rtBadge.textContent = rt.charAt(0).toUpperCase() + rt.slice(1) + ' Run';

      // Weather
      const weatherEl = document.getElementById('sc-weather');
      if (data.weather_emoji && data.weather_temp !== '') {
        weatherEl.innerHTML = data.weather_emoji + ' ' + data.weather_temp + '°C';
        weatherEl.style.display = 'flex';
      } else {
        weatherEl.style.display = 'none';
      }

      // AI Insight
      const insightEl = document.getElementById('sc-insight');
      if (data.insight) {
        insightEl.innerHTML = data.insight;
        insightEl.style.display = 'block';
      } else {
        insightEl.style.display = 'none';
      }

      // Show overlay with loading state
      const overlay = document.getElementById('shareCardOverlay');
      const preview = document.getElementById('shareCardPreview');
      const actions = document.getElementById('shareCardActions');
      const loading = document.getElementById('shareCardLoading');

      preview.innerHTML = '';
      actions.style.display = 'none';
      loading.classList.add('active');
      overlay.classList.add('active');
      document.body.style.overflow = 'hidden';

      // Check Web Share API support
      const shareBtn = document.getElementById('shareCardShareBtn');
      if (navigator.canShare) {
        shareBtn.style.display = '';
      } else {
        shareBtn.textContent = '📋 Copy';
        shareBtn.style.display = '';
      }

      // Render after fonts are ready
      renderShareCard();
    }

    function renderShareCard() {
      const renderEl = document.getElementById('shareCardRender');
      const preview = document.getElementById('shareCardPreview');
      const actions = document.getElementById('shareCardActions');
      const loading = document.getElementById('shareCardLoading');

      // Wait for all fonts to be loaded before capturing
      const fontReady = document.fonts && document.fonts.ready
        ? document.fonts.ready
        : Promise.resolve();

      fontReady.then(() => {
        // Small delay to ensure layout is painted with correct fonts
        return new Promise(resolve => setTimeout(resolve, 150));
      }).then(() => {
        return html2canvas(renderEl.firstElementChild, {
          width: 1080,
          height: 1920,
          scale: 1,
          useCORS: true,
          backgroundColor: null,
          logging: false,
        });
      }).then(canvas => {
        // Convert to blob for sharing
        return new Promise(resolve => {
          canvas.toBlob(blob => {
            _shareCardBlob = blob;

            // Show preview as image (not canvas) for crisp display
            const img = document.createElement('img');
            img.src = URL.createObjectURL(blob);
            img.alt = 'RunRush Run Card';
            preview.innerHTML = '';
            preview.appendChild(img);

            loading.classList.remove('active');
            actions.style.display = 'flex';
            resolve();
          }, 'image/png');
        });
      }).catch(err => {
        console.error('Share card render failed:', err);
        loading.classList.remove('active');
        preview.innerHTML = '<div style="color:#ff6b6b;padding:2rem;text-align:center;">Failed to generate card. Please try again.</div>';
        actions.style.display = 'flex';
      });
    }

    function downloadShareCard() {
      if (!_shareCardBlob || !_shareCardData) return;
      const url = URL.createObjectURL(_shareCardBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'runrush_' + _shareCardData.date + '.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
    }

    function shareShareCard() {
      if (!_shareCardBlob || !_shareCardData) return;
      const file = new File([_shareCardBlob], 'runrush_' + _shareCardData.date + '.png', { type: 'image/png' });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({
          title: 'My RunRush Run',
          text: _shareCardData.distance_km + ' km in ' + _shareCardData.time_min + ' min — ' + _shareCardData.pace + ' min/km pace 🏃',
          files: [file],
        }).catch(() => {});
      } else {
        // Fallback: copy stats text to clipboard
        const text = '🏃 RunRush Run\n'
          + '📍 ' + _shareCardData.distance_km + ' km\n'
          + '⏱ ' + _shareCardData.time_min + ' min\n'
          + '🏃 ' + _shareCardData.pace + ' min/km\n'
          + '🔥 ' + _shareCardData.calories + ' cal\n'
          + '📅 ' + _shareCardData.date;
        navigator.clipboard.writeText(text).then(() => {
          const btn = document.getElementById('shareCardShareBtn');
          btn.textContent = '✅ Copied!';
          setTimeout(() => { btn.textContent = '📋 Copy'; }, 2000);
        });
      }
    }

    function closeShareCard() {
      const overlay = document.getElementById('shareCardOverlay');
      overlay.classList.remove('active');
      document.body.style.overflow = '';
      _shareCardBlob = null;
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.getElementById('shareCardOverlay').classList.contains('active')) {
        closeShareCard();
      }
    });

    // Heatmap Info Popover
    function toggleHeatmapInfo(e) {
      e.stopPropagation();
      const popover = document.getElementById('heatmapInfoPopover');
      if (popover.style.display === 'none') {
        popover.style.display = 'block';
      } else {
        popover.style.display = 'none';
      }
    }

    document.addEventListener('click', (e) => {
      const popover = document.getElementById('heatmapInfoPopover');
      if (popover && popover.style.display === 'block') {
        if (!popover.contains(e.target)) {
          popover.style.display = 'none';
        }
      }
    });

/* --- New Script Block --- */


/* --- New Script Block --- */
// Dynamic Filter/Sort
    function resetFilters() {
      document.getElementById('filterAll').checked = true;
      document.getElementById('sortDate').checked = true;
    }

    async function applyFiltersDynamic() {
      const filterOpt = document.querySelector('input[name="filterOpt"]:checked').value;
      const sortOpt = document.querySelector('input[name="sortOpt"]:checked').value;
      const spinner = document.getElementById('filterSpinner');
      
      // Close modal
      const filterModalEl = document.getElementById('filterModal');
      const filterModal = bootstrap.Modal.getInstance(filterModalEl) || new bootstrap.Modal(filterModalEl);
      filterModal.hide();
      
      spinner.style.display = 'inline-block';
      try {
        const response = await fetch(`/dashboard?filter=${filterOpt}&sort=${sortOpt}`);
        const html = await response.text();
        
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        
        // Update table body
        const newTbody = doc.querySelector('#runsTable tbody');
        const currentTbody = document.querySelector('#runsTable tbody');
        
        if (newTbody && currentTbody) {
          const runRows = newTbody.querySelectorAll('tr.runs-table-row');
          if (runRows.length === 0) {
            currentTbody.innerHTML = `<tr><td colspan="9" class="text-center py-5 text-muted empty-state-container">
              <div class="fs-1 mb-2">🏃</div>
              No runs match your selected filters.<br>Try changing your filter or resetting it.
            </td></tr>`;
          } else {
            currentTbody.innerHTML = newTbody.innerHTML;
          }
        }
        
        // Update cards view
        const newCardView = doc.querySelector('#runsCardView');
        const currentCardView = document.querySelector('#runsCardView');
        if (newCardView && currentCardView) {
            currentCardView.innerHTML = newCardView.innerHTML;
            formatMonthHeaders();
        }
        
        // Update run count
        const newCount = doc.querySelector('#runCount');
        const currentCount = document.querySelector('#runCount');
        if (newCount && currentCount) {
          currentCount.textContent = newCount.textContent;
        }
      } catch (err) {
        console.error("Failed to fetch filtered runs", err);
      } finally {
        spinner.style.display = 'none';
      }
    }

    // Runs View Switcher
    function setRunsView(view) {
      const cardView = document.getElementById('runsCardView');
      const listView = document.getElementById('runsListView');
      const btnCards = document.getElementById('btnCardsView');
      const btnList = document.getElementById('btnListView');
      
      if (!cardView || !listView) return;

      if (view === 'list') {
        cardView.style.display = 'none';
        listView.style.display = 'block';
        if (btnList) btnList.classList.add('active');
        if (btnCards) btnCards.classList.remove('active');
      } else {
        cardView.style.display = 'block';
        listView.style.display = 'none';
        if (btnCards) btnCards.classList.add('active');
        if (btnList) btnList.classList.remove('active');
      }
      localStorage.setItem('runrush_runs_view', view);
    }

    function initRunsView() {
      const savedView = localStorage.getItem('runrush_runs_view') || 'cards';
      setRunsView(savedView);
      formatMonthHeaders();
    }

    function toggleRunCard(runId) {
      const details = document.getElementById(`runCardDetails-${runId}`);
      const chevron = document.getElementById(`chevron-${runId}`);
      if (!details) return;

      if (details.classList.contains('show')) {
        const bsCollapse = bootstrap.Collapse.getInstance(details);
        if (bsCollapse) bsCollapse.hide();
        if (chevron) chevron.style.transform = 'rotate(0deg)';
      } else {
        const bsCollapse = new bootstrap.Collapse(details) || bootstrap.Collapse.getInstance(details);
        bsCollapse.show();
        if (chevron) chevron.style.transform = 'rotate(180deg)';
      }
    }

    function formatMonthHeaders() {
      const months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
      document.querySelectorAll('.month-header-raw').forEach(el => {
        const raw = el.getAttribute('data-month'); // e.g. "2026-09"
        if (raw && raw.length >= 7) {
          const parts = raw.split('-');
          if (parts.length >= 2) {
            const year = parts[0];
            const monthIdx = parseInt(parts[1], 10) - 1;
            if (monthIdx >= 0 && monthIdx < 12) {
              el.textContent = `${months[monthIdx]} ${year}`;
              el.classList.remove('month-header-raw');
            }
          }
        }
      });
    }

    document.addEventListener('DOMContentLoaded', initRunsView);

/* --- New Script Block --- */


/* --- New Script Block --- */


/* --- New Script Block --- */
var profileModalEl = document.getElementById('profileModal');
    if (profileModalEl) {
      profileModalEl.addEventListener('show.bs.modal', function () {
        loadProfile('{{ username }}', false);
        loadHeatmap('{{ username }}');
      });
    }

/* --- New Script Block --- */
// Pace Pet Logic
    function getPetIcon(type, level) {
      let icon = 'fa-egg';
      if (level > 1) {
        if (type === 'dog') icon = 'fa-dog';
        else if (type === 'bird') icon = 'fa-crow';
        else if (type === 'dragon') icon = 'fa-dragon';
      }
      return `<i class="fas ${icon}"></i>`;
    }

    function selectPetType(type, elem) {
      document.querySelectorAll('.pet-choice').forEach(el => {
        el.style.background = 'transparent';
        el.style.boxShadow = 'none';
        el.classList.remove('border-info');
        el.classList.add('border-secondary');
      });
      elem.style.background = 'rgba(0, 242, 255, 0.1)';
      elem.style.boxShadow = '0 0 10px rgba(0, 242, 255, 0.2)';
      elem.classList.remove('border-secondary');
      elem.classList.add('border-info');
      document.getElementById('adoptPetType').value = type;
    }

    async function submitAdoption() {
      const type = document.getElementById('adoptPetType').value;
      const name = document.getElementById('adoptPetName').value;
      if (!name) return alert('Please enter a name for your pet!');
      
      const res = await fetch('/api/adopt-pet', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ pet_name: name, pet_type: type })
      });
      
      if (res.ok) {
        const modal = bootstrap.Modal.getInstance(document.getElementById('adoptPetModal'));
        if (modal) modal.hide();
        // If collection modal is open, hide it too
        const colModal = bootstrap.Modal.getInstance(document.getElementById('petCollectionModal'));
        if (colModal) colModal.hide();
        
        loadPetStatus();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to adopt pet.');
      }
    }

    let currentPetLevel = null;

    async function loadPetStatus() {
      const res = await fetch('/api/pet-status?_t=' + Date.now());
      if (!res.ok) return;
      const data = await res.json();
      
      if (!data.has_pet) {
        document.getElementById('pacePetWidget').style.display = 'none';
        const modal = new bootstrap.Modal(document.getElementById('adoptPetModal'));
        modal.show();
        return;
      }
      
      // Evolution Check
      if (currentPetLevel !== null && data.level > currentPetLevel) {
        // Trigger evolution modal
        document.getElementById('evoPetName').innerText = data.pet_name;
        document.getElementById('evoPetStage').innerText = data.level_name;
        
        const evoVisual = document.getElementById('evoPetVisual');
        evoVisual.innerHTML = getPetIcon(data.pet_type, data.level);
        let evoClasses = `pet-icon pet-lvl-${data.level} pet-anim-bounce`;
        if (data.level > 1) evoClasses += ` pet-color-${data.pet_type}`;
        evoVisual.className = evoClasses;
        
        const evoModal = new bootstrap.Modal(document.getElementById('petEvolutionModal'));
        evoModal.show();
      }
      currentPetLevel = data.level;
      
      // Update widget
      document.getElementById('pacePetWidget').style.display = 'block';
      document.getElementById('petNameDisplay').innerText = data.pet_name;
      document.getElementById('petLevelDisplay').innerText = data.level;
      document.getElementById('petHealthDisplay').innerText = data.health_status;
      document.getElementById('petKmsDisplay').innerText = data.total_km_fed;
      document.getElementById('petNextKmsDisplay').innerText = data.km_until_next_evolution;
      
      const visual = document.getElementById('petVisual');
      visual.innerHTML = getPetIcon(data.pet_type, data.level);
      
      let baseClasses = `pet-icon pet-lvl-${data.level}`;
      if (data.level > 1) baseClasses += ` pet-color-${data.pet_type}`;
      
      if (data.health_status === 'waiting for you' || data.health_status === 'sleepy') {
        visual.className = `${baseClasses} pet-anim-sway`;
      } else {
        visual.className = `${baseClasses} pet-anim-bounce`;
      }
      
      if (data.next_threshold) {
        const currentLevelStart = data.current_threshold || 0;
        const progress = ((data.total_km_fed - currentLevelStart) / (data.next_threshold - currentLevelStart)) * 100;
        document.getElementById('petProgressBar').style.width = Math.min(100, Math.max(0, progress)) + '%';
      } else {
        document.getElementById('petProgressBar').style.width = '100%';
        document.getElementById('petNextKmsDisplay').innerText = '0';
      }
    }

    async function openPetCollection() {
      const res = await fetch('/api/pet-collection');
      if (!res.ok) return;
      const data = await res.json();
      
      const grid = document.getElementById('petCollectionGrid');
      grid.innerHTML = '';
      
      // Render unlocked/owned pets first
      data.collection.forEach(pet => {
        let baseClasses = `pet-icon pet-lvl-${pet.level}`;
        if (pet.level > 1) baseClasses += ` pet-color-${pet.pet_type}`;
        
        let actionBtn = pet.is_active 
          ? `<button class="btn btn-sm btn-success w-100 disabled"><i class="fas fa-check"></i> Active</button>`
          : `<button class="btn btn-sm btn-outline-info w-100" onclick="switchPet(${pet.id})"><i class="fas fa-exchange-alt"></i> Switch to ${pet.pet_name}</button>`;

        grid.innerHTML += `
          <div class="col-12 col-md-6">
            <div class="card bg-card border-subtle h-100 p-3 text-center ${pet.is_active ? 'border-info' : ''}">
              <div class="mb-3 ${baseClasses}" style="transform: scale(0.7);">${getPetIcon(pet.pet_type, pet.level)}</div>
              <h5>${pet.pet_name}</h5>
              <p class="text-muted small mb-2">${pet.level_name} (Lvl ${pet.level})</p>
              <div class="progress mb-3" style="height: 5px;">
                <div class="progress-bar bg-info" style="width: ${pet.next_threshold ? ((pet.total_km_fed - (pet.current_threshold||0)) / (pet.next_threshold - (pet.current_threshold||0))) * 100 : 100}%"></div>
              </div>
              ${actionBtn}
            </div>
          </div>
        `;
      });
      
      // Render locked / adoptable pet types
      const types = data.pet_types || {};
      for (const [t, info] of Object.entries(types)) {
        // If user already owns this type, skip it in the adoptable list
        if (data.collection.find(p => p.pet_type === t)) continue;
        
        if (info.unlocked) {
          // Adoptable
          grid.innerHTML += `
            <div class="col-12 col-md-6">
              <div class="card bg-card border-subtle h-100 p-3 text-center" style="border-style: dashed !important;">
                <div class="mb-3 text-muted" style="font-size: 2rem;"><i class="fas fa-egg"></i></div>
                <h5>Adopt ${info.definition.name}</h5>
                <p class="text-muted small mb-2">${info.definition.description}</p>
                <button class="btn btn-sm btn-outline-primary w-100" onclick="openAdoptModal('${t}')">Adopt</button>
              </div>
            </div>
          `;
        } else {
          // Locked
          grid.innerHTML += `
            <div class="col-12 col-md-6">
              <div class="card bg-card border-subtle h-100 p-3 text-center" style="opacity: 0.5;">
                <div class="mb-3 text-muted" style="font-size: 2rem;"><i class="fas fa-lock"></i></div>
                <h5>???</h5>
                <p class="text-muted small mb-2">Unlocks at ${info.unlock_distance || '?'} km lifetime</p>
                <button class="btn btn-sm btn-outline-secondary w-100 disabled">Locked</button>
              </div>
            </div>
          `;
        }
      }
      
      const modal = new bootstrap.Modal(document.getElementById('petCollectionModal'));
      modal.show();
    }
    
    function openAdoptModal(type) {
      document.getElementById('adoptPetName').value = '';
      selectPetType(type, document.querySelector(`.pet-choice[onclick*="${type}"]`));
      const modal = new bootstrap.Modal(document.getElementById('adoptPetModal'));
      modal.show();
    }
    
    async function switchPet(collectionId) {
      const res = await fetch('/api/pet/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ collection_id: collectionId })
      });
      
      if (res.ok) {
        const modal = bootstrap.Modal.getInstance(document.getElementById('petCollectionModal'));
        if (modal) modal.hide();
        loadPetStatus();
      } else {
        alert('Failed to switch pet.');
      }
    }
    
    window.addEventListener('DOMContentLoaded', () => {
      loadPetStatus();
    });

