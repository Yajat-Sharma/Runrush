import subprocess
import os
import pytest
import sys

def run_smoke_test(env_updates):
    env = os.environ.copy()
    
    # Remove any existing keys we are testing
    for key in ["DATABASE_URL", "STAGING_DATABASE_URL", "MIGRATION_DATABASE_URL", "APPROVED_TEST_DB_URL"]:
        env.pop(key, None)
        
    env.update(env_updates)
    
    # We just want to see if it passes the initialization guardrails
    # We don't want to actually run the test suite if it gets past them, 
    # but we can capture the output and exit code.
    
    # We will pass --help or similar if possible to unittest to exit early,
    # or just rely on the fact that if it connects it will fail anyway because
    # it is a dummy URL. However, the guardrails trigger *before* unittest.main()
    
    result = subprocess.run(
        [sys.executable, "scratch/smoke_test.py"],
        env=env,
        capture_output=True,
        text=True
    )
    return result

def test_missing_staging_db_rejected():
    result = run_smoke_test({})
    assert result.returncode == 1
    assert "STAGING_DATABASE_URL environment variable is required" in result.stdout

def test_production_db_rejected():
    result = run_smoke_test({
        "STAGING_DATABASE_URL": "postgresql://user:pass@host/runrush_prod"
    })
    assert result.returncode == 1
    assert "appears to point to production" in result.stdout

def test_accepted_staging_db():
    result = run_smoke_test({
        "STAGING_DATABASE_URL": "postgresql://user:pass@host/runrush_staging"
    })
    # Since the DB doesn't exist, it will likely fail during connection or test execution,
    # but it SHOULD NOT fail with the specific guardrail messages.
    assert "STAGING_DATABASE_URL environment variable is required" not in result.stdout
    assert "appears to point to production" not in result.stdout
    
    # Ensure no credentials from the URL are printed in the guardrail check
    assert "user:pass" not in result.stdout
    assert "user:pass" not in result.stderr
