with open('tests/test_dashboard_layout.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_test_get = '''    assert len(layout) == 6
    assert layout[0]['widget_type'] == 'leaderboard'
    assert layout[1]['widget_type'] == 'quick_start'
    assert layout[2]['widget_type'] == 'weekly_goal'
    assert layout[3]['widget_type'] == 'personal_goal'
    assert layout[4]['widget_type'] == 'this_month'
    assert layout[5]['widget_type'] == 'predicted_run'
'''

new_test_get = '''    assert len(layout) == 7
    assert layout[0]['widget_type'] == 'leaderboard'
    assert layout[1]['widget_type'] == 'quick_start'
    assert layout[2]['widget_type'] == 'weekly_goal'
    assert layout[3]['widget_type'] == 'this_month'
    assert layout[4]['widget_type'] == 'predicted_run'
    assert layout[5]['widget_type'] == 'personal_goal'
    assert layout[6]['widget_type'] == 'pace_pet'
'''

old_test_post = '''    assert len(layout) == 3
    assert layout[0]['widget_type'] == 'predicted_run'
    assert layout[0]['visible'] == False
    assert layout[0]['order'] == 0
    assert layout[1]['widget_type'] == 'this_month'
    assert layout[1]['visible'] == True
    assert layout[1]['order'] == 1'''

new_test_post = '''    assert len(layout) == 4
    assert layout[0]['widget_type'] == 'predicted_run'
    assert layout[0]['visible'] == False
    assert layout[0]['order'] == 0
    assert layout[1]['widget_type'] == 'this_month'
    assert layout[1]['visible'] == True
    assert layout[1]['order'] == 1'''

code = code.replace(old_test_get, new_test_get)
code = code.replace(old_test_post, new_test_post)

with open('tests/test_dashboard_layout.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched test_dashboard_layout.py")
