def get_block(text, start_str, end_str):
    start = text.find(start_str)
    if start == -1: return None
    end = text.find(end_str, start)
    if end == -1: return None
    return text[start:end + len(end_str)]

with open('index_new_clean.html', 'r', encoding='utf-8') as f:
    new_text = f.read()
    
with open('index_old_clean.html', 'r', encoding='utf-8') as f:
    old_text = f.read()

dash_lb_new = get_block(new_text, '<div class="glass p-3 mb-3 mb-md-4" id="weeklyLeaderboardCard"', '{% endif %}\n    </div>\n\n\n')
dash_lb_old = get_block(old_text, '<div class="glass p-3 mb-3 mb-md-4" id="weeklyLeaderboardCard"', '{% endif %}\n    </div>\n\n\n')

if dash_lb_new and dash_lb_old:
    old_text = old_text.replace(dash_lb_old, dash_lb_new)
    print("Replaced dash_lb")
else:
    print("Failed dash_lb")

lb_modal_new = get_block(new_text, '<div id="leaderboardView" style="display: none;">', '</div> <!-- /#leaderboardView -->')
lb_modal_old = get_block(old_text, '<div id="leaderboardView" style="display: none;">', '</div> <!-- /#leaderboardView -->')

if lb_modal_new and lb_modal_old:
    old_text = old_text.replace(lb_modal_old, lb_modal_new)
    print("Replaced lb_modal")
else:
    print("Failed lb_modal")

mp_new = get_block(new_text, '<div id="monthly-progress-container"', '</div>\n      \n    </div>')
mp_old = get_block(old_text, '<div id="monthly-progress-container"', '</div>\n      \n    </div>')

if mp_new and mp_old:
    old_text = old_text.replace(mp_old, mp_new)
    print("Replaced mp")
else:
    print("Failed mp")

mg_modal_new = get_block(new_text, '<!-- Edit Monthly Goal Modal -->', '</script>')

if mg_modal_new:
    old_text = old_text.replace('</body>', mg_modal_new + '\n</body>')
    print("Replaced mg_modal")
else:
    print("Failed mg_modal")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(old_text)
