"""Patch index.html: add Map button in run card actions."""
import os

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates', 'index.html')

with open(HTML, 'r', encoding='utf-8', newline='') as f:
    src = f.read()

NL = '\r\n'

# Target: the Share button in the run card actions area
old_share_end = (
    "                  <i class=\"fas fa-arrow-up-from-bracket text-info\"></i> Share\r\n"
    "                </button>\r\n"
    "                \r\n"
    "                {% if 'is_locked' in r.keys() and r['is_locked'] %}"
)

new_share_end = (
    "                  <i class=\"fas fa-arrow-up-from-bracket text-info\"></i> Share\r\n"
    "                </button>\r\n"
    "\r\n"
    "                <!-- Map button — only shows if run has GPS route -->\r\n"
    "                <button type=\"button\" class=\"btn btn-glass run-map-btn d-flex align-items-center justify-content-center gap-2 py-2\"\r\n"
    "                  style=\"border-color:rgba(40,167,69,.5);background:rgba(40,167,69,.1);display:none!important;\"\r\n"
    "                  data-run-id=\"{{ r['id'] }}\"\r\n"
    "                  onclick=\"viewRunRoute({{ r['id'] }})\" title=\"View GPS route map\">\r\n"
    "                  🗺️\r\n"
    "                </button>\r\n"
    "\r\n"
    "                {% if 'is_locked' in r.keys() and r['is_locked'] %}"
)

if old_share_end in src:
    src = src.replace(old_share_end, new_share_end, 1)
    print('OK: Map button added to run card')
else:
    print('WARN: Share button target not found in run card')
    # Show snippet around the Share button for debug
    idx = src.find('fa-arrow-up-from-bracket')
    if idx >= 0:
        print(repr(src[idx-100:idx+200]))

with open(HTML, 'w', encoding='utf-8', newline='') as f:
    f.write(src)
print('index.html saved.')
