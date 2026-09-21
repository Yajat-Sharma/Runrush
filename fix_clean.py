import re

def get_block_by_regex(text, pattern):
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(0)
    return None

with open('index_new_clean.html', 'r', encoding='utf-8') as f:
    new_text = f.read()
    
with open('index_old_clean.html', 'r', encoding='utf-8') as f:
    old_text = f.read()

# 1. Dashboard Leaderboard
dash_lb_new_pattern = r'<div class="glass p-3 mb-3 mb-md-4" id="weeklyLeaderboardCard".*?</div>\s*</div>\s*{% endif %}\s*</div>'
dash_lb_new = get_block_by_regex(new_text, dash_lb_new_pattern)

dash_lb_old_pattern = r'<div class="glass p-3 mb-3 mb-md-4" id="weeklyLeaderboardCard".*?</script>\s*{% endif %}\s*</div>'

if dash_lb_new:
    old_text = re.sub(dash_lb_old_pattern, dash_lb_new.replace('\\', '\\\\'), old_text, flags=re.DOTALL)

# 2. Leaderboard Modal
lb_modal_new_pattern = r'<div id="leaderboardView" style="display: none;">.*?</div> <!-- /#leaderboardView -->'
lb_modal_new = get_block_by_regex(new_text, lb_modal_new_pattern)

if lb_modal_new:
    old_text = re.sub(lb_modal_new_pattern, lb_modal_new.replace('\\', '\\\\'), old_text, flags=re.DOTALL)

# 3. Monthly Progress Container
mp_new_pattern = r'<div id="monthly-progress-container" class="monthly-progress-compact.*?<!-- JS fills this -->\s*</div>.*?</div>\s*</div>'
mp_new = get_block_by_regex(new_text, mp_new_pattern)

mp_old_pattern = r'<div id="monthly-progress-container" class="monthly-progress-compact.*?<!-- JS fills this -->\s*</div>.*?</div>\s*</div>'

if mp_new:
    old_text = re.sub(mp_old_pattern, mp_new.replace('\\', '\\\\'), old_text, flags=re.DOTALL)

# 4. Monthly Goal Modal
mg_modal_new_pattern = r'<!-- Edit Monthly Goal Modal -->.*?</script>'
mg_modal_new = get_block_by_regex(new_text, mg_modal_new_pattern)

if mg_modal_new:
    old_text = old_text.replace('</body>', mg_modal_new + '\n</body>')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(old_text)

print(f"dash_lb_new found: {dash_lb_new is not None}")
print(f"lb_modal_new found: {lb_modal_new is not None}")
print(f"mp_new found: {mp_new is not None}")
print(f"mg_modal_new found: {mg_modal_new is not None}")
