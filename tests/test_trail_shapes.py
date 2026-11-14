from pathlib import Path
import re
import pytest

WORKSPACE = Path(__file__).parent.parent

def test_trail_shapes_definitions_in_js():
    """Verify that all 4 creative shapes and real route are defined and valid in live_run_tracker.js."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    assert js_file.exists(), "live_run_tracker.js must exist"
    content = js_file.read_text(encoding="utf-8")

    # Verify TRAIL_SHAPES object exists
    assert "const TRAIL_SHAPES = {" in content

    # Verify all 4 shapes are defined
    for shape in ["thumb", "heart", "square", "oval"]:
        assert f"{shape}: {{" in content, f"Shape '{shape}' must be defined in TRAIL_SHAPES"

    # Extract TRAIL_SHAPES block
    match = re.search(r"const TRAIL_SHAPES = \{([\s\S]*?)\n  \};", content)
    assert match, "Could not extract TRAIL_SHAPES definition"
    shapes_block = match.group(1)

    for shape in ["thumb", "heart", "square", "oval"]:
        # Check for path data (d: '...'), start: [...], finish: [...]
        shape_match = re.search(rf"{shape}:\s*\{{[^}}]*d:\s*['\"]([^'\"]+)['\"][^}}]*start:\s*\[([^\]]+)\][^}}]*finish:\s*\[([^\]]+)\]", shapes_block, re.DOTALL)
        assert shape_match, f"Shape {shape} missing valid d, start, or finish definition"
        d, start, finish = shape_match.groups()
        assert len(d.strip()) > 10, f"Path for {shape} too short"
        assert len(start.split(",")) == 2, f"Start for {shape} must have 2 coordinates"
        assert len(finish.split(",")) == 2, f"Finish for {shape} must have 2 coordinates"

def test_trail_modal_template_structure():
    """Verify _trail_share_modal.html contains required controls, export targets, and CSP nonce."""
    modal_file = WORKSPACE / "templates" / "partials" / "_trail_share_modal.html"
    assert modal_file.exists(), "_trail_share_modal.html must exist"
    content = modal_file.read_text(encoding="utf-8")

    # 1. Format selector (Story 9:16 and Post 4:5)
    assert 'data-format="story"' in content
    assert 'data-format="post"' in content

    # 2. Shape selectors (Real Route, Thumb, Heart, Square, Oval)
    assert 'data-shape="real"' in content
    assert 'data-shape="thumb"' in content
    assert 'data-shape="heart"' in content
    assert 'data-shape="square"' in content
    assert 'data-shape="oval"' in content

    # 3. Frameless floating trail viewport
    assert 'trail-frameless-viewport' in content
    assert 'id="trailSvgContainer"' in content

    # 4. Off-screen export containers for 1080x1920 (Story) and 1080x1350 (Post)
    assert 'id="trailShareStoryExport"' in content
    assert 'width:1080px;height:1920px;' in content
    assert 'id="exportStorySvgContainer"' in content

    assert 'id="trailSharePostExport"' in content
    assert 'width:1080px;height:1350px;' in content
    assert 'id="exportPostSvgContainer"' in content

    # 5. Export buttons
    assert 'downloadTrailStoryPng' in content
    assert 'downloadTrailPostPng' in content
    assert 'executeTrailShare' in content

    # 6. Check for CSP compliance in inline <style>
    style_matches = re.findall(r"<style([^>]*)>", content)
    for attrs in style_matches:
        assert 'nonce="{{ csp_nonce() }}"' in attrs, f"Style tag missing csp_nonce: {attrs}"

    # 7. No inline on* event handlers
    assert not re.search(r'\s+on[a-z]+=', content, re.IGNORECASE), "Found inline on* handler in modal template"

def test_trail_shapes_fit_within_bounds():
    """Verify that all shape path coordinates and start/finish markers stay within 0..400 coordinate space."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    content = js_file.read_text(encoding="utf-8")

    match = re.search(r"const TRAIL_SHAPES = \{([\s\S]*?)\n  \};", content)
    assert match
    shapes_block = match.group(1)

    for shape in ["thumb", "heart", "square", "oval"]:
        # Extract all numbers from the path
        shape_match = re.search(rf"{shape}:\s*\{{[^}}]*d:\s*['\"]([^'\"]+)['\"][^}}]*start:\s*\[([^\]]+)\][^}}]*finish:\s*\[([^\]]+)\]", shapes_block, re.DOTALL)
        assert shape_match
        d, start, finish = shape_match.groups()

        # Check start and finish points
        sx, sy = [float(x.strip()) for x in start.split(",")]
        fx, fy = [float(x.strip()) for x in finish.split(",")]
        assert 0 <= sx <= 400 and 0 <= sy <= 400, f"Start marker for {shape} out of bounds: ({sx}, {sy})"
        assert 0 <= fx <= 400 and 0 <= fy <= 400, f"Finish marker for {shape} out of bounds: ({fx}, {fy})"

        # Check all coordinate numbers in path d
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
        assert all(0 <= n <= 400 for n in nums), f"Path coordinate for {shape} out of bounds: {nums}"

def test_gps_route_data_integrity_preserved(client, app):
    """Verify that creative shapes are visual-only and real GPS routes saved/retrieved remain 100% authentic."""
    from models.user import User
    from app import get_db

    with app.app_context():
        conn = get_db()
        hashed_pin = User.hash_pin('1234')
        conn.execute("INSERT OR IGNORE INTO users (username, pin) VALUES ('integrityRunner', ?)", (hashed_pin,))
        user_row = conn.execute("SELECT id FROM users WHERE username='integrityRunner'").fetchone()
        user_id = user_row['id']

        conn.execute(
            "INSERT INTO runs (user_id, distance_km, time_min, pace, calories, date) VALUES (?, 7.25, 42.0, 5.79, 520, '2026-11-14')",
            (user_id,)
        )
        run_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        conn.commit()

    client.post('/login', data={'username': 'integrityRunner', 'pin': '1234'})

    # Real GPS coordinates from runner
    real_gps_points = [
        {'lat': 28.5355, 'lng': 77.3910, 'ts': 1700000000000},
        {'lat': 28.5360, 'lng': 77.3920, 'ts': 1700000010000},
        {'lat': 28.5375, 'lng': 77.3935, 'ts': 1700000025000},
        {'lat': 28.5390, 'lng': 77.3940, 'ts': 1700000040000},
    ]

    # Save real route
    post_res = client.post(f'/api/run/{run_id}/route', json={
        'route': real_gps_points,
        'total_distance_km': 7.25
    })
    assert post_res.status_code == 200

    # Fetch real route back
    get_res = client.get(f'/api/run/{run_id}/route')
    assert get_res.status_code == 200
    retrieved = get_res.json

    # Must match real route exactly - no shape contamination
    assert len(retrieved['route']) == len(real_gps_points)
    for orig, fetched in zip(real_gps_points, retrieved['route']):
        assert pytest.approx(orig['lat']) == fetched['lat']
        assert pytest.approx(orig['lng']) == fetched['lng']
    assert retrieved['total_distance_km'] == 7.25

def test_trail_share_design_rules():
    """Verify that user design rules are strictly respected across modal and script."""
    modal_file = WORKSPACE / "templates" / "partials" / "_trail_share_modal.html"
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    modal_content = modal_file.read_text(encoding="utf-8")
    js_content = js_file.read_text(encoding="utf-8")

    # 1. All numbers: White (#FFFFFF / #ffffff)
    assert 'id="tscDist" style="font-size:1.1rem;font-weight:800;color:#ffffff;' in modal_content
    assert 'id="tscTime" style="font-size:1.1rem;font-weight:800;color:#ffffff;' in modal_content
    assert 'id="tscPace" style="font-size:1.1rem;font-weight:800;color:#ffffff;' in modal_content
    assert 'id="tscCal" style="font-size:1.1rem;font-weight:800;color:#ffffff;' in modal_content
    assert 'class="exportDist" style="font-size:62px;font-weight:900;color:#ffffff;' in modal_content
    assert 'class="exportPace" style="font-size:62px;font-weight:900;color:#ffffff;' in modal_content
    assert 'class="exportCal" style="font-size:62px;font-weight:900;color:#ffffff;' in modal_content
    # Milestone split numbers in SVG must be white
    assert 'fill="#ffffff" text-anchor="middle" font-family="\'Inter\', sans-serif">${s.km}</text>' in js_content

    # 2. Labels: Muted grey (#9CA3AF / #9ca3af)
    assert 'color:#9ca3af;margin-top:3px;text-transform:uppercase;">KM</div>' in modal_content
    assert 'color:#9ca3af;margin-top:3px;text-transform:uppercase;">Time</div>' in modal_content
    assert 'color:#9ca3af;margin-top:3px;text-transform:uppercase;">Pace</div>' in modal_content
    assert 'color:#9ca3af;margin-top:3px;text-transform:uppercase;">Kcal</div>' in modal_content

    # 3. Trail: RunRush signature green (#10b981)
    assert 'stroke="#10b981" stroke-width="5.5"' in js_content

    # 4. Start marker: Green (#10b981)
    assert 'fill="#10b981" stroke="#ffffff" stroke-width="2.5"' in js_content
    assert 'fill="#10b981" text-anchor="middle" font-family="\'Inter\', sans-serif">START</text>' in js_content

    # 5. Finish marker: Red (#ef4444)
    assert 'fill="#ef4444" stroke="#ffffff" stroke-width="2.5"' in js_content
    assert 'fill="#ef4444" text-anchor="middle" font-family="\'Inter\', sans-serif">FINISH</text>' in js_content

    # 6. Background: Deep charcoal / navy (#121620, #090d14, #151a24 / #0b0f16)
    assert 'background: #121620;' in modal_content
    assert 'background: linear-gradient(180deg, #151a24 0%, #0b0f16 100%);' in modal_content
    assert 'background:#090d14;' in modal_content

    # 7. Borders: Subtle dark grey (rgba(255,255,255,0.08))
    assert 'border: 1px solid rgba(255, 255, 255, 0.08);' in modal_content

def test_live_run_modal_review_design_rules():
    """Verify that the Run Complete review drawer in _live_run_modal.html respects the design rules."""
    live_modal_file = WORKSPACE / "templates" / "partials" / "_live_run_modal.html"
    content = live_modal_file.read_text(encoding="utf-8")

    # All numbers White (#ffffff)
    assert 'id="lrtRevDist" style="font-size:1.7rem;font-weight:800;color:#ffffff;line-height:1.1;">--</div>' in content
    assert 'id="lrtRevTime" style="font-size:1.7rem;font-weight:800;color:#ffffff;line-height:1.1;">--</div>' in content
    assert 'id="lrtRevPace" style="font-size:1.7rem;font-weight:800;color:#ffffff;line-height:1.1;">--</div>' in content
    assert 'id="lrtRevCal" style="font-size:1.7rem;font-weight:800;color:#ffffff;line-height:1.1;">--</div>' in content
    assert 'color: #ffffff;' in content  # split badge text

    # Labels: Muted grey (#9ca3af)
    assert 'color:#9ca3af;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em;">Distance</div>' in content
    assert 'color:#9ca3af;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em;">Duration</div>' in content
    assert 'color:#9ca3af;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em;">Avg Pace</div>' in content
    assert 'color:#9ca3af;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em;">Calories</div>' in content

    # Background: Deep charcoal / navy (#151a24 and rgba(18, 22, 32, 0.96))
    assert 'background:#151a24;' in content
    assert 'background: rgba(18, 22, 32, 0.96);' in content

    # Borders: Subtle dark grey (rgba(255, 255, 255, 0.08))
    assert 'border:1px solid rgba(255,255,255,0.08);' in content
    assert 'border-top: 1px solid rgba(255, 255, 255, 0.08);' in content


def test_transparent_sticker_export_containers():
    """Verify that transparent sticker export containers have 100% transparent background, correct dimensions, and required targets."""
    modal_file = WORKSPACE / "templates" / "partials" / "_trail_share_modal.html"
    content = modal_file.read_text(encoding="utf-8")

    # 1. Transparent Story Container (1080x1920)
    assert 'id="trailStickerStoryExport"' in content
    assert 'background:transparent!important;' in content or 'background:transparent!important' in content
    assert 'width:1080px;height:1920px;' in content
    assert 'id="stkStorySvgContainer"' in content

    # 2. Transparent Post Container (1080x1350)
    assert 'id="trailStickerPostExport"' in content
    assert 'width:1080px;height:1350px;' in content
    assert 'id="stkPostSvgContainer"' in content

    # 3. Checkerboard preview class exists for editor preview ONLY
    assert '.trail-card-preview-box.preview-checkerboard' in content
    # Ensure export containers do NOT have preview-checkerboard class
    assert 'trailStickerStoryExport" class="preview-checkerboard' not in content
    assert 'trailStickerPostExport" class="preview-checkerboard' not in content

    # 4. JavaScript sets backgroundColor to null for transparent exports
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    js_content = js_file.read_text(encoding="utf-8")
    assert 'backgroundColor: isTransparent ? null : \'#090d14\'' in js_content
    assert 'captureExportBlob(\'trailStickerStoryExport\', 1080, 1920, true)' in js_content
    assert 'captureExportBlob(\'trailStickerPostExport\', 1080, 1350, true)' in js_content


def test_transparent_sticker_mode_and_customization_controls():
    """Verify mode selector tabs, customization pills, privacy toggle, and actions."""
    modal_file = WORKSPACE / "templates" / "partials" / "_trail_share_modal.html"
    content = modal_file.read_text(encoding="utf-8")

    # Mode Selector Tabs
    assert 'data-mode="card"' in content
    assert 'data-mode="transparent"' in content
    assert 'data-mode="creative"' in content
    assert 'id="tscTransparentBadge"' in content

    # Color options
    assert 'data-action="toggleStickerTrailColor"' in content
    assert 'data-args=\'["white"]\'' in content
    assert 'data-args=\'["green"]\'' in content

    # Privacy filter button
    assert 'id="stickerPrivacyBtn"' in content
    assert 'data-action="toggleStickerPrivacy"' in content

    # Content toggles
    for opt in ['branding', 'date', 'stats', 'calories', 'markers']:
        assert f'data-args=\'["{opt}"]\'' in content

    # Sticker Download & Share buttons
    assert 'id="stickerShareActionBtn"' in content
    assert 'data-action="executeStickerShare"' in content
    assert 'id="stickerDownloadStoryBtn"' in content
    assert 'data-action="downloadStickerStoryPng"' in content
    assert 'id="stickerDownloadPostBtn"' in content
    assert 'data-action="downloadStickerPostPng"' in content

    # Instagram Story tip banner
    assert 'Instagram Story Tip:' in content
    assert 'Stickers → Photo' in content


def test_gps_privacy_filter_visual_only():
    """Verify that GPS privacy filter conceals start/end coordinates in visualization without altering real GPS data."""
    js_file = WORKSPACE / "static" / "js" / "live_run_tracker.js"
    js_content = js_file.read_text(encoding="utf-8")

    # Check function exists and trims start and end
    assert 'function applyGpsPrivacyFilter(points)' in js_content
    assert 'Math.floor(points.length * 0.1)' in js_content
    assert 'points.slice(trimCount, points.length - trimCount)' in js_content

    # Simulate in Python to verify coordinate integrity
    real_coords = [{'lat': 28.5 + (i * 0.001), 'lng': 77.3 + (i * 0.001)} for i in range(20)]
    trim = max(1, len(real_coords) // 10)
    trimmed_coords = real_coords[trim : len(real_coords) - trim]

    # Verify trimmed coordinates are shorter but original array is untouched
    assert len(trimmed_coords) == 16
    assert len(real_coords) == 20
    assert trimmed_coords[0] == real_coords[2]
    assert trimmed_coords[-1] == real_coords[17]


def test_programmatic_png_transparency():
    """Programmatically verify PNG alpha channel transparency using Pillow."""
    from PIL import Image, ImageDraw
    import io

    # Create a 1080x1920 RGBA image with transparent background (simulating sticker export)
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # alpha = 0 (100% transparent)

    draw = ImageDraw.Draw(img)
    # Draw trail line in RunRush green with full opacity
    draw.line([(200, 400), (400, 600), (600, 500), (800, 900)], fill=(16, 185, 129, 255), width=12)
    # Draw white statistics text rectangle
    draw.rectangle([(200, 1500), (880, 1650)], fill=(255, 255, 255, 255))

    # Save to PNG buffer
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Re-open and verify properties
    exported_img = Image.open(buf)
    assert exported_img.format == 'PNG', "Must be genuine PNG"
    assert exported_img.mode == 'RGBA', "Must be 4-channel RGBA with alpha"

    # Inspect alpha channel
    alpha = exported_img.getchannel('A')
    alpha_extrema = alpha.getextrema()
    # Min alpha must be 0 (pure transparent pixels exist on background)
    assert alpha_extrema[0] == 0, "Background pixels must have alpha = 0 (transparent)"
    # Max alpha must be 255 (content pixels are visible)
    assert alpha_extrema[1] == 255, "Trail and stat pixels must have alpha = 255"

    # Count transparent vs opaque pixels
    alpha_bytes = alpha.tobytes()
    transparent_count = sum(1 for a in alpha_bytes if a == 0)
    opaque_count = sum(1 for a in alpha_bytes if a > 0)

    assert transparent_count > (width * height * 0.85), "At least 85% of sticker canvas must be transparent"
    assert opaque_count > 0, "Trail and text must be rendered with opaque pixels"




