/* static/js/goals.js */

// Global State for Multi-step Builder
let builderState = {
    step: 1,
    targetDistance: null,
    targetDate: null,
    daysPerWeek: 3
};

function getRecentStats() {
    let runs = [];
    try {
        const scriptEl = document.getElementById('runs-data-json');
        if (scriptEl) {
            runs = JSON.parse(scriptEl.textContent.trim() || '[]');
        }
    } catch (e) {
        console.error("Failed to parse runs data", e);
    }

    const today = new Date();
    const eightWeeksAgo = new Date();
    eightWeeksAgo.setDate(today.getDate() - 56);
    
    const recentRuns = runs.filter(r => {
        const d = new Date(r.date);
        return d >= eightWeeksAgo && d <= today;
    });

    if (recentRuns.length === 0) {
        return null;
    }

    let maxSingle = 0;
    let totalDist = 0;
    let totalPace = 0;
    let paceCount = 0;

    recentRuns.forEach(r => {
        if (r.distance_km > maxSingle) maxSingle = r.distance_km;
        totalDist += r.distance_km;
        if (r.pace > 0) {
            totalPace += r.pace;
            paceCount++;
        }
    });

    const avgWeekly = totalDist / 8.0;
    const baseline = Math.max(maxSingle, avgWeekly);
    const avgPace = paceCount > 0 ? (totalPace / paceCount) : 0;
    const runsPerWeek = recentRuns.length / 8.0;

    return {
        baselineKm: baseline,
        recentWeeklyDistance: avgWeekly,
        longestRecentRun: maxSingle,
        averagePace: avgPace,
        runsPerWeek: runsPerWeek
    };
}

function getRecommendedGoal(stats) {
    if (!stats) return null;
    
    let recommendation = {
        title: "First 3K",
        distance: 3,
        weeks: 3,
        desc: "A great starting point for beginners."
    };

    if (stats.baselineKm >= 24) {
        recommendation = { title: "Marathon", distance: 42, weeks: 16, desc: "Commit to the ultimate distance." };
    } else if (stats.baselineKm >= 12) {
        recommendation = { title: "Half Marathon", distance: 21, weeks: 12, desc: "Commit to the 21.1 km milestone." };
    } else if (stats.baselineKm >= 6) {
        recommendation = { title: "10K Challenge", distance: 10, weeks: 10, desc: "Push your limits with a 10K." };
    } else if (stats.baselineKm >= 2.5) {
        recommendation = { title: "5K Builder", distance: 5, weeks: 6, desc: "Build up to the classic 5K distance." };
    }

    return recommendation;
}

function loadPersonalGoals() {
    fetch('/api/goals')
        .then(res => res.json())
        .then(data => {
            if(data.status !== 'success') return;
            
            const activeSection = document.getElementById('activeGoalSection');
            const completedSection = document.getElementById('completedGoalsSection');
            const completedList = document.getElementById('completedGoalsList');
            const dashboardContainer = document.getElementById('dashboardGoalContainer');
            
            activeSection.innerHTML = '';
            completedList.innerHTML = '';
            if(dashboardContainer) dashboardContainer.innerHTML = '';
            
            let hasActive = false;
            let hasCompleted = false;

            if (data.goals.length === 0) {
                activeSection.innerHTML = `
                    <div class="card glass border-0 py-4 text-center">
                        <div class="card-body">
                            <h5 class="fw-bold" style="color:var(--text-main);">No active goal yet</h5>
                            <p class="mb-3" style="color:var(--text-muted);">Pick a goal below and RunRush will build a personalized training plan for you.</p>
                            <button class="btn btn-outline-primary rounded-pill px-4" onclick="showGoalBuilder()">Create Custom Goal</button>
                        </div>
                    </div>`;
                if(dashboardContainer) dashboardContainer.innerHTML = `<div class="card glass border-0"><div class="card-body text-center py-4"><p class="mb-0" style="color:var(--text-muted);">No active personal goals.</p></div></div>`;
            } else {
                data.goals.forEach(goal => {
                    if (goal.status === 'completed') {
                        hasCompleted = true;
                        completedList.innerHTML += renderCompletedGoal(goal);
                    } else {
                        hasActive = true;
                        activeSection.innerHTML += renderActiveGoal(goal);
                        
                        if(dashboardContainer && dashboardContainer.innerHTML === '') {
                            dashboardContainer.innerHTML = renderActiveGoal(goal, true);
                        }
                    }
                });
                
                if(!hasActive && dashboardContainer) {
                    dashboardContainer.innerHTML = `<div class="card glass border-0"><div class="card-body text-center py-4"><p class="mb-0" style="color:var(--text-muted);">No active personal goals.</p></div></div>`;
                }
            }
            
            completedSection.style.display = hasCompleted ? 'block' : 'none';
            
            renderRecommendationsAndPresets();
        })
        .catch(err => console.error("Error loading goals:", err));
}

function renderRecommendationsAndPresets() {
    try {
        const stats = getRecentStats();
        const recSection = document.getElementById('recommendedGoalSection');
        const recCard = document.getElementById('recommendedGoalCard');
        
        if (recSection && recCard) {
        if (stats) {
            const rec = getRecommendedGoal(stats);
            recSection.style.display = 'block';
            recCard.innerHTML = `
                <div class="card glass" style="background: var(--accent-soft); border: 1px solid var(--cyan-accent) !important;">
                    <div class="card-body d-flex flex-column flex-md-row align-items-md-center justify-content-between p-4">
                    <div class="mb-3 mb-md-0">
                        <h5 class="card-title fw-bold mb-1" style="color:var(--cyan-accent);">${rec.title}</h5>
                        <h6 class="mb-2" style="color:var(--text-main);">${rec.distance} km target &middot; ~${rec.weeks} weeks</h6>
                        <p class="small mb-2" style="color:var(--text-muted);">${rec.desc}</p>
                        <div class="d-flex align-items-center gap-3 mt-3">
                            <div class="text-center p-2 rounded" style="font-size:0.8rem; background:var(--premium-surface);">
                                <div class="mb-1" style="color:var(--text-muted);">Longest Run</div>
                                <div class="fw-bold" style="color:var(--text-main);">${stats.longestRecentRun.toFixed(1)} km</div>
                            </div>
                            <div class="text-center p-2 rounded" style="font-size:0.8rem; background:var(--premium-surface);">
                                <div class="mb-1" style="color:var(--text-muted);">Avg Weekly</div>
                                <div class="fw-bold" style="color:var(--text-main);">${stats.recentWeeklyDistance.toFixed(1)} km</div>
                            </div>
                        </div>
                        <p class="mt-3 mb-0" style="font-size: 0.8rem; color:var(--text-faint);">
                            <i class="fas fa-info-circle me-1"></i> Based on your recent running, this looks like a good next milestone.
                        </p>
                    </div>
                    <div>
                        <button class="btn btn-primary fw-bold rounded-pill px-4 py-2 w-100" onclick="createPresetGoal(${rec.distance}, ${rec.weeks})">
                            Set Goal
                        </button>
                    </div>
                    </div>
                </div>
            `;
        } else {
            recSection.style.display = 'block';
            recCard.innerHTML = `
            <div class="card glass border-0">
                <div class="card-body text-center p-4">
                    <p class="mb-0" style="color:var(--text-muted);">Log a few more runs to personalize your recommendation.</p>
                </div>
            </div>
            </div>
        `;
        }
    }

    const presets = [
        { title: "First 3K", distance: 3, weeks: 3, desc: "A great starting point for beginners." },
        { title: "Couch to 5K", distance: 5, weeks: 6, desc: "Build up to the classic 5K distance." },
        { title: "10K Challenge", distance: 10, weeks: 10, desc: "Push your limits with a 10K." },
        { title: "Half Marathon", distance: 21, weeks: 12, desc: "Commit to the 21.1 km milestone." }
    ];
    
    const list = document.getElementById('presetGoalsList');
    list.innerHTML = presets.map(p => `
        <div class="col-12 col-md-6">
            <div class="card glass h-100 preset-goal-card" onclick="createPresetGoal(${p.distance}, ${p.weeks})" style="cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                <div class="card-body text-center p-4">
                    <h5 class="card-title fw-bold mb-2" style="color:var(--text-main);">${p.title}</h5>
                    <h6 class="mb-3" style="color:var(--cyan-accent);">${p.distance} km &middot; ~${p.weeks} weeks</h6>
                    <p class="card-text small mb-4" style="color:var(--text-muted);">${p.desc}</p>
                    <button class="btn btn-sm rounded-pill px-3" style="border:1px solid var(--premium-border); color:var(--text-main);">Select</button>
                </div>
            </div>
        </div>
    `).join('');
    } catch (e) {
        console.error("Error rendering recommendations and presets:", e);
    }
}

function renderActiveGoal(goal, isDashboard = false) {
    let progressHtml = '';
    if (goal.created_at && goal.target_date) {
        const created = new Date(goal.created_at);
        const target = new Date(goal.target_date);
        const today = new Date();
        const totalDuration = target - created;
        const elapsed = today - created;
        let percent = Math.max(0, Math.min(100, (elapsed / totalDuration) * 100));
        
        progressHtml = `
            <div class="mt-4 mb-3">
                <div class="d-flex justify-content-between mb-1" style="font-size: 0.8rem; color:var(--text-muted);">
                    <span>Progress</span>
                    <span>${Math.round(percent)}%</span>
                </div>
                <div class="challenge-progress-track">
                    <div class="challenge-progress-fill" style="width: ${percent}%;"></div>
                </div>
            </div>
        `;
    }
    
    // Check if missed visually
    let isMissed = false;
    let isAtRisk = false;
    let suggestedDate = null;
    let calendarWeeks = [];
    
    if (goal.calendar && typeof goal.calendar === 'object' && goal.calendar.weeks) {
        calendarWeeks = goal.calendar.weeks;
        isMissed = goal.calendar.is_missed;
        isAtRisk = goal.calendar.is_at_risk;
        suggestedDate = goal.calendar.suggested_date;
    } else if (goal.calendar && Array.isArray(goal.calendar)) {
        calendarWeeks = goal.calendar; // fallback for older format just in case
    }
    
    const missedHtml = isMissed ? `
        <div class="mt-3 mb-0 p-3 rounded-3" style="background: var(--danger-soft); border: 1px solid var(--danger-soft); color: var(--danger); font-size: 0.9rem;">
            <i class="fas fa-times-circle me-1"></i> <strong>Goal Missed:</strong> Target date reached but distance not completed.
        </div>
    ` : '';

    const atRiskHtml = isAtRisk && !isMissed && !isDashboard ? `
        <div class="mt-3 mb-0 p-3 rounded-3" style="background: var(--warning-soft); border: 1px solid var(--warning-soft); color: var(--warning); font-size: 0.9rem;">
            <i class="fas fa-exclamation-triangle me-1"></i> <strong>You're behind pace</strong> — even with an adjusted plan, this goal may need more time.
            <button class="btn btn-sm d-block w-100 mt-2" style="border: 1px solid var(--warning); color: var(--warning); background: transparent;" onclick="extendGoalDate(${goal.id}, '${suggestedDate}')">
                Extend target date to ${suggestedDate}
            </button>
        </div>
    ` : '';

    let calendarHtml = '';
    if (isDashboard) {
        // Dashboard Widget simplified view
        let thisWeekTarget = "0";
        if (calendarWeeks.length > 0) {
            const currentWeek = calendarWeeks.find(w => w.is_current) || calendarWeeks[calendarWeeks.length - 1];
            thisWeekTarget = currentWeek.long_run;
        }
        
        calendarHtml = `
            <div class="mt-2 text-center" style="cursor:pointer;" onclick="document.getElementById('nav-goals-tab').click();">
                <span style="font-size: 0.85rem; color:var(--text-muted);">This Week's Target</span>
                <div class="fw-bold fs-5" style="color:var(--cyan-accent);">${thisWeekTarget} km</div>
            </div>
        `;
    } else {
        // Full Tab View with Collapsible Calendar
        calendarHtml = '<div class="mt-4">';
        
        if (calendarWeeks.length > 0) {
            const currentWeek = calendarWeeks.find(w => w.is_current) || calendarWeeks[calendarWeeks.length - 1];
            
            calendarHtml += `
                <div class="d-flex justify-content-between align-items-center mb-2" data-bs-toggle="collapse" data-bs-target="#calendarCollapse-${goal.id}" style="cursor:pointer;">
                    <h6 class="fw-bold mb-0" style="font-size: 0.85rem; letter-spacing: 1px; color:var(--text-muted);">
                        TRAINING CALENDAR
                    </h6>
                    <i class="fas fa-chevron-down transition-icon" style="color:var(--text-muted);"></i>
                </div>

                <div class="mb-2 small fw-bold" data-bs-toggle="collapse" data-bs-target="#calendarCollapse-${goal.id}" style="cursor:pointer; color:var(--cyan-accent);">
                    ${calendarWeeks.length}-week plan, ${currentWeek.long_run}km long run this week
                </div>

                <div class="collapse" id="calendarCollapse-${goal.id}">
                    <ul class="list-group list-group-flush bg-transparent gap-2 mt-3">
            `;

            calendarWeeks.forEach(week => {
                const isCurrentBadge = week.is_current ? `<span class="badge ms-1" style="background:var(--success);">Current</span>` : '';
                const actualHtml = week.is_past && week.actual_long_run !== null ?
                    `<div class="small" style="color:${week.actual_long_run >= week.long_run ? 'var(--success)' : 'var(--danger)'};">Actual: ${week.actual_long_run} km</div>` : '';

                calendarHtml += `
                    <li class="list-group-item border-0 rounded-3 px-3 py-2 d-flex justify-content-between align-items-center mb-1" style="background:var(--premium-surface); ${week.is_current ? 'border-left: 3px solid var(--success) !important;' : ''}">
                        <div>
                            <span class="badge rounded-pill me-1" style="background:var(--cyan-accent);">Week ${week.week_number}</span>
                            ${isCurrentBadge}
                            <div class="small mt-1" style="color:var(--text-muted);">${week.date_range}</div>
                        </div>
                        <div class="text-end">
                            <div class="fw-bold" style="color:var(--cyan-accent);">${week.long_run} km long</div>
                            <small style="color:var(--text-muted);">${week.days_per_week - 1}x ${week.other_runs} km</small>
                            ${actualHtml}
                        </div>
                    </li>
                `;
            });
            calendarHtml += '</ul></div>';
        } else {
            calendarHtml += '<div class="px-0" style="color:var(--text-muted);">No calendar generated</div>';
        }
        calendarHtml += '</div>';
    }

    return `
        <div class="card glass ${isDashboard ? 'border-0' : 'mb-4'}" style="${isDashboard ? 'cursor:pointer;' : 'border-color: var(--cyan-accent) !important;'}" ${isDashboard ? 'onclick="document.getElementById(\'nav-goals-tab\').click();"' : ''}>
            <div class="card-body ${isDashboard ? 'p-3 p-md-4' : 'p-4'}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="badge mb-2" style="background:${isMissed ? 'var(--danger)' : 'var(--cyan-accent)'};">${isMissed ? 'MISSED GOAL' : 'ACTIVE GOAL'}</span>
                        <h4 class="card-title fw-bold mb-1" style="color:var(--text-main);">${goal.target_distance_km} km Target</h4>
                        <h6 class="card-subtitle mb-0" style="color:var(--text-muted);"><i class="far fa-calendar-alt me-1"></i> Target Date: ${goal.target_date}</h6>
                    </div>
                    ${!isDashboard ? `
                        <button class="btn btn-sm" style="color:var(--text-faint);" onclick="deleteGoal(${goal.id})" title="Delete Goal">
                            <i class="fas fa-trash"></i>
                        </button>
                    ` : ''}
                </div>
                ${missedHtml}
                ${atRiskHtml}
                ${progressHtml}
                ${calendarHtml}
            </div>
        </div>
    `;
}

function extendGoalDate(goalId, newDateStr) {
    if(!confirm('Extend goal target date to ' + newDateStr + '?')) return;
    fetch('/api/goals/' + goalId + '/extend', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ new_date: newDateStr })
    })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            loadPersonalGoals();
        } else {
            alert(data.message || 'Error extending goal');
        }
    });
}

function renderCompletedGoal(goal) {
    return `
        <div class="col-12 col-md-6">
            <div class="card mb-3" style="background: var(--success-soft); border: 1px solid var(--success) !important;">
                <div class="card-body p-4 d-flex align-items-center">
                    <div class="me-3">
                        <i class="fas fa-medal" style="font-size: 2.5rem; color:var(--success);"></i>
                    </div>
                    <div class="flex-grow-1">
                        <h5 class="fw-bold mb-1" style="color:var(--success);">${goal.target_distance_km} km Target</h5>
                        <p class="mb-0 small" style="color:var(--text-muted);">Smashed on ${goal.target_date}</p>
                    </div>
                    <button class="btn btn-sm" style="color:var(--text-faint);" onclick="deleteGoal(${goal.id})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

function createPresetGoal(distance, weeks) {
    const today = new Date();
    today.setDate(today.getDate() + (weeks * 7));
    const targetDate = today.toISOString().split('T')[0];
    
    submitGoal({
        goal_type: 'preset',
        target_distance_km: distance,
        target_date: targetDate,
        days_per_week: 3
    });
}

// ----------------- Multi-step Goal Builder -----------------
function showGoalBuilder() {
    builderState = { step: 1, targetDistance: 10, targetDate: null, daysPerWeek: 3 };
    const today = new Date();
    today.setDate(today.getDate() + 56); // Default 8 weeks
    builderState.targetDate = today.toISOString().split('T')[0];
    
    renderBuilderStep();
    const modal = new bootstrap.Modal(document.getElementById('goalBuilderModal'));
    modal.show();
}

function renderBuilderStep() {
    const content = document.getElementById('goalBuilderContent');
    const title = document.getElementById('goalBuilderTitle');
    
    let html = '';
    
    // Progress Indicator
    html += `
        <div class="d-flex justify-content-between mb-4">
            ${[1,2,3,4].map(s => `
                <div style="flex:1; height: 4px; background: ${s <= builderState.step ? 'var(--cyan-accent)' : 'var(--premium-border)'}; margin: 0 2px; border-radius: 2px;"></div>
            `).join('')}
        </div>
    `;

    if (builderState.step === 1) {
        title.innerText = "Target Distance";
        html += `
            <h5 class="fw-bold mb-3 text-center" style="color:var(--text-main);">How far do you want to run?</h5>
            <div class="mb-4">
                <select id="b_targetDistance" class="form-select form-select-lg" style="background:var(--premium-surface); color:var(--text-main); border:1px solid var(--premium-border);">
                    <option value="3" ${builderState.targetDistance == 3 ? 'selected':''}>3 km</option>
                    <option value="5" ${builderState.targetDistance == 5 ? 'selected':''}>5 km</option>
                    <option value="10" ${builderState.targetDistance == 10 ? 'selected':''}>10 km</option>
                    <option value="21" ${builderState.targetDistance == 21 ? 'selected':''}>21.1 km (Half Marathon)</option>
                    <option value="42" ${builderState.targetDistance == 42 ? 'selected':''}>42.2 km (Marathon)</option>
                    <option value="100" ${builderState.targetDistance == 100 ? 'selected':''}>100 km (Ultra)</option>
                </select>
            </div>
            <button class="btn btn-primary w-100 py-2 fw-bold rounded-pill" onclick="builderState.targetDistance = document.getElementById('b_targetDistance').value; builderState.step++; renderBuilderStep();">Next Step <i class="fas fa-arrow-right ms-1"></i></button>
        `;
    } 
    else if (builderState.step === 2) {
        title.innerText = "Target Date";
        html += `
            <h5 class="fw-bold mb-3 text-center" style="color:var(--text-main);">When is race day?</h5>
            <div class="mb-4">
                <input type="date" id="b_targetDate" class="form-control form-control-lg text-center" style="background:var(--premium-surface); color:var(--text-main); border:1px solid var(--premium-border);" value="${builderState.targetDate}" required>
            </div>
            <div class="d-flex gap-2">
                <button class="btn btn-outline-secondary py-2 rounded-pill w-50" onclick="builderState.step--; renderBuilderStep();">Back</button>
                <button class="btn btn-primary py-2 fw-bold rounded-pill w-50" onclick="
                    const d = document.getElementById('b_targetDate').value;
                    if(!d) { alert('Please select a date'); return; }
                    builderState.targetDate = d;
                    builderState.step++; renderBuilderStep();
                ">Next Step <i class="fas fa-arrow-right ms-1"></i></button>
            </div>
        `;
    }
    else if (builderState.step === 3) {
        title.innerText = "Training Frequency";
        html += `
            <h5 class="fw-bold mb-3 text-center" style="color:var(--text-main);">How many days a week?</h5>
            <div class="mb-4 text-center">
                <input type="range" class="form-range w-100" min="2" max="6" step="1" id="b_daysPerWeek" value="${builderState.daysPerWeek}" oninput="document.getElementById('daysVal').innerText = this.value + ' Days'">
                <div id="daysVal" class="fs-1 fw-bold mt-2" style="color:var(--cyan-accent);">${builderState.daysPerWeek} Days</div>
            </div>
            <div class="d-flex gap-2">
                <button class="btn btn-outline-secondary py-2 rounded-pill w-50" onclick="builderState.step--; renderBuilderStep();">Back</button>
                <button class="btn btn-primary py-2 fw-bold rounded-pill w-50" onclick="builderState.daysPerWeek = document.getElementById('b_daysPerWeek').value; builderState.step++; renderBuilderStep();">Review Plan <i class="fas fa-arrow-right ms-1"></i></button>
            </div>
        `;
    }
    else if (builderState.step === 4) {
        title.innerText = "Review & Feasibility";
        html += `
            <div id="builderReviewContent" class="text-center">
                <div class="spinner-border text-primary mb-3" role="status"></div>
                <p class="text-secondary">Checking feasibility with RunRush AI...</p>
            </div>
        `;
        
        content.innerHTML = html;
        
        // Auto-trigger feasibility check
        checkBuilderFeasibility();
        return; 
    }

    content.innerHTML = html;
}

function checkBuilderFeasibility() {
    const goalData = {
        goal_type: 'custom',
        target_distance_km: builderState.targetDistance,
        target_date: builderState.targetDate,
        days_per_week: builderState.daysPerWeek
    };

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value || '';
    
    fetch('/api/goals', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(goalData)
    })
    .then(res => res.json().then(data => ({status: res.status, body: data})))
    .then(({status, body}) => {
        const reviewContainer = document.getElementById('builderReviewContent');
        if (!reviewContainer) return; // User closed modal
        
        if (status === 400 && body.error === 'infeasible') {
            reviewContainer.innerHTML = `
                <div class="p-4 rounded-4 text-start" style="background:var(--warning-soft); border:1px solid var(--warning-soft); color:var(--warning);">
                    <h6 class="fw-bold mb-2"><i class="fas fa-exclamation-triangle me-2"></i>Challenging / Not Recommended</h6>
                    <p class="mb-3 small">${body.message}</p>
                    <p class="mb-3 small"><strong>Suggested alternative:</strong> Target ${body.suggested_date} instead.</p>
                    <button class="btn fw-bold w-100 rounded-pill mb-2" style="background:var(--warning); color:#fff;" onclick="builderState.targetDate = '${body.suggested_date}'; checkBuilderFeasibility();">Use Suggested Date</button>
                    <button class="btn w-100 rounded-pill" style="border:1px solid var(--premium-border); color:var(--text-main);" onclick="builderState.step = 2; renderBuilderStep();">Go Back</button>
                </div>
            `;
        } else if (status === 200) {
            reviewContainer.innerHTML = `
                <div class="p-4 rounded-4 text-start" style="background:var(--success-soft); border:1px solid var(--success-soft); color:var(--success);">
                    <h6 class="fw-bold mb-2"><i class="fas fa-check-circle me-2"></i>Goal looks solid!</h6>
                    <p class="mb-0 small">Based on your recent runs, this target is highly achievable. A personalized training plan is ready to be generated.</p>
                </div>
                <button class="btn fw-bold w-100 py-3 rounded-pill mt-3 shadow-lg" style="background:var(--success); color:#fff;" onclick="finalizeBuilderGoal()">Set Goal & Generate Plan</button>
            `;
        } else {
            reviewContainer.innerHTML = `<div class="p-3 rounded-3" style="background:var(--danger-soft); color:var(--danger);">${body.error || "Failed to create goal"}</div>
            <button class="btn w-100 rounded-pill mt-2" style="border:1px solid var(--premium-border); color:var(--text-main);" onclick="builderState.step = 3; renderBuilderStep();">Go Back</button>`;
        }
    })
    .catch(err => console.error(err));
}

function finalizeBuilderGoal() {
    // Goal is already created in DB from the POST request that returned 200
    bootstrap.Modal.getInstance(document.getElementById('goalBuilderModal')).hide();
    loadPersonalGoals();
}

// ----------------- End Multi-step Builder -----------------

function submitGoal(goalData) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value || '';
    
    fetch('/api/goals', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(goalData)
    })
    .then(res => res.json().then(data => ({status: res.status, body: data})))
    .then(({status, body}) => {
        if (status === 200) {
            loadPersonalGoals();
        } else {
            alert(body.error || "Failed to create goal");
        }
    })
    .catch(err => console.error(err));
}

function deleteGoal(id) {
    if(!confirm("Delete this goal?")) return;
    
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value || '';
    
    fetch('/api/goals/' + id, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            loadPersonalGoals();
        }
    });
}
