
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

    // --- CACHING STATE ---
    let tabCache = {
      analytics: false,
      achievements_personalBests: false,
      achievements_badges: false,
      achievements_challenges: false,
      achievements_personalGoals: false
    };

    function invalidateCache() {
      tabCache.analytics = false;
      tabCache.achievements_personalBests = false;
      tabCache.achievements_badges = false;
      tabCache.achievements_challenges = false;
      tabCache.achievements_personalGoals = false;
    }

    async function loadMoreRuns() {
      const container = document.getElementById('runsCardContainer');
      const pbEl = document.getElementById('pbRunIdsData');
      const userEl = document.getElementById('userData');
      const btnContainer = document.getElementById('loadMoreContainer');
      const countEl = document.getElementById('loadMoreCount');
      
      if (!container) return;
      
      if (!window.pbRunIds) {
        window.pbRunIds = pbEl ? JSON.parse(pbEl.textContent) : {};
        window.userData = userEl ? JSON.parse(userEl.textContent) : {display_name: "", username: "", csrf_token: ""};
      }
      
      if (typeof window.currentRunOffset === 'undefined') {
        window.currentRunOffset = 15;
      }
      
      const sortOpt = new URLSearchParams(window.location.search).get('sort') || 'date';
      const filterOpt = new URLSearchParams(window.location.search).get('filter') || 'all';
      
      const btn = btnContainer ? btnContainer.querySelector('button') : null;
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
      }
      
      try {
        const res = await fetch(`/api/runs?offset=${window.currentRunOffset}&limit=15&sort=${sortOpt}&filter=${filterOpt}`);
        const data = await res.json();
        const batch = data.runs || [];
        
        window.currentRunOffset += batch.length;
      
        batch.forEach(r => {
          // Month grouping is simplified: we don't duplicate the month header logic here to keep it minimal,
          // or we could track last_month globally. To avoid visual glitches, we'll append cards directly.
          // If sorting by date, they are in order.
          
          let rt = r.run_type ? r.run_type.toLowerCase() : 'easy';
          let border_color = rt === 'easy' ? 'var(--success)' : (rt === 'long' ? 'var(--info)' : (rt === 'tempo' ? 'var(--warning)' : (rt === 'interval' ? 'var(--primary)' : 'var(--secondary)')));
          
          let source_text = '';
          let display_notes = r.notes || '';
          if (display_notes.startsWith('[Screenshot Import')) {
            let parts = display_notes.split(']', 2); // Split once by ']'
            source_text = parts[0].substring(1);
            display_notes = parts.length > 1 ? parts[1].trim() : '';
          } else if (display_notes === 'Imported from Strava') {
            source_text = 'Strava Import';
            display_notes = '';
          }
          
          let pbBadges = '';
          if (window.pbRunIds[r.id]) {
            window.pbRunIds[r.id].forEach(title => {
              pbBadges += `<span class="badge mt-1" style="background:rgba(255,215,0,0.15);color:var(--gold);border:1px solid rgba(255,215,0,0.3);font-size:0.65rem;" title="${title}">🏆 NEW PERSONAL BEST</span> `;
            });
          }
          
          let insightHtml = '';
          if (r.insight) {
            insightHtml = `
            <div class="mb-3">
              <div class="rc-muted small mb-1">AI NOTES</div>
              <div class="insight-container rc-light" style="background: var(--accent-soft); border-left: 3px solid var(--accent); border-radius: 8px; padding: 0.5rem 0.75rem; font-size: 0.85rem;">
                <span style="margin-right: 0.5rem;">💡</span> ${r.insight}
              </div>
            </div>`;
          }
          
          let notesHtml = '';
          if (display_notes) {
            notesHtml = `
            <div class="mb-3">
              <div class="rc-muted small mb-1">NOTES</div>
              <div class="rc-light" style="font-size: 0.85rem;">${display_notes}</div>
            </div>`;
          }
          
          let sourceHtml = '';
          if (source_text) {
            sourceHtml = `
            <div class="col-12 col-md-6 mt-2 mt-md-0">
              <div class="rc-muted small mb-1">SOURCE</div>
              <div class="fw-bold rc-light"><i class="fas fa-file-import text-secondary me-1"></i> ${source_text}</div>
            </div>`;
          }
          
          let weatherHtml = `<span class="text-secondary">—</span>`;
          if (r.weather_emoji && r.weather_temp !== null && r.weather_temp !== 'null' && r.weather_temp !== '') {
            weatherHtml = `${r.weather_emoji} ${r.weather_temp}°C`;
          }
          
          let actionButtons = '';
          if (r.is_locked) {
            actionButtons += `<span class="btn btn-glass btn-secondary flex-grow-1 d-flex align-items-center justify-content-center gap-2 py-2" title="Locked (>24h old)"><i class="fas fa-lock"></i> Locked</span>`;
          } else {
            actionButtons += `<a href="/run/${r.id}/edit" class="btn btn-glass btn-primary-soft flex-grow-1 d-flex align-items-center justify-content-center gap-2 py-2"><i class="fas fa-pen text-primary"></i> Edit</a>`;
          }
          
          const shareData = {
            date: r.date, distance_km: r.distance_km, time_min: r.time_min, pace: r.pace, calories: r.calories,
            run_type: rt, weather_emoji: r.weather_emoji || "", weather_temp: (r.weather_temp !== null && r.weather_temp !== '') ? r.weather_temp : "",
            weather_condition: r.weather_condition || "", insight: r.insight || "",
            display_name: window.userData.display_name, username: window.userData.username
          };
          const shareJson = JSON.stringify(shareData).replace(/'/g, "&#39;");

          const card = document.createElement('div');
          card.className = "card glass mb-3 border-0 position-relative run-card-modern";
          card.style = "cursor: pointer; transition: 0.2s;";
          card.setAttribute("onclick", `toggleRunCard('${r.id}')`);
          card.innerHTML = `
            <div class="position-absolute top-0 bottom-0 start-0" style="width: 4px; background-color: ${border_color}; border-radius: 8px 0 0 8px;"></div>
            <div class="card-body py-3 py-md-2 px-3 ps-4">
              <div class="d-flex justify-content-between align-items-start mb-2 mb-md-1">
                <div>
                  <div class="rc-muted small fw-bold text-uppercase">${r.date}</div>
                  ${pbBadges}
                </div>
                <div class="text-end">
                  <div class="fw-bold rc-primary" style="font-size: 1.5rem; line-height: 1;">${r.distance_km} <span class="rc-primary" style="font-size: 0.9rem; opacity: 0.9;">KM</span></div>
                  <div class="fw-bold rc-accent" style="font-size: 0.9rem;">${r.pace} <span class="rc-accent fw-normal" style="opacity: 0.8;">/km</span></div>
                </div>
              </div>
              
              <div class="d-flex align-items-center gap-2 mt-3 mt-md-2 rc-light" style="font-size: 0.85rem;">
                <span>${r.time_min} min</span>
                <span class="rc-muted">·</span>
                <span>${r.calories} kcal</span>
                <span class="rc-muted">·</span>
                <span class="run-type-badge rt-${rt} px-2 py-1" style="font-size: 0.7rem;">${rt.charAt(0).toUpperCase() + rt.slice(1)}</span>
                <span class="run-type-badge ms-1 pz-badge" data-pace="${r.pace}" style="font-size: 0.7rem;"></span>
                <div class="ms-auto"><i class="fas fa-chevron-down rc-muted transition-transform" id="chevron-${r.id}"></i></div>
              </div>

              <div class="collapse mt-3 pt-3 border-top border-secondary" id="runCardDetails-${r.id}" onclick="event.stopPropagation()">
                <div class="row g-2 mb-3" style="font-size: 0.85rem;">
                  <div class="col-6">
                    <div class="rc-muted small mb-1">TIME</div>
                    <div class="fw-bold rc-light">${r.time_min} min</div>
                  </div>
                  <div class="col-6">
                    <div class="rc-muted small mb-1">CALORIES</div>
                    <div class="fw-bold rc-light">${r.calories}</div>
                  </div>
                  <div class="col-6">
                    <div class="rc-muted small mb-1">TYPE</div>
                    <div class="fw-bold rc-light">${rt.charAt(0).toUpperCase() + rt.slice(1)}</div>
                  </div>
                  <div class="col-6">
                    <div class="rc-muted small mb-1">ZONE</div>
                    <div class="fw-bold pz-badge-text rc-light" data-pace="${r.pace}"></div>
                  </div>
                  
                  ${sourceHtml}

                  <div class="col-12 col-md-6 mt-2 mt-md-0">
                    <div class="rc-muted small mb-1">WEATHER</div>
                    <div class="fw-bold rc-light">
                      ${weatherHtml}
                    </div>
                  </div>
                </div>

                ${notesHtml}
                ${insightHtml}

                <div class="d-flex align-items-center gap-2 mt-2">
                  <button type="button" class="btn btn-glass flex-grow-1 d-flex align-items-center justify-content-center gap-2 py-2"
                    style="border-color: rgba(0,242,255,0.4);background:rgba(0,242,255,0.08);"
                    title="Share run"
                    onclick='openShareCard(${shareJson})'>
                    <i class="fas fa-arrow-up-from-bracket text-info"></i> Share
                  </button>
                  
                  ${actionButtons}
                  
                  <form action="/run/${r.id}/delete" method="post" style="display:inline; flex-grow: 1;">
                    <input type="hidden" name="csrf_token" value="${window.userData.csrf_token}">
                    <button class="btn btn-glass w-100 d-flex align-items-center justify-content-center gap-2 py-2"
                      style="border-color: rgba(220,53,69,0.6);background:rgba(220,53,69,0.12);"
                      onclick="return confirm('Delete this run? This cannot be undone.');">
                      <i class="fas fa-trash text-danger"></i> Delete
                    </button>
                  </form>
                </div>
              </div>
            </div>
          `;
          container.appendChild(card);
          
          // Append to list view
          const tbody = document.getElementById('runsTableBody');
          if (tbody) {
            const tr = document.createElement('tr');
            tr.className = "align-middle runs-table-row";
            
            let pbBadgesList = '';
            if (window.pbRunIds[r.id]) {
              window.pbRunIds[r.id].forEach(title => {
                pbBadgesList += `<br><span class="badge" style="background:rgba(255,215,0,0.15);color:var(--gold);border:1px solid rgba(255,215,0,0.3);margin-top:0.3rem;font-weight:600;" title="${title}">🏆 ${title}</span>`;
              });
            }
            
            let aiNotesBtn = r.insight ? `<br><button class="btn btn-sm p-0 text-muted" type="button" data-bs-toggle="collapse" data-bs-target="#insight-${r.id}" aria-expanded="false" style="font-size:0.75rem;margin-top:0.3rem;"><i class="fa-solid fa-chevron-down"></i> AI Notes</button>` : '';
            
            let actionsHtml = r.is_locked ? 
              `<span class="text-secondary small"><i class="fas fa-lock"></i> Locked</span>` :
              `<a href="/run/${r.id}/edit" class="btn btn-sm btn-outline-primary" style="padding: 0.1rem 0.4rem;" title="Edit"><i class="fas fa-pen"></i></a>
               <form action="/run/${r.id}/delete" method="post" style="display:inline;">
                 <input type="hidden" name="csrf_token" value="${window.userData.csrf_token}">
                 <button class="btn btn-sm btn-outline-danger" style="padding: 0.1rem 0.4rem;" title="Delete" onclick="return confirm('Delete this run? This cannot be undone.');"><i class="fas fa-trash"></i></button>
               </form>`;
            
            let notesStr = r.notes ? r.notes.replace(/'/g, "&#39;").replace(/"/g, "&quot;") : "";
            let notesHtml = r.notes ? 
              `<button class="btn btn-sm p-0 text-muted" type="button" data-bs-container="body" data-bs-toggle="popover" data-bs-trigger="focus" data-bs-placement="left" data-bs-content="${notesStr}">
                 <i class="fas fa-note-sticky text-warning" style="opacity: 0.8;"></i> Note
               </button>` : `<span class="text-muted" style="font-size:0.72rem;">—</span>`;
            
            let weatherCond = r.weather_condition ? r.weather_condition.replace(/'/g, "&#39;").replace(/"/g, "&quot;") : "";
            let weatherHtmlList = (r.weather_emoji && r.weather_temp !== null && r.weather_temp !== 'null' && r.weather_temp !== '') ? 
              `<span title="${weatherCond} · ${r.weather_temp}°C" style="cursor:default;white-space:nowrap;font-size:0.82rem;">${r.weather_emoji} <span style="color:var(--text-secondary);">${r.weather_temp}°C</span></span>` : 
              `<span class="text-muted" style="font-size:0.72rem;">—</span>`;
              
            tr.innerHTML = `
              <td>
                <span class="badge bg-dark badge-pill">${r.date}</span>
                ${aiNotesBtn}
                ${pbBadgesList}
              </td>
              <td><strong>${r.distance_km}</strong> km</td>
              <td>${r.time_min} min</td>
              <td><code class="text-info">${r.pace}</code> <span class="run-type-badge ms-1 pz-badge" data-pace="${r.pace}"></span></td>
              <td><span class="text-warning">${r.calories}</span></td>
              <td><span class="run-type-badge rt-${rt}">${rt.charAt(0).toUpperCase() + rt.slice(1)}</span></td>
              <td class="d-none d-md-table-cell">${weatherHtmlList}</td>
              <td class="d-none d-md-table-cell">${notesHtml}</td>
              <td class="text-end text-nowrap">${actionsHtml}</td>
            `;
            
            if (r.insight) {
              const trInsight = document.createElement('tr');
              trInsight.className = "collapse runs-table-row";
              trInsight.id = `insight-${r.id}`;
              trInsight.innerHTML = `<td colspan="9" class="p-0 border-0">
                  <div class="p-3 m-2" style="background: var(--accent-soft); border-left: 3px solid var(--accent); border-radius: 8px; font-size: 0.85rem; color: var(--text-primary);">
                    <span style="margin-right: 0.5rem;">💡</span> ${r.insight}
                  </div>
                </td>`;
              tbody.appendChild(tr);
              tbody.appendChild(trInsight);
            } else {
              tbody.appendChild(tr);
            }
            
            // Re-initialize popovers for the new row
            const popoverTriggerList = [].slice.call(tr.querySelectorAll('[data-bs-toggle="popover"]'))
            popoverTriggerList.map(function (popoverTriggerEl) {
              return new bootstrap.Popover(popoverTriggerEl)
            });
          }
          
          // Populate pace zones for new cards
          const paceStr = r.pace;
          let [m, s] = paceStr.split(':');
          let pace_sec = parseInt(m) * 60 + parseInt(s);
          let zone = "Z2";
          let color = "var(--success)";
          if(pace_sec < 270) { zone = "Z5"; color = "var(--danger)"; }
          else if(pace_sec < 300) { zone = "Z4"; color = "var(--warning)"; }
          else if(pace_sec < 330) { zone = "Z3"; color = "var(--info)"; }
          else if(pace_sec > 390) { zone = "Z1"; color = "var(--secondary)"; }
          
          const badge = card.querySelector('.pz-badge');
          if(badge) {
            badge.textContent = zone;
            badge.style.backgroundColor = color;
            badge.style.color = "#000";
            if (zone === "Z1" || zone === "Z5") badge.style.color = "#fff";
          }
          const badgeText = card.querySelector('.pz-badge-text');
          if(badgeText) {
            badgeText.textContent = zone;
            badgeText.style.color = color;
          }
        });
        
        if (btn) {
          const totalRuns = 0;
          const left = Math.max(0, totalRuns - window.currentRunOffset);
          if (left > 0) {
            btn.innerHTML = `<i class="fas fa-chevron-down me-2"></i>Load More (<span id="loadMoreCount">${left}</span> left)`;
            btn.disabled = false;
          } else {
            if (btnContainer) btnContainer.style.display = 'none';
          }
        }
      } catch (err) {
        console.error("Error loading more runs:", err);
        if (btn) {
          btn.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Error (Retry)';
          btn.disabled = false;
        }
      }
    }

    function switchTab(tabId, el) {
      if (el) {
        document.querySelectorAll('.tab-nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll(`.tab-nav-item[data-tab="${tabId}"]`).forEach(i => i.classList.add('active'));
      }

      ['homeView', 'runsView', 'leaderboardView', 'analyticsView', 'achievementsView'].forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
      document.getElementById(tabId + 'View').style.display = 'block';

      setTimeout(() => window.dispatchEvent(new Event('resize')), 50);

      if (tabId === 'home') {
        loadWeeklyGoal();
      }

      if (tabId === 'analytics') {
        if (!tabCache.analytics) {
          loadInsights();
          loadMonthlyComparison();
          loadPaceTrend();
          tabCache.analytics = true;
        }
      }

      if (tabId === 'achievements') {
        loadAchievements();
      }
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
        if (!tabCache.achievements_personalBests) { loadPersonalBests(); tabCache.achievements_personalBests = true; }
      } else if (tabId === 'badges') {
        if (!tabCache.achievements_badges) { loadBadges(); tabCache.achievements_badges = true; }
      } else if (tabId === 'challenges') {
        if (!tabCache.achievements_challenges) { loadChallenges(); tabCache.achievements_challenges = true; }
      } else if (tabId === 'personalGoals') {
        if (!tabCache.achievements_personalGoals) { loadPersonalGoals(); tabCache.achievements_personalGoals = true; }
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
  