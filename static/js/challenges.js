/**
 * RunRush Challenges - Phase 2, 3 & 4
 * Client-side Controller for Friendly Challenges (1v1 Duels), Invitations, Ongoing Progress & History
 */

// Global State
let challengeState = {
  currentTab: 'discover',
  searchQuery: '',
  searchPage: 1,
  searchTotalPages: 1,
  searchDebounceTimer: null,
  
  // Invitations State
  invitations: [],
  outgoingInvitations: [],
  unseenInvitations: [],
  popupIndex: 0,

  // Ongoing & History State
  ongoing: [],
  history: [],
  historyPage: 1,
  historyTotalPages: 1,
  historyFilter: 'all',

  // Builder State
  builder: {
    opponent: null,
    step: 1,
    type: 'DISTANCE',
    startDate: '',
    endDate: '',
    durationDays: 7,
    title: '',
    message: '',
    timezone: (typeof Intl !== 'undefined' && Intl.DateTimeFormat) ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'UTC'
  }
};

const CHALLENGE_TYPE_INFO = {
  DISTANCE: {
    name: 'Distance Duel',
    icon: '🏃',
    rule: 'Highest cumulative distance over the challenge period wins.',
    unit: 'Kilometers'
  },
  CONSISTENCY: {
    name: 'Consistency Duel',
    icon: '📅',
    rule: 'Most distinct calendar days with at least one eligible run wins.',
    unit: 'Active Days'
  },
  LONGEST: {
    name: 'Longest Single Run',
    icon: '⚡',
    rule: 'Highest individual run distance logged during the window wins.',
    unit: 'Kilometers'
  },
  DAILY: {
    name: 'Daily Showdown',
    icon: '🎯',
    rule: 'Highest total distance on one selected calendar day wins.',
    unit: 'Kilometers on Date'
  }
};

// Utilities
function formatLocalISODate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDays(d, days) {
  const result = new Date(d);
  result.setDate(result.getDate() + days);
  return result;
}

function formatFriendlyDateRange(startStr, endStr, isDaily) {
  if (isDaily || startStr === endStr) {
    return startStr;
  }
  return `${startStr} to ${endStr}`;
}

function getCsrfToken() {
  if (typeof window !== 'undefined' && window.userData && window.userData.csrf_token) {
    return window.userData.csrf_token;
  }
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

function getDismissedPopupIds() {
  try {
    if (typeof sessionStorage === 'undefined') return [];
    const raw = sessionStorage.getItem('runrush_dismissed_challenge_invitations');
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function addDismissedPopupId(id) {
  try {
    if (typeof sessionStorage === 'undefined') return;
    const ids = getDismissedPopupIds();
    if (!ids.includes(id)) {
      ids.push(id);
      sessionStorage.setItem('runrush_dismissed_challenge_invitations', JSON.stringify(ids));
    }
  } catch (e) {
    // ignore
  }
}

// Sub-Tab Navigation
function switchChallengeTab(tabName) {
  challengeState.currentTab = tabName;

  const tabs = ['discover', 'invitations', 'ongoing', 'history'];
  tabs.forEach(t => {
    const capitalized = t.charAt(0).toUpperCase() + t.slice(1);
    const btn = document.getElementById(`btnChTab${capitalized}`);
    const pane = document.getElementById(`chPane${capitalized}`);

    if (btn) {
      if (t === tabName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }

    if (pane) {
      if (t === tabName) {
        pane.style.display = 'block';
      } else {
        pane.style.display = 'none';
      }
    }
  });

  if (tabName === 'discover') {
    loadPlayerDiscovery(challengeState.searchPage);
  } else if (tabName === 'invitations') {
    loadInvitations();
  } else if (tabName === 'ongoing') {
    loadOngoingChallenges();
  } else if (tabName === 'history') {
    loadChallengeHistory(challengeState.historyPage);
  }
}

// Load Summary Stats
async function loadChallengeStats() {
  try {
    const res = await fetch('/api/challenges/stats');
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'success' && data.stats) {
      const s = data.stats;
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = (val !== undefined && val !== null) ? val : '-';
      };
      setVal('chStatParticipated', s.total_participated !== undefined ? s.total_participated : s.participated);
      setVal('chStatWins', s.wins);
      setVal('chStatLosses', s.losses);
      setVal('chStatDraws', s.draws);
      setVal('chStatMedals', s.medals_count !== undefined ? s.medals_count : s.medal_count);

      // Update badge if pending invitations returned
      if (s.pending_invitations !== undefined) {
        updateInvitationsBadge(s.pending_invitations);
      }
    }
  } catch (err) {
    console.warn('Failed to load challenge stats:', err);
  }
}

function updateInvitationsBadge(count) {
  const badge = document.getElementById('chInvitationsBadge');
  if (badge) {
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = 'inline-flex';
    } else {
      badge.style.display = 'none';
    }
  }
}

// ============================================================================
// Phase 4: ONGOING CHALLENGES & PROGRESS VIEW
// ============================================================================

// Load Ongoing Challenges
async function loadOngoingChallenges() {
  const listEl = document.getElementById('chOngoingList');
  if (!listEl) return;

  listEl.innerHTML = `
    <div class="col-12 text-center py-5 text-secondary">
      <i class="fa-solid fa-spinner fa-spin fa-2x mb-3" style="color: var(--accent);"></i>
      <div>Updating duel progress...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/challenges/ongoing');
    if (!res.ok) throw new Error('Failed to load ongoing challenges');
    const data = await res.json();

    if (data.status !== 'success') {
      throw new Error(data.message || 'Error fetching ongoing challenges');
    }

    challengeState.ongoing = data.challenges || [];
    renderOngoingChallenges(challengeState.ongoing);
  } catch (err) {
    console.error('Error in loadOngoingChallenges:', err);
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-danger small">
        Failed to load ongoing challenges. Please check your connection.
      </div>
    `;
  }
}

// Render Ongoing Challenge Cards
function renderOngoingChallenges(challenges) {
  const listEl = document.getElementById('chOngoingList');
  if (!listEl) return;

  if (!challenges || challenges.length === 0) {
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">⚔️</div>
        <div class="fw-semibold text-light">No ongoing duels</div>
        <div class="small mt-1">Accept an incoming invitation or challenge a runner to start competing!</div>
        <button class="btn btn-sm rr-btn-primary mt-3 px-3 py-1.5" onclick="switchChallengeTab('discover')">
          <span>🏃</span> Find Opponents
        </button>
      </div>
    `;
    return;
  }

  let html = '<div class="row g-3">';

  challenges.forEach(c => {
    const typeInfo = CHALLENGE_TYPE_INFO[c.challenge_type] || { name: c.challenge_type, icon: '⚔️' };
    const datesLabel = formatFriendlyDateRange(c.start_date, c.end_date, c.challenge_type === 'DAILY');
    const opp = c.opponent || {};

    let leaderBadgeHtml = '';
    if (c.leader === 'you') {
      leaderBadgeHtml = `<span class="cb-leader-pill leading"><i class="fa-solid fa-crown me-1"></i> Leading by ${c.score_diff} ${c.score_unit}</span>`;
    } else if (c.leader === 'opponent') {
      leaderBadgeHtml = `<span class="cb-leader-pill trailing"><i class="fa-solid fa-arrow-down me-1"></i> Trailing by ${c.score_diff} ${c.score_unit}</span>`;
    } else {
      leaderBadgeHtml = `<span class="cb-leader-pill tied"><i class="fa-solid fa-handshake me-1"></i> Tied</span>`;
    }

    const statusPill = c.display_status === 'SCHEDULED'
      ? `<span class="badge bg-secondary-subtle text-secondary small" style="font-size:0.68rem;">SCHEDULED</span>`
      : `<span class="badge" style="background: rgba(0, 242, 255, 0.15); color: var(--accent); font-size:0.68rem; font-weight:700;">ACTIVE</span>`;

    html += `
      <div class="col-12 col-lg-6">
        <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 20px; border: 1px solid rgba(0, 242, 255, 0.2) !important;">
          <div>
            <!-- Header -->
            <div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom border-secondary-subtle">
              <div class="d-flex align-items-center gap-2">
                <span class="fs-5">${typeInfo.icon}</span>
                <div>
                  <h6 class="fw-bold mb-0 text-light text-truncate" style="max-width: 180px;">${c.title || typeInfo.name}</h6>
                  <small class="text-secondary" style="font-size: 0.72rem;">${datesLabel}</small>
                </div>
              </div>
              <div class="text-end">
                ${statusPill}
                <div class="small text-secondary mt-0.5" style="font-size: 0.72rem;">${c.time_remaining || ''}</div>
              </div>
            </div>

            <!-- Scoreboard -->
            <div class="row g-2 align-items-center text-center my-3">
              <!-- You -->
              <div class="col-5">
                <div class="text-secondary small fw-semibold" style="font-size: 0.75rem;">YOU</div>
                <div class="fw-bold fs-4 text-light mt-0.5">${c.my_score} <small class="fs-6 text-secondary">${c.score_unit}</small></div>
              </div>

              <!-- VS & Leader status -->
              <div class="col-2 text-center">
                <div class="text-secondary fw-bold" style="font-size: 0.75rem;">VS</div>
              </div>

              <!-- Opponent -->
              <div class="col-5">
                <div class="d-flex align-items-center justify-content-center gap-1.5 overflow-hidden">
                  <div class="avatar-ring" style="width: 20px; height: 20px; font-size: 0.7rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                    <span>${opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase()}</span>
                  </div>
                  <span class="text-secondary small fw-semibold text-truncate" style="font-size: 0.75rem; max-width: 90px;">${opp.display_name || opp.username}</span>
                </div>
                <div class="fw-bold fs-4 mt-0.5" style="color: #f59e0b;">${c.opponent_score} <small class="fs-6 text-secondary">${c.score_unit}</small></div>
              </div>
            </div>

            <!-- Comparison Bar -->
            <div class="my-2">
              <div class="cb-ratio-track mb-1.5">
                <div class="cb-ratio-fill-my" style="width: ${c.my_ratio}%;"></div>
                <div class="cb-ratio-fill-opp" style="width: ${c.opponent_ratio}%;"></div>
              </div>
              <div class="d-flex justify-content-between text-secondary" style="font-size: 0.7rem;">
                <span style="color: var(--accent); font-weight: 600;">You: ${c.my_ratio}%</span>
                <span>${leaderBadgeHtml}</span>
                <span style="color: #f59e0b; font-weight: 600;">${opp.display_name}: ${c.opponent_ratio}%</span>
              </div>
            </div>
          </div>

          <!-- Card Actions -->
          <div class="pt-3 mt-2 border-top border-secondary-subtle">
            <button class="btn btn-sm btn-glass w-100 py-1.5 d-flex align-items-center justify-content-center gap-1.5" onclick="openChallengeProgress(${c.id})">
              <i class="fa-solid fa-chart-simple"></i> View Detailed Breakdown
            </button>
          </div>
        </div>
      </div>
    `;
  });

  html += '</div>';
  listEl.innerHTML = html;
}

// Open Detailed Progress Modal
async function openChallengeProgress(challengeId) {
  const bodyEl = document.getElementById('challengeProgressModalBody');
  const badgeEl = document.getElementById('cpmStatusBadge');
  const timerEl = document.getElementById('cpmTimeRemaining');
  const titleEl = document.getElementById('challengeProgressModalTitle');

  if (bodyEl) {
    bodyEl.innerHTML = `
      <div class="text-center py-5 text-secondary">
        <i class="fa-solid fa-spinner fa-spin fa-2x mb-3" style="color: var(--accent);"></i>
        <div>Recalculating live progress from run logs...</div>
      </div>
    `;
  }

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeProgressModal');
    if (modalEl) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  }

  try {
    const res = await fetch(`/api/challenges/${challengeId}/progress`);
    if (!res.ok) throw new Error('Could not calculate challenge progress');
    const data = await res.json();

    if (data.status !== 'success' || !data.progress) {
      throw new Error(data.error || 'Failed to calculate progress');
    }

    const p = data.progress;
    const chal = p.challenge;
    const typeInfo = CHALLENGE_TYPE_INFO[chal.challenge_type] || { name: chal.challenge_type, icon: '⚔️', rule: '' };
    const datesLabel = formatFriendlyDateRange(chal.start_date, chal.end_date, chal.challenge_type === 'DAILY');

    if (titleEl) titleEl.textContent = chal.title || `${typeInfo.name}`;
    if (badgeEl) {
      badgeEl.textContent = p.display_status || chal.status;
      badgeEl.style.background = chal.status === 'COMPLETED' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(0, 242, 255, 0.15)';
      badgeEl.style.color = chal.status === 'COMPLETED' ? '#22c55e' : 'var(--accent)';
    }
    if (timerEl) timerEl.textContent = p.time_remaining || '';

    // Render detailed modal view
    const c = p.challenger;
    const o = p.opponent;
    const unit = p.score_unit;

    let leaderText = 'Tied';
    if (!p.is_tied) {
      leaderText = p.leader_id === c.user_id ? `${c.display_name} leads` : `${o.display_name} leads`;
    }

    let runsHtml = '';
    const renderRunList = (runs, runnerName) => {
      if (!runs || runs.length === 0) {
        return `<div class="text-secondary small fst-italic py-2">No qualifying runs recorded yet.</div>`;
      }
      return runs.map(r => `
        <div class="cb-run-item">
          <div>
            <div class="fw-semibold text-light small">${r.distance_km} km</div>
            <div class="text-secondary" style="font-size: 0.7rem;">${r.local_date || r.date} • ${r.run_type || 'Run'}</div>
          </div>
          <div class="text-end text-secondary small" style="font-size: 0.72rem;">
            ${r.time_min ? `${Math.round(r.time_min)} min` : ''}
          </div>
        </div>
      `).join('');
    };

    let activityHtml = '';
    if (p.activity && p.activity.length > 0) {
      activityHtml = p.activity.map(a => `
        <div class="d-flex align-items-center gap-2 py-1 text-secondary" style="font-size: 0.72rem;">
          <span>${a.actor_emoji || '⚡'}</span>
          <span class="text-light fw-semibold">${a.actor_name}:</span>
          <span>${a.activity_type.toLowerCase()}</span>
          <span class="ms-auto">${a.created_at ? a.created_at.substring(0, 16) : ''}</span>
        </div>
      `).join('');
    }

    let completionBanner = '';
    if (chal.status === 'COMPLETED') {
      if (chal.result_type === 'DRAW') {
        completionBanner = `
          <div class="p-2.5 rounded-3 mb-3 d-flex align-items-center gap-2" style="background: rgba(148, 163, 184, 0.15); border: 1px solid rgba(148, 163, 184, 0.3);">
            <span style="font-size: 1.25rem;">🤝</span>
            <div>
              <div class="fw-bold text-light small">Final Result: Draw / Tie</div>
              <div class="text-secondary" style="font-size: 0.72rem;">Both runners achieved equal scores. No medal awarded.</div>
            </div>
          </div>
        `;
      } else if (chal.winner_id) {
        const winnerName = chal.winner_id === c.user_id ? c.display_name : o.display_name;
        completionBanner = `
          <div class="p-2.5 rounded-3 mb-3 d-flex align-items-center gap-2" style="background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35);">
            <span style="font-size: 1.25rem;">🏆</span>
            <div>
              <div class="fw-bold text-light small">Final Result: Winner — ${winnerName}!</div>
              <div class="text-warning small" style="font-size: 0.72rem;">🎖️ 1 Friendly Challenges Medal Awarded</div>
            </div>
          </div>
        `;
      }
    }

    if (bodyEl) {
      bodyEl.innerHTML = `
        ${completionBanner}
        <!-- Top Metrics & Rules -->
        <div class="glass p-3 mb-3" style="border-radius: 16px;">
          <div class="d-flex align-items-center justify-content-between mb-2">
            <span class="text-secondary small">TIME WINDOW & TIMEZONE</span>
            <span class="text-light small fw-bold">${datesLabel} (${chal.challenge_timezone || 'UTC'})</span>
          </div>
          <div class="text-secondary small mb-3">
            <i class="fa-solid fa-circle-info me-1" style="color: var(--accent);"></i> ${typeInfo.rule}
          </div>

          <!-- Scoreboard Duel Comparison -->
          <div class="row g-2 align-items-center text-center py-2 px-1 rounded-3" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-subtle);">
            <div class="col-5">
              <div class="d-flex align-items-center justify-content-center gap-1.5 mb-1">
                <span class="avatar-ring" style="width: 24px; height: 24px; font-size: 0.8rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                  ${c.profile_emoji}
                </span>
                <span class="fw-bold text-light small text-truncate" style="max-width: 100px;">${c.display_name}</span>
              </div>
              <div class="fs-4 fw-bold" style="color: var(--accent);">${c.display_score} <small class="fs-6 text-secondary">${unit}</small></div>
            </div>

            <div class="col-2">
              <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.65rem;">VS</span>
            </div>

            <div class="col-5">
              <div class="d-flex align-items-center justify-content-center gap-1.5 mb-1">
                <span class="avatar-ring" style="width: 24px; height: 24px; font-size: 0.8rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                  ${o.profile_emoji}
                </span>
                <span class="fw-bold text-light small text-truncate" style="max-width: 100px;">${o.display_name}</span>
              </div>
              <div class="fs-4 fw-bold" style="color: #f59e0b;">${o.display_score} <small class="fs-6 text-secondary">${unit}</small></div>
            </div>
          </div>

          <!-- Relative Share Comparison Bar -->
          <div class="mt-3">
            <div class="cb-ratio-track mb-1.5">
              <div class="cb-ratio-fill-my" style="width: ${p.ratio_challenger}%;"></div>
              <div class="cb-ratio-fill-opp" style="width: ${p.ratio_opponent}%;"></div>
            </div>
            <div class="d-flex justify-content-between text-secondary" style="font-size: 0.72rem;">
              <span style="color: var(--accent); font-weight: 600;">${c.display_name}: ${p.ratio_challenger}%</span>
              <span class="fw-bold text-light">${leaderText}</span>
              <span style="color: #f59e0b; font-weight: 600;">${o.display_name}: ${p.ratio_opponent}%</span>
            </div>
            <div class="text-center text-secondary mt-1" style="font-size: 0.68rem; opacity: 0.75;">
              Relative score ratio based on current verified runs (not a predictive forecast)
            </div>
          </div>
        </div>

        <!-- Qualifying Run Breakdown -->
        <div class="row g-3 mb-3">
          <div class="col-12 col-md-6">
            <div class="glass p-3 h-100" style="border-radius: 16px;">
              <h6 class="fw-bold text-light small mb-2 d-flex align-items-center gap-1.5">
                <span style="color: var(--accent);">•</span> ${c.display_name}'s Runs (${c.qualifying_runs.length})
              </h6>
              ${renderRunList(c.qualifying_runs, c.display_name)}
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="glass p-3 h-100" style="border-radius: 16px;">
              <h6 class="fw-bold text-light small mb-2 d-flex align-items-center gap-1.5">
                <span style="color: #f59e0b;">•</span> ${o.display_name}'s Runs (${o.qualifying_runs.length})
              </h6>
              ${renderRunList(o.qualifying_runs, o.display_name)}
            </div>
          </div>
        </div>

        ${activityHtml ? `
          <div class="glass p-3" style="border-radius: 16px;">
            <h6 class="fw-bold text-light small mb-2">Challenge Activity</h6>
            ${activityHtml}
          </div>
        ` : ''}
      `;
    }

  } catch (err) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div class="text-danger small py-4 text-center">${err.message}</div>`;
    }
  }
}

// ============================================================================
// Phase 4: CHALLENGE HISTORY & FILTERING
// ============================================================================

// Load History
async function loadChallengeHistory(page = 1) {
  const listEl = document.getElementById('chHistoryList');
  const pagEl = document.getElementById('chHistoryPagination');
  if (!listEl) return;

  challengeState.historyPage = page;
  listEl.innerHTML = `
    <div class="col-12 text-center py-5 text-secondary">
      <i class="fa-solid fa-spinner fa-spin fa-2x mb-3" style="color: var(--accent);"></i>
      <div>Loading challenge history...</div>
    </div>
  `;

  try {
    const params = new URLSearchParams({
      page: page,
      limit: 10,
      filter: challengeState.historyFilter || 'all'
    });

    const res = await fetch(`/api/challenges/history?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();

    if (data.status !== 'success') {
      throw new Error(data.message || 'Error fetching history');
    }

    challengeState.history = data.challenges || [];
    renderChallengeHistory(challengeState.history, data.pagination || {});
  } catch (err) {
    console.error('Error in loadChallengeHistory:', err);
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-danger small">
        Failed to load challenge history. Please try again.
      </div>
    `;
    if (pagEl) pagEl.style.display = 'none';
  }
}

// Render History Cards
function renderChallengeHistory(challenges, pagination) {
  const listEl = document.getElementById('chHistoryList');
  const pagEl = document.getElementById('chHistoryPagination');
  if (!listEl) return;

  challengeState.historyTotalPages = pagination.total_pages || 1;

  if (!challenges || challenges.length === 0) {
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">📜</div>
        <div class="fw-semibold text-light">No challenge history found</div>
        <div class="small mt-1">Completed, declined, and expired challenges will appear here.</div>
      </div>
    `;
    if (pagEl) pagEl.style.display = 'none';
    return;
  }

  let html = '';

  challenges.forEach(h => {
    const typeInfo = CHALLENGE_TYPE_INFO[h.challenge_type] || { name: h.challenge_type, icon: '⚔️' };
    const datesLabel = formatFriendlyDateRange(h.start_date, h.end_date, h.challenge_type === 'DAILY');
    const opp = h.opponent || {};

    let outcomeBadge = '';
    if (h.outcome === 'WIN') {
      outcomeBadge = `<span class="badge bg-success" style="font-weight: 700;">WIN 🏆</span>`;
    } else if (h.outcome === 'LOSS') {
      outcomeBadge = `<span class="badge bg-danger" style="font-weight: 700;">LOSS</span>`;
    } else if (h.outcome === 'DRAW') {
      outcomeBadge = `<span class="badge bg-warning text-dark" style="font-weight: 700;">DRAW 🤝</span>`;
    } else if (h.outcome === 'DECLINED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">DECLINED</span>`;
    } else if (h.outcome === 'EXPIRED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">EXPIRED</span>`;
    } else if (h.outcome === 'CANCELLED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">CANCELLED</span>`;
    } else {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary">${h.outcome}</span>`;
    }

    const scoresDisplay = (h.status === 'COMPLETED' && h.my_final_score !== undefined)
      ? `<div class="small text-light mt-1">Final Score: <strong>${h.my_final_score}</strong> vs <strong>${h.opponent_final_score}</strong></div>`
      : '';

    html += `
      <div class="col-12 col-md-6">
        <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px;">
          <div>
            <div class="d-flex align-items-center justify-content-between mb-2">
              <div class="d-flex align-items-center gap-1.5">
                <span class="fs-6">${typeInfo.icon}</span>
                <span class="fw-bold small text-light text-truncate" style="max-width: 170px;">${h.title || typeInfo.name}</span>
              </div>
              ${outcomeBadge}
            </div>

            <div class="d-flex align-items-center gap-2.5 my-2">
              <div class="avatar-ring" style="width: 36px; height: 36px; font-size: 1.1rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                <span>${opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase()}</span>
              </div>
              <div class="overflow-hidden">
                <div class="fw-bold text-light small text-truncate">${opp.display_name || opp.username}</div>
                <small class="text-secondary" style="font-size: 0.72rem;">@${opp.username} • ${datesLabel}</small>
              </div>
            </div>

            ${scoresDisplay}
          </div>

          <div class="pt-2 mt-2 border-top border-secondary-subtle d-flex justify-content-end">
            <button class="btn btn-sm btn-link text-secondary text-decoration-none p-0 small" onclick="openChallengeProgress(${h.id})">
              Inspect Breakdown <i class="fa fa-chevron-right ms-1"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  });

  listEl.innerHTML = html;

  // Pagination controls
  if (pagEl) {
    if (challengeState.historyTotalPages > 1) {
      pagEl.style.display = 'flex';
      const infoEl = document.getElementById('chHistoryPageInfo');
      const prevBtn = document.getElementById('chHistoryPrevBtn');
      const nextBtn = document.getElementById('chHistoryNextBtn');
      if (infoEl) infoEl.textContent = `Page ${challengeState.historyPage} of ${challengeState.historyTotalPages}`;
      if (prevBtn) prevBtn.disabled = challengeState.historyPage <= 1;
      if (nextBtn) nextBtn.disabled = challengeState.historyPage >= challengeState.historyTotalPages;
    } else {
      pagEl.style.display = 'none';
    }
  }
}

function filterChallengeHistory(filterName, btnEl) {
  challengeState.historyFilter = filterName;
  document.querySelectorAll('.cb-history-filter-btn').forEach(btn => {
    if (btn === btnEl || btn.dataset.filter === filterName || btn.getAttribute('data-filter') === filterName) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  loadChallengeHistory(1);
}

function changeHistoryPage(delta) {
  const newPage = challengeState.historyPage + delta;
  if (newPage >= 1 && newPage <= challengeState.historyTotalPages) {
    loadChallengeHistory(newPage);
  }
}

// ============================================================================
// Phase 3: INVITATIONS WORKFLOW (Preserved)
// ============================================================================

// Load Invitations for Inbox & Popup
async function loadInvitations(checkPopup = false) {
  const listEl = document.getElementById('chInvitationsList');
  if (listEl && challengeState.currentTab === 'invitations') {
    listEl.innerHTML = `
      <div class="text-center py-5 text-secondary">
        <i class="fa-solid fa-spinner fa-spin fa-2x mb-3" style="color: var(--accent);"></i>
        <div>Loading invitations...</div>
      </div>
    `;
  }

  try {
    const res = await fetch('/api/challenges/invitations');
    if (!res.ok) throw new Error('Failed to load invitations');
    const data = await res.json();

    if (data.status !== 'success') {
      throw new Error(data.message || 'Error fetching invitations');
    }

    challengeState.invitations = data.incoming || [];
    challengeState.outgoingInvitations = data.outgoing || [];

    // Update notification pill badge
    updateInvitationsBadge(challengeState.invitations.length);

    // Render Inbox if on invitations tab
    if (listEl) {
      renderInvitations(challengeState.invitations, challengeState.outgoingInvitations);
    }

    // Check for unseen popup invitations on app open
    if (checkPopup && challengeState.invitations.length > 0) {
      checkAndShowInvitationPopup(challengeState.invitations);
    }

  } catch (err) {
    console.error('Error in loadInvitations:', err);
    if (listEl && challengeState.currentTab === 'invitations') {
      listEl.innerHTML = `
        <div class="text-center py-5 text-danger small">
          Failed to load invitations. Please try again.
        </div>
      `;
    }
  }
}

// Render Invitations Inbox
function renderInvitations(incoming, outgoing) {
  const listEl = document.getElementById('chInvitationsList');
  if (!listEl) return;

  if ((!incoming || incoming.length === 0) && (!outgoing || outgoing.length === 0)) {
    listEl.innerHTML = `
      <div class="text-center py-5 text-secondary">
        <div class="fs-1 mb-2">✉️</div>
        <div class="fw-semibold text-light">No pending invitations</div>
        <div class="small mt-1">Discover runners to send a challenge duel!</div>
        <button class="btn btn-sm rr-btn-primary mt-3 px-3 py-1.5" onclick="switchChallengeTab('discover')">
          <span>⚔️</span> Discover Runners
        </button>
      </div>
    `;
    return;
  }

  let html = '';

  // Incoming Invitations Section
  if (incoming && incoming.length > 0) {
    html += `
      <h6 class="fw-bold mb-3 d-flex align-items-center gap-2" style="color: var(--text-main);">
        <span>Incoming Duels</span>
        <span class="badge bg-danger rounded-pill">${incoming.length}</span>
      </h6>
      <div class="row g-3 mb-4">
    `;

    incoming.forEach(inv => {
      const typeInfo = CHALLENGE_TYPE_INFO[inv.challenge_type] || { name: inv.challenge_type, icon: '⚔️', rule: '' };
      const challenger = inv.challenger || {};
      const datesLabel = formatFriendlyDateRange(inv.start_date, inv.end_date, inv.challenge_type === 'DAILY');
      const sentTimeStr = inv.created_at ? new Date(inv.created_at + (inv.created_at.includes('Z') ? '' : 'Z')).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';

      html += `
        <div class="col-12 col-lg-6">
          <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px; border: 1px solid rgba(234, 179, 8, 0.25) !important;">
            <div>
              <div class="d-flex align-items-center justify-content-between mb-2">
                <span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-weight: 700;">INVITATION</span>
                <span class="text-secondary small" style="font-size: 0.72rem;">${sentTimeStr ? `Sent ${sentTimeStr}` : ''}</span>
              </div>

              <!-- Challenger info -->
              <div class="d-flex align-items-center gap-3 mb-3">
                <a href="/profile/${encodeURIComponent(challenger.username || '')}" class="text-decoration-none">
                  <div class="avatar-ring" style="width: 44px; height: 44px; font-size: 1.3rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                    <span>${challenger.profile_emoji || (challenger.display_name || challenger.username || 'U')[0].toUpperCase()}</span>
                  </div>
                </a>
                <div class="overflow-hidden">
                  <div class="fw-bold text-light text-truncate">
                    <a href="/profile/${encodeURIComponent(challenger.username || '')}" class="text-light text-decoration-none hover-underline">
                      ${challenger.display_name || challenger.username}
                    </a>
                  </div>
                  <small class="text-secondary d-block">@${challenger.username}</small>
                </div>
              </div>

              <!-- Challenge specifics -->
              <div class="p-2.5 rounded-3 mb-3" style="background: rgba(255,255,255,0.025); border: 1px solid var(--border-subtle);">
                <div class="d-flex align-items-center gap-2 mb-1">
                  <span class="fs-5">${typeInfo.icon}</span>
                  <div>
                    <span class="fw-bold small text-light">${inv.title || typeInfo.name}</span>
                    <span class="text-secondary small ms-1">(${typeInfo.name})</span>
                  </div>
                </div>
                <div class="small text-secondary mb-1">
                  <i class="fa-regular fa-calendar me-1"></i> ${datesLabel}
                </div>
                <div class="small text-secondary" style="font-size: 0.75rem;">
                  ${typeInfo.rule}
                </div>
                ${inv.message ? `
                  <div class="small fst-italic mt-2 pt-2 border-top border-secondary-subtle" style="color: #cbd5e1; font-size: 0.78rem;">
                    "${inv.message}"
                  </div>
                ` : ''}
              </div>
            </div>

            <!-- Action buttons -->
            <div class="d-flex gap-2 align-items-center pt-2">
              <button class="btn btn-sm btn-outline-danger flex-fill py-1.5" onclick="rejectInvitation(${inv.id})">
                Decline
              </button>
              <button class="btn btn-sm btn-glass text-secondary px-2.5 py-1.5" title="View full details" onclick="viewChallengeDetails(${inv.id})">
                <i class="fa-solid fa-circle-info"></i> Details
              </button>
              <button class="btn btn-sm rr-btn-primary flex-fill py-1.5" onclick="acceptInvitation(${inv.id})">
                <span>⚔️</span> Accept
              </button>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
  }

  // Outgoing / Sent Invitations Section
  if (outgoing && outgoing.length > 0) {
    html += `
      <h6 class="fw-bold mb-3 d-flex align-items-center gap-2 text-secondary">
        <span>Sent Invitations</span>
        <span class="badge bg-secondary-subtle text-secondary rounded-pill">${outgoing.length}</span>
      </h6>
      <div class="row g-3">
    `;

    outgoing.forEach(inv => {
      const typeInfo = CHALLENGE_TYPE_INFO[inv.challenge_type] || { name: inv.challenge_type, icon: '⚔️' };
      const opp = inv.opponent || {};
      const datesLabel = formatFriendlyDateRange(inv.start_date, inv.end_date, inv.challenge_type === 'DAILY');

      html += `
        <div class="col-12 col-lg-6">
          <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px; opacity: 0.88;">
            <div>
              <div class="d-flex align-items-center justify-content-between mb-2">
                <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.68rem;">SENT</span>
                <span class="text-secondary small" style="font-size: 0.72rem;">Waiting for response...</span>
              </div>
              <div class="d-flex align-items-center gap-3 mb-2">
                <div class="avatar-ring" style="width: 38px; height: 38px; font-size: 1.1rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                  <span>${opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase()}</span>
                </div>
                <div class="overflow-hidden">
                  <div class="fw-bold text-light text-truncate">${opp.display_name || opp.username}</div>
                  <small class="text-secondary">@${opp.username}</small>
                </div>
              </div>
              <div class="small text-secondary mb-2">
                ${typeInfo.icon} <strong>${inv.title || typeInfo.name}</strong> • ${datesLabel}
              </div>
            </div>
            <div class="d-flex justify-content-between align-items-center pt-2">
              <button class="btn btn-sm btn-link text-secondary text-decoration-none p-0 small" onclick="viewChallengeDetails(${inv.id})">
                View Rules
              </button>
              <button class="btn btn-sm btn-outline-secondary py-1 px-3" style="font-size: 0.75rem;" onclick="cancelInvitation(${inv.id})">
                Cancel Invitation
              </button>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
  }

  listEl.innerHTML = html;
}

// Accept Invitation
async function acceptInvitation(challengeId) {
  try {
    const res = await fetch(`/api/challenges/${challengeId}/accept`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken()
      }
    });

    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.error || data.message || 'Failed to accept challenge.');
    }

    if (typeof showToast === 'function') {
      showToast(`⚔️ Challenge accepted! Status: ${data.display_status || 'active'}`, 'success');
    } else {
      alert(`⚔️ Challenge accepted! Status: ${data.display_status || 'active'}`);
    }

    loadChallengeStats();
    loadInvitations();
    switchChallengeTab('ongoing');

  } catch (err) {
    console.error('Error accepting challenge:', err);
    alert(err.message || 'Failed to accept challenge.');
  }
}

// Reject Invitation
async function rejectInvitation(challengeId) {
  if (!confirm('Are you sure you want to decline this challenge invitation?')) {
    return;
  }

  try {
    const res = await fetch(`/api/challenges/${challengeId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken()
      }
    });

    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.error || data.message || 'Failed to decline challenge.');
    }

    if (typeof showToast === 'function') {
      showToast('Challenge invitation declined.', 'info');
    }

    loadChallengeStats();
    loadInvitations();

  } catch (err) {
    console.error('Error declining challenge:', err);
    alert(err.message || 'Failed to decline challenge.');
  }
}

// Cancel Sent Invitation
async function cancelInvitation(challengeId) {
  if (!confirm('Cancel this pending challenge invitation?')) {
    return;
  }

  try {
    const res = await fetch(`/api/challenges/${challengeId}/cancel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken()
      }
    });

    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.error || data.message || 'Failed to cancel invitation.');
    }

    if (typeof showToast === 'function') {
      showToast('Challenge invitation cancelled.', 'info');
    }

    loadChallengeStats();
    loadInvitations();

  } catch (err) {
    console.error('Error cancelling challenge:', err);
    alert(err.message || 'Failed to cancel invitation.');
  }
}

// View Challenge Details Modal
async function viewChallengeDetails(challengeId) {
  const bodyEl = document.getElementById('challengeDetailsModalBody');
  if (bodyEl) {
    bodyEl.innerHTML = `
      <div class="text-center py-4 text-secondary">
        <i class="fa-solid fa-spinner fa-spin fa-2x mb-2" style="color: var(--accent);"></i>
        <div>Loading details...</div>
      </div>
    `;
  }

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeDetailsModal');
    if (modalEl) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  }

  try {
    const res = await fetch(`/api/challenges/${challengeId}`);
    if (!res.ok) throw new Error('Could not load challenge details');
    const data = await res.json();

    if (data.status !== 'success' || !data.challenge) {
      throw new Error(data.error || 'Failed to load details');
    }

    const chal = data.challenge;
    const typeInfo = CHALLENGE_TYPE_INFO[chal.challenge_type] || { name: chal.challenge_type, icon: '⚔️', rule: '' };
    const datesLabel = formatFriendlyDateRange(chal.start_date, chal.end_date, chal.challenge_type === 'DAILY');

    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="d-flex align-items-center gap-3 mb-3 pb-3 border-bottom border-secondary-subtle">
          <div class="avatar-ring" style="width: 48px; height: 48px; font-size: 1.5rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
            <span>${typeInfo.icon}</span>
          </div>
          <div>
            <h6 class="fw-bold mb-0 text-light">${chal.title || typeInfo.name}</h6>
            <span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size: 0.7rem;">${chal.display_status || chal.status}</span>
          </div>
        </div>

        <div class="row g-2 small mb-3">
          <div class="col-6">
            <span class="text-secondary d-block" style="font-size: 0.72rem;">CHALLENGER</span>
            <span class="fw-bold text-light">${chal.challenger.display_name} (@${chal.challenger.username})</span>
          </div>
          <div class="col-6">
            <span class="text-secondary d-block" style="font-size: 0.72rem;">OPPONENT</span>
            <span class="fw-bold text-light">${chal.opponent.display_name} (@${chal.opponent.username})</span>
          </div>
          <div class="col-6">
            <span class="text-secondary d-block" style="font-size: 0.72rem;">DATES</span>
            <span class="text-light">${datesLabel}</span>
          </div>
          <div class="col-6">
            <span class="text-secondary d-block" style="font-size: 0.72rem;">TIMEZONE</span>
            <span class="text-light">${chal.challenge_timezone || 'UTC'}</span>
          </div>
        </div>

        <div class="p-2.5 rounded-3 mb-3" style="background: rgba(255,255,255,0.03);">
          <span class="text-secondary d-block small fw-bold mb-1" style="font-size: 0.72rem;">WINNING CONDITION</span>
          <p class="small text-light mb-0">${typeInfo.rule}</p>
        </div>

        ${chal.message ? `
          <div class="p-2.5 rounded-3 mb-3" style="background: rgba(255,255,255,0.03);">
            <span class="text-secondary d-block small fw-bold mb-1" style="font-size: 0.72rem;">NOTE FROM CHALLENGER</span>
            <p class="small fst-italic text-light mb-0">"${chal.message}"</p>
          </div>
        ` : ''}

        <div class="alert alert-info py-2 px-3 small border-0 mb-0" style="background: var(--accent-soft); color: var(--accent); border-radius: 12px; font-size: 0.78rem;">
          <i class="fa-solid fa-medal me-1"></i> Winner receives 1 Friendly Challenges Medal. Draws award no medal.
        </div>
      `;
    }

  } catch (err) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div class="text-danger small py-3">${err.message}</div>`;
    }
  }
}

// ============================================================================
// Automatic In-App Invitation Popup Modal
// ============================================================================

function checkAndShowInvitationPopup(invitations) {
  if (!invitations || invitations.length === 0) return;

  const dismissedIds = getDismissedPopupIds();
  const unseen = invitations.filter(inv => !dismissedIds.includes(inv.id));

  if (unseen.length === 0) return;

  challengeState.unseenInvitations = unseen;
  challengeState.popupIndex = 0;

  renderPopupCurrentInvitation();

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeInvitationPopupModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }
}

function renderPopupCurrentInvitation() {
  const list = challengeState.unseenInvitations;
  if (!list || list.length === 0) {
    dismissInvitationPopup();
    return;
  }

  const idx = Math.max(0, Math.min(challengeState.popupIndex, list.length - 1));
  challengeState.popupIndex = idx;
  const inv = list[idx];

  const typeInfo = CHALLENGE_TYPE_INFO[inv.challenge_type] || { name: inv.challenge_type, icon: '⚔️', rule: '' };
  const challenger = inv.challenger || {};
  const datesLabel = formatFriendlyDateRange(inv.start_date, inv.end_date, inv.challenge_type === 'DAILY');

  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setEl('popupChallengerName', challenger.display_name || challenger.username || 'Runner');
  setEl('popupChallengerHandle', `@${challenger.username || 'user'}`);
  setEl('popupChallengerEmoji', challenger.profile_emoji || (challenger.display_name || challenger.username || 'U')[0].toUpperCase());
  setEl('popupChallengeTitle', inv.title ? `${inv.title} (${typeInfo.name})` : typeInfo.name);
  setEl('popupChallengeDates', datesLabel);
  setEl('popupChallengeRule', typeInfo.rule);

  const iconEl = document.getElementById('popupTypeIcon');
  if (iconEl) iconEl.textContent = typeInfo.icon;

  const msgContainer = document.getElementById('popupMessageContainer');
  const msgEl = document.getElementById('popupMessage');
  if (inv.message) {
    if (msgContainer) msgContainer.style.display = 'block';
    if (msgEl) msgEl.textContent = `"${inv.message}"`;
  } else {
    if (msgContainer) msgContainer.style.display = 'none';
  }

  const counterEl = document.getElementById('popupInvitationCounter');
  const prevBtn = document.getElementById('popupPrevBtn');
  const nextBtn = document.getElementById('popupNextBtn');

  if (list.length > 1) {
    if (counterEl) {
      counterEl.textContent = `${idx + 1} of ${list.length}`;
      counterEl.style.display = 'inline-block';
    }
    if (prevBtn) prevBtn.style.display = idx > 0 ? 'inline-block' : 'none';
    if (nextBtn) nextBtn.style.display = idx < list.length - 1 ? 'inline-block' : 'none';
  } else {
    if (counterEl) counterEl.style.display = 'none';
    if (prevBtn) prevBtn.style.display = 'none';
    if (nextBtn) nextBtn.style.display = 'none';
  }

  const errAlert = document.getElementById('popupActionError');
  if (errAlert) errAlert.style.display = 'none';
}

function navigatePopupInvitation(delta) {
  challengeState.popupIndex += delta;
  renderPopupCurrentInvitation();
}

function dismissInvitationPopup() {
  if (challengeState.unseenInvitations && challengeState.unseenInvitations.length > 0) {
    challengeState.unseenInvitations.forEach(inv => addDismissedPopupId(inv.id));
  }

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeInvitationPopupModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
  }
}

async function respondToPopupInvitation(action) {
  const list = challengeState.unseenInvitations;
  if (!list || list.length === 0) return;

  const inv = list[challengeState.popupIndex];
  if (!inv) return;

  const acceptBtn = document.getElementById('popupAcceptBtn');
  const rejectBtn = document.getElementById('popupRejectBtn');
  const errAlert = document.getElementById('popupActionError');

  if (errAlert) errAlert.style.display = 'none';
  if (acceptBtn) acceptBtn.disabled = true;
  if (rejectBtn) rejectBtn.disabled = true;

  try {
    const endpoint = action === 'accept' ? `/api/challenges/${inv.id}/accept` : `/api/challenges/${inv.id}/reject`;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken()
      }
    });

    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.error || data.message || `Failed to ${action} challenge.`);
    }

    addDismissedPopupId(inv.id);
    challengeState.unseenInvitations.splice(challengeState.popupIndex, 1);

    if (action === 'accept') {
      if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const modalEl = document.getElementById('challengeInvitationPopupModal');
        if (modalEl) {
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
      }
      if (typeof showToast === 'function') {
        showToast(`⚔️ Challenge accepted! Status: ${data.display_status || 'active'}`, 'success');
      }
      loadChallengeStats();
      loadInvitations();
      switchChallengeTab('ongoing');
      return;
    }

    if (challengeState.unseenInvitations.length > 0) {
      if (challengeState.popupIndex >= challengeState.unseenInvitations.length) {
        challengeState.popupIndex = challengeState.unseenInvitations.length - 1;
      }
      renderPopupCurrentInvitation();
    } else {
      if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const modalEl = document.getElementById('challengeInvitationPopupModal');
        if (modalEl) {
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
      }
    }

    loadChallengeStats();
    loadInvitations();

  } catch (err) {
    console.error('Error responding to popup invitation:', err);
    if (errAlert) {
      errAlert.textContent = err.message || 'Action failed.';
      errAlert.style.display = 'block';
    } else {
      alert(err.message);
    }
  } finally {
    if (acceptBtn) acceptBtn.disabled = false;
    if (rejectBtn) rejectBtn.disabled = false;
  }
}

// ============================================================================
// Phase 2: PLAYER DISCOVERY & BUILDER (Preserved)
// ============================================================================

// Load Player Discovery
async function loadPlayerDiscovery(page = 1) {
  const listEl = document.getElementById('chPlayersList');
  if (!listEl) return;

  challengeState.searchPage = page;
  listEl.innerHTML = `
    <div class="col-12 text-center py-4 text-secondary">
      <i class="fa-solid fa-spinner fa-spin fa-2x mb-2" style="color: var(--accent);"></i>
      <div>Finding runners...</div>
    </div>
  `;

  try {
    const q = challengeState.searchQuery || '';
    const params = new URLSearchParams({
      q: q,
      page: page,
      limit: 12
    });

    const res = await fetch(`/api/challenges/players?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch runners');
    const data = await res.json();

    if (data.status !== 'success') {
      throw new Error(data.message || 'Error searching runners');
    }

    renderPlayerDiscovery(data.players || [], data.pagination || {});
  } catch (err) {
    console.error('Error in loadPlayerDiscovery:', err);
    listEl.innerHTML = `
      <div class="col-12 text-center py-4 text-danger small">
        Failed to load runners. Please check your connection and try again.
      </div>
    `;
  }
}

// Render Discovery Player Cards
function renderPlayerDiscovery(players, pagination) {
  const listEl = document.getElementById('chPlayersList');
  const pagEl = document.getElementById('chPlayersPagination');
  if (!listEl) return;

  challengeState.searchTotalPages = pagination.total_pages || pagination.pages || 1;

  if (!players || players.length === 0) {
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">🏃</div>
        <div class="fw-semibold text-light">No runners found</div>
        <div class="small mt-1">Try searching for a different username or display name.</div>
      </div>
    `;
    if (pagEl) pagEl.style.display = 'none';
    return;
  }

  listEl.innerHTML = players.map(p => {
    const avatar = p.profile_emoji || (p.display_name || p.username || 'U')[0].toUpperCase();
    const isFollowing = p.is_following;
    const pending = p.has_pending_challenge;

    const followBadge = isFollowing
      ? `<span class="badge bg-secondary-subtle text-secondary small ms-1" style="font-size:0.65rem;">Following</span>`
      : '';

    let actionBtn = '';
    if (pending) {
      actionBtn = `
        <button class="btn btn-sm btn-outline-warning disabled w-100 py-1" style="font-size: 0.78rem; opacity: 0.75;" disabled>
          <i class="fa-solid fa-hourglass-half me-1"></i> Invitation Pending
        </button>
      `;
    } else {
      actionBtn = `
        <button class="btn btn-sm rr-btn-primary w-100 py-1 d-flex align-items-center justify-content-center gap-1" style="font-size: 0.8rem;" onclick='openChallengeBuilder(${JSON.stringify(p).replace(/'/g, "&#39;")})'>
          <span>⚔️</span> Challenge
        </button>
      `;
    }

    return `
      <div class="col-12 col-md-6 col-lg-4">
        <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 16px;">
          <div class="d-flex align-items-center gap-3 mb-3">
            <a href="/profile/${encodeURIComponent(p.username)}" class="text-decoration-none">
              <div class="avatar-ring" style="width: 44px; height: 44px; font-size: 1.3rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                <span>${avatar}</span>
              </div>
            </a>
            <div class="overflow-hidden">
              <div class="fw-bold text-light text-truncate d-flex align-items-center">
                <a href="/profile/${encodeURIComponent(p.username)}" class="text-light text-decoration-none hover-underline text-truncate">
                  ${p.display_name || p.username}
                </a>
                ${followBadge}
              </div>
              <small class="text-secondary text-truncate d-block">@${p.username}</small>
            </div>
          </div>
          <div>
            ${actionBtn}
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (pagEl) {
    if (challengeState.searchTotalPages > 1) {
      pagEl.style.display = 'flex';
      const infoEl = document.getElementById('chPlayersPageInfo');
      const prevBtn = document.getElementById('chPlayersPrevBtn');
      const nextBtn = document.getElementById('chPlayersNextBtn');
      if (infoEl) infoEl.textContent = `Page ${challengeState.searchPage} of ${challengeState.searchTotalPages}`;
      if (prevBtn) prevBtn.disabled = challengeState.searchPage <= 1;
      if (nextBtn) nextBtn.disabled = challengeState.searchPage >= challengeState.searchTotalPages;
    } else {
      pagEl.style.display = 'none';
    }
  }
}

// Search Handler
function searchPlayers(query) {
  challengeState.searchQuery = (query || '').trim();
  challengeState.searchPage = 1;
  const clearBtn = document.getElementById('chPlayerSearchClear');
  if (clearBtn) {
    clearBtn.style.display = challengeState.searchQuery ? 'inline-block' : 'none';
  }
  loadPlayerDiscovery(1);
}

function clearPlayerSearch() {
  const input = document.getElementById('chPlayerSearchInput');
  if (input) input.value = '';
  searchPlayers('');
}

function changePlayerSearchPage(delta) {
  const newPage = challengeState.searchPage + delta;
  if (newPage >= 1 && newPage <= challengeState.searchTotalPages) {
    loadPlayerDiscovery(newPage);
  }
}

// Challenge Builder Stepper & Modal
function openChallengeBuilder(player) {
  challengeState.builder.opponent = player;
  challengeState.builder.step = 1;
  challengeState.builder.type = 'DISTANCE';
  challengeState.builder.durationDays = 7;
  challengeState.builder.title = '';
  challengeState.builder.message = '';

  const today = new Date();
  challengeState.builder.startDate = formatLocalISODate(today);
  challengeState.builder.endDate = formatLocalISODate(addDays(today, 6)); // 7 days inclusive

  const nameHeader = document.getElementById('cbOpponentNameHeader');
  if (nameHeader) {
    nameHeader.textContent = player.display_name || player.username;
  }

  const titleInput = document.getElementById('cbTitle');
  if (titleInput) titleInput.value = '';
  const msgInput = document.getElementById('cbMessage');
  if (msgInput) msgInput.value = '';

  const startInput = document.getElementById('cbStartDate');
  const endInput = document.getElementById('cbEndDate');
  if (startInput) startInput.value = challengeState.builder.startDate;
  if (endInput) endInput.value = challengeState.builder.endDate;

  const dailyInput = document.getElementById('cbDailyDate');
  if (dailyInput) dailyInput.value = challengeState.builder.startDate;

  const errAlert = document.getElementById('cbErrorAlert');
  if (errAlert) errAlert.style.display = 'none';

  selectChallengeType('DISTANCE');
  applyDurationPreset(7);

  updateBuilderStepView();

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeBuilderModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }
}

// Select Challenge Type
function selectChallengeType(type, element) {
  challengeState.builder.type = type;

  document.querySelectorAll('.cb-type-card').forEach(card => {
    const cardType = (card.dataset && card.dataset.type) || (card.getAttribute && card.getAttribute('data-type'));
    if (cardType === type) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  });

  const rangeControls = document.getElementById('cbRangeControls');
  const dailyControls = document.getElementById('cbDailyControls');

  if (type === 'DAILY') {
    if (rangeControls) rangeControls.style.display = 'none';
    if (dailyControls) dailyControls.style.display = 'block';
  } else {
    if (rangeControls) rangeControls.style.display = 'block';
    if (dailyControls) dailyControls.style.display = 'none';
  }
}

// Duration Presets
function applyDurationPreset(preset, element) {
  document.querySelectorAll('.cb-preset-btn').forEach(btn => {
    const btnPreset = (btn.dataset && btn.dataset.preset) || (btn.getAttribute && btn.getAttribute('data-preset'));
    if (btnPreset === String(preset)) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  if (preset === 'custom') {
    return;
  }

  const days = parseInt(preset, 10);
  if (!isNaN(days)) {
    challengeState.builder.durationDays = days;
    const today = new Date();
    const startStr = formatLocalISODate(today);
    const endStr = formatLocalISODate(addDays(today, days - 1));

    challengeState.builder.startDate = startStr;
    challengeState.builder.endDate = endStr;

    const startInput = document.getElementById('cbStartDate');
    const endInput = document.getElementById('cbEndDate');
    if (startInput) startInput.value = startStr;
    if (endInput) endInput.value = endStr;
  }
}

function onDateInputChange() {
  const startInput = document.getElementById('cbStartDate');
  const endInput = document.getElementById('cbEndDate');
  if (startInput && endInput) {
    challengeState.builder.startDate = startInput.value;
    challengeState.builder.endDate = endInput.value;
  }
  document.querySelectorAll('.cb-preset-btn').forEach(btn => btn.classList.remove('active'));
  const customBtn = document.querySelector('.cb-preset-btn[data-preset="custom"]');
  if (customBtn) customBtn.classList.add('active');
}

function onDailyDateInputChange() {
  const dailyInput = document.getElementById('cbDailyDate');
  if (dailyInput) {
    challengeState.builder.startDate = dailyInput.value;
    challengeState.builder.endDate = dailyInput.value;
  }
}

// Stepper Navigation
function navigateChallengeStep(delta) {
  const current = challengeState.builder.step;
  const target = current + delta;

  const errAlert = document.getElementById('cbErrorAlert');
  if (errAlert) errAlert.style.display = 'none';

  if (delta > 0) {
    if (current === 1) {
      if (!challengeState.builder.type) {
        showBuilderError('Please select a challenge type to continue.');
        return;
      }
    } else if (current === 2) {
      const b = challengeState.builder;
      const titleInput = document.getElementById('cbTitle');
      const msgInput = document.getElementById('cbMessage');
      if (titleInput) b.title = titleInput.value.trim();
      if (msgInput) b.message = msgInput.value.trim();

      if (b.type === 'DAILY') {
        const dailyInput = document.getElementById('cbDailyDate');
        const dVal = dailyInput ? dailyInput.value : b.startDate;
        if (!dVal) {
          showBuilderError('Please select a calendar date for the showdown.');
          return;
        }
        b.startDate = dVal;
        b.endDate = dVal;
      } else {
        const sInput = document.getElementById('cbStartDate');
        const eInput = document.getElementById('cbEndDate');
        const sVal = sInput ? sInput.value : b.startDate;
        const eVal = eInput ? eInput.value : b.endDate;

        if (!sVal || !eVal) {
          showBuilderError('Please select both a start date and an end date.');
          return;
        }
        if (sVal > eVal) {
          showBuilderError('Start date cannot be after end date.');
          return;
        }
        b.startDate = sVal;
        b.endDate = eVal;
      }
    }
  }

  if (target >= 1 && target <= 3) {
    challengeState.builder.step = target;
    updateBuilderStepView();
  }
}

function showBuilderError(msg) {
  const errAlert = document.getElementById('cbErrorAlert');
  if (errAlert) {
    errAlert.textContent = msg;
    errAlert.style.display = 'block';
  } else {
    alert(msg);
  }
}

// Update Modal Views for Active Step
function updateBuilderStepView() {
  const step = challengeState.builder.step;
  const b = challengeState.builder;

  const stepCounter = document.getElementById('cbStepCounter');
  if (stepCounter) stepCounter.textContent = `Step ${step} of 3`;

  const progressBar = document.getElementById('cbProgressBar');
  if (progressBar) {
    progressBar.style.width = step === 1 ? '33.3%' : step === 2 ? '66.6%' : '100%';
  }

  ['cbStep1', 'cbStep2', 'cbStep3'].forEach((paneId, idx) => {
    const pane = document.getElementById(paneId);
    if (pane) {
      pane.style.display = (idx + 1 === step) ? 'block' : 'none';
    }
  });

  const prevBtn = document.getElementById('cbPrevBtn');
  const nextBtn = document.getElementById('cbNextBtn');
  const submitBtn = document.getElementById('cbSubmitBtn');

  if (prevBtn) prevBtn.style.display = step > 1 ? 'inline-block' : 'none';
  if (nextBtn) nextBtn.style.display = step < 3 ? 'inline-block' : 'none';
  if (submitBtn) submitBtn.style.display = step === 3 ? 'inline-block' : 'none';

  if (step === 3 && b.opponent) {
    const opp = b.opponent;
    const typeInfo = CHALLENGE_TYPE_INFO[b.type] || { name: b.type, rule: '' };

    const setEl = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };

    setEl('cbPreviewOpponentName', opp.display_name || opp.username);
    setEl('cbPreviewOpponentHandle', `@${opp.username}`);
    setEl('cbPreviewEmoji', opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase());
    setEl('cbPreviewType', b.title ? `${b.title} (${typeInfo.name})` : typeInfo.name);
    setEl('cbPreviewWinningRule', typeInfo.rule);

    const datesLabel = formatFriendlyDateRange(b.startDate, b.endDate, b.type === 'DAILY');
    setEl('cbPreviewDates', datesLabel);

    const msgBlock = document.getElementById('cbPreviewMessageBlock');
    const msgEl = document.getElementById('cbPreviewMessage');
    if (b.message) {
      if (msgBlock) msgBlock.style.display = 'block';
      if (msgEl) msgEl.textContent = `"${b.message}"`;
    } else {
      if (msgBlock) msgBlock.style.display = 'none';
    }
  }
}

// Submit Challenge Creation
async function submitChallengeForm() {
  const b = challengeState.builder;
  if (!b.opponent) return;

  const submitBtn = document.getElementById('cbSubmitBtn');
  const submitSpinner = document.getElementById('cbSubmitSpinner');
  const submitText = document.getElementById('cbSubmitText');
  const errAlert = document.getElementById('cbErrorAlert');

  if (errAlert) errAlert.style.display = 'none';
  if (submitBtn) submitBtn.disabled = true;
  if (submitSpinner) submitSpinner.style.display = 'inline-block';
  if (submitText) submitText.textContent = 'Sending...';

  try {
    const payload = {
      opponent_id: b.opponent.id,
      challenge_type: b.type,
      start_date: b.startDate,
      end_date: b.endDate,
      title: b.title || undefined,
      message: b.message || undefined,
      challenge_timezone: b.timezone
    };

    const res = await fetch('/api/challenges', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || data.error || 'Failed to create challenge');
    }

    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
      const modalEl = document.getElementById('challengeBuilderModal');
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
    }

    if (typeof showToast === 'function') {
      showToast('⚔️ Challenge invitation sent!', 'success');
    } else {
      alert('⚔️ Challenge invitation sent successfully!');
    }

    loadChallengeStats();
    loadPlayerDiscovery(challengeState.searchPage);
    loadInvitations();

  } catch (err) {
    console.error('Error submitting challenge:', err);
    showBuilderError(err.message || 'An error occurred while creating the challenge.');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (submitSpinner) submitSpinner.style.display = 'none';
    if (submitText) submitText.textContent = '⚔️ Send Challenge';
  }
}

// ============================================================================
// Challenges V1 Update Announcement Modal
// ============================================================================

function getChallengesStorage() {
  try {
    if (typeof localStorage !== 'undefined') return localStorage;
    if (typeof window !== 'undefined' && window.localStorage) return window.localStorage;
  } catch (e) {}
  return null;
}

function getChallengesUpdateStorageKey() {
  let user = 'default';
  if (typeof OWN_USERNAME !== 'undefined' && OWN_USERNAME) {
    user = OWN_USERNAME;
  } else if (typeof window !== 'undefined' && window.OWN_USERNAME) {
    user = window.OWN_USERNAME;
  }
  return `runrush_challenges_v1_announced_${user}`;
}

function checkChallengesUpdateAnnouncementPopup() {
  try {
    const storage = getChallengesStorage();
    if (!storage) return;
    const storageKey = getChallengesUpdateStorageKey();
    const hasSeen = storage.getItem(storageKey);
    if (hasSeen === 'true') return;

    const modalEl = document.getElementById('challengesUpdateAnnouncementModal');
    if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) return;

    // Check if an invitation modal is currently open to avoid collision
    const invModalEl = document.getElementById('challengeInvitationPopupModal');
    const isInvModalOpen = invModalEl && invModalEl.classList && typeof invModalEl.classList.contains === 'function'
      ? invModalEl.classList.contains('show')
      : false;
    if (isInvModalOpen) return;

    setTimeout(() => {
      try {
        if (storage.getItem(storageKey) === 'true') return;
        const stillInvOpen = invModalEl && invModalEl.classList && typeof invModalEl.classList.contains === 'function'
          ? invModalEl.classList.contains('show')
          : false;
        if (stillInvOpen) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      } catch (e) {
        console.warn('Could not display update modal:', e);
      }
    }, 700);
  } catch (err) {
    console.warn('Error checking challenges update announcement popup:', err);
  }
}

function dismissChallengesUpdateModal() {
  try {
    const storage = getChallengesStorage();
    if (storage) {
      const storageKey = getChallengesUpdateStorageKey();
      storage.setItem(storageKey, 'true');
    }
  } catch (err) {
    console.warn('Error saving update announcement state:', err);
  }
  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengesUpdateAnnouncementModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
  }
}

function exploreChallengesFromUpdateModal() {
  dismissChallengesUpdateModal();
  if (typeof switchTab === 'function') {
    const tabEl = document.querySelector('.tab-nav-item[data-tab="challenges"]');
    switchTab('challenges', tabEl);
  } else if (typeof switchChallengeTab === 'function') {
    switchChallengeTab('discover');
  }
}

// Initialization
function initChallengesTab() {
  loadChallengeStats();
  switchChallengeTab(challengeState.currentTab);
  loadInvitations(true);
  checkChallengesUpdateAnnouncementPopup();

  const searchInput = document.getElementById('chPlayerSearchInput');
  if (searchInput && !(searchInput.dataset && searchInput.dataset.initialized)) {
    if (!searchInput.dataset) searchInput.dataset = {};
    searchInput.dataset.initialized = 'true';
    if (typeof searchInput.addEventListener === 'function') {
      searchInput.addEventListener('input', (e) => {
        if (challengeState.searchDebounceTimer) {
          clearTimeout(challengeState.searchDebounceTimer);
        }
        challengeState.searchDebounceTimer = setTimeout(() => {
          searchPlayers(e.target ? e.target.value : searchInput.value);
        }, 350);
      });
    }
  }

  if (typeof window !== 'undefined' && window.location && window.location.search) {
    const params = new URLSearchParams(window.location.search);
    const targetUser = params.get('challenge');
    if (targetUser) {
      fetch(`/api/challenges/players?q=${encodeURIComponent(targetUser)}`)
        .then(r => r.json())
        .then(data => {
          if (data.status === 'success' && data.players && data.players.length > 0) {
            const match = data.players.find(p => p.username.toLowerCase() === targetUser.toLowerCase()) || data.players[0];
            if (match && !match.has_pending_challenge) {
              openChallengeBuilder(match);
            }
          }
        })
        .catch(e => console.warn('Could not auto-open challenge modal:', e));
    }
  }
}

// Global Exports
if (typeof window !== 'undefined') {
  window.challengeState = challengeState;
  window.switchChallengeTab = switchChallengeTab;
  window.loadChallengeStats = loadChallengeStats;
  window.loadPlayerDiscovery = loadPlayerDiscovery;
  window.renderPlayerDiscovery = renderPlayerDiscovery;
  window.searchPlayers = searchPlayers;
  window.clearPlayerSearch = clearPlayerSearch;
  window.changePlayerSearchPage = changePlayerSearchPage;
  window.openChallengeBuilder = openChallengeBuilder;
  window.selectChallengeType = selectChallengeType;
  window.applyDurationPreset = applyDurationPreset;
  window.onDateInputChange = onDateInputChange;
  window.onDailyDateInputChange = onDailyDateInputChange;
  window.navigateChallengeStep = navigateChallengeStep;
  window.submitChallengeForm = submitChallengeForm;
  window.initChallengesTab = initChallengesTab;

  // Phase 3 Exports
  window.loadInvitations = loadInvitations;
  window.renderInvitations = renderInvitations;
  window.acceptInvitation = acceptInvitation;
  window.rejectInvitation = rejectInvitation;
  window.cancelInvitation = cancelInvitation;
  window.viewChallengeDetails = viewChallengeDetails;
  window.checkAndShowInvitationPopup = checkAndShowInvitationPopup;
  window.renderPopupCurrentInvitation = renderPopupCurrentInvitation;
  window.navigatePopupInvitation = navigatePopupInvitation;
  window.dismissInvitationPopup = dismissInvitationPopup;
  window.respondToPopupInvitation = respondToPopupInvitation;

  // Phase 4 Exports
  window.loadOngoingChallenges = loadOngoingChallenges;
  window.renderOngoingChallenges = renderOngoingChallenges;
  window.openChallengeProgress = openChallengeProgress;
  window.loadChallengeHistory = loadChallengeHistory;
  window.renderChallengeHistory = renderChallengeHistory;
  window.filterChallengeHistory = filterChallengeHistory;
  window.changeHistoryPage = changeHistoryPage;

  // Update Announcement Modal Exports
  window.getChallengesUpdateStorageKey = getChallengesUpdateStorageKey;
  window.checkChallengesUpdateAnnouncementPopup = checkChallengesUpdateAnnouncementPopup;
  window.dismissChallengesUpdateModal = dismissChallengesUpdateModal;
  window.exploreChallengesFromUpdateModal = exploreChallengesFromUpdateModal;
}

// Auto-run if DOM already loaded
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (document.getElementById('challengesView')) {
        initChallengesTab();
      } else if (document.getElementById('challengesUpdateAnnouncementModal')) {
        checkChallengesUpdateAnnouncementPopup();
      }
    });
  } else {
    if (document.getElementById('challengesView')) {
      initChallengesTab();
    } else if (document.getElementById('challengesUpdateAnnouncementModal')) {
      checkChallengesUpdateAnnouncementPopup();
    }
  }
}
