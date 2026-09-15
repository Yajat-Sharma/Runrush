import os
import sys

# Force SQLite for test
os.environ["USE_PG"] = "0"
os.environ["DATABASE_URL"] = ""

from app import init_db
print("Initializing SQLite DB...")
init_db()
print("Success!")
