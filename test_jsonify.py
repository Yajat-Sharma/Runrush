from flask import Flask, jsonify
from datetime import datetime
app = Flask(__name__)
with app.app_context():
    print(jsonify({'d': datetime.now()}).get_data())
