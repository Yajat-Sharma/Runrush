import pytest
import os
import importlib
import db
from flask import Flask
from unittest import mock

def test_production_db_rejected():
    """
    Test that the guardrail successfully blocks a connection to a remote 
    production PostgreSQL database, even if it contains the word 'test',
    because APPROVED_TEST_DB_URL is not set.
    """
    app = Flask(__name__)
    app.config['TESTING'] = True

    # A URL that looks like a production DB, but maliciously contains 'test'
    # to bypass the old substring guardrail.
    sneaky_prod_url = "postgresql://user:pass@some-remote-host.neon.tech/runrush_prod_test"

    with mock.patch('db.DATABASE_URL', sneaky_prod_url), \
         mock.patch('db.USE_PG', True), \
         mock.patch.dict(os.environ, clear=True), \
         app.app_context():
        
        with pytest.raises(RuntimeError) as excinfo:
            db.get_db()
            
        assert "explicitly approved via APPROVED_TEST_DB_URL" in str(excinfo.value)

def test_approved_db_accepted():
    """
    Test that the guardrail allows the connection when APPROVED_TEST_DB_URL
    exactly matches the DATABASE_URL.
    """
    app = Flask(__name__)
    app.config['TESTING'] = True

    approved_url = "postgresql://user:pass@localhost:5432/runrush_test"

    with mock.patch('db.DATABASE_URL', approved_url), \
         mock.patch('db.USE_PG', True), \
         mock.patch('db.psycopg2', create=True) as mock_psycopg2, \
         mock.patch('db.pg_pool', None, create=True), \
         mock.patch.dict(os.environ, {"APPROVED_TEST_DB_URL": approved_url}), \
         app.app_context():
        
        # Should not raise RuntimeError
        db.get_db()
        mock_psycopg2.connect.assert_called_once_with(approved_url)
