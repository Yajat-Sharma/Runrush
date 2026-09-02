import os
os.environ['DATABASE_URL'] = 'sqlite:///runs.db'
import app
with app.app.test_request_context():
    app.session['user_id'] = 1
    try:
        r = app.get_badges()
        print(r.get_json())
    except Exception as e:
        import traceback; traceback.print_exc()
