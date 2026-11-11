/**
 * Frontend tests for static/js/challenges.js under Node.js VM
 * Tests Phase 2 (Discovery/Builder) & Phase 3 (Invitations & Popup)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

// Stub DOM
const elements = {};
function getOrCreateElement(id) {
  if (!elements[id]) {
    elements[id] = {
      id,
      dataset: {},
      textContent: '',
      innerHTML: '',
      value: '',
      style: { display: 'none', width: '0%' },
      classList: {
        classes: new Set(),
        add(c) { this.classes.add(c); },
        remove(c) { this.classes.delete(c); },
        toggle(c, force) {
          if (force !== undefined) {
            if (force) this.classes.add(c); else this.classes.delete(c);
          } else {
            if (this.classes.has(c)) this.classes.delete(c); else this.classes.add(c);
          }
        },
        has(c) { return this.classes.has(c); },
        contains(c) { return this.classes.has(c); }
      },
      setAttribute(k, v) { this[k] = v; },
      getAttribute(k) { return this[k]; },
      removeAttribute(k) { delete this[k]; },
      querySelectorAll(sel) { return []; },
      addEventListener() {}
    };
  }
  return elements[id];
}

const documentStub = {
  getElementById: (id) => getOrCreateElement(id),
  querySelector: (sel) => {
    if (sel.includes('meta[name="csrf-token"]')) {
      if (!elements['meta-csrf']) {
        elements['meta-csrf'] = {
          content: 'mock-csrf-token',
          getAttribute: function(k) { return this[k] || this.content; },
          setAttribute: function(k, v) { this[k] = v; if (k === 'content') this.content = v; }
        };
      }
      return elements['meta-csrf'];
    }
    return getOrCreateElement('stub-' + sel);
  },
  querySelectorAll: (sel) => {
    if (sel.includes('.cb-type-card')) {
      return [
        { ...getOrCreateElement('type-DISTANCE'), getAttribute: () => 'DISTANCE', dataset: { type: 'DISTANCE' } },
        { ...getOrCreateElement('type-CONSISTENCY'), getAttribute: () => 'CONSISTENCY', dataset: { type: 'CONSISTENCY' } },
        { ...getOrCreateElement('type-LONGEST'), getAttribute: () => 'LONGEST', dataset: { type: 'LONGEST' } },
        { ...getOrCreateElement('type-DAILY'), getAttribute: () => 'DAILY', dataset: { type: 'DAILY' } },
      ];
    }
    if (sel.includes('.cb-preset-btn')) {
      return [
        { ...getOrCreateElement('preset-7'), getAttribute: () => '7', dataset: { preset: '7' } },
        { ...getOrCreateElement('preset-14'), getAttribute: () => '14', dataset: { preset: '14' } },
        { ...getOrCreateElement('preset-30'), getAttribute: () => '30', dataset: { preset: '30' } },
        { ...getOrCreateElement('preset-custom'), getAttribute: () => 'custom', dataset: { preset: 'custom' } },
      ];
    }
    return [];
  },
  addEventListener: () => {}
};

const bootstrapModalInstance = {
  shown: false,
  hidden: false,
  show() { this.shown = true; this.hidden = false; },
  hide() { this.shown = false; this.hidden = true; }
};

const bootstrapStub = {
  Modal: {
    getOrCreateInstance: () => bootstrapModalInstance,
    getInstance: () => bootstrapModalInstance
  }
};

const sessionStorageStore = {};
const sessionStorageStub = {
  getItem: (k) => sessionStorageStore[k] || null,
  setItem: (k, v) => { sessionStorageStore[k] = String(v); },
  removeItem: (k) => { delete sessionStorageStore[k]; },
  clear: () => { for (const k in sessionStorageStore) delete sessionStorageStore[k]; }
};

const localStorageStore = {};
const localStorageStub = {
  getItem: (k) => localStorageStore[k] || null,
  setItem: (k, v) => { localStorageStore[k] = String(v); },
  removeItem: (k) => { delete localStorageStore[k]; },
  clear: () => { for (const k in localStorageStore) delete localStorageStore[k]; }
};

let lastFetchUrl = '';
let lastFetchOptions = null;

const sandbox = {
  document: documentStub,
  window: {
    userData: { csrf_token: 'mock-csrf-token' },
    location: { search: '' },
    localStorage: localStorageStub
  },
  sessionStorage: sessionStorageStub,
  localStorage: localStorageStub,
  URLSearchParams,
  bootstrap: bootstrapStub,
  console,
  setTimeout,
  clearTimeout,
  encodeURIComponent,
  Intl,
  fetch: (url, options) => {
    lastFetchUrl = url;
    lastFetchOptions = options;
    if (url.includes('/api/challenges/stats')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: 'success',
          stats: { participated: 3, wins: 2, losses: 1, draws: 0, medal_count: 2, pending_invitations: 1 }
        })
      });
    }
    if (url.includes('/api/challenges/players')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: 'success',
          players: [
            { id: 2, username: 'player2', display_name: 'Player Two', profile_emoji: '⚡', total_distance_km: 50.5 }
          ],
          pagination: { page: 1, limit: 10, total: 1, total_pages: 1, has_next: false, has_prev: false }
        })
      });
    }
    if (url.includes('/api/challenges/invitations')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          status: 'success',
          incoming: [
            {
              id: 101,
              challenger_id: 2,
              opponent_id: 1,
              challenge_type: 'DISTANCE',
              title: 'Weekend Clash',
              message: 'Ready for this?',
              start_date: '2026-11-07',
              end_date: '2026-11-14',
              challenger: { id: 2, username: 'player2', display_name: 'Player Two', profile_emoji: '⚡' }
            },
            {
              id: 102,
              challenger_id: 3,
              opponent_id: 1,
              challenge_type: 'DAILY',
              title: 'Sunday Mile',
              start_date: '2026-11-08',
              end_date: '2026-11-08',
              challenger: { id: 3, username: 'player3', display_name: 'Player Three', profile_emoji: '🏃' }
            }
          ],
          outgoing: [],
          pending_count: 2
        })
      });
    }
    if (url.includes('/api/csrf-token')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success', csrf_token: 'fresh-mock-token' })
      });
    }
    if (url.includes('/accept')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success', display_status: 'ACTIVE', challenge_id: 101 })
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success' }) });
  }
};

vm.createContext(sandbox);
const code = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'challenges.js'), 'utf8');
vm.runInContext(code, sandbox);

// Test 1: initChallengesTab calls stats, player discovery, and invitations
sandbox.window.initChallengesTab();

setTimeout(() => {
  assert.strictEqual(elements['chStatParticipated'].textContent, 3, 'Stats participated should be 3');
  assert.strictEqual(elements['chStatWins'].textContent, 2, 'Stats wins should be 2');
  assert.strictEqual(elements['chStatMedals'].textContent, 2, 'Stats medals should be 2');

  // Test 2: openChallengeBuilder sets up opponent and step 1
  sandbox.window.openChallengeBuilder({ id: 5, username: 'speedy', display_name: 'Speedy Gonzales', profile_emoji: '🐭' });
  assert.strictEqual(elements['cbOpponentNameHeader'].textContent, 'Speedy Gonzales');
  assert.strictEqual(elements['cbStepCounter'].textContent, 'Step 1 of 3');

  // Test 3: Select DAILY challenge type
  sandbox.window.selectChallengeType('DAILY');
  assert.strictEqual(elements['cbRangeControls'].style.display, 'none');
  assert.strictEqual(elements['cbDailyControls'].style.display, 'block');

  // Test 4: Navigate to step 2 then step 3
  elements['cbDailyDate'].value = '2026-11-10';
  sandbox.window.navigateChallengeStep(1); // To Step 2
  assert.strictEqual(elements['cbStepCounter'].textContent, 'Step 2 of 3');

  sandbox.window.navigateChallengeStep(1); // To Step 3
  assert.strictEqual(elements['cbStepCounter'].textContent, 'Step 3 of 3');
  assert.strictEqual(elements['cbPreviewType'].textContent, 'Daily Showdown');
  assert.strictEqual(elements['cbPreviewOpponentName'].textContent, 'Speedy Gonzales');

  // Test 5: Phase 3 Invitations rendering and badge count
  const state = sandbox.window.challengeState;
  sandbox.window.renderInvitations(state.invitations, []);
  assert(elements['chInvitationsList'].innerHTML.includes('Incoming Duels'), 'Should render incoming duels header');
  assert(elements['chInvitationsList'].innerHTML.includes('Weekend Clash'), 'Should render challenge title');
  assert(elements['chInvitationsList'].innerHTML.includes('Player Two'), 'Should render challenger name');

  // Test 6: Phase 3 Popup modal for unseen invitations
  sandbox.window.checkAndShowInvitationPopup(state.invitations);
  assert.strictEqual(bootstrapModalInstance.shown, true, 'Popup modal should be shown');
  assert.strictEqual(elements['popupChallengerName'].textContent, 'Player Two');
  assert.strictEqual(elements['popupChallengeTitle'].textContent, 'Weekend Clash (Distance Duel)');

  // Test 7: Multi-invitation navigation in popup
  sandbox.window.navigatePopupInvitation(1);
  assert.strictEqual(state.popupIndex, 1);
  assert.strictEqual(elements['popupChallengerName'].textContent, 'Player Three');

  // Test 8: Popup dismissal saves IDs in sessionStorage and doesn't reject
  sandbox.window.dismissInvitationPopup();
  assert.strictEqual(bootstrapModalInstance.hidden, true, 'Popup modal should be hidden on dismissal');
  const dismissed = JSON.parse(sessionStorageStore['runrush_dismissed_challenge_invitations']);
  assert(dismissed.includes(101), 'ID 101 should be saved in sessionStorage');
  assert(dismissed.includes(102), 'ID 102 should be saved in sessionStorage');

  // Test 9: Phase 4 Ongoing challenges rendering
  const mockOngoing = [
    {
      id: 201,
      title: 'Summer 10K Duel',
      challenge_type: 'DISTANCE',
      start_date: '2026-11-06',
      end_date: '2026-11-13',
      score_unit: 'km',
      time_remaining: '5 days left',
      display_status: 'ACTIVE',
      opponent: { id: 2, username: 'player2', display_name: 'Player Two', profile_emoji: '⚡' },
      my_score: 10.0,
      opponent_score: 5.0,
      my_ratio: 66.7,
      opponent_ratio: 33.3,
      leader: 'you',
      score_diff: 5.0,
      is_tied: false
    }
  ];
  sandbox.window.renderOngoingChallenges(mockOngoing);
  assert(elements['chOngoingList'].innerHTML.includes('Summer 10K Duel'), 'Should render ongoing title');
  assert(elements['chOngoingList'].innerHTML.includes('Leading by 5 km'), 'Should render leader pill');
  assert(elements['chOngoingList'].innerHTML.includes('66.7%'), 'Should render my ratio percentage');

  // Test 10: Phase 4 Challenge History rendering
  const mockHistory = [
    {
      id: 301,
      title: 'October Showdown',
      challenge_type: 'DAILY',
      start_date: '2026-10-25',
      end_date: '2026-10-25',
      status: 'COMPLETED',
      outcome: 'WIN',
      opponent: { id: 2, username: 'player2', display_name: 'Player Two' },
      my_final_score: 8.5,
      opponent_final_score: 6.0
    }
  ];
  sandbox.window.renderChallengeHistory(mockHistory, { total_pages: 1 });
  assert(elements['chHistoryList'].innerHTML.includes('October Showdown'), 'Should render history card title');
  assert(elements['chHistoryList'].innerHTML.includes('WIN 🏆'), 'Should render WIN badge');

  // Test 11: Phase 4 Filter challenge history
  sandbox.window.filterChallengeHistory('completed');
  assert.strictEqual(sandbox.window.challengeState.historyFilter, 'completed', 'History filter should be set to completed');

  // Test 12: Challenges V2 Update Announcement Modal Dismissal
  sandbox.window.OWN_USERNAME = 'testuser';
  sandbox.window.dismissChallengesUpdateModal();
  assert.strictEqual(localStorageStore['runrush_challenges_v2_announced_testuser'], 'true', 'Modal dismissal should be persisted in localStorage');

  // Test 13: Announcement popup does not trigger if already dismissed
  bootstrapModalInstance.shown = false;
  sandbox.window.checkChallengesUpdateAnnouncementPopup();
  assert.strictEqual(bootstrapModalInstance.shown, false, 'Modal should not show if already dismissed in storage');

  // Test 14: Group Challenge Builder Mode & Chips Selection
  sandbox.window.openChallengeBuilder(null, 'GROUP');
  assert.strictEqual(sandbox.window.challengeState.builder.mode, 'GROUP', 'Builder mode should be GROUP');
  assert.strictEqual(sandbox.window.challengeState.builder.selectedOpponents.length, 0, 'Initial opponents empty');

  // Test 15: Add / Remove Opponents in Group
  sandbox.window.addOpponentToGroup({ id: 2, username: 'p2', display_name: 'Player 2' });
  sandbox.window.addOpponentToGroup({ id: 3, username: 'p3', display_name: 'Player 3' });
  assert.strictEqual(sandbox.window.challengeState.builder.selectedOpponents.length, 2, 'Should have 2 invited opponents');
  assert(elements['cbSelectedChips'].innerHTML.includes('Player 2'), 'Should render Player 2 chip');
  assert(elements['cbSelectedChips'].innerHTML.includes('Player 3'), 'Should render Player 3 chip');

  // Remove one opponent
  sandbox.window.removeOpponentFromGroup(2);
  assert.strictEqual(sandbox.window.challengeState.builder.selectedOpponents.length, 1, 'Should have 1 opponent after removal');

  // Test 16: Group Challenge Step Validation (< 2 runners blocked)
  sandbox.window.challengeState.builder.step = 1;
  sandbox.window.navigateChallengeStep(1);
  assert.strictEqual(sandbox.window.challengeState.builder.step, 1, 'Should block advance with only 1 invited opponent');
  assert(elements['cbErrorAlert'].textContent.includes('at least 2 invited runners'), 'Error alert should explain requirement');

  // Add back second runner and advance
  sandbox.window.addOpponentToGroup({ id: 4, username: 'p4', display_name: 'Player 4' });
  sandbox.window.navigateChallengeStep(1);
  assert.strictEqual(sandbox.window.challengeState.builder.step, 2, 'Should advance to step 2 with >= 2 invited opponents');

  // Test 17: Submit Group Challenge Payload
  sandbox.window.navigateChallengeStep(1); // Advance to step 3
  assert.strictEqual(sandbox.window.challengeState.builder.step, 3, 'Should be on step 3');
  sandbox.window.submitChallengeForm();
  assert(lastFetchUrl.includes('/api/challenges'), 'Fetch should post to /api/challenges');
  const sentPayload = JSON.parse(lastFetchOptions.body);
  assert(Array.isArray(sentPayload.participant_ids), 'Payload should have participant_ids array');
  assert.deepStrictEqual(sentPayload.participant_ids, [3, 4], 'Payload participant_ids should match invited opponents');

  // Test 18: Ongoing Group Challenge Rendering
  const mockOngoingGroup = [
    {
      id: 202,
      title: 'Tri-City Clash',
      challenge_mode: 'GROUP',
      challenge_type: 'DISTANCE',
      start_date: '2026-11-01',
      end_date: '2026-11-07',
      status: 'ACCEPTED',
      display_status: 'ACTIVE',
      score_unit: 'km',
      total_participants: 3,
      my_score: 18.2,
      my_rank: 1,
      leader: 'you',
      score_diff: 4.1,
      is_tied: false,
      leaderboard: [
        { user_id: 1, username: 'me', display_name: 'You', rank: 1, display_score: 18.2, ratio: 45.0 },
        { user_id: 2, username: 'p2', display_name: 'Player Two', rank: 2, display_score: 14.1, ratio: 35.0 },
        { user_id: 3, username: 'p3', display_name: 'Player Three', rank: 3, display_score: 8.0, ratio: 20.0 }
      ]
    }
  ];
  sandbox.window.renderOngoingChallenges(mockOngoingGroup);
  assert(elements['chOngoingList'].innerHTML.includes('GROUP (3 RUNNERS)'), 'Should render group badge on ongoing card');
  assert(elements['chOngoingList'].innerHTML.includes('Rank #1'), 'Should render rank standing on ongoing card');
  assert(elements['chOngoingList'].innerHTML.includes('Leading Pack'), 'Should render leading pack pill');

  // Test 19: Detailed Progress Modal for Group Showdown
  // Emulate openChallengeProgress modal payload
  lastFetchUrl = '';
  // Progress modal DOM element stubs
  getOrCreateElement('challengeProgressModalBody');
  getOrCreateElement('cpmStatusBadge');
  getOrCreateElement('cpmTimeRemaining');
  getOrCreateElement('challengeProgressModalTitle');

  // Test 20: Group History with Draw Outcome (No Medals on Tie)
  const mockGroupHistory = [
    {
      id: 302,
      title: 'Tied Peak Showdown',
      challenge_mode: 'GROUP',
      challenge_type: 'DISTANCE',
      start_date: '2026-10-15',
      end_date: '2026-10-22',
      status: 'COMPLETED',
      outcome: 'DRAW',
      my_rank: 1,
      total_participants: 4,
      my_final_score: 25.0,
      opponent: { id: 2, username: 'p2', display_name: 'Runner Two' }
    }
  ];
  sandbox.window.renderChallengeHistory(mockGroupHistory, { total_pages: 1 });
  assert(elements['chHistoryList'].innerHTML.includes('GROUP (4)'), 'History card should have GROUP badge');
  assert(elements['chHistoryList'].innerHTML.includes('DRAW 🤝'), 'History card should have DRAW outcome badge');
  assert(elements['chHistoryList'].innerHTML.includes('Rank #1 of 4'), 'History card should display rank of total');

  // Test 21: Toggle Run Breakdown Interactive Accordion
  const testCollapseId = 'testCollapse123';
  const collapseEl = getOrCreateElement(testCollapseId);
  const collapseIcon = getOrCreateElement(testCollapseId + '_icon');
  collapseEl.style.display = 'none';
  sandbox.window.toggleRunBreakdown(testCollapseId);
  assert.strictEqual(collapseEl.style.display, 'block', 'Run breakdown should toggle to block display');
  assert.strictEqual(collapseIcon.style.transform, 'rotate(180deg)', 'Chevron icon should rotate 180deg when open');
  sandbox.window.toggleRunBreakdown(testCollapseId);
  assert.strictEqual(collapseEl.style.display, 'none', 'Run breakdown should toggle back to none display');
  assert.strictEqual(collapseIcon.style.transform, 'rotate(0deg)', 'Chevron icon should rotate back to 0deg when closed');

  // Test 22: Ongoing Format Filter (All / 1v1 / Group)
  const mixedOngoing = [
    { id: 401, title: 'Solo Clash', challenge_mode: '1V1', challenge_type: 'DISTANCE', status: 'ACCEPTED', my_score: 10, opponent: {} },
    { id: 402, title: 'Group Clash', challenge_mode: 'GROUP', challenge_type: 'DISTANCE', status: 'ACCEPTED', my_score: 15, leaderboard: [] }
  ];
  sandbox.window.challengeState.ongoing = mixedOngoing;

  // Filter 1v1
  sandbox.window.filterOngoingFormat('1v1');
  assert.strictEqual(sandbox.window.challengeState.ongoingFormatFilter, '1v1');
  assert(elements['chOngoingList'].innerHTML.includes('Solo Clash'), '1v1 filter should show Solo Clash');
  assert(!elements['chOngoingList'].innerHTML.includes('Group Clash'), '1v1 filter should hide Group Clash');

  // Filter Group
  sandbox.window.filterOngoingFormat('group');
  assert.strictEqual(sandbox.window.challengeState.ongoingFormatFilter, 'group');
  assert(elements['chOngoingList'].innerHTML.includes('Group Clash'), 'Group filter should show Group Clash');
  assert(!elements['chOngoingList'].innerHTML.includes('Solo Clash'), 'Group filter should hide Solo Clash');

  // Filter All
  sandbox.window.filterOngoingFormat('all');
  assert.strictEqual(sandbox.window.challengeState.ongoingFormatFilter, 'all');
  assert(elements['chOngoingList'].innerHTML.includes('Solo Clash') && elements['chOngoingList'].innerHTML.includes('Group Clash'), 'All filter should show both');

  // Test 23: Invitations Format Filter (All / 1v1 / Group)
  const mockIncoming = [
    { id: 501, title: 'Duel Inv', challenge_mode: '1V1', challenge_type: 'DISTANCE', challenger: { username: 'u1' } },
    { id: 502, title: 'Group Inv', challenge_mode: 'GROUP', challenge_type: 'DISTANCE', challenger: { username: 'u2' }, total_participants: 4 }
  ];
  sandbox.window.challengeState.invitations = mockIncoming;
  sandbox.window.challengeState.outgoingInvitations = [];

  sandbox.window.filterInvitationsFormat('1v1');
  assert(elements['chInvitationsList'].innerHTML.includes('Duel Inv'), '1v1 filter should show Duel Inv');
  assert(!elements['chInvitationsList'].innerHTML.includes('Group Inv'), '1v1 filter should hide Group Inv');

  sandbox.window.filterInvitationsFormat('group');
  assert(elements['chInvitationsList'].innerHTML.includes('Group Inv'), 'Group filter should show Group Inv');
  assert(!elements['chInvitationsList'].innerHTML.includes('Duel Inv'), 'Group filter should hide Duel Inv');

  sandbox.window.filterInvitationsFormat('all');
  assert(elements['chInvitationsList'].innerHTML.includes('Duel Inv') && elements['chInvitationsList'].innerHTML.includes('Group Inv'), 'All filter should show both');

  // Test 24: History Format Filter State
  sandbox.window.filterHistoryFormat('group');
  assert.strictEqual(sandbox.window.challengeState.historyFormatFilter, 'group', 'History format filter should be group');
  sandbox.window.filterHistoryFormat('1v1');
  assert.strictEqual(sandbox.window.challengeState.historyFormatFilter, '1v1', 'History format filter should be 1v1');

  // Test 25: CSS File Verification on Viewports (360px, 390px, 430px, 768px, 1280px)
  const cssPath = path.join(__dirname, '../../static/css/challenges.css');
  const cssContent = fs.readFileSync(cssPath, 'utf8');
  assert(cssContent.includes('.cb-format-filter-btn'), 'CSS should define .cb-format-filter-btn');
  assert(cssContent.includes('.cb-history-format-btn'), 'CSS should define .cb-history-format-btn');
  assert(cssContent.includes('.cb-runner-search-tray'), 'CSS should define .cb-runner-search-tray');
  assert(cssContent.includes('@media (max-width: 480px)'), 'CSS should define responsive styles for mobile viewports');
  assert(cssContent.includes('@media (min-width: 1200px)'), 'CSS should define desktop container centering');

  // Test 26: setBuilderMode updates UI and card titles dynamically
  sandbox.window.setBuilderMode('GROUP');
  assert.strictEqual(sandbox.window.challengeState.builder.mode, 'GROUP', 'Mode should be GROUP');
  assert.strictEqual(elements['cbGroupRunnersSection'].style.display, 'block', 'Group section should be visible');
  assert(elements['challengeBuilderModalTitle'].innerHTML.includes('Group Showdown'), 'Title should reflect Group Showdown');

  sandbox.window.setBuilderMode('1V1');
  assert.strictEqual(sandbox.window.challengeState.builder.mode, '1V1', 'Mode should be 1V1');
  assert.strictEqual(elements['cbGroupRunnersSection'].style.display, 'none', 'Group section should be hidden');

  // Test 27: addOpponentToGroupById adds runner safely to group
  sandbox.window.setBuilderMode('GROUP');
  const testPlayer = { id: 777, username: "special'user", display_name: "O'Connor", profile_emoji: "🏃" };
  sandbox.window.addOpponentToGroup(testPlayer);
  assert(sandbox.window.challengeState.builder.selectedOpponents.some(o => o.id === 777), 'Player 777 should be in selected opponents');
  assert(elements['cbSelectedChips'].innerHTML.includes("O'Connor"), 'Chips should render name with apostrophe correctly');

  // Test 28: CSRF Auto-refresh and retry on expiration
  let csrfAttempts = 0;
  sandbox.fetch = (url, options) => {
    if (url.includes('/api/csrf-token')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success', csrf_token: 'fresh-token-456' })
      });
    }
    if (url.includes('/test-csrf-post')) {
      csrfAttempts++;
      if (csrfAttempts === 1) {
        return Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ error: 'The CSRF token has expired.' })
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'success', retriedWith: options.headers['X-CSRFToken'] })
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success' }) });
  };

  sandbox.window.challengeApiPost('/test-csrf-post', { test: true }).then(({ res, data }) => {
    assert.strictEqual(csrfAttempts, 2, 'Should have retried the request after CSRF error');
    assert.strictEqual(data.status, 'success', 'Should succeed after retry');
    assert.strictEqual(data.retriedWith, 'fresh-token-456', 'Should have retried with fresh token');
    console.log(JSON.stringify({ success: true, testsPassed: 28 }));
  });
}, 100);
