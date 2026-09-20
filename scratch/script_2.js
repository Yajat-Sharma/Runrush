
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
  