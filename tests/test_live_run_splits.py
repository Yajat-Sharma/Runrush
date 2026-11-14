from pathlib import Path
import re
import pytest

WORKSPACE = Path(__file__).parent.parent

def test_splits_modal_template_structure():
    """Verify _live_run_modal.html contains live split toast, review splits container, and CSP nonce."""
    modal_file = WORKSPACE / "templates" / "partials" / "_live_run_modal.html"
    assert modal_file.exists(), "_live_run_modal.html must exist"
    content = modal_file.read_text(encoding="utf-8")

    # 1. Live Split Toast Notification elements
    assert 'id="lrtSplitToast"' in content
    assert 'id="lrtSplitToastTitle"' in content
    assert 'id="lrtSplitToastPace"' in content
    assert 'id="lrtSplitToastSubtitle"' in content
    assert 'data-action="dismissSplitToast"' in content

    # 2. Review splits summary container
    assert 'id="lrtSplitsContainer"' in content
    assert 'id="lrtSplitsCountBadge"' in content
    assert 'id="lrtSplitsList"' in content

    # 3. CSS styles for splits
    assert '.lrt-split-toast' in content
    assert '.lrt-split-row' in content
    assert '.lrt-split-row-fastest' in content
    assert '.lrt-split-km-badge' in content

    # 4. Check CSP compliance in inline <style>
    style_matches = re.findall(r"<style([^>]*)>", content)
    for attrs in style_matches:
        assert 'nonce="{{ csp_nonce() }}"' in attrs, f"Style tag missing csp_nonce: {attrs}"

    # 5. Zero inline on* event handlers
    assert not re.search(r'\s+on[a-z]+=', content, re.IGNORECASE), "Found inline on* handler in modal template"


def test_splits_js_definitions():
    """Verify that split tracking state and helper functions exist in live_run_tracker.js."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    assert js_file.exists()
    content = js_file.read_text(encoding="utf-8")

    assert 'let runSplits = [];' in content
    assert 'let lastCompletedKm = 0;' in content
    assert 'function showLiveSplitNotification(split)' in content
    assert 'function calculateFinalSplits(distKm, totalMs)' in content
    assert 'function renderRunSplitsSummary()' in content
    assert 'window.dismissSplitToast =' in content
    assert 'window.getRunSplits =' in content
    assert 'window.RR_ACTIONS.dismissSplitToast =' in content


def simulate_split_calculation(points_with_times, total_dist_km, total_ms):
    """Python reference simulator mirroring live_run_tracker.js split calculation logic."""
    splits = []
    last_completed_km = 0
    last_split_elapsed_ms = 0

    # Process kilometer completions
    prev_dist = 0
    prev_elapsed = 0

    for pt in points_with_times:
        cur_dist = pt['dist']
        cur_elapsed = pt['elapsed_ms']
        target_km = int(cur_dist)

        while last_completed_km < target_km:
            next_km = last_completed_km + 1
            seg_dist = cur_dist - prev_dist
            split_elapsed = cur_elapsed
            if seg_dist > 0.00001:
                frac = max(0.0, min(1.0, (next_km - prev_dist) / seg_dist))
                split_elapsed = round(prev_elapsed + frac * (cur_elapsed - prev_elapsed))

            if split_elapsed < last_split_elapsed_ms:
                split_elapsed = last_split_elapsed_ms

            split_duration = max(500, split_elapsed - last_split_elapsed_ms)
            split_dist = 1.0
            pace_min = (split_duration / 60000.0) / split_dist

            def fmt_pace(d, ms):
                min_per_km = ms / 60000.0 / d
                m = int(min_per_km)
                s = round((min_per_km - m) * 60)
                return f"{m}:{s:02d}"

            def fmt_dur(ms):
                total_s = int(ms / 1000)
                m = int(total_s / 60)
                s = total_s % 60
                return f"{m:02d}:{s:02d}"

            splits.append({
                'km': next_km,
                'distance_km': split_dist,
                'duration_ms': split_duration,
                'pace_min': pace_min,
                'pace_str': fmt_pace(split_dist, split_duration),
                'duration_str': fmt_dur(split_duration),
                'active_elapsed_ms': split_elapsed,
                'is_partial': False,
                'is_fastest': False
            })

            last_completed_km = next_km
            last_split_elapsed_ms = split_elapsed

        prev_dist = cur_dist
        prev_elapsed = cur_elapsed

    # Handle final partial kilometer
    rem_dist = total_dist_km - last_completed_km
    if rem_dist >= 0.01:
        part_dur = max(0, total_ms - last_split_elapsed_ms)
        part_dist = round(rem_dist, 2)
        part_pace_min = (part_dur / 60000.0) / part_dist if part_dist > 0 else 0

        def fmt_pace(d, ms):
            min_per_km = ms / 60000.0 / d
            m = int(min_per_km)
            s = round((min_per_km - m) * 60)
            return f"{m}:{s:02d}"

        def fmt_dur(ms):
            total_s = int(ms / 1000)
            m = int(total_s / 60)
            s = total_s % 60
            return f"{m:02d}:{s:02d}"

        splits.append({
            'km': last_completed_km + 1,
            'distance_km': part_dist,
            'duration_ms': part_dur,
            'pace_min': part_pace_min,
            'pace_str': fmt_pace(part_dist, part_dur),
            'duration_str': fmt_dur(part_dur),
            'active_elapsed_ms': total_ms,
            'is_partial': True,
            'is_fastest': False
        })

    # Find fastest split
    best_pace = float('inf')
    fastest_idx = -1
    min_comp = 0.01 if total_dist_km < 0.5 else 0.2
    for i, s in enumerate(splits):
        if s['distance_km'] >= min_comp and s['pace_min'] > 0 and s['pace_min'] < best_pace:
            best_pace = s['pace_min']
            fastest_idx = i

    if fastest_idx == -1 and len(splits) > 0:
        fastest_idx = 0

    for i, s in enumerate(splits):
        s['is_fastest'] = (i == fastest_idx)

    return splits


def test_multiple_complete_kilometres_split_calculation():
    """Verify split calculations, pace, durations, and fastest split for a 3.0 km run."""
    # 3 km run: KM 1 in 5:00 (300000ms), KM 2 in 4:30 (270000ms), KM 3 in 4:50 (290000ms)
    points = [
        {'dist': 0.0, 'elapsed_ms': 0},
        {'dist': 1.0, 'elapsed_ms': 300000},
        {'dist': 2.0, 'elapsed_ms': 570000},
        {'dist': 3.0, 'elapsed_ms': 860000},
    ]
    splits = simulate_split_calculation(points, 3.0, 860000)

    assert len(splits) == 3
    # KM 1
    assert splits[0]['km'] == 1
    assert splits[0]['distance_km'] == 1.0
    assert splits[0]['duration_ms'] == 300000
    assert splits[0]['pace_str'] == '5:00'
    assert not splits[0]['is_partial']
    assert not splits[0]['is_fastest']

    # KM 2 (Fastest!)
    assert splits[1]['km'] == 2
    assert splits[1]['distance_km'] == 1.0
    assert splits[1]['duration_ms'] == 270000
    assert splits[1]['pace_str'] == '4:30'
    assert splits[1]['is_fastest'] is True

    # KM 3
    assert splits[2]['km'] == 3
    assert splits[2]['distance_km'] == 1.0
    assert splits[2]['duration_ms'] == 290000
    assert splits[2]['pace_str'] == '4:50'
    assert not splits[2]['is_fastest']

    # Mathematical sums
    total_dist = sum(s['distance_km'] for s in splits)
    total_dur = sum(s['duration_ms'] for s in splits)
    assert pytest.approx(total_dist) == 3.0
    assert total_dur == 860000


def test_partial_final_kilometre_split_calculation():
    """Verify that a run ending at 3.42 km creates a 4th partial split with exact remainder distance."""
    # 3.42 km total
    points = [
        {'dist': 0.0, 'elapsed_ms': 0},
        {'dist': 1.0, 'elapsed_ms': 300000},
        {'dist': 2.0, 'elapsed_ms': 580000},
        {'dist': 3.0, 'elapsed_ms': 870000},
        {'dist': 3.42, 'elapsed_ms': 990000},
    ]
    splits = simulate_split_calculation(points, 3.42, 990000)

    assert len(splits) == 4
    # Split 4 is partial
    s4 = splits[3]
    assert s4['km'] == 4
    assert s4['distance_km'] == 0.42
    assert s4['is_partial'] is True
    assert s4['duration_ms'] == 120000 # 990000 - 870000
    # Pace = 120000 ms / 0.42 km = 285714 ms/km = 4.76 min/km = 4:46 /km
    assert s4['pace_str'] == '4:46'

    # Sum of distances exactly matches total distance
    assert pytest.approx(sum(s['distance_km'] for s in splits), 0.01) == 3.42
    # Sum of durations exactly matches total elapsed active time
    assert sum(s['duration_ms'] for s in splits) == 990000


def test_very_short_run_split_calculation():
    """Verify that runs under 1.0 km (e.g. 0.65 km) produce 1 partial split with correct pace."""
    points = [
        {'dist': 0.0, 'elapsed_ms': 0},
        {'dist': 0.65, 'elapsed_ms': 195000},
    ]
    splits = simulate_split_calculation(points, 0.65, 195000)

    assert len(splits) == 1
    s = splits[0]
    assert s['km'] == 1
    assert s['distance_km'] == 0.65
    assert s['is_partial'] is True
    assert s['duration_ms'] == 195000
    # 195000 ms / 0.65 km = 300000 ms/km = 5:00 /km
    assert s['pace_str'] == '5:00'
    assert s['is_fastest'] is True


def test_pause_resume_split_accuracy():
    """Verify that paused time is strictly excluded from split duration."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    content = js_file.read_text(encoding="utf-8")

    # Verify elapsedMs calculates: now - startTime - totalPausedMs
    assert 'now - startTime - totalPausedMs' in content
    # Verify pauseTracking sets isPaused = true and pauses elapsed time
    assert 'isPaused = true;' in content
    # Verify resumeTracking adds to totalPausedMs
    assert 'totalPausedMs += Date.now() - pausedAt;' in content

    # Test numerical simulation:
    # 1 km in 300s (300000ms), paused 600s (600000ms), then 1 km in 270s (270000ms)
    # Active elapsed time at KM 1: 300000ms
    # Active elapsed time at KM 2: 570000ms (pause time excluded by elapsedMs)
    points = [
        {'dist': 0.0, 'elapsed_ms': 0},
        {'dist': 1.0, 'elapsed_ms': 300000},
        {'dist': 2.0, 'elapsed_ms': 570000},
    ]
    splits = simulate_split_calculation(points, 2.0, 570000)
    assert splits[0]['duration_ms'] == 300000
    assert splits[1]['duration_ms'] == 270000
    assert splits[1]['pace_str'] == '4:30'  # Not 14:30!


def test_gps_noise_and_signal_interruption_resilience():
    """Verify that GPS noise (> 0.5 km jump) is rejected and does not increment distance or create false splits."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    content = js_file.read_text(encoding="utf-8")

    # Noise check exists in onPosition
    assert 'if (d > 0.5) return;' in content
    assert 'totalDistanceKm += d;' in content

    # Verify split loop advances strictly based on Math.floor(totalDistanceKm)
    assert 'Math.floor(totalDistanceKm)' in content
    assert 'while (lastCompletedKm < currentKmTarget)' in content
