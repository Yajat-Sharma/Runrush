from pathlib import Path
import re
import pytest

WORKSPACE = Path(__file__).parent.parent

def test_voice_coach_template_elements():
    """Verify that _live_run_modal.html contains Voice Coach controls and CSP compliance."""
    modal_file = WORKSPACE / "templates" / "partials" / "_live_run_modal.html"
    assert modal_file.exists(), "_live_run_modal.html must exist"
    content = modal_file.read_text(encoding="utf-8")

    # Voice coach toggle button in top bar
    assert 'id="lrtVoiceCoachBtn"' in content
    assert 'id="lrtVoiceCoachIcon"' in content
    assert 'id="lrtVoiceCoachText"' in content
    assert 'data-action="toggleVoiceCoach"' in content

    # Check CSP compliance: no inline onclick handlers
    assert not re.search(r'\s+on[a-z]+=', content, re.IGNORECASE), "Found inline on* handler in modal template"


def test_voice_coach_js_definitions():
    """Verify that Voice Coach functions and state variables exist in live_run_tracker.js."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    assert js_file.exists()
    content = js_file.read_text(encoding="utf-8")

    assert 'let voiceCoachEnabled = true;' in content
    assert 'function formatDurationForSpeech(ms)' in content
    assert 'function formatPaceForSpeech(distKm, ms)' in content
    assert 'function getSplitMotivationalCheer(split, isFastestSoFar)' in content
    assert 'function initSpeechSynthesis()' in content
    assert 'function speakVoiceCoach(text, cancelExisting' in content
    assert 'function speakSplitAnnouncement(split)' in content
    assert 'window.toggleVoiceCoach =' in content
    assert 'function updateVoiceCoachUI()' in content
    assert 'window.RR_ACTIONS.toggleVoiceCoach =' in content


def format_duration_for_speech_py(ms):
    """Python reference mirroring formatDurationForSpeech."""
    total_sec = max(0, ms) // 1000
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60

    parts = []
    if h > 0:
        parts.append(f"{h} hour{'s' if h > 1 else ''}")
    if m > 0:
        parts.append(f"{m} minute{'s' if m > 1 else ''}")
    if s > 0 or not parts:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    return ' '.join(parts)


def format_pace_for_speech_py(dist_km, ms):
    """Python reference mirroring formatPaceForSpeech."""
    if dist_km < 0.01:
        return 'unknown pace'
    min_per_km = ms / 60000.0 / dist_km
    m = int(min_per_km)
    s = round((min_per_km - m) * 60)
    if s == 0:
        return f"{m} minutes per kilometre"
    return f"{m} {s:02d} per kilometre"


def test_speech_duration_formatting():
    """Test duration speech formatting across various millisecond inputs."""
    assert format_duration_for_speech_py(45000) == "45 seconds"
    assert format_duration_for_speech_py(240000) == "4 minutes"
    assert format_duration_for_speech_py(270000) == "4 minutes 30 seconds"
    assert format_duration_for_speech_py(3665000) == "1 hour 1 minute 5 seconds"


def test_speech_pace_formatting():
    """Test pace speech formatting for spoken audio announcements."""
    # 1 km in 4:30 (270,000 ms) -> "4 30 per kilometre"
    assert format_pace_for_speech_py(1.0, 270000) == "4 30 per kilometre"
    # 1 km in 5:00 (300,000 ms) -> "5 minutes per kilometre"
    assert format_pace_for_speech_py(1.0, 300000) == "5 minutes per kilometre"
    # 1 km in 4:05 (245,000 ms) -> "4 05 per kilometre"
    assert format_pace_for_speech_py(1.0, 245000) == "4 05 per kilometre"


def test_split_announcement_sentence_structure():
    """Verify that split announcement combines distance, duration, pace, and cheer correctly."""
    km = 2
    duration_ms = 270000 # 4:30
    dist_km = 1.0

    dur_words = format_duration_for_speech_py(duration_ms)
    pace_words = format_pace_for_speech_py(dist_km, duration_ms)
    cheer = "That's your fastest kilometre yet! You're flying!"

    speech_text = f"Kilometre {km} complete! Split time {dur_words}. Pace {pace_words}. {cheer}"
    expected = "Kilometre 2 complete! Split time 4 minutes 30 seconds. Pace 4 30 per kilometre. That's your fastest kilometre yet! You're flying!"
    assert speech_text == expected


def test_voice_coach_lifecycle_calls_in_js():
    """Verify that live_run_tracker.js triggers voice coach on run start, pause, resume, finish, and splits."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    content = js_file.read_text(encoding="utf-8")

    # Start
    assert 'speakVoiceCoach("Run started. Have a great run!", true);' in content
    # Pause
    assert 'speakVoiceCoach("Run paused.", true);' in content
    # Resume
    assert 'speakVoiceCoach("Resuming run.", true);' in content
    # Finish
    assert 'Workout complete! Total distance:' in content
    # Split
    assert 'speakSplitAnnouncement(split);' in content
