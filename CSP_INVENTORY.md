# RunRush Content Security Policy (CSP) Inventory

**Generated:** Phase 0 AST & Regex Scan  
**Branch:** `chore/csp-enforcement`  

## Summary Metrics

- **Total Template Files Scanned:** 33
- **Inline Event Handlers (`on*`):** 212
- **Inline Executable `<script>` Tags:** 45
- **JSON Data Islands (`<script type="application/json">`):** 3
- **External `<script src="...">` Tags:** 47
- **Inline `<style>` Blocks:** 34
- **Inline `style="..."` Attributes:** 796
- **`javascript:` URLs:** 0
- **Distinct External Origins:** 5

## 1. External Origins & Assets

### `https://cdn.jsdelivr.net`
- `https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css`
- `https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js`
- `https://cdn.jsdelivr.net/npm/chart.js`

### `https://cdnjs.cloudflare.com`
- `https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css`
- `https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js`
- `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css`
- `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css`
- `https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js`

### `https://fonts.googleapis.com`
- `https://fonts.googleapis.com`
- `https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300;14..32,400;14..32,600;14..32,700;14..32,800&display=swap`
- `https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700;14..32,800&display=swap`
- `https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,800&display=swap`
- `https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,600;14..32,800&display=swap`
- `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap`
- `https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap`

### `https://fonts.gstatic.com`
- `https://fonts.gstatic.com`

### `https://unpkg.com`
- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css`
- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`

## 2. Inline Executable `<script>` Blocks (Total: 45)

| File | Line | Snippet / Tag |
|---|---|---|
| `templates/admin.html` | 720 | `<script>` |
| `templates/admin.html` | 779 | `<script>` |
| `templates/admin_notifications.html` | 235 | `<script>` |
| `templates/dev_design_system.html` | 221 | `<script>` |
| `templates/edit.html` | 406 | `<script>` |
| `templates/forgot_pin_reset.html` | 108 | `<script>` |
| `templates/forgot_pin_verify.html` | 82 | `<script>` |
| `templates/index.html` | 2096 | `<script>` |
| `templates/index.html` | 2304 | `<script>` |
| `templates/index.html` | 2771 | `<script>` |
| `templates/index.html` | 3372 | `<script>` |
| `templates/index.html` | 3820 | `<script>` |
| `templates/index.html` | 4845 | `<script>` |
| `templates/index.html` | 5140 | `<script>` |
| `templates/index.html` | 5319 | `<script>` |
| `templates/index.html` | 5361 | `<script>` |
| `templates/index.html` | 5479 | `<script>` |
| `templates/index.html` | 5626 | `<script>` |
| `templates/index.html` | 5851 | `<script>` |
| `templates/index.html` | 6283 | `<script>` |
| `templates/index.html` | 6287 | `<script>` |
| `templates/index.html` | 6388 | `<script>` |
| `templates/index.html` | 6549 | `<script>` |
| `templates/index.html` | 6639 | `<script>` |
| `templates/index.html` | 6658 | `<script>` |
| `templates/index.html` | 6875 | `<script>` |
| `templates/index.html` | 8549 | `<script>` |
| `templates/index.html` | 9407 | `<script>` |
| `templates/index.html` | 9488 | `<script>` |
| `templates/index.html` | 9638 | `<script>` |
| `templates/index.html` | 9955 | `<script>` |
| `templates/index.html` | 9987 | `<script>` |
| `templates/index.html` | 10087 | `<script>` |
| `templates/landing.html` | 22 | `<script>` |
| `templates/login.html` | 190 | `<script>` |
| `templates/offline.html` | 269 | `<script>` |
| `templates/onboarding.html` | 558 | `<script>` |
| `templates/partials/_coming_soon_modal.html` | 179 | `<script>` |
| `templates/partials/_quick_actions_fab.html` | 325 | `<script>` |
| `templates/partials/_theme_init.html` | 20 | `<script>` |
| `templates/public_profile.html` | 124 | `<script>` |
| `templates/register.html` | 187 | `<script>` |
| `templates/settings.html` | 575 | `<script>` |
| `templates/settings.html` | 929 | `<script>` |
| `templates/settings.html` | 1121 | `<script>` |

## 3. JSON Data Islands (`<script type="application/json">`) (Total: 3)

| File | Line | Tag |
|---|---|---|
| `templates/index.html` | 4818 | `<script id="pbRunIdsData" type="application/json">` |
| `templates/index.html` | 4821 | `<script id="userData" type="application/json">` |
| `templates/index.html` | 8125 | `<script id="runs-data-json" type="application/json">` |

## 4. Inline `<style>` Blocks (Total: 34)

| File | Line | Snippet / Tag |
|---|---|---|
| `templates/403.html` | 19 | `<style>` |
| `templates/admin.html` | 29 | `<style>` |
| `templates/admin.html` | 708 | `<style>` |
| `templates/admin_notifications.html` | 13 | `<style>` |
| `templates/dev_design_system.html` | 14 | `<style>` |
| `templates/edit.html` | 24 | `<style>` |
| `templates/forgot_pin.html` | 15 | `<style>` |
| `templates/forgot_pin_methods.html` | 15 | `<style>` |
| `templates/forgot_pin_reset.html` | 15 | `<style>` |
| `templates/forgot_pin_verify.html` | 15 | `<style>` |
| `templates/index.html` | 43 | `<style>` |
| `templates/index.html` | 2372 | `<style>` |
| `templates/index.html` | 2391 | `<style>` |
| `templates/index.html` | 2531 | `<style>` |
| `templates/index.html` | 2911 | `<style>` |
| `templates/index.html` | 3447 | `<style>` |
| `templates/index.html` | 4496 | `<style>` |
| `templates/index.html` | 7341 | `<style>` |
| `templates/index.html` | 10265 | `<style>` |
| `templates/leaderboard.html` | 31 | `<style>` |
| `templates/monthly_report.html` | 7 | `<style>` |
| `templates/offline.html` | 25 | `<style>` |
| `templates/onboarding.html` | 15 | `<style>` |
| `templates/partials/_auth_light.html` | 3 | `<style> blocks are dark-only with hard-coded` |
| `templates/partials/_auth_light.html` | 5 | `<style> block, with partials/_theme_init.html` |
| `templates/partials/_auth_light.html` | 9 | `<style>` |
| `templates/partials/_coming_soon_modal.html` | 19 | `<style>` |
| `templates/partials/_design_system_links.html` | 3 | `<style> block so` |
| `templates/partials/_design_system_links.html` | 9 | `<style> /* page-specific styles */ </style>` |
| `templates/partials/_quick_actions_fab.html` | 54 | `<style>` |
| `templates/partials/_rumi_chat_modal.html` | 102 | `<style>` |
| `templates/public_profile.html` | 25 | `<style>` |
| `templates/set_pin.html` | 10 | `<style>` |
| `templates/settings.html` | 19 | `<style>` |

## 5. Inline Event Handlers (`on*`) (Total: 212)

| File | Line | Event | Handler Expression |
|---|---|---|---|
| `templates/admin.html` | 462 | `onclick` | `openUserAnalytics({{ u.id }}, '{{ u.username }}'); return false;` |
| `templates/admin.html` | 467 | `onclick` | `confirmAction('block', {{ u.id }}, '{{ u.username }}')` |
| `templates/admin.html` | 471 | `onclick` | `confirmAction('unblock', {{ u.id }}, '{{ u.username }}')` |
| `templates/admin.html` | 480 | `onclick` | `confirmAction('promote', {{ u.id }}, '{{ u.username }}')` |
| `templates/admin.html` | 485 | `onclick` | `confirmAction('demote', {{ u.id }}, '{{ u.username }}')` |
| `templates/admin.html` | 492 | `onclick` | `confirmAction('delete', {{ u.id }}, '{{ u.username }}')` |
| `templates/admin.html` | 518 | `onclick` | `sendWeeklyEmails()` |
| `templates/admin.html` | 522 | `onclick` | `sendMonthlyEmails()` |
| `templates/admin.html` | 605 | `onclick` | `closeAnalytics(event)` |
| `templates/admin.html` | 620 | `onclick` | `closeAnalytics()` |
| `templates/components/challenges_section.html` | 15 | `onclick` | `openChallengeBuilder(null, 'GROUP')` |
| `templates/components/challenges_section.html` | 18 | `onclick` | `switchChallengeTab('discover')` |
| `templates/components/challenges_section.html` | 52 | `onclick` | `switchChallengeTab('discover')` |
| `templates/components/challenges_section.html` | 56 | `onclick` | `switchChallengeTab('invitations')` |
| `templates/components/challenges_section.html` | 61 | `onclick` | `switchChallengeTab('ongoing')` |
| `templates/components/challenges_section.html` | 65 | `onclick` | `switchChallengeTab('history')` |
| `templates/components/challenges_section.html` | 79 | `onclick` | `clearPlayerSearch()` |
| `templates/components/challenges_section.html` | 89 | `onclick` | `changePlayerSearchPage(-1)` |
| `templates/components/challenges_section.html` | 93 | `onclick` | `changePlayerSearchPage(1)` |
| `templates/components/challenges_section.html` | 103 | `onclick` | `filterInvitationsFormat('all', this)` |
| `templates/components/challenges_section.html` | 104 | `onclick` | `filterInvitationsFormat('1v1', this)` |
| `templates/components/challenges_section.html` | 105 | `onclick` | `filterInvitationsFormat('group', this)` |
| `templates/components/challenges_section.html` | 120 | `onclick` | `filterOngoingFormat('all', this)` |
| `templates/components/challenges_section.html` | 121 | `onclick` | `filterOngoingFormat('1v1', this)` |
| `templates/components/challenges_section.html` | 122 | `onclick` | `filterOngoingFormat('group', this)` |
| `templates/components/challenges_section.html` | 139 | `onclick` | `filterChallengeHistory('all', this)` |
| `templates/components/challenges_section.html` | 140 | `onclick` | `filterChallengeHistory('completed', this)` |
| `templates/components/challenges_section.html` | 141 | `onclick` | `filterChallengeHistory('declined', this)` |
| `templates/components/challenges_section.html` | 142 | `onclick` | `filterChallengeHistory('expired', this)` |
| `templates/components/challenges_section.html` | 143 | `onclick` | `filterChallengeHistory('cancelled', this)` |
| `templates/components/challenges_section.html` | 148 | `onclick` | `filterHistoryFormat('all', this)` |
| `templates/components/challenges_section.html` | 149 | `onclick` | `filterHistoryFormat('1v1', this)` |
| `templates/components/challenges_section.html` | 150 | `onclick` | `filterHistoryFormat('group', this)` |
| `templates/components/challenges_section.html` | 163 | `onclick` | `changeHistoryPage(-1)` |
| `templates/components/challenges_section.html` | 167 | `onclick` | `changeHistoryPage(1)` |
| `templates/components/challenges_section.html` | 203 | `onclick` | `setBuilderMode('1V1')` |
| `templates/components/challenges_section.html` | 206 | `onclick` | `setBuilderMode('GROUP')` |
| `templates/components/challenges_section.html` | 231 | `oninput` | `onBuilderRunnerSearch(this.value)` |
| `templates/components/challenges_section.html` | 231 | `onfocus` | `onBuilderRunnerSearch(this.value)` |
| `templates/components/challenges_section.html` | 231 | `onclick` | `onBuilderRunnerSearch(this.value)` |
| `templates/components/challenges_section.html` | 247 | `onclick` | `selectChallengeType('DISTANCE', this)` |
| `templates/components/challenges_section.html` | 259 | `onclick` | `selectChallengeType('CONSISTENCY', this)` |
| `templates/components/challenges_section.html` | 271 | `onclick` | `selectChallengeType('LONGEST', this)` |
| `templates/components/challenges_section.html` | 283 | `onclick` | `selectChallengeType('DAILY', this)` |
| `templates/components/challenges_section.html` | 305 | `onclick` | `applyDurationPreset(7, this)` |
| `templates/components/challenges_section.html` | 306 | `onclick` | `applyDurationPreset(14, this)` |
| `templates/components/challenges_section.html` | 307 | `onclick` | `applyDurationPreset(30, this)` |
| `templates/components/challenges_section.html` | 308 | `onclick` | `applyDurationPreset('custom', this)` |
| `templates/components/challenges_section.html` | 314 | `onchange` | `onDateInputChange()` |
| `templates/components/challenges_section.html` | 318 | `onchange` | `onDateInputChange()` |
| `templates/components/challenges_section.html` | 327 | `onchange` | `onDailyDateInputChange()` |
| `templates/components/challenges_section.html` | 407 | `onclick` | `navigateChallengeStep(-1)` |
| `templates/components/challenges_section.html` | 412 | `onclick` | `navigateChallengeStep(1)` |
| `templates/components/challenges_section.html` | 415 | `onclick` | `submitChallengeForm()` |
| `templates/components/challenges_section.html` | 439 | `onclick` | `dismissInvitationPopup()` |
| `templates/components/challenges_section.html` | 477 | `onclick` | `respondToPopupInvitation('reject')` |
| `templates/components/challenges_section.html` | 480 | `onclick` | `respondToPopupInvitation('accept')` |
| `templates/components/challenges_section.html` | 485 | `onclick` | `navigatePopupInvitation(-1)` |
| `templates/components/challenges_section.html` | 488 | `onclick` | `dismissInvitationPopup()` |
| `templates/components/challenges_section.html` | 491 | `onclick` | `navigatePopupInvitation(1)` |
| `templates/components/challenges_section.html` | 563 | `onclick` | `dismissChallengesUpdateModal()` |
| `templates/components/challenges_section.html` | 617 | `onclick` | `exploreChallengesFromUpdateModal()` |
| `templates/components/challenges_section.html` | 620 | `onclick` | `dismissChallengesUpdateModal()` |
| `templates/forgot_pin_reset.html` | 70 | `onclick` | `"` |
| `templates/forgot_pin_reset.html` | 87 | `onclick` | `"` |
| `templates/index.html` | 2092 | `onclick` | `dismissFlash(this.parentElement)` |
| `templates/index.html` | 2130 | `onclick` | `switchTab('home', this)` |
| `templates/index.html` | 2133 | `onclick` | `switchTab('runs', this)` |
| `templates/index.html` | 2136 | `onclick` | `switchTab('leaderboard', this)` |
| `templates/index.html` | 2139 | `onclick` | `switchTab('analytics', this)` |
| `templates/index.html` | 2142 | `onclick` | `switchTab('challenges', this)` |
| `templates/index.html` | 2201 | `onclick` | `markAllAsRead(event)` |
| `templates/index.html` | 2233 | `onclick` | `syncNow()` |
| `templates/index.html` | 2258 | `onclick` | `event.preventDefault(); drawerGo('profile');` |
| `templates/index.html` | 2277 | `onclick` | `drawerGo('follows')` |
| `templates/index.html` | 2289 | `onclick` | `drawerGo('help')` |
| `templates/index.html` | 2297 | `onclick` | `window.triggerInstallPrompt && window.triggerInstallPrompt()` |
| `templates/index.html` | 2745 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 2766 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 2797 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 2804 | `onclick` | `event.stopPropagation(); switchTab('leaderboard', document.querySelector('.tab-nav-item[data-tab=&quot;leaderboard&quot;]'));` |
| `templates/index.html` | 2835 | `onclick` | `toggleGoalEdit(event)` |
| `templates/index.html` | 2851 | `onclick` | `saveWeeklyGoal()` |
| `templates/index.html` | 3289 | `onclick` | `dismissLogRunIntro()` |
| `templates/index.html` | 3345 | `onclick` | `openImportTab('screenshot')` |
| `templates/index.html` | 3852 | `onclick` | `drawerGo(\'help\')` |
| `templates/index.html` | 3883 | `onclick` | `openImportTab('csv')` |
| `templates/index.html` | 3954 | `onclick` | `toggleStopwatch()` |
| `templates/index.html` | 4050 | `onclick` | `document.getElementById('wpTakeInput').click()` |
| `templates/index.html` | 4053 | `onclick` | `document.getElementById('wpUploadInput').click()` |
| `templates/index.html` | 4057 | `onchange` | `handleWatchPhotoSelected(this)` |
| `templates/index.html` | 4058 | `onchange` | `handleWatchPhotoSelected(this)` |
| `templates/index.html` | 4063 | `onmouseover` | `this.style.opacity=1` |
| `templates/index.html` | 4063 | `onmouseout` | `this.style.opacity=0.85` |
| `templates/index.html` | 4145 | `onclick` | `resetWatchPhotoModal()` |
| `templates/index.html` | 4156 | `onclick` | `resetWatchPhotoModal()` |
| `templates/index.html` | 4161 | `onclick` | `uploadAndParseWatchPhoto()` |
| `templates/index.html` | 4164 | `onclick` | `confirmWatchPhotoImport()` |
| `templates/index.html` | 4211 | `onclick` | `if(event.target.id !== 'stravaCsvInput') document.getElementById('stravaCsvInput').click()` |
| `templates/index.html` | 4215 | `onchange` | `handleCsvFileSelected(this)` |
| `templates/index.html` | 4272 | `onclick` | `resetImportModal()` |
| `templates/index.html` | 4277 | `onclick` | `uploadAndParseCsv()` |
| `templates/index.html` | 4280 | `onclick` | `confirmBatchImport()` |
| `templates/index.html` | 4318 | `onclick` | `if(event.target.id !== 'screenshotInput') document.getElementById('screenshotInput').click()` |
| `templates/index.html` | 4322 | `onchange` | `handleScreenshotSelected(this)` |
| `templates/index.html` | 4329 | `onmouseover` | `this.style.opacity=1` |
| `templates/index.html` | 4329 | `onmouseout` | `this.style.opacity=0.85` |
| `templates/index.html` | 4415 | `onclick` | `resetScreenshotModal()` |
| `templates/index.html` | 4426 | `onclick` | `resetScreenshotModal()` |
| `templates/index.html` | 4431 | `onclick` | `uploadAndParseScreenshot()` |
| `templates/index.html` | 4434 | `onclick` | `confirmScreenshotImport()` |
| `templates/index.html` | 4608 | `onclick` | `shiftMonth(-1)` |
| `templates/index.html` | 4609 | `onclick` | `openGoalModal()` |
| `templates/index.html` | 4610 | `onclick` | `shiftMonth(1)` |
| `templates/index.html` | 4613 | `onclick` | `openGoalModal()` |
| `templates/index.html` | 4661 | `onclick` | `toggleRunCard('{{ r['id'] }}')` |
| `templates/index.html` | 4700 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 4707 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 4762 | `onclick` | `'openShareCard({{` |
| `templates/index.html` | 4783 | `onclick` | `viewRunRoute({{ r['id'] }})` |
| `templates/index.html` | 4801 | `onclick` | `handleDeleteClick(this)` |
| `templates/index.html` | 4814 | `onclick` | `loadMoreRuns()` |
| `templates/index.html` | 4835 | `onclick` | `goToLogRun()` |
| `templates/index.html` | 6621 | `onclick` | `()` |
| `templates/index.html` | 7904 | `onclick` | `toggleHeatmapInfo(event)` |
| `templates/index.html` | 7949 | `onclick` | `loadProgressData('week', this)` |
| `templates/index.html` | 7951 | `onclick` | `loadProgressData('month', this)` |
| `templates/index.html` | 7953 | `onclick` | `loadProgressData('year', this)` |
| `templates/index.html` | 8050 | `onclick` | `toggleAcwrInfo(event)` |
| `templates/index.html` | 8094 | `onclick` | `switchAchievementTab('personalBests')` |
| `templates/index.html` | 8095 | `onclick` | `switchAchievementTab('badges')` |
| `templates/index.html` | 8096 | `onclick` | `switchAchievementTab('challenges')` |
| `templates/index.html` | 8097 | `onclick` | `switchAchievementTab('personalGoals')` |
| `templates/index.html` | 8157 | `onclick` | `showGoalBuilder()` |
| `templates/index.html` | 8341 | `onclick` | `if(event.target===this)closeShareCard()` |
| `templates/index.html` | 8348 | `onclick` | `downloadShareCard()` |
| `templates/index.html` | 8351 | `onclick` | `shareShareCard()` |
| `templates/index.html` | 8354 | `onclick` | `closeShareCard()` |
| `templates/index.html` | 8518 | `onclick` | `switchTab('home', this)` |
| `templates/index.html` | 8524 | `onclick` | `switchTab('runs', this)` |
| `templates/index.html` | 8530 | `onclick` | `switchTab('leaderboard', this)` |
| `templates/index.html` | 8536 | `onclick` | `switchTab('analytics', this)` |
| `templates/index.html` | 8542 | `onclick` | `switchTab('challenges', this)` |
| `templates/index.html` | 8719 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 8725 | `onclick` | `event.stopPropagation()` |
| `templates/index.html` | 8750 | `onclick` | `openShareCard(${shareJson})` |
| `templates/index.html` | 8760 | `onclick` | `handleDeleteClick(this)` |
| `templates/index.html` | 9981 | `onclick` | `saveMonthlyGoal()` |
| `templates/index.html` | 10044 | `onclick` | `openGoalModal(); event.stopPropagation();` |
| `templates/index.html` | 10202 | `onclick` | `()` |
| `templates/login.html` | 60 | `onclick` | `document.getElementById('dbNoticeBanner').style.display='none';sessionStorage.setItem('db_notice_dismissed','1');` |
| `templates/login.html` | 127 | `onclick` | `togglePinVisibility()` |
| `templates/login.html` | 163 | `onclick` | `showComingSoonModal()` |
| `templates/offline.html` | 251 | `onclick` | `saveOffline()` |
| `templates/onboarding.html` | 446 | `onclick` | `nextStep()` |
| `templates/onboarding.html` | 550 | `onclick` | `prevStep()` |
| `templates/onboarding.html` | 551 | `onclick` | `submitForm()` |
| `templates/partials/_coming_soon_modal.html` | 3 | `onclick` | `handleComingSoonBackdrop(event)` |
| `templates/partials/_coming_soon_modal.html` | 4 | `onclick` | `event.stopPropagation()` |
| `templates/partials/_coming_soon_modal.html` | 5 | `onclick` | `closeComingSoonModal()` |
| `templates/partials/_coming_soon_modal.html` | 13 | `onclick` | `closeComingSoonModal()` |
| `templates/partials/_live_run_modal.html` | 6 | `onclick` | `closeLiveRunTracker()` |
| `templates/partials/_live_run_modal.html` | 39 | `onclick` | `startLiveRun()` |
| `templates/partials/_live_run_modal.html` | 42 | `onclick` | `toggleLiveRunPause()` |
| `templates/partials/_live_run_modal.html` | 45 | `onclick` | `finishLiveRun()` |
| `templates/partials/_live_run_modal.html` | 75 | `onclick` | `saveLiveRun()` |
| `templates/partials/_live_run_modal.html` | 78 | `onclick` | `discardLiveRun()` |
| `templates/partials/_quick_actions_fab.html` | 2 | `onclick` | `toggleQuickActions(false)` |
| `templates/partials/_quick_actions_fab.html` | 10 | `onclick` | `handleQuickAction('rumi')` |
| `templates/partials/_quick_actions_fab.html` | 22 | `onclick` | `handleQuickAction('live')` |
| `templates/partials/_quick_actions_fab.html` | 30 | `onclick` | `handleQuickAction('voice')` |
| `templates/partials/_quick_actions_fab.html` | 38 | `onclick` | `handleQuickAction('manual')` |
| `templates/partials/_quick_actions_fab.html` | 45 | `onclick` | `toggleQuickActions()` |
| `templates/partials/_quick_actions_fab.html` | 48 | `onerror` | `this.src='/static/icons/icon-192.png'` |
| `templates/partials/_rumi_chat_modal.html` | 26 | `onclick` | `clearRumiChat()` |
| `templates/partials/_rumi_chat_modal.html` | 51 | `onclick` | `askRumiSuggested(this)` |
| `templates/partials/_rumi_chat_modal.html` | 52 | `onclick` | `askRumiSuggested(this)` |
| `templates/partials/_rumi_chat_modal.html` | 53 | `onclick` | `askRumiSuggested(this)` |
| `templates/partials/_rumi_chat_modal.html` | 54 | `onclick` | `askRumiSuggested(this)` |
| `templates/partials/_rumi_chat_modal.html` | 55 | `onclick` | `askRumiSuggested(this)` |
| `templates/partials/_rumi_chat_modal.html` | 77 | `onclick` | `retryLastRumiMessage()` |
| `templates/partials/_rumi_chat_modal.html` | 83 | `onsubmit` | `submitRumiChat(event)` |
| `templates/partials/_rumi_chat_modal.html` | 85 | `onkeydown` | `handleRumiInputKey(event)` |
| `templates/partials/_rumi_chat_modal.html` | 85 | `oninput` | `autoResizeRumiInput(this)` |
| `templates/partials/_voice_modal.html` | 14 | `onclick` | `startVoice()` |
| `templates/partials/_voice_modal.html` | 37 | `onclick` | `useManualValues()` |
| `templates/partials/_voice_modal.html` | 49 | `onclick` | `confirmVoiceLog()` |
| `templates/register.html` | 60 | `onclick` | `document.getElementById('dbNoticeBanner').style.display='none';sessionStorage.setItem('db_notice_dismissed','1');` |
| `templates/register.html` | 133 | `onclick` | `togglePinVisibility()` |
| `templates/register.html` | 169 | `onclick` | `showComingSoonModal()` |
| `templates/settings.html` | 436 | `onclick` | `toggleMobileMenu()` |
| `templates/settings.html` | 439 | `onclick` | `switchTab('profile')` |
| `templates/settings.html` | 442 | `onclick` | `switchTab('appearance')` |
| `templates/settings.html` | 445 | `onclick` | `switchTab('notifications')` |
| `templates/settings.html` | 448 | `onclick` | `switchTab('weather')` |
| `templates/settings.html` | 451 | `onclick` | `switchTab('security')` |
| `templates/settings.html` | 454 | `onclick` | `switchTab('app')` |
| `templates/settings.html` | 457 | `onclick` | `switchTab('data')` |
| `templates/settings.html` | 460 | `onclick` | `switchTab('danger')` |
| `templates/settings.html` | 512 | `onsubmit` | `saveSettings(event, '/settings/update', 'Profile updated')` |
| `templates/settings.html` | 609 | `onclick` | `selectTheme('system')` |
| `templates/settings.html` | 617 | `onclick` | `selectTheme('dark')` |
| `templates/settings.html` | 625 | `onclick` | `selectTheme('light')` |
| `templates/settings.html` | 645 | `onsubmit` | `saveSettings(event, '/settings/email', 'Notification preferences saved')` |
| `templates/settings.html` | 725 | `onsubmit` | `saveSettings(event, '/settings/location', 'Location updated')` |
| `templates/settings.html` | 742 | `onclick` | `clearLocation()` |
| `templates/settings.html` | 773 | `onsubmit` | `saveSettings(event, '/settings/recovery-email', 'Verification email sent')` |
| `templates/settings.html` | 810 | `onsubmit` | `return confirm('Are you sure you want to disconnect your Google account?');` |
| `templates/settings.html` | 836 | `onclick` | `installApp()` |
| `templates/settings.html` | 866 | `onclick` | `deleteAllGpsData()` |
| `templates/settings.html` | 904 | `onsubmit` | `return confirm('WARNING: This will delete ALL your logged runs permanently. This cannot be undone. Continue?');` |
| `templates/settings.html` | 915 | `onsubmit` | `return confirm('CRITICAL WARNING: This will delete your ENTIRE account and ALL data permanently. Continue?');` |

## 6. Inline `style="..."` Attributes by File (Total: 796)

| File | Style Attribute Count |
|---|---|
| `templates/index.html` | 425 |
| `templates/components/challenges_section.html` | 90 |
| `templates/admin.html` | 62 |
| `templates/settings.html` | 46 |
| `templates/partials/_live_run_modal.html` | 37 |
| `templates/leaderboard.html` | 23 |
| `templates/components/profile_content.html` | 19 |
| `templates/dev_design_system.html` | 18 |
| `templates/onboarding.html` | 18 |
| `templates/partials/components/profile_content.html` | 18 |
| `templates/partials/_route_view_modal.html` | 7 |
| `templates/public_profile.html` | 7 |
| `templates/set_pin.html` | 6 |
| `templates/admin_notifications.html` | 5 |
| `templates/partials/_quick_actions_fab.html` | 4 |
| `templates/forgot_pin_methods.html` | 3 |
| `templates/partials/_rumi_chat_modal.html` | 2 |
| `templates/edit.html` | 1 |
| `templates/forgot_pin.html` | 1 |
| `templates/login.html` | 1 |
| `templates/partials/_auth_light.html` | 1 |
| `templates/partials/_voice_modal.html` | 1 |
| `templates/register.html` | 1 |

