with open('tests/test_google_auth.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_setup = '''            conn.execute(
                "INSERT INTO users (username, pin, email, google_id, google_email) VALUES (?, ?, ?, ?, ?)",
                ("existing_google_user", "hashed_pin", "guser@example.com", "google_123", "guser@example.com")
            )'''

new_setup = '''            conn.execute(
                "INSERT INTO users (username, pin, email, google_id, google_email, display_name, profile_emoji, experience, primary_goal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("existing_google_user", "hashed_pin", "guser@example.com", "google_123", "guser@example.com", "Display Name", "????", "Beginner", "5K")
            )
            
            conn.execute(
                "INSERT INTO users (username, pin, email, google_id, google_email) VALUES (?, ?, ?, ?, ?)",
                ("incomplete_google_user", "hashed_pin", "inc@example.com", "google_inc", "inc@example.com")
            )'''

if old_setup in code:
    code = code.replace(old_setup, new_setup)
else:
    print("Warning: Could not find old_setup snippet")

with open('tests/test_google_auth.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched test_google_auth.py successfully.")
