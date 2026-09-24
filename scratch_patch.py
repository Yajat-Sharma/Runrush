import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update primaryLogBtnText
html = re.sub(
    r'<div id="primaryLogBtnText"([^>]*)>\s*LOG YOUR RUN\s*</div>',
    r'<div id="primaryLogBtnText"\1>\n                Log your run\n              </div>',
    html
)

# 2. Add Intro Logic and adjust max-width of Log A Run
intro_css_html = """
              <style>
                @keyframes introFadeSlideUp {
                  0% { opacity: 0; transform: translateY(10px); }
                  100% { opacity: 1; transform: translateY(0); }
                }
                .intro-animate {
                  animation: introFadeSlideUp 0.6s ease forwards;
                }
                @media (prefers-reduced-motion: reduce) {
                  .intro-animate { animation: none; opacity: 1; transform: none; }
                }
              </style>
              <div id="logRunIntroSection" class="text-center mb-3 d-none">
                <div class="fw-bold intro-animate" style="font-size: 0.85rem; letter-spacing: 0.1em; color: var(--accent);">FOUR WAYS TO LOG YOUR RUN</div>
                <div class="text-muted small mb-2 intro-animate" style="animation-delay: 0.1s; opacity: 0;">Pick the one that works for you.</div>
                <button class="btn btn-sm btn-outline-secondary rounded-pill intro-animate" onclick="dismissLogRunIntro()" style="font-size: 0.75rem; padding: 0.1rem 0.6rem; animation-delay: 0.2s; opacity: 0;">Got it</button>
              </div>
              <div id="primaryLogBtnText"
"""

html = re.sub(
    r'<div id="primaryLogBtnText"',
    intro_css_html.strip(),
    html
)

# Fix max-width and internal proportions of Log A Run
html = html.replace('max-width: 380px;', 'max-width: 480px;')
html = html.replace('.log-launcher-tile .tile-icon {\n                  font-size: 2rem;', '.log-launcher-tile .tile-icon {\n                  font-size: 2.5rem;')

# Add dismiss function to scripts
dismiss_script = """
      function dismissLogRunIntro() {
        localStorage.setItem('runrush_log_run_intro_seen', 'true');
        document.getElementById('logRunIntroSection').classList.add('d-none');
        const pBtn = document.getElementById('primaryLogBtnText');
        if (pBtn) pBtn.style.display = 'block';
      }
      
      document.addEventListener('DOMContentLoaded', () => {
        if (!localStorage.getItem('runrush_log_run_intro_seen')) {
            const introSection = document.getElementById('logRunIntroSection');
            if (introSection) introSection.classList.remove('d-none');
            const pBtnText = document.getElementById('primaryLogBtnText');
            if (pBtnText) pBtnText.style.display = 'none';
        }
      });
"""
html = html.replace('function switchTab(tabId) {', dismiss_script + '\n      function switchTab(tabId) {')


# 3. Add CSS Grid for dashboardWidgetContainer
css_grid = """
        @media (min-width: 992px) {
          #dashboardWidgetContainer {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
          }
          #dashboardWidgetContainer > .dashboard-widget {
            grid-column: 1 / -1;
          }
          #dashboardWidgetContainer > .dashboard-widget[data-widget="quick_start"] {
            grid-column: 1 / 2;
            grid-row: 1;
          }
          #dashboardWidgetContainer > .dashboard-widget[data-widget="personal_goal"] {
            grid-column: 2 / 3;
            grid-row: 1;
          }
        }
      </style>
    </head>
"""
html = re.sub(r'</style>\s*</head>', css_grid, html)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html")
