import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_mp = '<div id="monthly-progress-container" class="monthly-progress-compact mb-4 d-flex flex-wrap flex-md-nowrap align-items-center justify-content-between">'
new_mp = '''<div id="monthly-progress-container" class="glass p-3 p-md-4 mb-4 d-flex flex-column justify-content-between mx-auto" style="border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); position: relative; overflow: hidden; max-width: 480px; width: 100%; border-radius: 20px; aspect-ratio: 1 / 1;">
      <div style="position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle at top right, rgba(0, 242, 255, 0.05), transparent 60%); pointer-events: none;"></div>
      <div style="position: relative; z-index: 1;" class="d-flex flex-column h-100">'''

if old_mp in html:
    html = html.replace(old_mp, new_mp)
else:
    print("Could not find old monthly progress container")

# Fix this_month emojis to fontawesome
html = html.replace('<div class="mb-1">📅</div>', '<div class="mb-1 text-accent"><i class="fas fa-calendar-day"></i></div>')
html = html.replace('<div class="mb-1">⏱️</div>', '<div class="mb-1 text-accent"><i class="fas fa-stopwatch"></i></div>')


with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Applied monthly progress styling and emojis")
