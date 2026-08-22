import pytest
from unittest.mock import patch, MagicMock
from ml_predictor import get_predictions_for_user
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

@pytest.fixture
def memory_db():
    conn = sqlite3.connect(':memory:')
    conn.execute('''
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            distance_km REAL NOT NULL,
            time_min REAL NOT NULL,
            pace REAL NOT NULL,
            calories REAL NOT NULL,
            insight TEXT,
            created_at TEXT,
            run_type TEXT DEFAULT 'easy',
            notes TEXT,
            weather_temp REAL,
            weather_humidity INTEGER,
            weather_wind_kph REAL,
            weather_condition TEXT,
            weather_emoji TEXT
        )
    ''')
    conn.commit()
    yield lambda: conn
    conn.close()

def test_no_runs(memory_db):
    result = get_predictions_for_user(1, memory_db)
    assert result['prediction_km'] is None
    assert result['method'] is None
    assert result['runs_used'] == 0

def test_cold_start_heuristic(memory_db):
    conn = memory_db()
    for i in range(5):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories) VALUES (?, ?, ?, ?, ?, ?)",
            (1, date, 5.0 + i, 30.0, 6.0, 300)
        )
    conn.commit()
    
    result = get_predictions_for_user(1, memory_db)
    assert result['method'] == 'heuristic'
    assert result['runs_used'] == 5
    assert result['confidence_mae'] is None
    assert result['prediction_km'] > 0

def test_ml_end_to_end_real(memory_db):
    conn = memory_db()
    # Insert 20 runs to trigger ML model
    for i in range(20, 0, -1):
        date = (datetime.now() - timedelta(days=i*2)).strftime("%Y-%m-%d %H:%M:%S")
        # Vary distance slightly
        dist = 5.0 + (i % 3)
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type, weather_temp, weather_humidity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, date, dist, dist*6, 6.0, dist*60, 'easy', 20.0, 50)
        )
    conn.commit()
    
    result = get_predictions_for_user(1, memory_db)
    assert result['method'] == 'ml'
    assert result['runs_used'] == 20
    assert result['confidence_mae'] is not None
    assert isinstance(result['prediction_km'], float)
    assert result['prediction_km'] >= 0.0

@patch('ml_predictor.GradientBoostingRegressor')
def test_ml_training_leakage_and_logic(mock_gbr, memory_db):
    # This mock test verifies the logic without actually training
    mock_model = MagicMock()
    mock_model.predict.return_value = [5.5]
    mock_gbr.return_value = mock_model
    
    conn = memory_db()
    for i in range(20, 0, -1):
        date = (datetime.now() - timedelta(days=i*2)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type, weather_temp, weather_humidity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, date, 5.0, 30.0, 6.0, 300, 'easy', 20.0, 50)
        )
    conn.commit()
    
    with patch('ml_predictor.mean_absolute_error', return_value=1.2):
        result = get_predictions_for_user(1, memory_db)
    
    assert result['method'] == 'ml'
    assert result['confidence_mae'] == 1.2
    assert result['prediction_km'] == 5.5
    
    # Verify split logic
    assert mock_model.fit.call_count == 2 # Once for split, once for full data
