/**
 * Running Plan & AI Coach Controller
 * RunRush Interactive AI Race Plan Generator & Home Screen Roadmap
 */

(function () {
  'use strict';

  let planWizardState = {
    step: 1,
    targetDistanceKm: null,
    targetDate: null,
    daysPerWeek: 3,
    longRunDay: null,
    fitnessLevel: 'intermediate',
    raceName: '',
    homeScreenChoice: 'yes',
    generatedPlan: null
  };

  let activeGoalPlan = null;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrf_token"]');
    if (input && input.value) return input.value;
    if (window.userData && window.userData.csrf_token) return window.userData.csrf_token;
    return '';
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatDisplayDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) {
      return dateStr;
    }
  }

  function calculateWeeksUntil(dateStr) {
    if (!dateStr) return 8;
    const target = new Date(dateStr + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((target - today) / (1000 * 60 * 60 * 24));
    return Math.max(1, Math.ceil(diffDays / 7));
  }

  function setDefaultRaceDate(weeks) {
    const today = new Date();
    today.setDate(today.getDate() + (weeks * 7));
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  function stripEmojis(str) {
    if (!str) return '';
    try {
      return String(str)
        .replace(/\p{Extended_Pictographic}/gu, '')
        .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FAFF}\u{200D}\u{FE0F}]/gu, '')
        .replace(/\s+/g, ' ')
        .trim();
    } catch (e) {
      return String(str)
        .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FAFF}\u{200D}\u{FE0F}]/gu, '')
        .replace(/\s+/g, ' ')
        .trim();
    }
  }

  function parseCoachDirective(rawNote) {
    const clean = stripEmojis(rawNote);
    const boldMatch = clean.match(/^\s*\*\*(.*?)\*\*\s*[:\-–]?\s*(.*)$/);
    if (boldMatch) {
      return { title: boldMatch[1].trim(), body: boldMatch[2].trim() };
    }
    const colonMatch = clean.match(/^\s*([^:–-]+)\s*[:\-–]\s*(.*)$/);
    if (colonMatch) {
      return { title: colonMatch[1].trim(), body: colonMatch[2].trim() };
    }
    return { title: 'TRAINING DIRECTIVE', body: clean };
  }

  function getDirectiveIcon(title) {
    const lower = (title || '').toLowerCase();
    if (lower.includes('pace') || lower.includes('split') || lower.includes('speed') || lower.includes('tempo')) {
      return 'fa-gauge-high';
    }
    if (lower.includes('hydrat') || lower.includes('fuel') || lower.includes('water') || lower.includes('nutrition')) {
      return 'fa-droplet';
    }
    if (lower.includes('recover') || lower.includes('sleep') || lower.includes('rest') || lower.includes('adapt')) {
      return 'fa-heart-pulse';
    }
    if (lower.includes('rule') || lower.includes('gear') || lower.includes('shoe') || lower.includes('equipment')) {
      return 'fa-shield-halved';
    }
    if (lower.includes('volume') || lower.includes('mileage') || lower.includes('distance') || lower.includes('endur')) {
      return 'fa-chart-line';
    }
    return 'fa-microchip';
  }

  function renderCoachDirectives(container, notesList) {
    if (!container) return;
    container.innerHTML = '';
    const notes = (notesList && notesList.length > 0) ? notesList : [
      "Pacing Discipline: Start your runs at an aerobic conversational pace and negative-split the second half.",
      "Hydration & Fuel: Practice fluid and electrolyte intake on all sessions exceeding 60 minutes.",
      "Recovery & Adaptation: Muscle repair and cardiovascular adaptations solidify during sleep. Honor your rest days."
    ];

    notes.forEach(noteRaw => {
      const parsed = parseCoachDirective(noteRaw);
      const icon = getDirectiveIcon(parsed.title);
      const card = document.createElement('div');
      card.className = 'tech-directive-card';
      card.innerHTML = `
        <div class="tech-directive-header">
          <div class="tech-directive-icon"><i class="fa-solid ${icon}" aria-hidden="true"></i></div>
          <span class="tech-directive-title">${escapeHtml(parsed.title)}</span>
        </div>
        <div class="tech-directive-body">${escapeHtml(parsed.body)}</div>
      `;
      container.appendChild(card);
    });
  }

  function renderWorkoutTelemetryRows(workouts) {
    if (!workouts || workouts.length === 0) return '';

    return workouts.map(wo => {
      const cleanType = stripEmojis(wo.type || 'Standard Run');
      const isRaceDay = cleanType.toUpperCase().includes('RACE DAY');
      const dayShort = (wo.day || '').substring(0, 3).toUpperCase();
      const distNum = parseFloat(wo.distance_km || 0).toFixed(1);
      const isCompleted = !!wo.completed;

      let metricHtml = `
        <span class="workout-km-num">${distNum}</span>
        <span class="workout-km-unit">KM</span>
      `;
      if (isCompleted && wo.completed_distance_km) {
        const compKm = parseFloat(wo.completed_distance_km).toFixed(1);
        metricHtml = `
          <span class="workout-km-num text-success">${compKm}</span>
          <span class="workout-km-unit" style="font-size:0.62rem;opacity:0.8;">/ ${distNum} KM</span>
        `;
      }

      return `
        <div class="workout-telemetry-row ${isRaceDay ? 'race-day-row' : ''} ${isCompleted ? 'completed-row' : ''}">
          <div class="workout-day-pill ${isCompleted ? 'completed' : ''}">
            ${isCompleted ? '<i class="fa-solid fa-check text-success me-1" aria-hidden="true"></i>' : ''}${escapeHtml(dayShort)}
          </div>
          <div class="workout-desc-block">
            ${isRaceDay ? '<i class="fa-solid fa-flag-checkered text-warning me-1" aria-hidden="true"></i>' : ''}
            <span>${escapeHtml(cleanType)}</span>
            ${isCompleted ? '<span class="workout-status-badge completed ms-1"><i class="fa-solid fa-circle-check me-1" aria-hidden="true"></i>COMPLETED</span>' : ''}
          </div>
          <div class="workout-metric-pill">
            ${metricHtml}
          </div>
        </div>
      `;
    }).join('');
  }

  // --- Modal Open & Init ---
  window.openRunningPlanModal = function () {
    const modalEl = document.getElementById('runningPlanModal');
    if (!modalEl) return;

    function doOpen() {
      if (typeof bootstrap !== 'undefined') {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      } else {
        modalEl.classList.add('show');
        modalEl.style.display = 'block';
      }
    }

    // Check if user already has an active goal
    if (activeGoalPlan && activeGoalPlan.status === 'active') {
      showActivePlanView(activeGoalPlan);
      doOpen();
    } else {
      // Re-fetch to ensure we don't open the wizard if an active plan already exists
      fetch('/api/goals')
        .then(res => res.json())
        .then(data => {
          if (data && data.status === 'success' && data.goals) {
            const activeGoals = data.goals.filter(g => g.status === 'active');
            if (activeGoals.length > 0) {
              const pinned = activeGoals.find(g => g.dashboard_pinned);
              activeGoalPlan = pinned || activeGoals[0];
              updateSmallCircleUI(activeGoalPlan);
              updateHomeScreenWidget(activeGoalPlan);
              showActivePlanView(activeGoalPlan);
              doOpen();
              return;
            }
          }
          initPlanWizard();
          doOpen();
        })
        .catch(() => {
          initPlanWizard();
          doOpen();
        });
    }
  };

  function initPlanWizard() {
    const wizardEl = document.getElementById('aiPlanWizard');
    const activeViewEl = document.getElementById('activePlanView');
    if (wizardEl) wizardEl.style.display = 'block';
    if (activeViewEl) activeViewEl.style.display = 'none';

    // Show or hide shortcut banner to active plan if one exists
    const shortcutBanner = document.getElementById('activePlanShortcutBanner');
    if (shortcutBanner) {
      shortcutBanner.style.display = (activeGoalPlan && activeGoalPlan.status === 'active') ? 'flex' : 'none';
    }

    // Reset wizard state: race distance, date, and preferred day are mandatory and unfilled by default
    planWizardState.step = 1;
    planWizardState.targetDistanceKm = null;
    planWizardState.targetDate = null;
    planWizardState.daysPerWeek = 3;
    planWizardState.longRunDay = null;
    planWizardState.raceName = '';
    planWizardState.generatedPlan = null;

    // Clear distance presets & custom input
    const customInput = document.getElementById('customDistanceInput');
    if (customInput) customInput.value = '';
    document.querySelectorAll('#distancePresetOptions .plan-choice-card').forEach(c => c.classList.remove('active'));

    // Clear race date input and shortcuts
    const dateInput = document.getElementById('planRaceDateInput');
    if (dateInput) {
      dateInput.value = '';
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      dateInput.min = tomorrow.toISOString().split('T')[0];
    }
    document.querySelectorAll('.plan-shortcut-btn').forEach(b => b.classList.remove('active'));

    // Days per week: 3 days by default
    const dayCards = document.querySelectorAll('#daysPerWeekOptions .plan-choice-card');
    dayCards.forEach(c => {
      const args = c.getAttribute('data-args');
      if (args && args.includes('3')) {
        c.classList.add('active');
      } else {
        c.classList.remove('active');
      }
    });

    // Clear preferred long run day selections
    document.querySelectorAll('#longRunDayOptions .plan-tab-choice').forEach(b => b.classList.remove('active'));

    // Hide any previous validation errors
    ['planStep1Error', 'planStep2Error', 'planStep4Error'].forEach(id => {
      const errEl = document.getElementById(id);
      if (errEl) {
        errEl.classList.add('d-none');
        errEl.classList.remove('d-flex');
      }
    });

    updateCalculatedWeeksDisplay();
    goToPlanStep(1);
  }

  function updateCalculatedWeeksDisplay() {
    const textEl = document.getElementById('planCalculatedWeeksText');
    if (!textEl) return;
    if (!planWizardState.targetDate) {
      textEl.textContent = 'Select a race date above to calculate training horizon';
      textEl.className = 'fw-bold fs-6 text-muted';
      return;
    }
    const weeks = calculateWeeksUntil(planWizardState.targetDate);
    textEl.textContent = `${weeks} Week${weeks === 1 ? '' : 's'} of Training`;
    textEl.className = 'fw-bold fs-5 text-accent';
  }

  function goToPlanStep(stepNum) {
    // --- Mandatory Validation Checks Before Advancing ---

    // Advancing from Step 1 requires distance selection
    if (stepNum > 1) {
      if (!planWizardState.targetDistanceKm || planWizardState.targetDistanceKm <= 0) {
        const err1 = document.getElementById('planStep1Error');
        if (err1) {
          err1.classList.remove('d-none');
          err1.classList.add('d-flex');
        }
        return;
      }
    }

    // Advancing from Step 2 requires target date selection in the future
    if (stepNum > 2) {
      if (!planWizardState.targetDate) {
        const err2 = document.getElementById('planStep2Error');
        if (err2) {
          const span = err2.querySelector('span');
          if (span) span.textContent = 'Please pick a future race date or choose a shortcut to proceed.';
          err2.classList.remove('d-none');
          err2.classList.add('d-flex');
        }
        return;
      }
      const selectedDate = new Date(planWizardState.targetDate + 'T00:00:00');
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (isNaN(selectedDate.getTime()) || selectedDate <= today) {
        const err2 = document.getElementById('planStep2Error');
        if (err2) {
          const span = err2.querySelector('span');
          if (span) span.textContent = 'Race date must be at least tomorrow or in the future.';
          err2.classList.remove('d-none');
          err2.classList.add('d-flex');
        }
        return;
      }
    }

    // Advancing from Step 3 ensures daysPerWeek is set (default 3)
    if (stepNum > 3) {
      if (!planWizardState.daysPerWeek || planWizardState.daysPerWeek < 2 || planWizardState.daysPerWeek > 6) {
        planWizardState.daysPerWeek = 3;
      }
    }

    planWizardState.step = stepNum;

    // Update Step Bars
    for (let s = 1; s <= 5; s++) {
      const bar = document.getElementById(`planStepBar${s}`);
      if (bar) {
        if (s <= stepNum) {
          bar.classList.add('active');
        } else {
          bar.classList.remove('active');
        }
      }
    }

    const stepText = document.getElementById('planStepNumber');
    if (stepText) {
      if (stepNum <= 4) {
        stepText.textContent = `Step ${stepNum} of 4`;
      } else if (stepNum === 5) {
        stepText.textContent = `Generating Plan...`;
      } else {
        stepText.textContent = `Review & Plan`;
      }
    }

    // Coach Speech Bubble message updates dynamically
    const coachMsg = document.getElementById('coachSpeechMessage');
    if (coachMsg) {
      if (stepNum === 1) {
        coachMsg.textContent = "Diagnostic Step 1: Select your target race distance or configure a custom endurance objective in kilometres.";
      } else if (stepNum === 2) {
        coachMsg.textContent = `Target set: ${planWizardState.targetDistanceKm} KM. Configure your race date so the engine can calculate optimal training horizon and progression curves.`;
      } else if (stepNum === 3) {
        coachMsg.textContent = "Training Frequency: How many sessions per week fit your schedule? A 3-day split provides an optimal balance between stimulus and recovery.";
      } else if (stepNum === 4) {
        coachMsg.textContent = "Final Calibration: Designate your long run anchor day and current aerobic baseline to prevent overtraining risk.";
      } else if (stepNum === 6) {
        coachMsg.textContent = "Periodized training plan generated. Review your progressive long runs, session telemetry, and tactical coach protocols below.";
      }
    }

    // Hide all step containers
    ['planWizardStep1', 'planWizardStep2', 'planWizardStep3', 'planWizardStep4', 'planWizardLoading', 'planWizardReview'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });

    if (stepNum === 1) {
      document.getElementById('planWizardStep1').style.display = 'block';
    } else if (stepNum === 2) {
      document.getElementById('planWizardStep2').style.display = 'block';
    } else if (stepNum === 3) {
      document.getElementById('planWizardStep3').style.display = 'block';
    } else if (stepNum === 4) {
      document.getElementById('planWizardStep4').style.display = 'block';
    } else if (stepNum === 5) {
      document.getElementById('planWizardLoading').style.display = 'block';
    } else if (stepNum === 6) {
      document.getElementById('planWizardReview').style.display = 'block';
    }
  }

  // --- Step 1 Handlers ---
  function selectPlanDistance(km, title) {
    planWizardState.targetDistanceKm = parseFloat(km);
    planWizardState.raceName = title || `${km} km Race`;

    const customInput = document.getElementById('customDistanceInput');
    if (customInput) customInput.value = '';

    const cards = document.querySelectorAll('#distancePresetOptions .plan-choice-card');
    cards.forEach(c => c.classList.remove('active'));
    if (this && this.classList) {
      this.classList.add('active');
    }

    const err1 = document.getElementById('planStep1Error');
    if (err1) {
      err1.classList.add('d-none');
      err1.classList.remove('d-flex');
    }
  }

  function handleCustomDistanceChange(event, el) {
    const val = parseFloat(el.value);
    if (!isNaN(val) && val > 0) {
      planWizardState.targetDistanceKm = val;
      planWizardState.raceName = `${val} km Custom Race`;
      const cards = document.querySelectorAll('#distancePresetOptions .plan-choice-card');
      cards.forEach(c => c.classList.remove('active'));

      const err1 = document.getElementById('planStep1Error');
      if (err1) {
        err1.classList.add('d-none');
        err1.classList.remove('d-flex');
      }
    } else {
      planWizardState.targetDistanceKm = null;
    }
  }

  // --- Step 2 Handlers ---
  function setPlanWeeksShortcut(weeks) {
    planWizardState.targetDate = setDefaultRaceDate(parseInt(weeks, 10));
    const input = document.getElementById('planRaceDateInput');
    if (input) input.value = planWizardState.targetDate;

    const btns = document.querySelectorAll('.plan-shortcut-btn');
    btns.forEach(b => b.classList.remove('active'));
    if (this && this.classList) {
      this.classList.add('active');
    }

    const err2 = document.getElementById('planStep2Error');
    if (err2) {
      err2.classList.add('d-none');
      err2.classList.remove('d-flex');
    }

    updateCalculatedWeeksDisplay();
  }

  function handlePlanDateChange(event, el) {
    if (el.value) {
      planWizardState.targetDate = el.value;
      const btns = document.querySelectorAll('.plan-shortcut-btn');
      btns.forEach(b => b.classList.remove('active'));

      const err2 = document.getElementById('planStep2Error');
      if (err2) {
        err2.classList.add('d-none');
        err2.classList.remove('d-flex');
      }

      updateCalculatedWeeksDisplay();
    } else {
      planWizardState.targetDate = null;
      updateCalculatedWeeksDisplay();
    }
  }

  // --- Step 3 Handlers ---
  function selectPlanDays(days) {
    planWizardState.daysPerWeek = parseInt(days, 10);
    const cards = document.querySelectorAll('#daysPerWeekOptions .plan-choice-card');
    cards.forEach(c => c.classList.remove('active'));
    if (this && this.classList) {
      this.classList.add('active');
    }
  }

  // --- Step 4 Handlers ---
  function selectLongRunDay(day) {
    planWizardState.longRunDay = day;
    const btns = document.querySelectorAll('#longRunDayOptions .plan-tab-choice');
    btns.forEach(b => b.classList.remove('active'));
    if (this && this.classList) {
      this.classList.add('active');
    }

    const err4 = document.getElementById('planStep4Error');
    if (err4) {
      err4.classList.add('d-none');
      err4.classList.remove('d-flex');
    }
  }

  // --- Step 5: Trigger AI Plan Generation ---
  function triggerPlanGeneration() {
    // Re-verify Step 1 mandatory distance
    if (!planWizardState.targetDistanceKm || planWizardState.targetDistanceKm <= 0) {
      goToPlanStep(1);
      const err1 = document.getElementById('planStep1Error');
      if (err1) { err1.classList.remove('d-none'); err1.classList.add('d-flex'); }
      return;
    }

    // Re-verify Step 2 mandatory date
    if (!planWizardState.targetDate) {
      goToPlanStep(2);
      const err2 = document.getElementById('planStep2Error');
      if (err2) { err2.classList.remove('d-none'); err2.classList.add('d-flex'); }
      return;
    }

    // Verify Step 4 mandatory preferred long run day
    if (!planWizardState.longRunDay) {
      const err4 = document.getElementById('planStep4Error');
      if (err4) { err4.classList.remove('d-none'); err4.classList.add('d-flex'); }
      return;
    }

    const fitnessEl = document.getElementById('planFitnessLevelSelect');
    if (fitnessEl) planWizardState.fitnessLevel = fitnessEl.value;

    const raceNameEl = document.getElementById('planRaceNameInput');
    if (raceNameEl && raceNameEl.value.trim()) {
      planWizardState.raceName = raceNameEl.value.trim();
    } else {
      planWizardState.raceName = `${planWizardState.targetDistanceKm} km Target Race`;
    }

    goToPlanStep(5); // Loading screen

    const payload = {
      target_distance_km: planWizardState.targetDistanceKm,
      target_date: planWizardState.targetDate,
      days_per_week: planWizardState.daysPerWeek,
      fitness_level: planWizardState.fitnessLevel,
      long_run_day: planWizardState.longRunDay,
      race_name: planWizardState.raceName
    };

    fetch('/api/goals/ai-generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(payload)
    })
      .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, body: data })))
      .then(({ status, ok, body }) => {
        if (ok && body.status === 'success') {
          planWizardState.generatedPlan = body;
          renderPlanReview(body);
          goToPlanStep(6);
        } else {
          alert(body.error || body.message || 'Error generating plan');
          goToPlanStep(4);
        }
      })
      .catch(err => {
        console.error('Plan generation failed', err);
        alert('Could not connect to plan generator. Please try again.');
        goToPlanStep(4);
      });
  }

  // --- Step 6: Render Plan Review Screen ---
  function renderPlanReview(plan) {
    // Feasibility Banner
    const banner = document.getElementById('planFeasibilityBanner');
    if (banner) {
      if (plan.is_feasible) {
        banner.style.display = 'block';
        banner.style.background = 'rgba(34, 197, 94, 0.12)';
        banner.style.border = '1px solid rgba(34, 197, 94, 0.3)';
        banner.style.color = '#4ade80';
        banner.innerHTML = `
          <div class="d-flex align-items-center gap-2">
            <i class="fas fa-check-circle fs-5"></i>
            <div>
              <div class="fw-bold small">Feasible &amp; Injury-Safe!</div>
              <div style="font-size: 0.74rem; opacity: 0.9;">This timeframe aligns with safe weekly volume progression.</div>
            </div>
          </div>
        `;
      } else {
        banner.style.display = 'block';
        banner.style.background = 'rgba(234, 179, 8, 0.12)';
        banner.style.border = '1px solid rgba(234, 179, 8, 0.3)';
        banner.style.color = '#fde047';
        const msg = plan.feasibility_info ? plan.feasibility_info.message : 'Tight timeline for this distance.';
        const sugg = plan.feasibility_info ? plan.feasibility_info.suggested_date : '';
        banner.innerHTML = `
          <div class="d-flex align-items-start gap-2">
            <i class="fas fa-exclamation-triangle fs-5 mt-1"></i>
            <div>
              <div class="fw-bold small">Challenging Timeline</div>
              <div style="font-size: 0.74rem; opacity: 0.9;">${escapeHtml(msg)}</div>
              ${sugg ? `<div class="mt-1" style="font-size: 0.72rem;"><strong>Suggested race date:</strong> ${sugg}</div>` : ''}
            </div>
          </div>
        `;
      }
    }

    // Hero Summary
    document.getElementById('reviewPlanDistanceBadge').textContent = `${plan.target_distance_km} KM TARGET`;
    document.getElementById('reviewPlanRaceTitle').textContent = stripEmojis(plan.race_name || `${plan.target_distance_km} km Race`);
    document.getElementById('reviewPlanTotalWeeks').textContent = `${plan.total_weeks} Weeks`;
    
    const raceDateEl = document.getElementById('reviewPlanRaceDate');
    if (raceDateEl) {
      raceDateEl.innerHTML = `<i class="fa-regular fa-calendar-check text-accent me-1" aria-hidden="true"></i>Race Day: ${formatDisplayDate(plan.target_date)}`;
    }
    const daysEl = document.getElementById('reviewPlanDays');
    if (daysEl) {
      daysEl.innerHTML = `<i class="fa-solid fa-person-running text-accent me-1" aria-hidden="true"></i>${plan.days_per_week} Sessions / week`;
    }
    document.getElementById('reviewPlanWeeksCount').textContent = `${plan.total_weeks} Weeks Total`;

    // Week-by-Week Roadmap
    const container = document.getElementById('reviewPlanWeeksContainer');
    if (container) {
      container.innerHTML = '';
      (plan.weeks || []).forEach(w => {
        const weekEl = document.createElement('div');
        weekEl.className = `plan-week-row ${w.is_current ? 'current-week' : ''}`;
        
        const longVal = parseFloat(w.long_run_km || w.long_run || 0).toFixed(1);
        const cleanPhase = stripEmojis(w.phase || `Week ${w.week_number}`).toUpperCase();
        const workoutsHtml = renderWorkoutTelemetryRows(w.workouts);

        weekEl.innerHTML = `
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <div class="d-flex align-items-center gap-2">
                <span class="week-index-badge">WK ${String(w.week_number).padStart(2, '0')}</span>
                <span class="week-phase-title">${escapeHtml(cleanPhase)}</span>
                ${w.is_current ? `<span class="tech-badge-current"><span class="tech-pulse-dot"></span>ACTIVE</span>` : ''}
              </div>
              <div class="text-muted" style="font-size: 0.68rem; margin-top: 3px; font-family: var(--font-family-mono, monospace); letter-spacing: 0.04em;">
                ${escapeHtml(w.date_range)}
              </div>
            </div>
            <div class="text-end">
              <div class="workout-metric-pill justify-content-end">
                <span class="workout-km-num" style="font-size: 0.98rem;">${longVal}</span>
                <span class="workout-km-unit">KM</span>
              </div>
              <div class="text-muted" style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em;">Long Run</div>
            </div>
          </div>
          <div class="mt-2 pt-1">
            ${workoutsHtml}
          </div>
        `;
        container.appendChild(weekEl);
      });
    }

    // Coach Notes
    const notesEl = document.getElementById('reviewPlanCoachNotes');
    if (notesEl) {
      renderCoachDirectives(notesEl, plan.coach_notes);
    }

    // Reset Home Screen Radio to default Yes
    const yesRadio = document.querySelector('input[name="planHomeScreenChoice"][value="yes"]');
    if (yesRadio) yesRadio.checked = true;
    updateHomeScreenChoiceCards();
  }

  // --- Home Screen Question Choice Card State ---
  function handleHomeScreenChoiceChange(event, el) {
    planWizardState.homeScreenChoice = el.value;
    updateHomeScreenChoiceCards();
  }

  function updateHomeScreenChoiceCards() {
    const isYes = document.querySelector('input[name="planHomeScreenChoice"][value="yes"]')?.checked;
    const yesCard = document.getElementById('homeChoiceYesLabel');
    const noCard = document.getElementById('homeChoiceNoLabel');

    if (yesCard && noCard) {
      if (isYes) {
        yesCard.classList.add('active');
        noCard.classList.remove('active');
        yesCard.querySelector('i')?.classList.replace('fa-circle', 'fa-check-circle');
        noCard.querySelector('i')?.classList.replace('fa-check-circle', 'fa-circle');
      } else {
        noCard.classList.add('active');
        yesCard.classList.remove('active');
        noCard.querySelector('i')?.classList.replace('fa-circle', 'fa-check-circle');
        yesCard.querySelector('i')?.classList.replace('fa-check-circle', 'fa-circle');
      }
    }
  }

  // --- Confirm & Activate Plan (The Final Handshake) ---
  function confirmAndActivatePlan() {
    const isPinnedToHome = document.querySelector('input[name="planHomeScreenChoice"][value="yes"]')?.checked;

    const payload = {
      goal_type: 'race_plan',
      target_distance_km: planWizardState.targetDistanceKm,
      target_date: planWizardState.targetDate,
      days_per_week: planWizardState.daysPerWeek,
      dashboard_pinned: !!isPinnedToHome,
      race_name: planWizardState.raceName || `${planWizardState.targetDistanceKm} km Race`,
      ai_plan: planWizardState.generatedPlan,
      force: true
    };

    fetch('/api/goals', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          // Play celebration & fly-to-circle effect
          animatePlanToCircle(planWizardState.targetDistanceKm);

          // Close modal
          const modalEl = document.getElementById('runningPlanModal');
          if (modalEl && typeof bootstrap !== 'undefined') {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
          }

          // Reload active plan from backend
          loadActiveRunningPlan();
        } else {
          alert(data.error || 'Failed to activate plan.');
        }
      })
      .catch(err => {
        console.error('Failed to save goal plan', err);
        alert('Could not save plan. Please check your connection.');
      });
  }

  // --- Animation: Plan comes and sits in the small circle ---
  function animatePlanToCircle(distKm) {
    const circleBtn = document.getElementById('runningPlanCircleBtn');
    const fabBtn = document.getElementById('runningPlanFabBtn');

    [circleBtn, fabBtn].forEach(btn => {
      if (!btn) return;
      btn.classList.add('has-plan');
      btn.style.transform = 'scale(1.25)';
      setTimeout(() => {
        btn.style.transform = '';
      }, 400);
    });

    const badge = document.getElementById('runningPlanCircleBadge');
    if (badge) {
      badge.textContent = `${distKm}K`;
      badge.style.display = 'block';
    }

    const fabBadge = document.getElementById('runningPlanFabBadge');
    if (fabBadge) {
      fabBadge.textContent = `${distKm}K`;
      fabBadge.style.display = 'block';
    }

    const titleEl = document.getElementById('runningPlanCircleTitle');
    if (titleEl) titleEl.textContent = planWizardState.raceName || `${distKm} km Race`;

    const subEl = document.getElementById('runningPlanCircleSub');
    if (subEl) subEl.textContent = 'Active Plan &bull; Tap to view';

    // Show flash toast
    showPlanToast(`Running Plan calibrated and activated in Running Plan hub.`);
  }

  function showPlanToast(msg) {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '110px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.zIndex = '1090';
    toast.style.background = 'rgba(15, 23, 42, 0.95)';
    toast.style.border = '1px solid #00d2ff';
    toast.style.color = '#f8fafc';
    toast.style.padding = '10px 18px';
    toast.style.borderRadius = '30px';
    toast.style.boxShadow = '0 8px 30px rgba(0, 210, 255, 0.35)';
    toast.style.fontSize = '0.85rem';
    toast.style.fontWeight = '700';
    toast.textContent = msg;

    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(-50%) translateY(10px)';
      setTimeout(() => toast.remove(), 400);
    }, 3200);
  }

  // --- Load Active Goal & Manage Home Widget / Circle ---
  function loadActiveRunningPlan() {
    fetch('/api/goals')
      .then(res => res.json())
      .then(data => {
        if (data.status !== 'success' || !data.goals) return;

        const activeGoals = data.goals.filter(g => g.status === 'active');
        if (activeGoals.length > 0) {
          // Find pinned goal, or pick the first active goal
          const pinned = activeGoals.find(g => g.dashboard_pinned);
          activeGoalPlan = pinned || activeGoals[0];
          updateSmallCircleUI(activeGoalPlan);
          updateHomeScreenWidget(activeGoalPlan);
        } else {
          activeGoalPlan = null;
          resetSmallCircleUI();
          hideHomeScreenWidget();

          // Check if there was a recently cancelled plan due to inactivity
          const cancelledPlan = data.goals.find(g => g.status === 'cancelled' && g.ai_plan && g.ai_plan.cancellation_reason);
          const speechEl = document.getElementById('coachSpeechMessage');
          if (cancelledPlan && speechEl) {
            const raceName = stripEmojis(cancelledPlan.race_name || `${cancelledPlan.target_distance_km} km`);
            speechEl.innerHTML = `
              <strong>Welcome back.</strong> Your previous <strong>${escapeHtml(raceName)}</strong> plan was archived due to 14 days of inactivity, but every training comeback begins with consistent base mileage.<br>
              Let's recalibrate a periodized plan tailored to your current fitness.
            `;
          }
        }
      })
      .catch(err => console.error('Error loading running plan', err));
  }

  function updateSmallCircleUI(goal) {
    const circleBtn = document.getElementById('runningPlanCircleBtn');
    const fabBtn = document.getElementById('runningPlanFabBtn');
    const badge = document.getElementById('runningPlanCircleBadge');
    const fabBadge = document.getElementById('runningPlanFabBadge');
    const titleEl = document.getElementById('runningPlanCircleTitle');
    const subEl = document.getElementById('runningPlanCircleSub');
    const openBtn = document.getElementById('runningPlanOpenActionBtn');

    if (circleBtn) circleBtn.classList.add('has-plan');
    if (fabBtn) fabBtn.classList.add('has-plan');

    const distLabel = `${goal.target_distance_km}K`;
    if (badge) {
      badge.textContent = distLabel;
      badge.style.display = 'block';
    }
    if (fabBadge) {
      fabBadge.textContent = distLabel;
      fabBadge.style.display = 'block';
    }

    if (titleEl) {
      titleEl.textContent = goal.race_name || `${goal.target_distance_km} km Race`;
    }

    if (subEl) {
      let thisWeekLong = goal.target_distance_km;
      if (goal.ai_plan && goal.ai_plan.weeks) {
        const cur = goal.ai_plan.weeks.find(w => w.is_current) || goal.ai_plan.weeks[0];
        if (cur) thisWeekLong = cur.long_run_km || cur.long_run;
      } else if (goal.calendar && goal.calendar.weeks) {
        const cur = goal.calendar.weeks.find(w => w.is_current) || goal.calendar.weeks[0];
        if (cur) thisWeekLong = cur.long_run;
      }
      subEl.textContent = `This week: ${thisWeekLong} km long run`;
    }

    if (openBtn) {
      openBtn.textContent = 'View Plan';
    }
  }

  function resetSmallCircleUI() {
    const circleBtn = document.getElementById('runningPlanCircleBtn');
    const fabBtn = document.getElementById('runningPlanFabBtn');
    const badge = document.getElementById('runningPlanCircleBadge');
    const fabBadge = document.getElementById('runningPlanFabBadge');
    const titleEl = document.getElementById('runningPlanCircleTitle');
    const subEl = document.getElementById('runningPlanCircleSub');
    const openBtn = document.getElementById('runningPlanOpenActionBtn');

    if (circleBtn) circleBtn.classList.remove('has-plan');
    if (fabBtn) fabBtn.classList.remove('has-plan');
    if (badge) badge.style.display = 'none';
    if (fabBadge) fabBadge.style.display = 'none';

    if (titleEl) titleEl.textContent = 'Running Plan';
    if (subEl) subEl.textContent = 'Set a race target & train with AI';
    if (openBtn) openBtn.textContent = 'Set Plan';
  }

  function updateHomeScreenWidget(goal) {
    const card = document.getElementById('pinnedRunningPlanCard');
    if (!card) return;

    if (!goal.dashboard_pinned) {
      card.style.display = 'none';
      return;
    }

    card.style.display = 'block';

    const titleEl = document.getElementById('pinnedPlanTitle');
    const countdownEl = document.getElementById('pinnedPlanCountdown');
    const weekFocusEl = document.getElementById('pinnedPlanWeekFocus');
    const progressBar = document.getElementById('pinnedPlanProgressBar');
    const progressText = document.getElementById('pinnedPlanProgressText');
    const daysText = document.getElementById('pinnedPlanDaysText');
    const workoutsList = document.getElementById('pinnedPlanWorkoutsList');

    if (titleEl) titleEl.textContent = stripEmojis(goal.race_name || `${goal.target_distance_km} km Race Target`);
    if (countdownEl) {
      countdownEl.innerHTML = `<i class="fa-regular fa-calendar-check text-accent me-1" aria-hidden="true"></i>Target: ${formatDisplayDate(goal.target_date)}`;
    }

    let thisWeekTarget = goal.target_distance_km;
    let currentWeekNum = 1;
    let totalWeeks = 8;
    let currentWorkouts = [];

    if (goal.ai_plan && goal.ai_plan.weeks) {
      totalWeeks = goal.ai_plan.total_weeks || goal.ai_plan.weeks.length;
      const cur = goal.ai_plan.weeks.find(w => w.is_current) || goal.ai_plan.weeks[0];
      if (cur) {
        thisWeekTarget = cur.long_run_km || cur.long_run;
        currentWeekNum = cur.week_number;
        currentWorkouts = cur.workouts || [];
      }
    } else if (goal.calendar && goal.calendar.weeks) {
      totalWeeks = goal.calendar.weeks.length;
      const cur = goal.calendar.weeks.find(w => w.is_current) || goal.calendar.weeks[0];
      if (cur) {
        thisWeekTarget = cur.long_run;
        currentWeekNum = cur.week_number;
        currentWorkouts = cur.workouts || [];
      }
    }

    if (weekFocusEl) weekFocusEl.textContent = `${parseFloat(thisWeekTarget).toFixed(1)} km`;
    if (daysText) daysText.textContent = `${goal.days_per_week} runs / week`;

    // Completion percentage calculation for this week's workouts
    const completedWorkoutsCount = currentWorkouts.filter(w => w.completed).length;
    const totalWeekWorkouts = currentWorkouts.length;
    let weekCompletionPct = 0;
    if (totalWeekWorkouts > 0) {
      weekCompletionPct = Math.round((completedWorkoutsCount / totalWeekWorkouts) * 100);
    } else {
      weekCompletionPct = Math.min(100, Math.round((currentWeekNum / totalWeeks) * 100));
    }

    if (progressBar) {
      progressBar.style.width = `${weekCompletionPct}%`;
      progressBar.setAttribute('aria-valuenow', weekCompletionPct);
      if (weekCompletionPct === 100 && totalWeekWorkouts > 0) {
        progressBar.style.background = 'linear-gradient(90deg, #10b981, #22c55e)';
        progressBar.style.boxShadow = '0 0 10px rgba(34, 197, 94, 0.5)';
      } else {
        progressBar.style.background = 'linear-gradient(90deg, #00b4d8, #00d2ff)';
        progressBar.style.boxShadow = '0 0 8px rgba(0, 210, 255, 0.3)';
      }
    }
    if (progressText) {
      if (totalWeekWorkouts > 0) {
        progressText.innerHTML = `Week ${currentWeekNum} of ${totalWeeks} &bull; <span class="${completedWorkoutsCount === totalWeekWorkouts ? 'text-success fw-bold' : ''}">${completedWorkoutsCount}/${totalWeekWorkouts} completed</span> (${weekCompletionPct}%)`;
      } else {
        progressText.textContent = `Week ${currentWeekNum} of ${totalWeeks} (${Math.round((currentWeekNum / totalWeeks) * 100)}% complete)`;
      }
    }

    if (workoutsList) {
      workoutsList.innerHTML = '';
      if (currentWorkouts.length > 0) {
        workoutsList.innerHTML = renderWorkoutTelemetryRows(currentWorkouts);
      } else {
        const item = document.createElement('div');
        item.className = 'workout-telemetry-row';
        item.innerHTML = `
          <div class="workout-day-pill">LONG</div>
          <div class="workout-desc-block"><span>Endurance Anchor</span></div>
          <div class="workout-metric-pill">
            <span class="workout-km-num">${parseFloat(thisWeekTarget).toFixed(1)}</span>
            <span class="workout-km-unit">KM</span>
          </div>
        `;
        workoutsList.appendChild(item);
      }
    }
  }

  function hideHomeScreenWidget() {
    const card = document.getElementById('pinnedRunningPlanCard');
    if (card) card.style.display = 'none';
  }

  // --- Show Active Plan View in Modal ---
  function showActivePlanView(goal) {
    const wizardEl = document.getElementById('aiPlanWizard');
    const activeViewEl = document.getElementById('activePlanView');
    if (wizardEl) wizardEl.style.display = 'none';
    if (activeViewEl) activeViewEl.style.display = 'block';

    document.getElementById('activePlanTitle').textContent = stripEmojis(goal.race_name || `${goal.target_distance_km} km Target`);
    
    const countdownEl = document.getElementById('activePlanCountdown');
    if (countdownEl) {
      countdownEl.innerHTML = `<i class="fa-regular fa-calendar-check text-accent me-1" aria-hidden="true"></i>Target Date: ${formatDisplayDate(goal.target_date)}`;
    }

    let currentWeekLong = goal.target_distance_km;
    let currentWeekNum = 1;
    let totalWeeks = 8;
    let weeksArray = [];

    if (goal.ai_plan && goal.ai_plan.weeks) {
      weeksArray = goal.ai_plan.weeks;
      totalWeeks = goal.ai_plan.total_weeks || weeksArray.length;
      const cur = weeksArray.find(w => w.is_current) || weeksArray[0];
      if (cur) {
        currentWeekLong = cur.long_run_km;
        currentWeekNum = cur.week_number;
      }
    } else if (goal.calendar && goal.calendar.weeks) {
      weeksArray = goal.calendar.weeks;
      totalWeeks = weeksArray.length;
      const cur = weeksArray.find(w => w.is_current) || weeksArray[0];
      if (cur) {
        currentWeekLong = cur.long_run;
        currentWeekNum = cur.week_number;
      }
    }

    document.getElementById('activePlanLongRunTarget').textContent = `${parseFloat(currentWeekLong).toFixed(1)} km`;

    // Overall workouts completion calculation
    let totalWorkoutsCount = 0;
    let completedWorkoutsCount = 0;
    weeksArray.forEach(w => {
      (w.workouts || []).forEach(wo => {
        totalWorkoutsCount++;
        if (wo.completed) completedWorkoutsCount++;
      });
    });

    const percent = totalWorkoutsCount > 0 
      ? Math.round((completedWorkoutsCount / totalWorkoutsCount) * 100)
      : Math.min(100, Math.round((currentWeekNum / totalWeeks) * 100));

    const pBar = document.getElementById('activePlanProgressBar');
    if (pBar) {
      pBar.style.width = `${percent}%`;
      if (percent === 100) {
        pBar.style.background = 'linear-gradient(90deg, #10b981, #22c55e)';
        pBar.style.boxShadow = '0 0 10px rgba(34, 197, 94, 0.5)';
      } else {
        pBar.style.background = 'linear-gradient(90deg, #00b4d8, #00d2ff)';
        pBar.style.boxShadow = '0 0 8px rgba(0, 210, 255, 0.3)';
      }
    }
    const percentLabel = document.getElementById('activePlanPercentLabel');
    if (percentLabel) percentLabel.textContent = `${percent}%`;
    const progressLabel = document.getElementById('activePlanProgressLabel');
    if (progressLabel) {
      progressLabel.textContent = totalWorkoutsCount > 0
        ? `Week ${currentWeekNum} of ${totalWeeks} • ${completedWorkoutsCount}/${totalWorkoutsCount} workouts done`
        : `Week ${currentWeekNum} of ${totalWeeks}`;
    }

    // Pin status button
    updateActivePinButtonUI(goal.dashboard_pinned);

    // Render Full Schedule
    const weeksListEl = document.getElementById('activePlanWeeksList');
    if (weeksListEl) {
      weeksListEl.innerHTML = '';
      weeksArray.forEach(w => {
        const row = document.createElement('div');
        const isCurrent = w.is_current;
        row.className = `plan-week-row ${isCurrent ? 'current-week' : ''}`;

        const longVal = parseFloat(w.long_run_km || w.long_run || 0).toFixed(1);
        const cleanPhase = stripEmojis(w.phase || `Week ${w.week_number}`).toUpperCase();
        const workoutsHtml = renderWorkoutTelemetryRows(w.workouts);

        const completedW = (w.workouts || []).filter(wo => wo.completed).length;
        const totalW = (w.workouts || []).length;
        let weekBadgeHtml = '';
        if (totalW > 0) {
          if (completedW === totalW) {
            weekBadgeHtml = `<span class="badge rounded-pill ms-2" style="background:rgba(34,197,94,0.18);color:#4ade80;border:1px solid rgba(34,197,94,0.4);font-size:0.62rem;font-weight:700;"><i class="fa-solid fa-check me-1"></i>ALL DONE</span>`;
          } else if (completedW > 0) {
            weekBadgeHtml = `<span class="badge rounded-pill ms-2" style="background:rgba(0,210,255,0.15);color:#00d2ff;border:1px solid rgba(0,210,255,0.3);font-size:0.62rem;font-weight:700;">${completedW}/${totalW} DONE</span>`;
          }
        }

        row.innerHTML = `
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <div class="d-flex align-items-center gap-2">
                <span class="week-index-badge">WK ${String(w.week_number).padStart(2, '0')}</span>
                <span class="week-phase-title">${escapeHtml(cleanPhase)}</span>
                ${isCurrent ? `<span class="tech-badge-current"><span class="tech-pulse-dot"></span>ACTIVE</span>` : ''}
                ${weekBadgeHtml}
              </div>
              <div class="text-muted" style="font-size: 0.68rem; margin-top: 3px; font-family: var(--font-family-mono, monospace); letter-spacing: 0.04em;">
                ${escapeHtml(w.date_range)}
              </div>
            </div>
            <div class="text-end">
              <div class="workout-metric-pill justify-content-end">
                <span class="workout-km-num" style="font-size: 0.98rem;">${longVal}</span>
                <span class="workout-km-unit">KM</span>
              </div>
              <div class="text-muted" style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em;">Long Run</div>
            </div>
          </div>
          <div class="mt-2 pt-1">
            ${workoutsHtml}
          </div>
        `;
        weeksListEl.appendChild(row);
      });
    }

    // Coach Notes
    const notesEl = document.getElementById('activePlanCoachNotes');
    if (notesEl) {
      const notes = (goal.ai_plan && goal.ai_plan.coach_notes) ? goal.ai_plan.coach_notes : [
        "Pacing Discipline: Negative splitting (running the second half strong) is the secret to a great race.",
        "Hydration & Fuel: Practice race day fluid intake on all long runs.",
        "Recovery & Sleep: Honor rest days just as much as hard runs!"
      ];
      renderCoachDirectives(notesEl, notes);
    }
  }

  function updateActivePinButtonUI(isPinned) {
    const btn = document.getElementById('activePinToggleBtn');
    const text = document.getElementById('activePinStatusText');
    const sub = document.getElementById('activePinStatusSub');

    if (isPinned) {
      if (btn) btn.textContent = 'Unpin';
      if (text) text.textContent = 'Pinned to Home Screen';
      if (sub) sub.textContent = 'Displaying full roadmap widget on home dashboard';
    } else {
      if (btn) btn.textContent = 'Pin to Home';
      if (text) text.textContent = 'Not on Home Screen';
      if (sub) sub.textContent = 'Tap to show on Home dashboard';
    }
  }

  // --- Toggle Pin from Modal or Home Widget ---
  function toggleActivePlanPin() {
    if (!activeGoalPlan) return;
    const newPinned = !activeGoalPlan.dashboard_pinned;

    fetch(`/api/goals/${activeGoalPlan.id}/pin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ pinned: newPinned })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          activeGoalPlan.dashboard_pinned = newPinned;
          updateActivePinButtonUI(newPinned);
          updateHomeScreenWidget(activeGoalPlan);
          showPlanToast(newPinned ? '📌 Plan pinned to Home Screen!' : 'Plan unpinned from Home Screen.');
        }
      });
  }

  function togglePinnedRunningPlan() {
    toggleActivePlanPin();
  }

  function deleteActivePlan() {
    if (!activeGoalPlan) return;
    if (!confirm('Are you sure you want to reset this running plan?')) return;

    fetch(`/api/goals/${activeGoalPlan.id}`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          activeGoalPlan = null;
          resetSmallCircleUI();
          hideHomeScreenWidget();
          initPlanWizard();
          showPlanToast('Plan reset. Ready to create a new one!');
        }
      });
  }

  function restartPlanWizard() {
    initPlanWizard();
  }

  // --- Register in window.RR_ACTIONS for CSP event delegation ---
  window.RR_ACTIONS = window.RR_ACTIONS || {};
  window.RR_ACTIONS.openRunningPlanModal = function () { window.openRunningPlanModal(); };
  window.RR_ACTIONS.goToPlanStep = function (step) { goToPlanStep(parseInt(step, 10)); };
  window.RR_ACTIONS.selectPlanDistance = function (km, title) { selectPlanDistance.call(this, km, title); };
  window.RR_ACTIONS.handleCustomDistanceChange = function (e) { handleCustomDistanceChange.call(this, e, this); };
  window.RR_ACTIONS.setPlanWeeksShortcut = function (w) { setPlanWeeksShortcut.call(this, w); };
  window.RR_ACTIONS.handlePlanDateChange = function (e) { handlePlanDateChange.call(this, e, this); };
  window.RR_ACTIONS.selectPlanDays = function (days) { selectPlanDays.call(this, days); };
  window.RR_ACTIONS.selectLongRunDay = function (day) { selectLongRunDay.call(this, day); };
  window.RR_ACTIONS.triggerPlanGeneration = function () { triggerPlanGeneration(); };
  window.RR_ACTIONS.handleHomeScreenChoiceChange = function (e) { handleHomeScreenChoiceChange.call(this, e, this); };
  window.RR_ACTIONS.confirmAndActivatePlan = function () { confirmAndActivatePlan(); };
  window.RR_ACTIONS.toggleActivePlanPin = function () { toggleActivePlanPin(); };
  window.RR_ACTIONS.togglePinnedRunningPlan = function () { togglePinnedRunningPlan(); };
  window.RR_ACTIONS.deleteActivePlan = function () { deleteActivePlan(); };
  window.RR_ACTIONS.restartPlanWizard = function () { restartPlanWizard(); };
  window.RR_ACTIONS.switchToActivePlanView = function () {
    if (activeGoalPlan) {
      showActivePlanView(activeGoalPlan);
    } else {
      loadActiveRunningPlan();
    }
  };

  // --- Initialize on Page Load ---
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      loadActiveRunningPlan();
    });
  } else {
    loadActiveRunningPlan();
  }

  // Expose for SPA tab switching or refresh
  window.RR = window.RR || {};
  window.RR.loadActiveRunningPlan = loadActiveRunningPlan;

})();
