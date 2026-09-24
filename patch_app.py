import re

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add is_onboarding_complete
helper_code = '''
def is_onboarding_complete(user):
    \"\"\"Check if the user has completed mandatory onboarding fields.\"\"\"
    if not user:
        return False
    return bool(user['display_name'] and user['profile_emoji'] and user['experience'] and user['primary_goal'])
'''

if 'def is_onboarding_complete' not in code:
    code = code.replace('def get_current_user():', helper_code + '\ndef get_current_user():')

# 2. Update google_auth for returning users
old_google_auth_returning = '''        if not user['pin']:
            return redirect(url_for('set_pin'))
            
        return redirect(url_for("index"))'''

new_google_auth_returning = '''        if not user['pin']:
            return redirect(url_for('set_pin'))
            
        if not is_onboarding_complete(user):
            return redirect(url_for("onboarding"))
            
        return redirect(url_for("index"))'''

if old_google_auth_returning in code:
    code = code.replace(old_google_auth_returning, new_google_auth_returning)
else:
    print("Warning: Could not find old_google_auth_returning snippet")

# 3. Update set_pin redirect
old_set_pin_redirect = '''        flash("PIN successfully set! Welcome to RunRush.", "success")
        return redirect(url_for("onboarding"))'''

new_set_pin_redirect = '''        flash("PIN successfully set! Welcome to RunRush.", "success")
        if not is_onboarding_complete(user):
            return redirect(url_for("onboarding"))
        return redirect(url_for("index"))'''

if old_set_pin_redirect in code:
    code = code.replace(old_set_pin_redirect, new_set_pin_redirect)
else:
    print("Warning: Could not find old_set_pin_redirect snippet")

# 4. Update onboarding GET check
old_onboarding_get = '''    # If user already has basic data, don't keep showing onboarding
    if request.method == "GET":
        if (user["display_name"] is not None or user["weight"] is not None):
            return redirect(url_for("index"))'''

new_onboarding_get = '''    if request.method == "GET":
        if is_onboarding_complete(user):
            return redirect(url_for("index"))'''

if old_onboarding_get in code:
    code = code.replace(old_onboarding_get, new_onboarding_get)
else:
    print("Warning: Could not find old_onboarding_get snippet")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched app.py successfully.")
