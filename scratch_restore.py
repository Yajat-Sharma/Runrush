import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '<!-- MOVED MONTHLY PROGRESS CONTAINER -->'
start_idx = content.find(start_marker)
if start_idx == -1:
    print('Could not find moved container')
    exit(1)

def find_matching_closing_div(html, start_index):
    depth = 0
    i = start_index
    while i < len(html):
        if html.startswith('<div', i):
            depth += 1
            i += 4
        elif html.startswith('</div>', i):
            depth -= 1
            i += 6
            if depth == 0:
                return i
        else:
            i += 1
    return -1

container_start = content.find('<div id="monthly-progress-container"', start_idx)
container_end = find_matching_closing_div(content, container_start)

extracted_html = content[start_idx:container_end]
content = content[:start_idx] + content[container_end:]

runs_view_start = content.find('<div id="runsView"')
h3_idx = content.find('<h3', runs_view_start)
h3_end = content.find('</h3>', h3_idx) + 5

content = content[:h3_end] + '\n\n' + extracted_html.replace('<!-- MOVED MONTHLY PROGRESS CONTAINER -->', '') + '\n' + content[h3_end:]

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Restored monthly-progress-container to runsView')
