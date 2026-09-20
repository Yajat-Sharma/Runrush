
  // ──────────────────────────────────────────────
  // FEATURE 3: MOTIVATIONAL QUOTE OF THE DAY
  // ──────────────────────────────────────────────
  const QUOTES = [
    { text: "The miracle isn't that I finished. The miracle is that I had the courage to start.", author: "– John Bingham" },
    { text: "Run when you can, walk if you have to, crawl if you must; just never give up.", author: "– Dean Karnazes" },
    { text: "Most people never run far enough on their first wind to find out they've got a second.", author: "– William James" },
    { text: "If you run, you are a runner. It doesn't matter how fast or how far.", author: "– John Bingham" },
    { text: "Pain is inevitable. Suffering is optional.", author: "– Haruki Murakami" },
    { text: "The obsession with running is really an obsession with the potential for more and more life.", author: "– George Sheehan" },
    { text: "Every morning in Africa, a gazelle wakes up knowing it must run faster than the fastest lion.", author: "– African Proverb" },
    { text: "Running is the greatest metaphor for life, because you get out of it what you put into it.", author: "– Oprah Winfrey" },
    { text: "Ask yourself: Can I give more? The answer is usually: Yes.", author: "– Paul Tergat" },
    { text: "It's very hard in the beginning to understand that the whole idea is not to beat the other runners... Eventually you learn that the competition is against the little voice inside you.", author: "– George Sheehan" },
    { text: "Running is nothing more than a series of arguments between the part of your brain that wants to stop and the part that wants to keep going.", author: "– Anonymous" },
    { text: "Don't dream of winning, train for it!", author: "– Mo Farah" },
    { text: "Your body will argue that there is no justifiable reason to continue. Your only recourse is to call on your spirit.", author: "– Tim Noakes" },
    { text: "If you're tired of starting over, stop giving up.", author: "– Anonymous" },
    { text: "The road to victory is paved with miles.", author: "– Anonymous" },
    { text: "Believe that you can run farther or faster. Believe that you're young enough, old enough, strong enough.", author: "– John Bingham" },
    { text: "Champions are not made in gyms. Champions are made from something they have deep inside them — a desire, a dream, a vision.", author: "– Muhammad Ali" },
    { text: "You don't have to go fast. You just have to go.", author: "– Anonymous" },
    { text: "Strive for progress, not perfection.", author: "– Anonymous" },
    { text: "The only bad run is the one that didn't happen.", author: "– Anonymous" },
  ];

  (function initQuote() {
    const today = new Date().toDateString();
    const idx = [...today].reduce((acc, c) => acc + c.charCodeAt(0), 0) % QUOTES.length;
    const q = QUOTES[idx];
    document.getElementById('quoteText').textContent = '\u201c' + q.text + '\u201d';
    document.getElementById('quoteAuthor').textContent = q.author;
    if (document.getElementById('drawerQuoteText')) {
      document.getElementById('drawerQuoteText').textContent = '\u201c' + q.text + '\u201d';
      document.getElementById('drawerQuoteAuthor').textContent = q.author;
    }
  })();

  // ──────────────────────────────────────────────
  // FEATURE 6: LIVE STOPWATCH
  // ──────────────────────────────────────────────
  let swInterval = null;
  let swRunning = false;
  let swSeconds = 0;

  function toggleStopwatch() {
    const btn = document.getElementById('swToggleBtn');
    const panel = document.getElementById('swPanel');
    const minutesInput = document.getElementById('minutes');

    if (!swRunning) {
      // Start
      swRunning = true;
      swSeconds = 0;
      panel.style.display = 'block';
      btn.textContent = 'Stop Timer';
      btn.style.borderColor = 'rgba(255,107,107,0.5)';
      btn.style.color = '#ff6b6b';
      swInterval = setInterval(() => {
        swSeconds++;
        const mm = String(Math.floor(swSeconds / 60)).padStart(2, '0');
        const ss = String(swSeconds % 60).padStart(2, '0');
        document.getElementById('swDisplay').textContent = mm + ':' + ss;
      }, 1000);
    } else {
      // Stop
      swRunning = false;
      clearInterval(swInterval);
      btn.textContent = 'Start Timer';
      btn.style.borderColor = '';
      btn.style.color = '';
      // Auto-fill minutes field
      const mins = (swSeconds / 60).toFixed(2);
      if (minutesInput) {
        minutesInput.value = mins;
        minutesInput.dispatchEvent(new Event('input'));
      }
    }
  }

  // Reset stopwatch when modal closes
  document.getElementById('addRunModal')?.addEventListener('hidden.bs.modal', () => {
    if (swRunning) toggleStopwatch();
    swSeconds = 0;
    document.getElementById('swDisplay').textContent = '00:00';
    document.getElementById('swPanel').style.display = 'none';
  });

  // ──────────────────────────────────────────────
  // FEATURE 4: GITHUB-STYLE HEATMAP
  // ──────────────────────────────────────────────
  function buildHeatmap(days) {
    const grid = document.getElementById('heatmapGrid');
    const monthsEl = document.getElementById('heatmapMonths');
    if (!grid) return;
    grid.innerHTML = '';
    monthsEl.innerHTML = '';

    // Pad so first day aligns to Sunday=0
    const firstDate = new Date(days[0].date + 'T00:00:00');
    const firstDow = firstDate.getDay(); // Sun=0

    let week = document.createElement('div');
    week.className = 'heatmap-week';

    // Empty cells before first day
    for (let i = 0; i < firstDow; i++) {
      const empty = document.createElement('div');
      empty.className = 'heatmap-cell';
      empty.style.visibility = 'hidden';
      week.appendChild(empty);
    }

    let weekNum = 0;
    let lastMonth = -1;
    const monthLabels = [];

    days.forEach((d, i) => {
      const dt = new Date(d.date + 'T00:00:00');
      const dow = dt.getDay(); // Sun=0

      // Month label tracking
      if (dt.getMonth() !== lastMonth) {
        monthLabels.push({ weekIdx: weekNum, name: dt.toLocaleString('en', { month: 'short' }) });
        lastMonth = dt.getMonth();
      }

      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      const km = d.km;
      if      (km >= 6) cell.classList.add('hm-4');
      else if (km >= 3) cell.classList.add('hm-3');
      else if (km >= 1) cell.classList.add('hm-2');
      else if (km > 0)  cell.classList.add('hm-1');

      cell.title = d.date + (km > 0 ? ' — ' + km + ' km' : ' — rest day');
      week.appendChild(cell);

      if (dow === 6) {
        grid.appendChild(week);
        week = document.createElement('div');
        week.className = 'heatmap-week';
        weekNum++;
      }
    });
    // Last partial week
    if (week.children.length > 0) grid.appendChild(week);

    // Month labels
    const totalWeeks = weekNum + 1;
    const cellW = 15; // 12px + 3px gap
    monthLabels.forEach((ml, i) => {
      // If the NEXT month label is less than 3 weeks away, skip THIS label.
      // This ensures we skip the partial starting month rather than the first full month.
      if (i < monthLabels.length - 1 && monthLabels[i + 1].weekIdx - ml.weekIdx < 3) {
        return;
      }
      const span = document.createElement('span');
      span.textContent = ml.name;
      span.style.paddingLeft = (ml.weekIdx * cellW) + 'px';
      span.style.position = 'absolute';
      monthsEl.appendChild(span);
    });
    monthsEl.style.position = 'relative';
    monthsEl.style.height = '16px';
  }

  fetch('/api/heatmap-data')
    .then(r => r.json())
    .then(data => buildHeatmap(data.days))
    .catch(() => {});

  // ──────────────────────────────────────────────
  // FEATURE 5: MILESTONE RINGS
  // ──────────────────────────────────────────────
  const MILESTONES = [
    { label: '5K',          dist: 5,    color: '#b0ff4f', emoji: '🟢' },
    { label: '10K',         dist: 10,   color: '#00f2ff', emoji: '🔵' },
    { label: 'Half (21K)', dist: 21.1,  color: '#c084fc', emoji: '🟣' },
    { label: 'Marathon',   dist: 42.2,  color: '#ff6e3a', emoji: '🟠' },
    { label: 'Ultra 50K',  dist: 50,    color: '#ff5858', emoji: '🔴' },
  ];

  async function fetchPrediction() {
    try {
      const res = await fetch('/api/predict-next-run');
      const data = await res.json();
      
      const valEl = document.getElementById('predictionValue');
      const msgEl = document.getElementById('predictionMessage');
      
      if (!valEl || !msgEl) return;
      
      if (data.error) {
        valEl.textContent = '-- km';
        msgEl.textContent = 'Prediction temporarily unavailable';
        return;
      }
      
      if (data.prediction_km === null) {
        valEl.textContent = '-- km';
        msgEl.textContent = 'Log more runs to unlock predictions';
        return;
      }
      
      valEl.textContent = data.prediction_km + ' km';
      if (data.method === 'ml') {
        const mae = data.confidence_mae !== null ? data.confidence_mae : 0;
        msgEl.textContent = 'Based on your training pattern (±' + mae + ' km)';
      } else {
        msgEl.textContent = 'Estimate based on recent runs — log a few more for AI predictions';
      }
    } catch (e) {
      console.error('Error fetching prediction:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', fetchPrediction);

  function buildMilestoneRings(allTimeDist) {
    const container = document.getElementById('milestoneRings');
    if (!container) return;
    container.innerHTML = '';

    MILESTONES.forEach(m => {
      const pct = Math.min(100, (allTimeDist / m.dist) * 100);
      const unlocked = allTimeDist >= m.dist;
      const r = 30, cx = 38, cy = 38, strokeW = 6;
      const circumference = 2 * Math.PI * r;
      const offset = circumference - (pct / 100) * circumference;

      const wrap = document.createElement('div');
      wrap.className = 'milestone-ring-wrap';
      wrap.innerHTML = `
        <svg class="ring-svg" width="76" height="76" viewBox="0 0 76 76">
          <circle class="ring-bg" cx="${cx}" cy="${cy}" r="${r}" stroke-width="${strokeW}"/>
          <circle class="ring-fill" cx="${cx}" cy="${cy}" r="${r}"
            stroke="${unlocked ? m.color : 'rgba(255,255,255,0.15)' }"
            stroke-width="${strokeW}"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"
            transform="rotate(-90 ${cx} ${cy})"/>
          <text x="${cx}" y="${cy+2}" text-anchor="middle" dominant-baseline="middle"
            fill="${unlocked ? m.color : 'rgba(255,255,255,0.3)'}"
            font-size="11" font-weight="700">${unlocked ? '✓' : Math.round(pct) + '%'}</text>
        </svg>
        <span class="milestone-label" style="color:${unlocked ? m.color : 'var(--text-tertiary)'}">${m.emoji} ${m.label}</span>
        <span class="milestone-sub">${allTimeDist >= m.dist ? 'Completed!' : m.dist + ' km'}</span>
      `;
      container.appendChild(wrap);
    });
  }

  // Fetch badge progress for milestone rings
  fetch('/api/badges/progress')
    .then(r => r.json())
    .then(data => buildMilestoneRings(data.total_distance || 0))
    .catch(() => buildMilestoneRings(0));

  // ──────────────────────────────────────────────
  // FEATURE 1: ACHIEVEMENTS / BADGES SHOWCASE
  // ──────────────────────────────────────────────
  const BADGE_DEFS = {
    'FIRST_5K':      { icon: '🏅', name: 'First 5K',         desc: 'Complete a 5K run' },
    'FIRST_10K':     { icon: '🥇', name: 'First 10K',        desc: 'Complete a 10K run' },
    'TOTAL_50KM':    { icon: '🚀', name: '50 KM Club',       desc: 'Run 50km total' },
    'TOTAL_100KM':   { icon: '💯', name: '100 KM Legend',    desc: 'Run 100km total' },
    'STREAK_7DAY':   { icon: '🔥', name: 'Week Warrior',     desc: '7 day running streak' },
    'STREAK_30DAY':  { icon: '⚡', name: 'Month of Miles',   desc: '30 day running streak' },
  };

  // Fallback badge definitions if server has no rows
  const HARDCODED_BADGES = Object.entries(BADGE_DEFS).map(([key, def]) => ({
    key, ...def,
    is_unlocked: false,
    progress: 0, current: 0,
    target: key.includes('5K') ? 5 : key.includes('10K') ? 10 : key.includes('50') ? 50 : key.includes('100') ? 100 : key.includes('7') ? 7 : 30,
    criteria_type: key.startsWith('STREAK') ? 'STREAK' : key.startsWith('TOTAL') ? 'ACCUMULATIVE_DISTANCE' : 'SINGLE_DISTANCE',
  }));

  function renderBadges(badges) {
    const grid = document.getElementById('badgeGrid');
    if (!grid) return;
    if (!badges.length) {
      grid.innerHTML = '<div class="col-12 text-muted text-center small py-3">No badges defined yet. Keep running!</div>';
      return;
    }
    grid.innerHTML = '';
    badges.forEach(b => {
      const def = BADGE_DEFS[b.key] || { icon: '🎖️', name: b.name || b.key, desc: b.description || '' };
      const col = document.createElement('div');
      col.className = 'col-6 col-md-4 col-lg-2';
      const pct = b.progress || 0;
      col.innerHTML = `
        <div class="badge-card ${b.is_unlocked ? 'unlocked' : 'locked'}">
          ${b.is_unlocked ? '<div class="badge-glow"></div>' : ''}
          <span class="badge-icon">${def.icon}</span>
          <div class="badge-name">${def.name}</div>
          <div class="badge-desc">${def.desc}</div>
          <div class="badge-prog">
            <div class="progress" style="height:4px;margin-top:6px;">
              <div class="progress-bar bg-info" style="width:${pct}%"></div>
            </div>
            <small class="text-muted" style="font-size:0.6rem;">${b.current || 0} / ${b.target || '?'} ${b.criteria_type === 'STREAK' ? 'days' : 'km'}</small>
          </div>
          ${b.is_unlocked ? '<div style="position:absolute;top:6px;right:8px;font-size:0.65rem;color:var(--accent);">Unlocked</div>' : ''}
        </div>
      `;
      grid.appendChild(col);
    });
  }

  fetch('/api/badges')
    .then(r => r.json())
    .then(data => {
      if (data.badges && data.badges.length) {
        renderBadges(data.badges);
      } else {
        // No DB badges seeded — show hardcoded with progress from stats
        fetch('/api/badges/progress')
          .then(r => r.json())
          .then(stats => {
            HARDCODED_BADGES.forEach(b => {
              if (b.criteria_type === 'ACCUMULATIVE_DISTANCE') {
                b.current = Math.round(stats.total_distance || 0);
                b.progress = Math.min(100, (b.current / b.target) * 100);
                b.is_unlocked = b.current >= b.target;
              } else if (b.criteria_type === 'STREAK') {
                b.current = stats.current_streak || 0;
                b.progress = Math.min(100, (b.current / b.target) * 100);
                b.is_unlocked = b.current >= b.target;
              }
            });
            renderBadges(HARDCODED_BADGES);
          });
      }
    })
    .catch(() => renderBadges(HARDCODED_BADGES));

  // ──────────────────────────────────────────────
  // CONFETTI on badge unlock
  // ──────────────────────────────────────────────
  function launchConfetti() {
    const colors = ['#00f2ff','#b0ff4f','#ff6e3a','#ff6b6b','#c084fc','#ffffff'];
    for (let i = 0; i < 60; i++) {
      const p = document.createElement('div');
      p.className = 'confetti-piece';
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[Math.floor(Math.random() * colors.length)];
      p.style.animationDuration = (1.5 + Math.random() * 2) + 's';
      p.style.animationDelay = (Math.random() * 0.8) + 's';
      p.style.width = (6 + Math.random() * 6) + 'px';
      p.style.height = (10 + Math.random() * 10) + 'px';
      p.style.transform = 'rotate(' + (Math.random() * 360) + 'deg)';
      document.body.appendChild(p);
      p.addEventListener('animationend', () => p.remove());
    }
  }

  // Check for new badges after page load
  
  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      launchConfetti();
      const badgesWon = 0;
      if (badgesWon.length) {
        const names = { 'FIRST_5K':'First 5K','FIRST_10K':'First 10K','TOTAL_50KM':'50 KM Club','TOTAL_100KM':'100 KM Legend','STREAK_7DAY':'Week Warrior','STREAK_30DAY':'Month of Miles' };
        const earned = badgesWon.map(k => names[k] || k).join(', ');
        const toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.9);border:1px solid #00f2ff;border-radius:14px;padding:1rem 1.5rem;color:#fff;z-index:9999;text-align:center;animation:slideIn 0.4s ease;max-width:90vw;';
        toast.innerHTML = '<div style="font-size:1.5rem;margin-bottom:0.3rem">Badge Unlocked!</div><div style="color:#00f2ff;font-weight:700;">' + earned + '</div>';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
      }
    }, 600);
  });
  

  