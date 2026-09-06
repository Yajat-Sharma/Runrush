const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  // Inject Flask session cookie directly — bypass login entirely
  await context.addCookies([{
    name: 'session',
    value: 'eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6IllhamF0In0.apxohg.HiagKsXtdg1l1Al3CmXb7mHMnTc',
    domain: '127.0.0.1',
    path: '/',
    httpOnly: false,
    secure: false,
  }]);

  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') process.stdout.write('PAGE ERROR: ' + msg.text() + '\n');
  });

  // Load main app page
  console.log('Loading main page with injected session...');
  await page.goto('http://127.0.0.1:5000/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(800);
  console.log('URL:', page.url());

  // Check if we're logged in (not redirected to login)
  const isLoggedIn = !page.url().includes('/login');
  console.log('Logged in:', isLoggedIn);

  // Force analyticsView visible and trigger heatmap fetch
  await page.evaluate(() => {
    // Show analytics tab
    ['homeView', 'runsView', 'leaderboardView', 'analyticsView', 'achievementsView'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = id === 'analyticsView' ? 'block' : 'none';
    });
    // Also click any analytics tab button to trigger the tab switch logic
    const analyticsBtn = document.querySelector('[data-tab="analytics"]');
    if (analyticsBtn) analyticsBtn.click();
  });

  // Wait for heatmap API fetch to complete and DOM to populate
  console.log('Waiting for heatmap to populate...');
  try {
    await page.waitForFunction(() => document.querySelectorAll('.heatmap-cell').length > 0, { timeout: 8000 });
  } catch(e) {
    console.log('Timed out waiting for cells. Current cell count:', 
      await page.$$eval('.heatmap-cell', els => els.length).catch(() => 0));
  }

  const cellCount = await page.$$eval('.heatmap-cell', els => els.length).catch(() => 0);
  const weekCount = await page.$$eval('.heatmap-week', els => els.length).catch(() => 0);
  console.log(`Heatmap populated: ${cellCount} cells, ${weekCount} weeks`);

  // Scroll heatmap into view
  await page.evaluate(() => {
    const el = document.getElementById('heatmapSection');
    if (el) el.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  await page.waitForTimeout(200);

  // ── COMPUTED STYLES ──────────────────────────────────────────────────────────
  const styles = await page.evaluate(() => {
    function info(sel, label) {
      const el = document.querySelector(sel);
      if (!el) return { label, error: 'NOT FOUND in DOM' };
      const cs = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return {
        label,
        // KEY properties to verify fix
        display:       cs.display,
        flexShrink:    cs.flexShrink,
        flexGrow:      cs.flexGrow,
        flexBasis:     cs.flexBasis,
        width:         cs.width,
        height:        cs.height,
        minWidth:      cs.minWidth,
        overflowX:     cs.overflowX,
        flexDirection: cs.flexDirection,
        flexWrap:      cs.flexWrap,
        // Actual rendered dimensions
        rectW: Math.round(rect.width * 10) / 10,
        rectH: Math.round(rect.height * 10) / 10,
        childCount: el.children.length,
      };
    }

    const analyticsView = document.getElementById('analyticsView');
    return {
      analyticsViewDisplay: analyticsView ? window.getComputedStyle(analyticsView).display : 'NOT FOUND',
      scrollContainer: info('.heatmap-scroll-container', '.heatmap-scroll-container'),
      grid:            info('.heatmap-grid',             '.heatmap-grid'),
      week:            info('.heatmap-week',             '.heatmap-week [first]'),
      cell:            info('.heatmap-cell',             '.heatmap-cell [first]'),
      weekCount:       document.querySelectorAll('.heatmap-week').length,
      cellCount:       document.querySelectorAll('.heatmap-cell').length,
    };
  });

  console.log('\n╔══════════════════════════════════════════════════════╗');
  console.log('║        ACTUAL COMPUTED STYLES — LIVE BROWSER         ║');
  console.log('╚══════════════════════════════════════════════════════╝\n');
  console.log(JSON.stringify(styles, null, 2));

  // Diagnose
  console.log('\n── DIAGNOSIS ──');
  const cell = styles.cell;
  const week = styles.week;
  const grid = styles.grid;
  const sc = styles.scrollContainer;
  if (!cell.error) {
    console.log(`cell.width (computed): ${cell.width} | cell.rectW (rendered): ${cell.rectW}px`);
    console.log(`cell.flexShrink: ${cell.flexShrink}  (should be 0)`);
    console.log(`week.width (computed): ${week.width} | week.rectW: ${week.rectW}px`);
    console.log(`week.flexBasis: ${week.flexBasis}  (should be 12px)`);
    console.log(`grid.display: ${grid.display}  (should be inline-flex)`);
    console.log(`scrollContainer.width: ${sc.width} | rectW: ${sc.rectW}px`);
    console.log(`scrollContainer.display: ${sc.display}  (should be block)`);
    
    const cellOk = Math.round(cell.rectW) === 12;
    const weekOk = Math.round(week.rectW) === 12;
    console.log(`\n✓ Cell is 12px wide: ${cellOk}`);
    console.log(`✓ Week is 12px wide: ${weekOk}`);
    console.log(`✓ Grid is inline-flex: ${grid.display === 'inline-flex'}`);
  } else {
    console.log('ERROR: Heatmap elements NOT found in DOM. Check if user is authenticated.');
  }

  // ── SCREENSHOT ───────────────────────────────────────────────────────────────
  const clip = await page.evaluate(() => {
    const el = document.getElementById('heatmapSection');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.max(0, r.x - 4), y: Math.max(0, r.y - 4), width: r.width + 8, height: r.height + 8 };
  });

  const shotPath = 'd:/Programming codes/Running-py/scratch/heatmap_after_fix.png';
  if (clip && clip.width > 0 && clip.height > 0) {
    await page.screenshot({ path: shotPath, clip });
    console.log('\n📸 Screenshot saved (heatmap section only):', shotPath);
    console.log(`   Dimensions: ${Math.round(clip.width)}x${Math.round(clip.height)}px`);
  } else {
    await page.screenshot({ path: shotPath });
    console.log('\n📸 Full-page screenshot saved (heatmap section not found for clip):', shotPath);
  }

  await browser.close();
})();
