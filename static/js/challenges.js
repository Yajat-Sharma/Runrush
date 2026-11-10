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
  ongoingFormatFilter: 'all',
  invitationsFormatFilter: 'all',
  historyFormatFilter: 'all',

  // Builder State
  builder: {
    mode: '1V1',
    opponent: null,
    selectedOpponents: [],
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

// Filter Ongoing by Format (All, 1v1, Group)
function filterOngoingFormat(format, btnEl) {
  challengeState.ongoingFormatFilter = format;
  const container = document.getElementById('chPaneOngoing');
  const btns = (container && typeof container.querySelectorAll === 'function')
    ? container.querySelectorAll('.cb-format-filter-btn')
    : (typeof document !== 'undefined' && document.querySelectorAll ? document.querySelectorAll('#chPaneOngoing .cb-format-filter-btn') : []);
  if (btns && typeof btns.forEach === 'function') {
    btns.forEach(btn => {
      if (btn && btn.classList && typeof btn.classList.toggle === 'function') {
        const isMatch = (btn === btnEl || (btn.dataset && btn.dataset.format === format) || (typeof btn.getAttribute === 'function' && btn.getAttribute('data-format') === format));
        btn.classList.toggle('active', isMatch);
      }
    });
  }
  renderOngoingChallenges(challengeState.ongoing);
}

// Render Ongoing Challenge Cards
function renderOngoingChallenges(challenges) {
  const listEl = document.getElementById('chOngoingList');
  if (!listEl) return;

  const fmt = challengeState.ongoingFormatFilter || 'all';
  let filtered = challenges || [];
  if (fmt === '1v1') {
    filtered = filtered.filter(c => c.challenge_mode !== 'GROUP');
  } else if (fmt === 'group') {
    filtered = filtered.filter(c => c.challenge_mode === 'GROUP');
  }

  if (filtered.length === 0) {
    const emptyMsg = fmt === 'group'
      ? 'No active group showdowns. Create one by clicking "Group Challenge" above!'
      : (fmt === '1v1' ? 'No active 1v1 duels. Challenge a runner from Discover Players!' : 'No ongoing challenges. Accept an incoming invitation or start a new challenge!');
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">${fmt === 'group' ? '👥' : '⚔️'}</div>
        <div class="fw-semibold text-light">${fmt === 'group' ? 'No ongoing group showdowns' : (fmt === '1v1' ? 'No ongoing 1v1 duels' : 'No ongoing challenges')}</div>
        <div class="small mt-1">${emptyMsg}</div>
        <div class="d-flex gap-2 justify-content-center mt-3">
          <button class="btn btn-sm rr-btn-primary px-3 py-1.5" onclick="openChallengeBuilder(null, 'GROUP')">
            <span>👥</span> New Group Showdown
          </button>
          <button class="btn btn-sm btn-glass px-3 py-1.5" onclick="switchChallengeTab('discover')">
            <span>⚔️</span> Find Opponents
          </button>
        </div>
      </div>
    `;
    return;
  }

  let html = '<div class="row g-3">';

  filtered.forEach(c => {
    const isGroup = (c.challenge_mode === 'GROUP');
    const typeInfo = CHALLENGE_TYPE_INFO[c.challenge_type] || { name: c.challenge_type, icon: '⚔️' };
    const datesLabel = formatFriendlyDateRange(c.start_date, c.end_date, c.challenge_type === 'DAILY');
    const opp = c.opponent || {};

    const statusPill = c.display_status === 'SCHEDULED'
      ? `<span class="badge bg-secondary-subtle text-secondary small" style="font-size:0.68rem;">SCHEDULED</span>`
      : `<span class="badge" style="background: rgba(0, 242, 255, 0.15); color: var(--accent); font-size:0.68rem; font-weight:700;">ACTIVE</span>`;

    if (isGroup) {
      const modePill = `<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size:0.68rem; font-weight:700;">GROUP (${c.total_participants || (c.leaderboard ? c.leaderboard.length : 3)} RUNNERS)</span>`;
      let leaderBadgeHtml = '';
      if (c.leader === 'you') {
        leaderBadgeHtml = `<span class="cb-leader-pill leading"><i class="fa-solid fa-crown me-1"></i> Leading Pack</span>`;
      } else if (c.is_tied) {
        leaderBadgeHtml = `<span class="cb-leader-pill tied"><i class="fa-solid fa-handshake me-1"></i> Tied for #1</span>`;
      } else {
        leaderBadgeHtml = `<span class="cb-leader-pill trailing"><i class="fa-solid fa-arrow-down me-1"></i> Trailing leader by ${c.score_diff} ${c.score_unit}</span>`;
      }

      const topRunners = (c.leaderboard || []).slice(0, 3);
      const podiumHtml = topRunners.map(p => {
        const medal = p.rank === 1 ? '🥇' : p.rank === 2 ? '🥈' : p.rank === 3 ? '🥉' : `#${p.rank}`;
        const emoji = p.profile_emoji || (p.display_name || p.username || 'U')[0].toUpperCase();
        return `
          <div class="d-flex align-items-center justify-content-between py-1 px-2 rounded-2 mb-1" style="background: rgba(255,255,255,0.03); font-size: 0.76rem;">
            <div class="d-flex align-items-center gap-1.5 overflow-hidden">
              <span>${medal}</span>
              <span class="avatar-ring" style="width: 18px; height: 18px; font-size: 0.65rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                <span>${emoji}</span>
              </span>
              <span class="text-truncate fw-semibold text-light" style="max-width: 110px;">${p.display_name || p.username}</span>
            </div>
            <div class="fw-bold text-light">${p.display_score} <small class="text-secondary">${c.score_unit}</small></div>
          </div>
        `;
      }).join('');

      html += `
        <div class="col-12 col-lg-6">
          <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 20px; border: 1px solid rgba(234, 179, 8, 0.25) !important;">
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
                <div class="text-end d-flex flex-column align-items-end gap-1">
                  <div class="d-flex gap-1">${modePill} ${statusPill}</div>
                  <div class="small text-secondary" style="font-size: 0.72rem;">${c.time_remaining || ''}</div>
                </div>
              </div>

              <!-- Your Standing Card -->
              <div class="p-2.5 rounded-3 mb-2.5 d-flex justify-content-between align-items-center" style="background: rgba(0, 242, 255, 0.06); border: 1px solid rgba(0, 242, 255, 0.2);">
                <div>
                  <div class="text-secondary small fw-semibold" style="font-size: 0.72rem;">YOUR STANDING</div>
                  <div class="fw-bold fs-4 text-light mt-0.5">Rank #${c.my_rank || '-'} <small class="fs-6 text-secondary">(${c.my_score} ${c.score_unit})</small></div>
                </div>
                <div>
                  ${leaderBadgeHtml}
                </div>
              </div>

              <!-- Top Leaders Snapshot -->
              <div class="mb-2">
                <div class="text-secondary mb-1.5 fw-semibold" style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px;">Current Leaders</div>
                ${podiumHtml}
              </div>
            </div>

            <!-- Card Actions -->
            <div class="pt-3 mt-2 border-top border-secondary-subtle">
              <button class="btn btn-sm btn-glass w-100 py-1.5 d-flex align-items-center justify-content-center gap-1.5" onclick="openChallengeProgress(${c.id})">
                <i class="fa-solid fa-list-ol"></i> View Full Leaderboard & Breakdown
              </button>
            </div>
          </div>
        </div>
      `;
    } else {
      let leaderBadgeHtml = '';
      if (c.leader === 'you') {
        leaderBadgeHtml = `<span class="cb-leader-pill leading"><i class="fa-solid fa-crown me-1"></i> Leading by ${c.score_diff} ${c.score_unit}</span>`;
      } else if (c.leader === 'opponent') {
        leaderBadgeHtml = `<span class="cb-leader-pill trailing"><i class="fa-solid fa-arrow-down me-1"></i> Trailing by ${c.score_diff} ${c.score_unit}</span>`;
      } else {
        leaderBadgeHtml = `<span class="cb-leader-pill tied"><i class="fa-solid fa-handshake me-1"></i> Tied</span>`;
      }

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
                  <span style="color: #f59e0b; font-weight: 600;">${opp.display_name || 'Opponent'}: ${c.opponent_ratio}%</span>
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
    }
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
        const isGroupDraw = (chal.challenge_mode === 'GROUP');
        completionBanner = `
          <div class="p-2.5 rounded-3 mb-3 d-flex align-items-center gap-2" style="background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.35);">
            <span style="font-size: 1.25rem;">🤝</span>
            <div>
              <div class="fw-bold text-light small">Final Result: Draw / Tie</div>
              <div class="text-warning small" style="font-size: 0.72rem;">
                ${isGroupDraw ? 'Tied for 1st place! Friendly Challenges victory medals are awarded only to unique 1st place winners.' : 'Both runners achieved equal scores. No medal awarded.'}
              </div>
            </div>
          </div>
        `;
      } else if (chal.winner_id) {
        let winnerName = 'Leader';
        if (chal.challenge_mode === 'GROUP' && p.leaderboard) {
          const topOne = p.leaderboard.find(x => x.user_id === chal.winner_id);
          winnerName = topOne ? topOne.display_name : 'Winner';
        } else {
          winnerName = chal.winner_id === (c && c.user_id) ? c.display_name : (o && o.display_name);
        }
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
      if (p.challenge_mode === 'GROUP') {
        // --- Group Showdown Detailed Modal View ---
        const leaderboard = p.leaderboard || [];
        const tableRows = leaderboard.map(runner => {
          const rankBadge = runner.rank === 1
            ? '<span class="cb-rank-badge rank-1">🥇</span>'
            : runner.rank === 2
            ? '<span class="cb-rank-badge rank-2">🥈</span>'
            : runner.rank === 3
            ? '<span class="cb-rank-badge rank-3">🥉</span>'
            : `<span class="cb-rank-badge rank-other">#${runner.rank || '-'}</span>`;

          const isMe = (p.current_user_id && runner.user_id === p.current_user_id);
          const emoji = runner.profile_emoji || (runner.display_name || runner.username || 'U')[0].toUpperCase();
          const runsCount = (runner.qualifying_runs || []).length;
          const statusText = runner.invitation_status !== 'ACCEPTED'
            ? `<span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.65rem;">${runner.invitation_status}</span>`
            : `<span class="text-secondary small">${runsCount} run${runsCount === 1 ? '' : 's'}</span>`;

          return `
            <tr class="${isMe ? 'current-user' : ''}">
              <td class="text-center" style="width: 44px;">${rankBadge}</td>
              <td>
                <div class="d-flex align-items-center gap-2">
                  <span class="avatar-ring" style="width: 24px; height: 24px; font-size: 0.75rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                    <span>${emoji}</span>
                  </span>
                  <div class="overflow-hidden">
                    <div class="fw-semibold text-light text-truncate" style="max-width: 140px;">
                      ${runner.display_name} ${isMe ? '<span class="badge ms-1" style="background: rgba(0, 242, 255, 0.15); color: var(--accent); font-size: 0.65rem;">You</span>' : ''}
                    </div>
                    <small class="text-secondary" style="font-size: 0.68rem;">@${runner.username}</small>
                  </div>
                </div>
              </td>
              <td class="text-end fw-bold text-light">${runner.display_score} <small class="text-secondary">${unit}</small></td>
              <td class="text-end" style="color: var(--accent); font-weight: 600;">${runner.ratio || 0}%</td>
              <td class="text-center">${statusText}</td>
            </tr>
          `;
        }).join('');

        const runsAccordion = leaderboard.map((runner, rIdx) => {
          const runs = runner.qualifying_runs || [];
          const isMe = (p.current_user_id && runner.user_id === p.current_user_id);
          const collapseId = `cpmRunsCollapse_${runner.user_id}_${rIdx}`;
          const runItems = runs.length === 0
            ? `<div class="text-secondary small fst-italic py-2 px-2">No qualifying runs recorded yet.</div>`
            : runs.map(r => `
              <div class="cb-run-item">
                <div>
                  <div class="fw-semibold text-light small">${r.distance_km} km</div>
                  <div class="text-secondary" style="font-size: 0.7rem;">${r.local_date || r.date} • ${r.run_type || 'Run'}</div>
                </div>
                <div class="text-end text-secondary small" style="font-size: 0.72rem;">
                  <div>${r.time_min ? `${Math.round(r.time_min)} min` : ''}</div>
                  <div style="font-size: 0.68rem; opacity: 0.8;">${r.pace ? `${r.pace.toFixed(2)} min/km` : ''}</div>
                </div>
              </div>
            `).join('');

          return `
            <div class="mb-2 rounded-3 overflow-hidden" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-subtle);">
              <div class="p-2.5 d-flex align-items-center justify-content-between cursor-pointer" onclick="toggleRunBreakdown('${collapseId}')" style="cursor: pointer;">
                <div class="d-flex align-items-center gap-2">
                  <span class="avatar-ring" style="width: 22px; height: 22px; font-size: 0.7rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                    ${runner.profile_emoji || '🏃'}
                  </span>
                  <span class="fw-semibold text-light small">${runner.display_name} ${isMe ? '<span class="badge" style="background: rgba(0, 242, 255, 0.15); color: var(--accent); font-size: 0.65rem;">You</span>' : ''}</span>
                  <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.65rem;">${runs.length} run${runs.length === 1 ? '' : 's'}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <span class="fw-bold text-light small">${runner.display_score} <small class="text-secondary">${unit}</small></span>
                  <i class="fa-solid fa-chevron-down text-secondary small transition-all" id="${collapseId}_icon" style="transition: transform 0.2s;"></i>
                </div>
              </div>
              <div id="${collapseId}" class="px-2.5 pb-2.5" style="display: ${rIdx === 0 || isMe ? 'block' : 'none'};">
                <div class="pt-2 border-top border-secondary-subtle">
                  ${runItems}
                </div>
              </div>
            </div>
          `;
        }).join('');

        bodyEl.innerHTML = `
          ${completionBanner}
          <div class="glass p-3 mb-3" style="border-radius: 16px;">
            <div class="d-flex align-items-center justify-content-between mb-2">
              <span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-weight: 700;">FREE-FOR-ALL SHOWDOWN</span>
              <span class="text-light small fw-bold">${datesLabel} (${chal.challenge_timezone || 'UTC'})</span>
            </div>
            <div class="text-secondary small mb-3">
              <i class="fa-solid fa-circle-info me-1" style="color: var(--accent);"></i> ${typeInfo.rule}
            </div>

            <!-- Group Leaderboard Table -->
            <div class="table-responsive mb-2">
              <table class="cb-group-table">
                <thead>
                  <tr>
                    <th class="text-center">Rank</th>
                    <th>Runner</th>
                    <th class="text-end">Score</th>
                    <th class="text-end">Share %</th>
                    <th class="text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${tableRows}
                </tbody>
              </table>
            </div>

            <div class="alert alert-info py-2 px-3 small border-0 d-flex align-items-center gap-2 mb-0" style="background: rgba(0, 242, 255, 0.08); color: var(--accent); border-radius: 12px; font-size: 0.75rem;">
              <i class="fa-solid fa-medal"></i>
              <span><strong>Victory Medal:</strong> Sole 1st place winner receives 1 Friendly Challenges medal upon completion. Ties resolve into draws with no medal awarded.</span>
            </div>
          </div>

          <!-- Qualifying Runs by Runner -->
          <div class="glass p-3 mb-3" style="border-radius: 16px;">
            <h6 class="fw-bold text-light small mb-2.5">Qualifying Runs Breakdown</h6>
            ${runsAccordion}
          </div>

          ${activityHtml ? `
            <div class="glass p-3" style="border-radius: 16px;">
              <h6 class="fw-bold text-light small mb-2">Challenge Activity</h6>
              ${activityHtml}
            </div>
          ` : ''}
        `;
      } else {
        // --- 1v1 Duel Detailed Modal View ---
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
                    ${c ? c.profile_emoji : '🏃'}
                  </span>
                  <span class="fw-bold text-light small text-truncate" style="max-width: 100px;">${c ? c.display_name : 'You'}</span>
                </div>
                <div class="fs-4 fw-bold" style="color: var(--accent);">${c ? c.display_score : 0} <small class="fs-6 text-secondary">${unit}</small></div>
              </div>

              <div class="col-2">
                <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.65rem;">VS</span>
              </div>

              <div class="col-5">
                <div class="d-flex align-items-center justify-content-center gap-1.5 mb-1">
                  <span class="avatar-ring" style="width: 24px; height: 24px; font-size: 0.8rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                    ${o ? o.profile_emoji : '🏃'}
                  </span>
                  <span class="fw-bold text-light small text-truncate" style="max-width: 100px;">${o ? o.display_name : 'Opponent'}</span>
                </div>
                <div class="fs-4 fw-bold" style="color: #f59e0b;">${o ? o.display_score : 0} <small class="fs-6 text-secondary">${unit}</small></div>
              </div>
            </div>

            <!-- Relative Share Comparison Bar -->
            <div class="mt-3">
              <div class="cb-ratio-track mb-1.5">
                <div class="cb-ratio-fill-my" style="width: ${p.ratio_challenger || 0}%;"></div>
                <div class="cb-ratio-fill-opp" style="width: ${p.ratio_opponent || 0}%;"></div>
              </div>
              <div class="d-flex justify-content-between text-secondary" style="font-size: 0.72rem;">
                <span style="color: var(--accent); font-weight: 600;">${c ? c.display_name : 'You'}: ${p.ratio_challenger || 0}%</span>
                <span class="fw-bold text-light">${leaderText}</span>
                <span style="color: #f59e0b; font-weight: 600;">${o ? o.display_name : 'Opponent'}: ${p.ratio_opponent || 0}%</span>
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
                  <span style="color: var(--accent);">•</span> ${c ? c.display_name : 'You'}'s Runs (${c ? c.qualifying_runs.length : 0})
                </h6>
                ${renderRunList(c ? c.qualifying_runs : [], c ? c.display_name : 'You')}
              </div>
            </div>
            <div class="col-12 col-md-6">
              <div class="glass p-3 h-100" style="border-radius: 16px;">
                <h6 class="fw-bold text-light small mb-2 d-flex align-items-center gap-1.5">
                  <span style="color: #f59e0b;">•</span> ${o ? o.display_name : 'Opponent'}'s Runs (${o ? o.qualifying_runs.length : 0})
                </h6>
                ${renderRunList(o ? o.qualifying_runs : [], o ? o.display_name : 'Opponent')}
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
    }

  } catch (err) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div class="text-danger small py-4 text-center">${err.message}</div>`;
    }
  }
}

// Toggle Participant Run Breakdown in Progress Modal
function toggleRunBreakdown(collapseId) {
  const el = document.getElementById(collapseId);
  const icon = document.getElementById(collapseId + '_icon');
  if (!el) return;
  const isHidden = (el.style.display === 'none');
  el.style.display = isHidden ? 'block' : 'none';
  if (icon) {
    icon.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
  }
}

// ============================================================================
// Phase 4: CHALLENGE HISTORY & FILTERING
// ============================================================================

// Filter Challenge History by Format (All, 1v1, Group)
function filterHistoryFormat(format, btnEl) {
  challengeState.historyFormatFilter = format;
  const container = document.getElementById('chPaneHistory');
  const btns = (container && typeof container.querySelectorAll === 'function')
    ? container.querySelectorAll('.cb-history-format-btn')
    : (typeof document !== 'undefined' && document.querySelectorAll ? document.querySelectorAll('#chPaneHistory .cb-history-format-btn') : []);
  if (btns && typeof btns.forEach === 'function') {
    btns.forEach(btn => {
      if (btn && btn.classList && typeof btn.classList.toggle === 'function') {
        const isMatch = (btn === btnEl || (btn.dataset && btn.dataset.format === format) || (typeof btn.getAttribute === 'function' && btn.getAttribute('data-format') === format));
        btn.classList.toggle('active', isMatch);
      }
    });
  }
  loadChallengeHistory(1);
}

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
      filter: challengeState.historyFilter || 'all',
      format: challengeState.historyFormatFilter || 'all'
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

  const fmt = challengeState.historyFormatFilter || 'all';
  let filtered = challenges || [];
  if (fmt === '1v1') {
    filtered = filtered.filter(h => h.challenge_mode !== 'GROUP');
  } else if (fmt === 'group') {
    filtered = filtered.filter(h => h.challenge_mode === 'GROUP');
  }

  if (filtered.length === 0) {
    const emptyMsg = fmt === 'group'
      ? 'No group showdown history found.'
      : (fmt === '1v1' ? 'No 1v1 duel history found.' : 'No challenge history found.');
    listEl.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">📜</div>
        <div class="fw-semibold text-light">${emptyMsg}</div>
        <div class="small mt-1">Completed, declined, and expired challenges will appear here.</div>
      </div>
    `;
    if (pagEl) pagEl.style.display = 'none';
    return;
  }

  let html = '';

  filtered.forEach(h => {
    const typeInfo = CHALLENGE_TYPE_INFO[h.challenge_type] || { name: h.challenge_type, icon: '⚔️' };
    const datesLabel = formatFriendlyDateRange(h.start_date, h.end_date, h.challenge_type === 'DAILY');
    const opp = h.opponent || {};

    const isGroup = (h.challenge_mode === 'GROUP');
    let outcomeBadge = '';
    if (h.outcome === 'WIN') {
      outcomeBadge = isGroup
        ? `<span class="badge bg-success" style="font-weight: 700;">1ST PLACE 🏆</span>`
        : `<span class="badge bg-success" style="font-weight: 700;">WIN 🏆</span>`;
    } else if (h.outcome === 'DRAW') {
      outcomeBadge = `<span class="badge bg-warning text-dark" style="font-weight: 700;">DRAW 🤝</span>`;
    } else if (h.outcome === 'LOSS') {
      outcomeBadge = isGroup
        ? `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">RANK #${h.my_rank || '-'}</span>`
        : `<span class="badge bg-danger" style="font-weight: 700;">LOSS</span>`;
    } else if (h.outcome === 'DECLINED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">DECLINED</span>`;
    } else if (h.outcome === 'EXPIRED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">EXPIRED</span>`;
    } else if (h.outcome === 'CANCELLED') {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary" style="font-weight: 600;">CANCELLED</span>`;
    } else {
      outcomeBadge = `<span class="badge bg-secondary-subtle text-secondary">${h.outcome}</span>`;
    }

    const modeBadge = isGroup
      ? `<span class="badge me-1" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size:0.65rem; font-weight:700;">GROUP (${h.total_participants || 3})</span>`
      : '';

    let scoresDisplay = '';
    if (h.status === 'COMPLETED' && h.my_final_score !== undefined) {
      if (isGroup) {
        scoresDisplay = `<div class="small text-light mt-1">Final Score: <strong>${h.my_final_score}</strong> (Rank #${h.my_rank || '-'} of ${h.total_participants || 3})</div>`;
      } else {
        scoresDisplay = `<div class="small text-light mt-1">Final Score: <strong>${h.my_final_score}</strong> vs <strong>${h.opponent_final_score}</strong></div>`;
      }
    }

    html += `
      <div class="col-12 col-md-6">
        <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px;">
          <div>
            <div class="d-flex align-items-center justify-content-between mb-2">
              <div class="d-flex align-items-center gap-1.5 overflow-hidden">
                <span class="fs-6">${typeInfo.icon}</span>
                <span class="fw-bold small text-light text-truncate" style="max-width: 170px;">${h.title || typeInfo.name}</span>
              </div>
              <div class="d-flex align-items-center">${modeBadge}${outcomeBadge}</div>
            </div>

            <div class="d-flex align-items-center gap-2.5 my-2">
              <div class="avatar-ring" style="width: 36px; height: 36px; font-size: 1.1rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                <span>${opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase()}</span>
              </div>
              <div class="overflow-hidden">
                <div class="fw-bold text-light small text-truncate">${opp.display_name || opp.username}</div>
                <small class="text-secondary" style="font-size: 0.72rem;">${isGroup ? 'Group Showdown' : `@${opp.username}`} • ${datesLabel}</small>
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

// Filter Invitations by Format (All, 1v1, Group)
function filterInvitationsFormat(format, btnEl) {
  challengeState.invitationsFormatFilter = format;
  const container = document.getElementById('chPaneInvitations');
  const btns = (container && typeof container.querySelectorAll === 'function')
    ? container.querySelectorAll('.cb-format-filter-btn')
    : (typeof document !== 'undefined' && document.querySelectorAll ? document.querySelectorAll('#chPaneInvitations .cb-format-filter-btn') : []);
  if (btns && typeof btns.forEach === 'function') {
    btns.forEach(btn => {
      if (btn && btn.classList && typeof btn.classList.toggle === 'function') {
        const isMatch = (btn === btnEl || (btn.dataset && btn.dataset.format === format) || (typeof btn.getAttribute === 'function' && btn.getAttribute('data-format') === format));
        btn.classList.toggle('active', isMatch);
      }
    });
  }
  renderInvitations(challengeState.invitations, challengeState.outgoingInvitations);
}

// Render Invitations Inbox
function renderInvitations(incoming, outgoing) {
  const listEl = document.getElementById('chInvitationsList');
  if (!listEl) return;

  const fmt = challengeState.invitationsFormatFilter || 'all';
  let filteredInc = incoming || [];
  let filteredOut = outgoing || [];

  if (fmt === '1v1') {
    filteredInc = filteredInc.filter(i => i.challenge_mode !== 'GROUP');
    filteredOut = filteredOut.filter(i => i.challenge_mode !== 'GROUP');
  } else if (fmt === 'group') {
    filteredInc = filteredInc.filter(i => i.challenge_mode === 'GROUP');
    filteredOut = filteredOut.filter(i => i.challenge_mode === 'GROUP');
  }

  if (filteredInc.length === 0 && filteredOut.length === 0) {
    const emptyMsg = fmt === 'group'
      ? 'No pending group showdown invitations.'
      : (fmt === '1v1' ? 'No pending 1v1 duel invitations.' : 'No pending challenge invitations.');
    listEl.innerHTML = `
      <div class="text-center py-5 text-secondary">
        <div class="fs-1 mb-2">${fmt === 'group' ? '👥' : '✉️'}</div>
        <div class="fw-semibold text-light">${emptyMsg}</div>
        <div class="small mt-1">Discover runners to send a challenge!</div>
        <div class="d-flex gap-2 justify-content-center mt-3">
          <button class="btn btn-sm rr-btn-primary px-3 py-1.5" onclick="openChallengeBuilder(null, 'GROUP')">
            <span>👥</span> New Group Showdown
          </button>
          <button class="btn btn-sm btn-glass px-3 py-1.5" onclick="switchChallengeTab('discover')">
            <span>⚔️</span> Discover Runners
          </button>
        </div>
      </div>
    `;
    return;
  }

  let html = '';

  // Incoming Invitations Section
  if (filteredInc && filteredInc.length > 0) {
    html += `
      <h6 class="fw-bold mb-3 d-flex align-items-center gap-2" style="color: var(--text-main);">
        <span>Incoming Duels</span>
        <span class="badge bg-danger rounded-pill">${filteredInc.length}</span>
      </h6>
      <div class="row g-3 mb-4">
    `;

    filteredInc.forEach(inv => {
      const typeInfo = CHALLENGE_TYPE_INFO[inv.challenge_type] || { name: inv.challenge_type, icon: '⚔️', rule: '' };
      const challenger = inv.challenger || {};
      const datesLabel = formatFriendlyDateRange(inv.start_date, inv.end_date, inv.challenge_type === 'DAILY');
      const sentTimeStr = inv.created_at ? new Date(inv.created_at + (inv.created_at.includes('Z') ? '' : 'Z')).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';

      const isGroup = (inv.challenge_mode === 'GROUP');
      const invBadge = isGroup
        ? `<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-weight: 700;">GROUP INVITATION (${inv.total_participants} RUNNERS)</span>`
        : `<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-weight: 700;">1v1 INVITATION</span>`;

      html += `
        <div class="col-12 col-lg-6">
          <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px; border: 1px solid rgba(234, 179, 8, 0.25) !important;">
            <div>
              <div class="d-flex align-items-center justify-content-between mb-2">
                ${invBadge}
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
  if (filteredOut && filteredOut.length > 0) {
    html += `
      <h6 class="fw-bold mb-3 d-flex align-items-center gap-2 text-secondary">
        <span>Sent Invitations</span>
        <span class="badge bg-secondary-subtle text-secondary rounded-pill">${filteredOut.length}</span>
      </h6>
      <div class="row g-3">
    `;

    filteredOut.forEach(inv => {
      const typeInfo = CHALLENGE_TYPE_INFO[inv.challenge_type] || { name: inv.challenge_type, icon: '⚔️' };
      const opp = inv.opponent || {};
      const datesLabel = formatFriendlyDateRange(inv.start_date, inv.end_date, inv.challenge_type === 'DAILY');

      const isGroup = (inv.challenge_mode === 'GROUP');
      const sentBadge = isGroup
        ? `<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size: 0.68rem; font-weight: 700;">GROUP (${inv.accepted_count || 1}/${inv.total_participants || 3} JOINED)</span>`
        : `<span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.68rem;">SENT (1v1)</span>`;

      html += `
        <div class="col-12 col-lg-6">
          <div class="glass p-3 h-100 d-flex flex-column justify-content-between" style="border-radius: 18px; opacity: 0.88;">
            <div>
              <div class="d-flex align-items-center justify-content-between mb-2">
                ${sentBadge}
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

    const isGroup = (chal.challenge_mode === 'GROUP');

    if (bodyEl) {
      let participantsBlock = '';
      if (isGroup) {
        const parts = chal.participants || [];
        const partsHtml = parts.map(pt => {
          const emoji = pt.profile_emoji || (pt.display_name || pt.username || 'U')[0].toUpperCase();
          const statusBadge = pt.invitation_status === 'ACCEPTED'
            ? '<span class="badge bg-success-subtle text-success small" style="font-size:0.65rem;">Accepted</span>'
            : (pt.invitation_status === 'INVITED'
              ? '<span class="badge bg-warning-subtle text-warning small" style="font-size:0.65rem;">Invited</span>'
              : `<span class="badge bg-secondary-subtle text-secondary small" style="font-size:0.65rem;">${pt.invitation_status}</span>`);
          return `
            <div class="d-flex align-items-center justify-content-between p-2 rounded-2 mb-1" style="background: rgba(255,255,255,0.025); font-size: 0.78rem;">
              <div class="d-flex align-items-center gap-2 overflow-hidden">
                <span class="avatar-ring" style="width: 22px; height: 22px; font-size: 0.7rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
                  <span>${emoji}</span>
                </span>
                <span class="fw-semibold text-light text-truncate">${pt.display_name || pt.username}</span>
                ${pt.role === 'CHALLENGER' ? '<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size:0.6rem;">HOST</span>' : ''}
              </div>
              <div>${statusBadge}</div>
            </div>
          `;
        }).join('');

        participantsBlock = `
          <div class="mb-3">
            <div class="d-flex justify-content-between align-items-center mb-1.5">
              <span class="text-secondary small fw-bold" style="font-size: 0.72rem;">PARTICIPANTS (${chal.accepted_count || 1}/${chal.total_participants || parts.length} JOINED)</span>
              <span class="text-secondary" style="font-size: 0.7rem;">Free-for-all Showdown</span>
            </div>
            <div class="p-2 rounded-3" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-subtle); max-height: 180px; overflow-y: auto;">
              ${partsHtml}
            </div>
          </div>
        `;
      } else {
        participantsBlock = `
          <div class="row g-2 small mb-3">
            <div class="col-6">
              <span class="text-secondary d-block" style="font-size: 0.72rem;">CHALLENGER</span>
              <span class="fw-bold text-light">${chal.challenger.display_name} (@${chal.challenger.username})</span>
            </div>
            <div class="col-6">
              <span class="text-secondary d-block" style="font-size: 0.72rem;">OPPONENT</span>
              <span class="fw-bold text-light">${chal.opponent ? chal.opponent.display_name : 'Opponent'} (@${chal.opponent ? chal.opponent.username : ''})</span>
            </div>
          </div>
        `;
      }

      bodyEl.innerHTML = `
        <div class="d-flex align-items-center gap-3 mb-3 pb-3 border-bottom border-secondary-subtle">
          <div class="avatar-ring" style="width: 48px; height: 48px; font-size: 1.5rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%;">
            <span>${typeInfo.icon}</span>
          </div>
          <div>
            <h6 class="fw-bold mb-0 text-light">${chal.title || typeInfo.name}</h6>
            <div class="d-flex gap-1 mt-1">
              ${isGroup ? '<span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; font-size: 0.7rem; font-weight:700;">GROUP SHOWDOWN</span>' : '<span class="badge" style="background: var(--accent-soft); color: var(--accent); font-size: 0.7rem; font-weight:700;">1v1 DUEL</span>'}
              <span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.7rem;">${chal.display_status || chal.status}</span>
            </div>
          </div>
        </div>

        ${participantsBlock}

        <div class="row g-2 small mb-3">
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
  const isGroup = (inv.challenge_mode === 'GROUP');

  const badgeEl = document.querySelector('#challengeInvitationPopupModal .modal-header .badge');
  if (badgeEl) {
    if (isGroup) {
      badgeEl.innerHTML = `👥 GROUP SHOWDOWN INVITATION (${inv.total_participants || 3} RUNNERS)`;
      badgeEl.style.background = 'rgba(234, 179, 8, 0.15)';
      badgeEl.style.color = '#eab308';
    } else {
      badgeEl.innerHTML = `⚔️ 1v1 DUEL INVITATION`;
      badgeEl.style.background = 'rgba(0, 242, 255, 0.15)';
      badgeEl.style.color = 'var(--accent)';
    }
  }

  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setEl('popupChallengerName', isGroup ? `${challenger.display_name || challenger.username || 'Runner'} (Host)` : (challenger.display_name || challenger.username || 'Runner'));
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
function openChallengeBuilder(player, mode = null) {
  const chosenMode = mode === 'GROUP' ? 'GROUP' : (player ? '1V1' : 'GROUP');
  challengeState.builder.mode = chosenMode;
  challengeState.builder.opponent = player || null;
  challengeState.builder.selectedOpponents = player ? [player] : [];
  challengeState.builder.step = 1;
  challengeState.builder.type = 'DISTANCE';
  challengeState.builder.durationDays = 7;
  challengeState.builder.title = '';
  challengeState.builder.message = '';

  const today = new Date();
  challengeState.builder.startDate = formatLocalISODate(today);
  challengeState.builder.endDate = formatLocalISODate(addDays(today, 6)); // 7 days inclusive

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
  setBuilderMode(chosenMode);
  renderSelectedChips();

  updateBuilderStepView();

  if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const modalEl = document.getElementById('challengeBuilderModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }
}

// Mode Switcher (1V1 vs GROUP)
function setBuilderMode(mode) {
  challengeState.builder.mode = mode;

  const btn1v1 = document.getElementById('cbMode1v1Btn');
  const btnGroup = document.getElementById('cbModeGroupBtn');
  const badge = document.getElementById('cbModeBadge');
  const groupSection = document.getElementById('cbGroupRunnersSection');
  const nameHeader = document.getElementById('cbOpponentNameHeader');
  const modalTitle = document.getElementById('challengeBuilderModalTitle');

  if (btn1v1) btn1v1.classList.toggle('active', mode === '1V1');
  if (btnGroup) btnGroup.classList.toggle('active', mode === 'GROUP');

  if (badge) {
    if (mode === 'GROUP') {
      badge.textContent = 'GROUP SHOWDOWN';
      badge.style.background = 'rgba(234, 179, 8, 0.2)';
      badge.style.color = '#eab308';
    } else {
      badge.textContent = '1v1 DUEL';
      badge.style.background = 'var(--accent-soft)';
      badge.style.color = 'var(--accent)';
    }
  }

  if (groupSection) {
    groupSection.style.display = (mode === 'GROUP') ? 'block' : 'none';
  }

  if (mode === '1V1') {
    const opp = challengeState.builder.opponent || (challengeState.builder.selectedOpponents[0] || null);
    challengeState.builder.opponent = opp;
    if (nameHeader) {
      nameHeader.textContent = opp ? (opp.display_name || opp.username) : 'Runner';
    }
    if (modalTitle) {
      modalTitle.innerHTML = `Challenge <span id="cbOpponentNameHeader" style="color: var(--accent);">${opp ? (opp.display_name || opp.username) : 'Runner'}</span>`;
    }
  } else {
    // If switching to GROUP, make sure previously chosen opponent is included in selected list
    if (challengeState.builder.opponent) {
      if (!challengeState.builder.selectedOpponents.some(o => o.id === challengeState.builder.opponent.id)) {
        challengeState.builder.selectedOpponents.push(challengeState.builder.opponent);
      }
    }
    if (nameHeader) {
      nameHeader.textContent = 'Group Showdown';
    }
    if (modalTitle) {
      modalTitle.innerHTML = `Create <span style="color: var(--accent);">Group Showdown</span>`;
    }
  }

  // Update card titles dynamically to match selected mode
  const distCard = document.querySelector('.cb-type-card[data-type="DISTANCE"] .cb-type-title');
  const consCard = document.querySelector('.cb-type-card[data-type="CONSISTENCY"] .cb-type-title');
  const longCard = document.querySelector('.cb-type-card[data-type="LONGEST"] .cb-type-title');
  const dailyCard = document.querySelector('.cb-type-card[data-type="DAILY"] .cb-type-title');
  if (distCard) distCard.textContent = (mode === 'GROUP') ? 'Distance Showdown' : 'Distance Duel';
  if (consCard) consCard.textContent = (mode === 'GROUP') ? 'Consistency Showdown' : 'Consistency Duel';
  if (longCard) longCard.textContent = (mode === 'GROUP') ? 'Longest Run Showdown' : 'Longest Single Run';
  if (dailyCard) dailyCard.textContent = (mode === 'GROUP') ? 'Daily Showdown' : 'Daily Sprint';

  renderSelectedChips();
  if (mode === 'GROUP') {
    onBuilderRunnerSearch('');
  }
}

// Selected Runner Chips for Group Mode
function renderSelectedChips() {
  const container = document.getElementById('cbSelectedChips');
  const countText = document.getElementById('cbGroupCountText');
  const countBadge = document.getElementById('cbGroupCountBadge');
  if (!container) return;

  const opponents = challengeState.builder.selectedOpponents || [];
  const totalRunners = opponents.length + 1; // +1 for challenger

  if (countText) {
    countText.textContent = `${opponents.length} / 9 invitees (${totalRunners} total runners)`;
  }

  if (countBadge) {
    if (totalRunners < 3) {
      countBadge.style.background = 'rgba(239, 68, 68, 0.15)';
      countBadge.style.color = '#ef4444';
    } else if (totalRunners <= 10) {
      countBadge.style.background = 'rgba(34, 197, 94, 0.15)';
      countBadge.style.color = '#22c55e';
    } else {
      countBadge.style.background = 'rgba(239, 68, 68, 0.15)';
      countBadge.style.color = '#ef4444';
    }
  }

  if (opponents.length === 0) {
    container.innerHTML = '<span class="text-secondary small fst-italic" id="cbSelectedChipsEmpty">Search and select 2 to 9 runners below</span>';
    return;
  }

  container.innerHTML = opponents.map(p => {
    const emoji = p.profile_emoji || (p.display_name || p.username || 'U')[0].toUpperCase();
    const name = p.display_name || p.username;
    return `
      <span class="cb-runner-chip">
        <span style="font-size: 0.95rem;">${emoji}</span>
        <span class="fw-semibold">${name}</span>
        <button type="button" class="chip-remove" title="Remove runner" onclick="removeOpponentFromGroup(${p.id})">✕</button>
      </span>
    `;
  }).join('');
}

let builderFetchedPlayers = {};

function addOpponentToGroupById(playerId) {
  const player = builderFetchedPlayers[playerId];
  if (player) {
    addOpponentToGroup(player);
  }
}

function addOpponentToGroup(player) {
  if (!player || !player.id) return;
  const opps = challengeState.builder.selectedOpponents;

  if (opps.some(o => o.id === player.id)) {
    return; // Already selected
  }

  if (opps.length >= 9) {
    showBuilderError('Maximum 9 invited runners allowed (10 total participants including yourself).');
    return;
  }

  opps.push(player);
  if (!challengeState.builder.opponent) {
    challengeState.builder.opponent = player;
  }

  const searchInput = document.getElementById('cbRunnerSearchInput');
  if (searchInput) searchInput.value = '';

  renderSelectedChips();
  onBuilderRunnerSearch('');
}

function removeOpponentFromGroup(playerId) {
  challengeState.builder.selectedOpponents = (challengeState.builder.selectedOpponents || []).filter(o => o.id !== playerId);
  if (challengeState.builder.opponent && challengeState.builder.opponent.id === playerId) {
    challengeState.builder.opponent = challengeState.builder.selectedOpponents[0] || null;
  }
  renderSelectedChips();
  onBuilderRunnerSearch('');
}

// Autocomplete Runner Search inside Builder
let builderSearchTimer = null;
function onBuilderRunnerSearch(query) {
  clearTimeout(builderSearchTimer);
  const resultsDiv = document.getElementById('cbRunnerSearchResults');
  if (!resultsDiv) return;

  const q = (query || '').trim();

  builderSearchTimer = setTimeout(async () => {
    try {
      const url = q.length > 0
        ? `/api/challenges/players?q=${encodeURIComponent(q)}&limit=10`
        : `/api/challenges/players?limit=10`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const players = data.players || [];

      builderFetchedPlayers = builderFetchedPlayers || {};
      players.forEach(p => {
        builderFetchedPlayers[p.id] = p;
      });

      const currentSelectedIds = new Set((challengeState.builder.selectedOpponents || []).map(o => o.id));
      const filtered = players.filter(p => !currentSelectedIds.has(p.id));

      if (filtered.length === 0) {
        resultsDiv.innerHTML = '<div class="p-2 text-secondary small text-center">' + (q.length > 0 ? 'No matching active runners' : 'All available runners selected') + '</div>';
        resultsDiv.style.display = 'block';
        return;
      }

      const headerTitle = q.length > 0 ? 'Matching Runners' : 'Suggested Runners to Invite (Click to Add)';
      const headerHtml = `<div class="px-2 py-1 text-secondary small fw-semibold border-bottom border-secondary-subtle">${headerTitle}</div>`;

      resultsDiv.innerHTML = headerHtml + filtered.map(p => {
        const emoji = p.profile_emoji || (p.display_name || p.username || 'U')[0].toUpperCase();
        const name = (p.display_name || p.username || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        const uname = (p.username || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        return `
          <div class="cb-search-result-item d-flex align-items-center gap-2 p-2 rounded-2" onclick="addOpponentToGroupById(${p.id})">
            <div class="avatar-ring" style="width: 28px; height: 28px; font-size: 0.85rem; display: flex; align-items: center; justify-content: center; background: var(--accent-soft); border-radius: 50%; flex-shrink: 0;">
              <span>${emoji}</span>
            </div>
            <div class="overflow-hidden flex-grow-1">
              <div class="fw-semibold text-truncate small text-light">${name}</div>
              <small class="text-secondary d-block text-truncate" style="font-size:0.7rem;">@${uname}</small>
            </div>
            <button type="button" class="btn btn-sm btn-outline-info py-0 px-2 flex-shrink-0" style="font-size: 0.72rem;" onclick="event.stopPropagation(); addOpponentToGroupById(${p.id})">+ Add</button>
          </div>
        `;
      }).join('');
      resultsDiv.style.display = 'block';
    } catch (err) {
      console.error('Error in onBuilderRunnerSearch:', err);
    }
  }, 100);
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
  const b = challengeState.builder;

  const errAlert = document.getElementById('cbErrorAlert');
  if (errAlert) errAlert.style.display = 'none';

  if (delta > 0) {
    if (current === 1) {
      if (!b.type) {
        showBuilderError('Please select a challenge type to continue.');
        return;
      }
      if (b.mode === 'GROUP') {
        const oppCnt = (b.selectedOpponents || []).length;
        if (oppCnt < 2) {
          showBuilderError(`Group challenges require at least 2 invited runners (3 total runners). You currently have ${oppCnt}.`);
          return;
        }
        if (oppCnt > 9) {
          showBuilderError(`Group challenges support at most 9 invited runners (10 total runners). You currently have ${oppCnt}.`);
          return;
        }
      } else {
        if (!b.opponent) {
          showBuilderError('Please select an opponent to challenge.');
          return;
        }
      }
    } else if (current === 2) {
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

  if (step === 3) {
    const typeInfo = CHALLENGE_TYPE_INFO[b.type] || { name: b.type, rule: '' };

    const setEl = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };

    const p1v1Block = document.getElementById('cbPreview1v1Block');
    const pGroupBlock = document.getElementById('cbPreviewGroupBlock');
    const awardInfo = document.getElementById('cbPreviewAwardInfo');

    if (b.mode === 'GROUP') {
      if (p1v1Block) {
        p1v1Block.classList.remove('d-flex');
        p1v1Block.classList.add('d-none');
        p1v1Block.style.display = 'none';
        if (typeof p1v1Block.style.setProperty === 'function') {
          p1v1Block.style.setProperty('display', 'none', 'important');
        }
      }
      if (pGroupBlock) {
        pGroupBlock.classList.remove('d-none');
        pGroupBlock.style.display = 'block';
        if (typeof pGroupBlock.style.setProperty === 'function') {
          pGroupBlock.style.setProperty('display', 'block', 'important');
        }
      }

      const totalCount = (b.selectedOpponents || []).length + 1;
      setEl('cbPreviewGroupTitle', `Group Showdown (${totalCount} Runners)`);

      const chipsContainer = document.getElementById('cbPreviewGroupChips');
      if (chipsContainer) {
        chipsContainer.innerHTML = [
          `<span class="cb-runner-chip cb-runner-chip-creator"><span>🏃</span> <span>You (Creator)</span></span>`,
          ...(b.selectedOpponents || []).map(p => {
            const emoji = p.profile_emoji || (p.display_name || p.username || 'U')[0].toUpperCase();
            const name = (p.display_name || p.username || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<span class="cb-runner-chip"><span style="font-size: 0.95rem;">${emoji}</span> <span class="fw-semibold">${name}</span></span>`;
          })
        ].join(' ');
      }

      if (awardInfo) {
        awardInfo.textContent = 'In Group Challenges, the 1st place runner receives 1 Friendly Challenges medal award. In case of ties for 1st place, a draw results and no medal is awarded.';
      }
    } else {
      if (p1v1Block) {
        p1v1Block.classList.remove('d-none');
        p1v1Block.classList.add('d-flex');
        p1v1Block.style.display = 'flex';
        if (typeof p1v1Block.style.setProperty === 'function') {
          p1v1Block.style.setProperty('display', 'flex', 'important');
        }
      }
      if (pGroupBlock) {
        pGroupBlock.classList.add('d-none');
        pGroupBlock.style.display = 'none';
        if (typeof pGroupBlock.style.setProperty === 'function') {
          pGroupBlock.style.setProperty('display', 'none', 'important');
        }
      }

      const opp = b.opponent || (b.selectedOpponents && b.selectedOpponents[0]) || {};
      setEl('cbPreviewOpponentName', opp.display_name || opp.username || 'Runner');
      setEl('cbPreviewOpponentHandle', `@${opp.username || 'opponent'}`);
      setEl('cbPreviewEmoji', opp.profile_emoji || (opp.display_name || opp.username || 'U')[0].toUpperCase());

      if (awardInfo) {
        awardInfo.textContent = 'The winner receives 1 Friendly Challenges medal award upon completion. Draws grant no medals.';
      }
    }

    const typeBaseName = (b.mode === 'GROUP')
      ? (b.type === 'DISTANCE' ? 'Distance Showdown' :
         b.type === 'CONSISTENCY' ? 'Consistency Showdown' :
         b.type === 'LONGEST' ? 'Longest Run Showdown' : 'Daily Showdown')
      : typeInfo.name;
    setEl('cbPreviewType', b.title ? `${b.title} (${typeBaseName})` : typeBaseName);
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

// Submit Challenge Creation (1V1 or GROUP)
async function submitChallengeForm() {
  const b = challengeState.builder;
  const isGroup = (b.mode === 'GROUP');

  if (isGroup) {
    if (!b.selectedOpponents || b.selectedOpponents.length < 2) {
      showBuilderError('Please select at least 2 runners to challenge.');
      return;
    }
  } else {
    if (!b.opponent) {
      showBuilderError('Please select an opponent.');
      return;
    }
  }

  const submitBtn = document.getElementById('cbSubmitBtn');
  const submitSpinner = document.getElementById('cbSubmitSpinner');
  const submitText = document.getElementById('cbSubmitText');
  const errAlert = document.getElementById('cbErrorAlert');

  if (errAlert) errAlert.style.display = 'none';
  if (submitBtn) submitBtn.disabled = true;
  if (submitSpinner) submitSpinner.style.display = 'inline-block';
  if (submitText) submitText.textContent = 'Sending...';

  try {
    let payload;
    if (isGroup) {
      payload = {
        participant_ids: b.selectedOpponents.map(o => o.id),
        challenge_type: b.type,
        start_date: b.startDate,
        end_date: b.endDate,
        title: b.title || undefined,
        message: b.message || undefined,
        challenge_timezone: b.timezone
      };
    } else {
      payload = {
        opponent_id: b.opponent.id,
        challenge_type: b.type,
        start_date: b.startDate,
        end_date: b.endDate,
        title: b.title || undefined,
        message: b.message || undefined,
        challenge_timezone: b.timezone
      };
    }

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

    const succMsg = isGroup
      ? `⚔️ Group challenge invitation sent to ${b.selectedOpponents.length} runners!`
      : '⚔️ Challenge invitation sent!';

    if (typeof showToast === 'function') {
      showToast(succMsg, 'success');
    } else if (typeof alert === 'function') {
      alert(succMsg);
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
  return `runrush_challenges_v2_announced_${user}`;
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

    const targetChallengeId = params.get('challenge_id') || params.get('progress');
    if (targetChallengeId) {
      const cid = parseInt(targetChallengeId, 10);
      if (!isNaN(cid) && cid > 0) {
        openChallengeProgress(cid);
      }
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

  // Group Challenges V2 Exports
  window.setBuilderMode = setBuilderMode;
  window.renderSelectedChips = renderSelectedChips;
  window.addOpponentToGroup = addOpponentToGroup;
  window.addOpponentToGroupById = addOpponentToGroupById;
  window.removeOpponentFromGroup = removeOpponentFromGroup;
  window.onBuilderRunnerSearch = onBuilderRunnerSearch;
  window.toggleRunBreakdown = toggleRunBreakdown;

  // Format Filter Exports
  window.filterOngoingFormat = filterOngoingFormat;
  window.filterInvitationsFormat = filterInvitationsFormat;
  window.filterHistoryFormat = filterHistoryFormat;
}

// Auto-run if DOM already loaded
if (typeof document !== 'undefined') {
  document.addEventListener('click', (e) => {
    const resultsDiv = document.getElementById('cbRunnerSearchResults');
    const searchInput = document.getElementById('cbRunnerSearchInput');
    if (resultsDiv && searchInput) {
      if (!resultsDiv.contains(e.target) && e.target !== searchInput) {
        resultsDiv.style.display = 'none';
      }
    }
  });

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


  window.RR_ACTIONS = window.RR_ACTIONS || {};
  window.RR_ACTIONS.switchChallengeTab = function(tab) { return switchChallengeTab(tab); };
  window.RR_ACTIONS.clearPlayerSearch = function() { return clearPlayerSearch(); };
  window.RR_ACTIONS.changePlayerSearchPage = function(delta) { return changePlayerSearchPage(delta); };
  window.RR_ACTIONS.openChallengeBuilder = function(target, mode) { return openChallengeBuilder(target, mode); };
  window.RR_ACTIONS.selectChallengeType = function(type, el) { return selectChallengeType(type, el || this); };
  window.RR_ACTIONS.applyDurationPreset = function(preset, el) { return applyDurationPreset(preset, el || this); };
  window.RR_ACTIONS.onDateInputChange = function() { return onDateInputChange(); };
  window.RR_ACTIONS.onDailyDateInputChange = function() { return onDailyDateInputChange(); };
  window.RR_ACTIONS.navigateChallengeStep = function(step) { return navigateChallengeStep(step); };
  window.RR_ACTIONS.submitChallengeForm = function() { return submitChallengeForm(); };
  window.RR_ACTIONS.dismissInvitationPopup = function() { return dismissInvitationPopup(); };
  window.RR_ACTIONS.respondToPopupInvitation = function(action) { return respondToPopupInvitation(action); };
  window.RR_ACTIONS.navigatePopupInvitation = function(delta) { return navigatePopupInvitation(delta); };
  window.RR_ACTIONS.filterChallengeHistory = function(filter, el) { return filterChallengeHistory(filter, el || this); };
  window.RR_ACTIONS.changeHistoryPage = function(delta) { return changeHistoryPage(delta); };
  window.RR_ACTIONS.dismissChallengesUpdateModal = function() { return dismissChallengesUpdateModal(); };
  window.RR_ACTIONS.exploreChallengesFromUpdateModal = function() { return exploreChallengesFromUpdateModal(); };
  window.RR_ACTIONS.setBuilderMode = function(mode) { return setBuilderMode(mode); };
  window.RR_ACTIONS.onBuilderRunnerSearch = function(val) { return onBuilderRunnerSearch(val || this.value); };
  window.RR_ACTIONS.filterOngoingFormat = function(fmt, el) { return filterOngoingFormat(fmt, el || this); };
  window.RR_ACTIONS.filterInvitationsFormat = function(fmt, el) { return filterInvitationsFormat(fmt, el || this); };
  window.RR_ACTIONS.filterHistoryFormat = function(fmt, el) { return filterHistoryFormat(fmt, el || this); };
