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
                    <div class="card glass text-light border-0 py-4 text-center">
                        <div class="card-body">
                            <h5 class="text-secondary fw-bold">No active goal yet</h5>
                            <p class="text-secondary mb-3">Pick a goal below and RunRush will build a personalized training plan for you.</p>
                            <button class="btn btn-outline-primary rounded-pill px-4" onclick="showGoalBuilder()">Create Custom Goal</button>
                        </div>
                    </div>`;
                if(dashboardContainer) dashboardContainer.innerHTML = '<div class="card glass text-light border-0"><div class="card-body text-center py-4"><p class="mb-0 text-secondary">No active personal goals.</p></div></div>';
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
                    dashboardContainer.innerHTML = '<div class="card glass text-light border-0"><div class="card-body text-center py-4"><p class="mb-0 text-secondary">No active personal goals.</p></div></div>';
                }
            }
            
            completedSection.style.display = hasCompleted ? 'block' : 'none';
            
            renderRecommendationsAndPresets();
        })
        .catch(err => console.error("Error loading goals:", err));
}

function renderRecommendationsAndPresets() {
    const stats = getRecentStats();
    const recSection = document.getElementById('recommendedGoalSection');
    const recCard = document.getElementById('recommendedGoalCard');
    
    if (stats) {
        const rec = getRecommendedGoal(stats);
        recSection.style.display = 'block';
        recCard.innerHTML = `
            <div class="card glass text-light border-primary" style="background: linear-gradient(145deg, rgba(22,131,247,0.1), rgba(22,131,247,0.02)); border: 1px solid rgba(22,131,247,0.3) !important;">
                <div class="card-body d-flex flex-column flex-md-row align-items-md-center justify-content-between p-4">
                    <div class="mb-3 mb-md-0">
                        <h5 class="card-title fw-bold text-primary mb-1">${rec.title}</h5>
                        <h6 class="text-white mb-2">${rec.distance} km target • ~${rec.weeks} weeks</h6>
                        <p class="small text-secondary mb-2">${rec.desc}</p>
                        <div class="d-flex align-items-center gap-3 mt-3">
                            <div class="text-center bg-dark p-2 rounded" style="font-size:0.8rem;">
                                <div class="text-secondary mb-1">Longest Run</div>
                                <div class="fw-bold text-white">${stats.longestRecentRun.toFixed(1)} km</div>
                            </div>
                            <div class="text-center bg-dark p-2 rounded" style="font-size:0.8rem;">
                                <div class="text-secondary mb-1">Avg Weekly</div>
                                <div class="fw-bold text-white">${stats.recentWeeklyDistance.toFixed(1)} km</div>
                            </div>
                        </div>
                        <p class="text-secondary mt-3 mb-0" style="font-size: 0.8rem;">
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
            <div class="card glass text-light border-0">
                <div class="card-body text-center p-4">
                    <p class="text-secondary mb-0">Log a few more runs to personalize your recommendation.</p>
                </div>
            </div>
        `;
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
            <div class="card glass text-light h-100 preset-goal-card" onclick="createPresetGoal(${p.distance}, ${p.weeks})" style="cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                <div class="card-body text-center p-4">
                    <h5 class="card-title fw-bold text-white mb-2">${p.title}</h5>
                    <h6 class="text-primary mb-3">${p.distance} km • ~${p.weeks} weeks</h6>
                    <p class="card-text small text-secondary mb-4">${p.desc}</p>
                    <button class="btn btn-sm btn-outline-light rounded-pill px-3">Select</button>
                </div>
            </div>
        </div>
    `).join('');
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
                <div class="d-flex justify-content-between text-secondary mb-1" style="font-size: 0.8rem;">
                    <span>Progress</span>
                    <span>${Math.round(percent)}%</span>
                </div>
                <div class="progress" style="height: 6px; background-color: rgba(255,255,255,0.1);">
                    <div class="progress-bar bg-primary" role="progressbar" style="width: ${percent}%;"></div>
                </div>
            </div>
        `;
    }

    let calendarHtml = '';
    if (!isDashboard) {
        calendarHtml = '<div class="mt-4"><h6 class="text-secondary fw-bold mb-3" style="font-size: 0.85rem; letter-spacing: 1px;">TRAINING CALENDAR</h6><ul class="list-group list-group-flush bg-transparent gap-2">';
        if (goal.calendar && goal.calendar.length > 0) {
            goal.calendar.forEach(week => {
                calendarHtml += `
                    <li class="list-group-item bg-dark text-light border-0 rounded-3 px-3 py-2 d-flex justify-content-between align-items-center mb-1">
                        <div>
                            <span class="badge bg-primary rounded-pill me-2">Week ${week.week_number}</span>
                            <small class="text-secondary">${week.date_range}</small>
                        </div>
                        <div class="text-end">
                            <div class="fw-bold text-info">${week.long_run} km long</div>
                            <small class="text-secondary">${week.days_per_week - 1}x ${week.other_runs} km</small>
                        </div>
                    </li>
                `;
            });
        } else {
            calendarHtml += '<li class="list-group-item bg-transparent text-secondary px-0">No calendar generated</li>';
        }
        calendarHtml += '</ul></div>';
    }

    return `
        <div class="card glass text-light ${isDashboard ? 'border-0' : 'border-primary mb-4'}">
            <div class="card-body ${isDashboard ? 'p-3 p-md-4' : 'p-4'}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="badge bg-primary mb-2">ACTIVE GOAL</span>
                        <h4 class="card-title fw-bold text-white mb-1">${goal.target_distance_km} km Target</h4>
                        <h6 class="card-subtitle text-secondary mb-0"><i class="far fa-calendar-alt me-1"></i> Target Date: ${goal.target_date}</h6>
                    </div>
                    ${!isDashboard ? `
                        <button class="btn btn-sm text-secondary hover-danger" onclick="deleteGoal(${goal.id})" title="Delete Goal">
                            <i class="fas fa-trash"></i>
                        </button>
                    ` : ''}
                </div>
                ${progressHtml}
                ${calendarHtml}
            </div>
        </div>
    `;
}

function renderCompletedGoal(goal) {
    return `
        <div class="col-12 col-md-6">
            <div class="card mb-3" style="background: linear-gradient(145deg, rgba(25,135,84,0.1), rgba(25,135,84,0.02)); border: 1px solid rgba(25,135,84,0.3) !important;">
                <div class="card-body p-4 d-flex align-items-center">
                    <div class="me-3">
                        <i class="fas fa-medal text-success" style="font-size: 2.5rem;"></i>
                    </div>
                    <div class="flex-grow-1">
                        <h5 class="fw-bold text-success mb-1">${goal.target_distance_km} km Target</h5>
                        <p class="text-secondary mb-0 small">Smashed on ${goal.target_date}</p>
                    </div>
                    <button class="btn btn-sm text-secondary hover-danger" onclick="deleteGoal(${goal.id})">
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
                <div style="flex:1; height: 4px; background: ${s <= builderState.step ? 'var(--primary)' : 'rgba(255,255,255,0.1)'}; margin: 0 2px; border-radius: 2px;"></div>
            `).join('')}
        </div>
    `;

    if (builderState.step === 1) {
        title.innerText = "Target Distance";
        html += `
            <h5 class="fw-bold text-white mb-3 text-center">How far do you want to run?</h5>
            <div class="mb-4">
                <select id="b_targetDistance" class="form-select bg-dark text-light border-secondary form-select-lg">
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
            <h5 class="fw-bold text-white mb-3 text-center">When is race day?</h5>
            <div class="mb-4">
                <input type="date" id="b_targetDate" class="form-control bg-dark text-light border-secondary form-control-lg text-center" value="${builderState.targetDate}" required>
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
            <h5 class="fw-bold text-white mb-3 text-center">How many days a week?</h5>
            <div class="mb-4 text-center">
                <input type="range" class="form-range w-100" min="2" max="6" step="1" id="b_daysPerWeek" value="${builderState.daysPerWeek}" oninput="document.getElementById('daysVal').innerText = this.value + ' Days'">
                <div id="daysVal" class="fs-1 fw-bold text-primary mt-2">${builderState.daysPerWeek} Days</div>
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
                <div class="alert bg-dark border border-warning text-warning p-4 rounded-4 text-start">
                    <h6 class="fw-bold mb-2"><i class="fas fa-exclamation-triangle me-2"></i>Challenging / Not Recommended</h6>
                    <p class="mb-3 small">${body.message}</p>
                    <p class="mb-3 small"><strong>Suggested alternative:</strong> Target ${body.suggested_date} instead.</p>
                    <button class="btn btn-warning fw-bold w-100 rounded-pill mb-2" onclick="builderState.targetDate = '${body.suggested_date}'; checkBuilderFeasibility();">Use Suggested Date</button>
                    <button class="btn btn-outline-secondary w-100 rounded-pill" onclick="builderState.step = 2; renderBuilderStep();">Go Back</button>
                </div>
            `;
        } else if (status === 200) {
            reviewContainer.innerHTML = `
                <div class="alert bg-dark border border-success text-success p-4 rounded-4 text-start">
                    <h6 class="fw-bold mb-2"><i class="fas fa-check-circle me-2"></i>Goal looks solid!</h6>
                    <p class="mb-0 small">Based on your recent runs, this target is highly achievable. A personalized training plan is ready to be generated.</p>
                </div>
                <button class="btn btn-success fw-bold w-100 py-3 rounded-pill mt-3 shadow-lg" onclick="finalizeBuilderGoal()">Set Goal & Generate Plan</button>
            `;
        } else {
            reviewContainer.innerHTML = `<div class="alert alert-danger">${body.error || "Failed to create goal"}</div>
            <button class="btn btn-outline-secondary w-100 rounded-pill mt-2" onclick="builderState.step = 3; renderBuilderStep();">Go Back</button>`;
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
