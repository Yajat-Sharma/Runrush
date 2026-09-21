import re
with open('index_old_clean.html', 'r', encoding='utf-8') as f:
    old_text = f.read()

dash_lb_old_pattern = r'<div class="glass p-3 mb-3 mb-md-4" id="weeklyLeaderboardCard".*?</script>\s*{% endif %}\s*</div>'
match = re.search(dash_lb_old_pattern, old_text, re.DOTALL)
print(f"dash_lb_old_pattern matched: {match is not None}")
