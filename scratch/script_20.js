
    let currentMonth = new Date().getMonth() + 1;
    let currentYear = new Date().getFullYear();
    const monthNames = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];

    function shiftMonth(dir) {
        currentMonth += dir;
        if (currentMonth > 12) {
            currentMonth = 1;
            currentYear++;
        } else if (currentMonth < 1) {
            currentMonth = 12;
            currentYear--;
        }
        fetchMonthlyProgress();
    }

    async function fetchMonthlyProgress() {
        const titleEl = document.getElementById("monthly-progress-title");
        if (titleEl) titleEl.innerText = `${monthNames[currentMonth-1]} ${currentYear}`;
        
        try {
            const res = await fetch(`/api/monthly-progress?year=${currentYear}&month=${currentMonth}`);
            const data = await res.json();
            renderMonthlyProgress(data);
        } catch(err) {
            console.error("Error fetching monthly progress", err);
        }
    }

    function renderMonthlyProgress(data) {
        const container = document.getElementById("monthly-progress-content");
        if (!container) return;
        
        const now = new Date();
        const isFuture = (data.year > now.getFullYear()) || (data.year === now.getFullYear() && data.month > (now.getMonth() + 1));
        
        let html = '';
        
        if (data.target_km) {
            let percent = (data.total_distance / data.target_km) * 100;
            let barPercent = Math.min(percent, 100);
            let message = '';
            if (percent >= 100) {
                message = '<span style="color: var(--accent-lime); font-size: 0.8rem; font-weight: 700;">GOAL HIT</span>';
            } else {
                message = `<span class="text-secondary" style="font-size: 0.8rem;">${(data.target_km - data.total_distance).toFixed(1)} km to goal</span>`;
            }
            
            html += `
            <div class="d-flex justify-content-between align-items-end mb-1">
                <span class="fw-bold fs-5">${data.total_distance} <span class="text-secondary" style="font-size: 0.9rem;">/ ${data.target_km} KM</span></span>
                ${message}
            </div>
            <div class="progress mb-3" style="height: 6px; background-color: rgba(255,255,255,0.1); border-radius: 3px;">
                <div class="progress-bar" role="progressbar" style="width: ${barPercent}%; background-color: var(--accent); border-radius: 3px;"></div>
            </div>
            `;
        } else {
            if (!isFuture) {
                html += `
                <div class="text-center mb-3">
                    <div class="fw-bold" style="font-size: 1.8rem;">${data.total_distance} <span class="text-secondary" style="font-size: 1rem;">KM</span></div>
                </div>
                `;
            } else {
                html += `
                <div class="text-center mb-3">
                    <div class="text-secondary fw-bold" style="font-size: 1.2rem;">0 KM / --</div>
                </div>
                `;
            }
        }
        
        html += `
        <div class="row text-center g-2 mb-2">
            <div class="col-4">
                <div class="fw-bold">${data.run_count}</div>
                <div class="text-secondary" style="font-size: 0.7rem; text-transform: uppercase;">Runs</div>
            </div>
            <div class="col-4">
                <div class="fw-bold">${data.time_str}</div>
                <div class="text-secondary" style="font-size: 0.7rem; text-transform: uppercase;">Time</div>
            </div>
            <div class="col-4">
                <div class="fw-bold">${data.pace_str}</div>
                <div class="text-secondary" style="font-size: 0.7rem; text-transform: uppercase;">/km</div>
            </div>
        </div>
        `;
        
        let actionBtn = '';
        if (!data.target_km) {
            if (isFuture) {
                actionBtn = `<button class="btn btn-sm btn-outline-info mt-2" style="font-size: 0.75rem; border-radius: 20px; border-color: rgba(77,173,255,0.5);" onclick="openGoalModal()">+ Set Goal</button>`;
            } else {
                actionBtn = `<button class="btn btn-sm btn-outline-info mt-2" style="font-size: 0.75rem; border-radius: 20px; border-color: rgba(77,173,255,0.5);" onclick="openGoalModal()">+ Set Goal</button>`;
            }
        } else {
            actionBtn = `<button class="btn btn-sm text-secondary mt-2" style="font-size: 0.75rem; border: none; background: transparent;" onclick="openGoalModal()"><i class="fas fa-edit"></i> Edit Goal</button>`;
        }
        
        html += `
        <div class="d-flex justify-content-center">
            ${actionBtn}
        </div>
        `;
        
        container.innerHTML = html;
        document.getElementById("input-monthly-target").value = data.target_km || "";
    }

    function openGoalModal() {
        const modal = new bootstrap.Modal(document.getElementById('monthlyGoalModal'));
        modal.show();
    }

    async function saveMonthlyGoal() {
        const val = document.getElementById("input-monthly-target").value;
        try {
            await fetch('/api/monthly-goals', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({
                    year: currentYear,
                    month: currentMonth,
                    target_km: val ? parseFloat(val) : null
                })
            });
            const modalEl = document.getElementById('monthlyGoalModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if(modal) modal.hide();
            fetchMonthlyProgress();
        } catch (err) {
            console.error("Error saving goal", err);
        }
    }
  