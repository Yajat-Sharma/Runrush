import re

with open('static/js/goals.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Modify renderActiveGoal to render a 1:1 square when isDashboard is true
old_dashboard_html = r'''return `
        <div class="card glass text-light border-0">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h5 class="mb-0 text-white">${goal.title || 'Personal Goal'}</h5>
                    ${badgeHtml}
                </div>
                ${statusHtml}
                <div class="d-flex justify-content-between align-items-center mt-3">
                    <div class="small">Target: ${goal.target_value} ${goal.target_metric}</div>
                    <div class="text-accent fw-bold">${goal.current_value || 0} ${goal.target_metric}</div>
                </div>
                ${progressHtml}
                <div class="text-end mt-2">
                    <button class="btn btn-sm btn-outline-light rounded-pill" onclick="showAddGoalProgressModal(${goal.id})" style="font-size: 0.75rem;"><i class="fas fa-plus"></i> Progress</button>
                </div>
            </div>
        </div>
    `;'''

new_dashboard_html = r'''return `
        <div class="card glass text-light border-0 d-flex flex-column justify-content-between mx-auto" style="border: 1px solid rgba(255, 255, 255, 0.05) !important; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); position: relative; overflow: hidden; max-width: 480px; width: 100%; border-radius: 20px; aspect-ratio: 1 / 1;">
            <div style="position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle at top right, rgba(0, 242, 255, 0.05), transparent 60%); pointer-events: none;"></div>
            <div class="card-body d-flex flex-column" style="position: relative; z-index: 1;">
                <div class="d-flex justify-content-between align-items-start mb-auto">
                    <h5 class="mb-0 text-white" style="font-size: 1.1rem;">${goal.title || 'Personal Goal'}</h5>
                    ${badgeHtml}
                </div>
                
                <div class="text-center my-4">
                    <i class="fas fa-bullseye mb-3" style="font-size: 2.5rem; color: rgba(255,255,255,0.7); filter: drop-shadow(0 2px 8px rgba(0,242,255,0.3));"></i>
                    <div class="d-flex justify-content-center align-items-baseline gap-2">
                        <span class="text-accent fw-bold" style="font-size: 1.5rem;">${goal.current_value || 0}</span>
                        <span class="text-secondary">/ ${goal.target_value} ${goal.target_metric}</span>
                    </div>
                    ${statusHtml}
                </div>
                
                ${progressHtml}
                <div class="text-end mt-auto pt-2">
                    <button class="btn btn-sm btn-outline-light rounded-pill w-100 py-2 fw-bold" onclick="showAddGoalProgressModal(${goal.id})" style="font-size: 0.85rem; border-color: rgba(255,255,255,0.1);"><i class="fas fa-plus"></i> LOG PROGRESS</button>
                </div>
            </div>
        </div>
    `;'''

if old_dashboard_html in js:
    js = js.replace(old_dashboard_html, new_dashboard_html)
else:
    print("Could not find old dashboard goal HTML in JS")

with open('static/js/goals.js', 'w', encoding='utf-8') as f:
    f.write(js)
print("Applied dashboard goal styling")
