/**
 * live_run_tracker.js — Live GPS Run Tracker & Trail Mapping for RunRush
 * Uses navigator.geolocation + Leaflet.js (OpenStreetMap) for route mapping.
 * Visualizes the route as an athletic running trail with start/finish badges,
 * kilometer splits, an interactive post-run review drawer, and shareable trail
 * cards in custom map shapes: Thumb, Heart, Square, and Oval.
 */

(function () {
  'use strict';

  // ─── State ───────────────────────────────────────────────────────────────
  let watchId = null;
  let timerInterval = null;
  let startTime = null;
  let pausedAt = null;
  let totalPausedMs = 0;
  let isPaused = false;
  let isRunning = false;
  let isSimulating = false;
  let simInterval = null;
  let routePoints = [];   // [{lat, lng, ts}]
  let totalDistanceKm = 0;
  let leafletMap = null;
  let routeGlowPolyline = null;
  let routePolyline = null;
  let currentMarker = null;
  let startMarker = null;
  let finishMarker = null;
  let splitMarkers = [];
  let mapInitialised = false;
  let wakeLock = null;
  let userPannedAway = false;

  // Trail Share State
  let trailShareData = null;
  let selectedTrailShape = 'thumb'; // 'thumb' | 'heart' | 'square' | 'oval'

  // ─── DOM helper ──────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  // ─── Screen Wake Lock (keeps phone screen on while running) ──────────────
  async function requestWakeLock() {
    if ('wakeLock' in navigator) {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
        const badge = $('lrtWakeLockBadge');
        if (badge) badge.style.display = '';
        wakeLock.addEventListener('release', () => {
          wakeLock = null;
          if (badge) badge.style.display = 'none';
        });
      } catch (err) {
        console.warn('[LiveRun] Wake lock unavailable or denied:', err);
      }
    }
  }

  function releaseWakeLock() {
    if (wakeLock) {
      wakeLock.release().catch(() => {}).finally(() => {
        wakeLock = null;
        const badge = $('lrtWakeLockBadge');
        if (badge) badge.style.display = 'none';
      });
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && isRunning && !isPaused) {
      requestWakeLock();
    }
  });

  // ─── Haversine Distance ───────────────────────────────────────────────────
  function haversineKm(lat1, lng1, lat2, lng2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Calculate KM split milestones along a point list
  function getKmSplitPoints(points) {
    if (!points || points.length < 2) return [];
    const splits = [];
    let cumDist = 0;
    let nextKm = 1.0;

    for (let i = 1; i < points.length; i++) {
      const d = haversineKm(points[i - 1].lat, points[i - 1].lng, points[i].lat, points[i].lng);
      const prevDist = cumDist;
      cumDist += d;

      while (cumDist >= nextKm) {
        const segDist = cumDist - prevDist;
        const frac = segDist > 0 ? (nextKm - prevDist) / segDist : 0;
        const lat = points[i - 1].lat + frac * (points[i].lat - points[i - 1].lat);
        const lng = points[i - 1].lng + frac * (points[i].lng - points[i - 1].lng);
        splits.push({ km: nextKm, lat, lng });
        nextKm += 1.0;
      }
    }
    return splits;
  }

  // ─── Format helpers ───────────────────────────────────────────────────────
  function fmtDuration(ms) {
    const totalSec = Math.floor(Math.max(0, ms) / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function fmtPace(distKm, ms) {
    if (distKm < 0.01) return '--:--';
    const minPerKm = ms / 60000 / distKm;
    const m = Math.floor(minPerKm);
    const s = Math.round((minPerKm - m) * 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function elapsedMs() {
    if (!startTime) return 0;
    const now = isPaused ? pausedAt : Date.now();
    return now - startTime - totalPausedMs;
  }

  // ─── Custom Leaflet Markers ───────────────────────────────────────────────
  function createPulseRunnerMarker(lat, lng) {
    const icon = L.divIcon({
      html: '<div class="lrt-pulse-container"><div class="lrt-pulse-ring"></div><div class="lrt-pulse-dot"></div></div>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      className: ''
    });
    return L.marker([lat, lng], { icon, zIndexOffset: 1200 });
  }

  function createStartMarker(lat, lng) {
    const icon = L.divIcon({
      html: '<div class="lrt-map-badge lrt-badge-start"><i class="fa-solid fa-play" style="font-size:8px;"></i> START</div>',
      iconSize: [68, 24],
      iconAnchor: [34, 12],
      className: ''
    });
    return L.marker([lat, lng], { icon, zIndexOffset: 1000 }).bindTooltip('Run Started Here', { direction: 'top' });
  }

  function createFinishMarker(lat, lng) {
    const icon = L.divIcon({
      html: '<div class="lrt-map-badge lrt-badge-finish"><i class="fa-solid fa-flag-checkered" style="font-size:9px;"></i> FINISH</div>',
      iconSize: [74, 24],
      iconAnchor: [37, 12],
      className: ''
    });
    return L.marker([lat, lng], { icon, zIndexOffset: 1050 }).bindTooltip('Run Finished Here', { direction: 'top' });
  }

  function createSplitMarker(km, lat, lng) {
    const icon = L.divIcon({
      html: `<div class="lrt-split-badge">${km}</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
      className: ''
    });
    return L.marker([lat, lng], { icon, zIndexOffset: 950 }).bindTooltip(`${km} km split`, { direction: 'top' });
  }

  // ─── Leaflet map initialization ──────────────────────────────────────────
  function initMap() {
    if (mapInitialised) return;
    mapInitialised = true;

    leafletMap = L.map('liveRunMap', {
      zoomControl: true,
      attributionControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19
    }).addTo(leafletMap);

    // Glowing casing polyline
    routeGlowPolyline = L.polyline([], {
      color: 'rgba(16, 185, 129, 0.35)',
      weight: 9,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(leafletMap);

    // Core athletic trail polyline
    routePolyline = L.polyline([], {
      color: '#10b981',
      weight: 5,
      opacity: 0.95,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(leafletMap);

    // Track user drag/pan to display recenter button
    leafletMap.on('dragstart', () => {
      if (isRunning && !isPaused) {
        userPannedAway = true;
        const btn = $('lrtRecenterBtn');
        if (btn) btn.style.display = 'flex';
      }
    });

    // Default world view until we get a GPS fix
    leafletMap.setView([20, 0], 2);
  }

  function clearTrailDecorations() {
    if (startMarker) { startMarker.remove(); startMarker = null; }
    if (finishMarker) { finishMarker.remove(); finishMarker = null; }
    splitMarkers.forEach(m => m.remove());
    splitMarkers = [];
  }

  function addPointToMap(lat, lng) {
    if (!leafletMap || !routePolyline) return;

    routeGlowPolyline.addLatLng([lat, lng]);
    routePolyline.addLatLng([lat, lng]);

    // First point sets up the Start badge
    if (routePoints.length === 1 && !startMarker) {
      startMarker = createStartMarker(lat, lng).addTo(leafletMap);
    }

    // Update / create live current position marker
    if (!currentMarker) {
      currentMarker = createPulseRunnerMarker(lat, lng).addTo(leafletMap);
    } else {
      currentMarker.setLatLng([lat, lng]);
    }

    // Auto-center unless runner manually dragged map away
    if (!userPannedAway) {
      if (routePoints.length > 4) {
        leafletMap.panTo([lat, lng], { animate: true });
      } else {
        leafletMap.setView([lat, lng], 17);
      }
    }
  }

  // ─── Timer tick ───────────────────────────────────────────────────────────
  function updateUI() {
    const ms = elapsedMs();
    const el = $('lrtElapsed');
    if (el) el.textContent = fmtDuration(ms);

    const dist = totalDistanceKm;
    const distEl = $('lrtDistance');
    if (distEl) distEl.textContent = dist.toFixed(2);

    const paceEl = $('lrtPace');
    if (paceEl) paceEl.textContent = fmtPace(dist, ms);
  }

  // ─── GPS position handler ─────────────────────────────────────────────────
  function onPosition(pos) {
    if (isPaused || !isRunning) return;

    const { latitude: lat, longitude: lng } = pos.coords;
    const ts = Date.now();

    // Filter noisy jumps
    if (routePoints.length > 0) {
      const prev = routePoints[routePoints.length - 1];
      const d = haversineKm(prev.lat, prev.lng, lat, lng);
      // Skip implausibly large jump (> 0.5 km in one fix) as GPS noise
      if (d > 0.5) return;
      totalDistanceKm += d;
    }

    routePoints.push({ lat, lng, ts });
    addPointToMap(lat, lng);
    updateUI();

    const waiting = $('lrtWaitingGps');
    if (waiting) waiting.style.display = 'none';
  }

  function onGpsError(err) {
    console.warn('[LiveRun] GPS error:', err.message);
    const el = $('lrtWaitingGps');
    if (el) el.textContent = '⚠️ GPS unavailable — move to an open area';
  }

  // ─── Start Tracking ───────────────────────────────────────────────────────
  function startTracking() {
    if (!navigator.geolocation) {
      alert('GPS not supported on this device/browser.');
      return;
    }

    isRunning = true;
    isPaused = false;
    userPannedAway = false;
    startTime = Date.now();
    totalPausedMs = 0;
    routePoints = [];
    totalDistanceKm = 0;

    // Reset map layers
    if (routeGlowPolyline) routeGlowPolyline.setLatLngs([]);
    if (routePolyline) routePolyline.setLatLngs([]);
    if (currentMarker) { currentMarker.remove(); currentMarker = null; }
    clearTrailDecorations();

    // Hide finish review elements if open
    $('lrtReviewOverlay').style.display = 'none';
    $('lrtFitTrailBtn').style.display = 'none';
    $('lrtTrailSummaryBadge').style.display = 'none';
    $('lrtRecenterBtn').style.display = 'none';

    // Show live timer and stats HUD
    $('lrtTimerSection').style.display = '';
    $('lrtLiveStatsRow').style.display = 'flex';
    $('lrtControlsRow').style.display = 'flex';
    $('lrtHeaderTitle').textContent = '🏃 LIVE RUN';

    watchId = navigator.geolocation.watchPosition(onPosition, onGpsError, {
      enableHighAccuracy: true,
      maximumAge: 2000,
      timeout: 10000
    });

    timerInterval = setInterval(updateUI, 1000);
    requestWakeLock();

    // Update buttons
    $('lrtPauseBtn').style.display = '';
    $('lrtFinishBtn').style.display = '';
    $('lrtStartBtn').style.display = 'none';

    setTimeout(() => { if (leafletMap) leafletMap.invalidateSize(); }, 300);
  }

  // ─── Pause / Resume ───────────────────────────────────────────────────────
  function pauseTracking() {
    if (!isRunning || isPaused) return;
    isPaused = true;
    pausedAt = Date.now();
    releaseWakeLock();
    $('lrtPauseBtn').innerHTML = '<i class="fa-solid fa-play"></i> Resume';
    $('lrtPauseBtn').classList.replace('btn-warning', 'btn-success');
  }

  function resumeTracking() {
    if (!isRunning || !isPaused) return;
    totalPausedMs += Date.now() - pausedAt;
    isPaused = false;
    requestWakeLock();
    $('lrtPauseBtn').innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
    $('lrtPauseBtn').classList.replace('btn-success', 'btn-warning');
  }

  window.toggleLiveRunPause = function () {
    if (isPaused) resumeTracking(); else pauseTracking();
  };

  // ─── Finish Run & Display Trail on Map ────────────────────────────────────
  window.finishLiveRun = function () {
    if (!isRunning && !isSimulating) return;

    if (isSimulating) {
      clearInterval(simInterval);
      isSimulating = false;
    }

    // Stop tracking
    isRunning = false;
    isPaused = false;
    releaseWakeLock();
    if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
    clearInterval(timerInterval);

    const ms = elapsedMs();
    const distKm = totalDistanceKm;
    const timeMin = ms / 60000;

    // Minimum sanity check
    if (distKm < 0.005 && routePoints.length < 2) {
      alert('Not enough movement recorded. Run or move a bit before finishing!');
      resumeLiveRunFromReview();
      return;
    }

    // 1. Update Header
    const headerTitle = $('lrtHeaderTitle');
    if (headerTitle) headerTitle.textContent = '🏅 RUN COMPLETE — YOUR TRAIL';

    // 2. Hide live tracking HUD and controls
    $('lrtTimerSection').style.display = 'none';
    $('lrtLiveStatsRow').style.display = 'none';
    $('lrtControlsRow').style.display = 'none';
    $('lrtRecenterBtn').style.display = 'none';

    // 3. Remove current moving pulse marker
    if (currentMarker) {
      currentMarker.remove();
      currentMarker = null;
    }

    // 4. Decorate the completed trail on the map!
    clearTrailDecorations();

    if (routePoints.length > 0) {
      // Start Marker
      startMarker = createStartMarker(routePoints[0].lat, routePoints[0].lng).addTo(leafletMap);

      // Finish Marker
      const lastPt = routePoints[routePoints.length - 1];
      finishMarker = createFinishMarker(lastPt.lat, lastPt.lng).addTo(leafletMap);

      // Kilometer split markers along the trail
      const splits = getKmSplitPoints(routePoints);
      splits.forEach(s => {
        const sm = createSplitMarker(s.km, s.lat, s.lng).addTo(leafletMap);
        splitMarkers.push(sm);
      });

      // Show Fit Trail button and Trail Summary Pill on the map
      $('lrtFitTrailBtn').style.display = 'inline-flex';
      $('lrtTrailSummaryBadge').style.display = 'flex';
      $('lrtTrailPillDist').textContent = `${distKm.toFixed(2)} km trail`;

      // Auto-fit bounds to the entire route trail with comfortable padding
      if (routePolyline && routePolyline.getLatLngs().length > 0) {
        leafletMap.fitBounds(routePolyline.getBounds(), {
          padding: [50, 50],
          maxZoom: 17
        });
      }
    }

    // 5. Populate Review Drawer Stats
    $('lrtRevDist').textContent = distKm.toFixed(2) + ' km';
    $('lrtRevTime').textContent = fmtDuration(ms);
    $('lrtRevPace').textContent = fmtPace(distKm, ms) + ' /km';
    const cal = Math.round(timeMin * 8.2); // ~8.2 kcal/min runner estimate
    $('lrtRevCal').textContent = cal + ' kcal';

    $('lrtRevDist').dataset.distKm = distKm;
    $('lrtRevDist').dataset.timeMin = timeMin;

    // 6. Display Review Drawer over bottom of map (keeping trail map in full view!)
    const reviewDrawer = $('lrtReviewOverlay');
    reviewDrawer.style.display = 'block';
    reviewDrawer.classList.remove('lrt-collapsed');
    $('lrtToggleMapText').textContent = 'Full Map';
    $('lrtToggleMapIcon').className = 'fa-solid fa-map me-1';

    // Invalidate map size so Leaflet resizes smoothly in the available area
    setTimeout(() => {
      if (leafletMap) {
        leafletMap.invalidateSize();
        if (routePolyline && routePolyline.getLatLngs().length > 0) {
          leafletMap.fitBounds(routePolyline.getBounds(), { padding: [50, 50], maxZoom: 17 });
        }
      }
    }, 200);
  };

  // Toggle review drawer collapse to reveal full-screen map trail
  window.toggleReviewDrawer = function () {
    const drawer = $('lrtReviewOverlay');
    if (!drawer) return;
    drawer.classList.toggle('lrt-collapsed');
    const isCollapsed = drawer.classList.contains('lrt-collapsed');
    $('lrtToggleMapText').textContent = isCollapsed ? 'Show Stats' : 'Full Map';
    $('lrtToggleMapIcon').className = isCollapsed ? 'fa-solid fa-chart-simple me-1' : 'fa-solid fa-map me-1';

    setTimeout(() => {
      if (leafletMap) {
        leafletMap.invalidateSize();
        if (routePolyline && routePolyline.getLatLngs().length > 0) {
          leafletMap.fitBounds(routePolyline.getBounds(), { padding: [40, 40], maxZoom: 17 });
        }
      }
    }, 350);
  };

  // Zoom/fit entire completed trail into view
  window.fitLiveRunTrail = function () {
    if (leafletMap && routePolyline && routePolyline.getLatLngs().length > 0) {
      leafletMap.fitBounds(routePolyline.getBounds(), { padding: [50, 50], maxZoom: 17 });
    }
  };

  // Recenter map on active runner location
  window.recenterLiveRunMap = function () {
    userPannedAway = false;
    $('lrtRecenterBtn').style.display = 'none';
    if (routePoints.length > 0 && leafletMap) {
      const last = routePoints[routePoints.length - 1];
      leafletMap.setView([last.lat, last.lng], 17);
    }
  };

  // Resume tracking if user finished by accident
  window.resumeLiveRunFromReview = function () {
    $('lrtReviewOverlay').style.display = 'none';
    $('lrtFitTrailBtn').style.display = 'none';
    $('lrtTrailSummaryBadge').style.display = 'none';

    $('lrtTimerSection').style.display = '';
    $('lrtLiveStatsRow').style.display = 'flex';
    $('lrtControlsRow').style.display = 'flex';
    $('lrtHeaderTitle').textContent = '🏃 LIVE RUN';

    if (finishMarker) { finishMarker.remove(); finishMarker = null; }
    splitMarkers.forEach(m => m.remove());
    splitMarkers = [];

    isRunning = true;
    isPaused = false;
    requestWakeLock();

    if (routePoints.length > 0) {
      const last = routePoints[routePoints.length - 1];
      if (!currentMarker) {
        currentMarker = createPulseRunnerMarker(last.lat, last.lng).addTo(leafletMap);
      }
      leafletMap.panTo([last.lat, last.lng]);
    }

    watchId = navigator.geolocation.watchPosition(onPosition, onGpsError, {
      enableHighAccuracy: true, maximumAge: 2000, timeout: 10000
    });
    timerInterval = setInterval(updateUI, 1000);

    setTimeout(() => { if (leafletMap) leafletMap.invalidateSize(); }, 200);
  };

  // ─── Discard ──────────────────────────────────────────────────────────────
  window.discardLiveRun = function () {
    if (isSimulating) {
      clearInterval(simInterval);
      isSimulating = false;
    }
    resetTracker();
    closeLiveRunTracker();
  };

  // ─── Save Run ─────────────────────────────────────────────────────────────
  window.saveLiveRun = async function () {
    const distKm = parseFloat($('lrtRevDist').dataset.distKm || 0);
    const timeMin = parseFloat($('lrtRevDist').dataset.timeMin || 0);
    const today = new Date().toISOString().split('T')[0];

    const saveBtn = $('lrtSaveBtn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving Run…';

    try {
      // 1. Save run with route_json directly to /add
      const formData = new FormData();
      formData.append('date', today);
      formData.append('distance', distKm.toFixed(4));
      formData.append('time', timeMin.toFixed(4));
      formData.append('run_type', 'easy');
      formData.append('notes', 'Recorded with Live GPS Trail Tracker 🗺️');
      formData.append('route_json', JSON.stringify(routePoints));

      const addResp = await fetch('/add', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: formData,
        redirect: 'follow'
      });

      // Extract run ID from redirect URL query param `open`
      const finalUrl = addResp.url || '';
      const openMatch = finalUrl.match(/[?&]open=(\d+)/);
      const runId = openMatch ? parseInt(openMatch[1]) : null;

      // 2. Also ensure route endpoint is synced
      if (runId && routePoints.length > 1) {
        try {
          await fetch(`/api/run/${runId}/route`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken()
            },
            body: JSON.stringify({
              route: routePoints,
              total_distance_km: distKm
            })
          });
        } catch (routeErr) {
          console.warn('[LiveRun] Route sync notice:', routeErr);
        }
      }

      resetTracker();
      closeLiveRunTracker();

      if (typeof loadRuns === 'function') loadRuns();
      showToast('🎉 Run saved! Check your history to see your trail.');

    } catch (err) {
      console.error('[LiveRun] Save error:', err);
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk me-2"></i>Save Run to Log';
      alert('Could not save run. Please try again.');
    }
  };

  // ─── Open / Close / Reset ─────────────────────────────────────────────────
  window.openLiveRunTracker = function () {
    const fab = $('quickActionsFab');
    if (fab) fab.style.setProperty('display', 'none', 'important');
    const overlay = $('liveRunOverlay');
    if (!overlay) { console.error('[LiveRun] Overlay not found'); return; }
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Initialise map after overlay is rendered
    if (typeof L !== 'undefined') {
      setTimeout(() => {
        initMap();
        if (leafletMap) leafletMap.invalidateSize();
      }, 200);
    } else {
      console.error('[LiveRun] Leaflet not loaded');
    }
  };

  window.closeLiveRunTracker = function () {
    if (isRunning || isSimulating) {
      if (!confirm('Stop tracking and discard this run?')) return;
      if (isSimulating) { clearInterval(simInterval); isSimulating = false; }
      if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
      clearInterval(timerInterval);
      resetTracker();
    }
    const overlay = $('liveRunOverlay');
    if (overlay) overlay.style.display = 'none';
    document.body.style.overflow = '';

    const fab = $('quickActionsFab');
    const homeView = $('homeView');
    if (fab && homeView && homeView.style.display !== 'none') {
      fab.style.removeProperty('display');
    }
  };

  function resetTracker() {
    isRunning = false;
    isPaused = false;
    isSimulating = false;
    userPannedAway = false;
    releaseWakeLock();
    watchId = null;
    timerInterval = null;
    startTime = null;
    pausedAt = null;
    totalPausedMs = 0;
    routePoints = [];
    totalDistanceKm = 0;

    if ($('lrtHeaderTitle')) $('lrtHeaderTitle').textContent = '🏃 LIVE RUN';
    if ($('lrtElapsed')) $('lrtElapsed').textContent = '00:00';
    if ($('lrtDistance')) $('lrtDistance').textContent = '0.00';
    if ($('lrtPace')) $('lrtPace').textContent = '--:--';
    if ($('lrtWaitingGps')) {
      $('lrtWaitingGps').style.display = '';
      $('lrtWaitingGps').textContent = '📡 Waiting for GPS fix…';
    }
    if ($('lrtStartBtn')) $('lrtStartBtn').style.display = '';
    if ($('lrtPauseBtn')) {
      $('lrtPauseBtn').style.display = 'none';
      $('lrtPauseBtn').innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
      $('lrtPauseBtn').classList.replace('btn-success', 'btn-warning');
    }
    if ($('lrtFinishBtn')) $('lrtFinishBtn').style.display = 'none';
    if ($('lrtTimerSection')) $('lrtTimerSection').style.display = '';
    if ($('lrtLiveStatsRow')) $('lrtLiveStatsRow').style.display = 'flex';
    if ($('lrtControlsRow')) $('lrtControlsRow').style.display = 'flex';
    if ($('lrtReviewOverlay')) $('lrtReviewOverlay').style.display = 'none';
    if ($('lrtFitTrailBtn')) $('lrtFitTrailBtn').style.display = 'none';
    if ($('lrtTrailSummaryBadge')) $('lrtTrailSummaryBadge').style.display = 'none';
    if ($('lrtRecenterBtn')) $('lrtRecenterBtn').style.display = 'none';

    if (routeGlowPolyline) routeGlowPolyline.setLatLngs([]);
    if (routePolyline) routePolyline.setLatLngs([]);
    if (currentMarker) { currentMarker.remove(); currentMarker = null; }
    clearTrailDecorations();
  }

  window.startLiveRun = function () { startTracking(); };

  // ─── Simulation / Demo Mode ───────────────────────────────────────────────
  // Allows testing realistic live trail tracking and review trail mapping
  window.simulateLiveRunDemo = function () {
    if (isRunning || isSimulating) {
      if (!confirm('Restart and simulate a new live demo trail?')) return;
      if (isSimulating) clearInterval(simInterval);
      resetTracker();
    }

    initMap();
    isSimulating = true;
    isRunning = true;
    isPaused = false;
    startTime = Date.now();
    totalPausedMs = 0;
    routePoints = [];
    totalDistanceKm = 0;

    $('lrtWaitingGps').style.display = 'none';
    $('lrtPauseBtn').style.display = '';
    $('lrtFinishBtn').style.display = '';
    $('lrtStartBtn').style.display = 'none';

    // Pick start coordinate: user current location or fallback scenic park loop
    let centerLat = 51.505;
    let centerLng = -0.09;
    if (routePoints.length > 0) {
      centerLat = routePoints[0].lat;
      centerLng = routePoints[0].lng;
    } else if (leafletMap && leafletMap.getCenter() && leafletMap.getZoom() > 5) {
      const c = leafletMap.getCenter();
      centerLat = c.lat;
      centerLng = c.lng;
    }

    // Generate ~35 realistic running path points forming a loop (~1.6 km)
    const totalSteps = 36;
    const simPoints = [];
    const radiusLat = 0.0055;
    const radiusLng = 0.0075;

    for (let i = 0; i < totalSteps; i++) {
      const angle = (i / (totalSteps - 1)) * 2 * Math.PI;
      // Add subtle curve perturbation for natural trail look
      const perturbation = 1 + 0.15 * Math.sin(angle * 3);
      const lat = centerLat + radiusLat * Math.sin(angle) * perturbation;
      const lng = centerLng + radiusLng * Math.cos(angle) * perturbation;
      simPoints.push({ lat, lng });
    }

    let stepIndex = 0;
    timerInterval = setInterval(updateUI, 1000);

    simInterval = setInterval(() => {
      if (stepIndex >= simPoints.length) {
        clearInterval(simInterval);
        finishLiveRun();
        return;
      }
      const pt = simPoints[stepIndex++];
      onPosition({ coords: { latitude: pt.lat, longitude: pt.lng } });
    }, 120);
  };

  // ─── Toast helper ─────────────────────────────────────────────────────────
  function showToast(msg) {
    if (typeof window.showSuccessToast === 'function') { window.showSuccessToast(msg); return; }
    const t = document.createElement('div');
    t.textContent = msg;
    Object.assign(t.style, {
      position: 'fixed', bottom: '80px', left: '50%', transform: 'translateX(-50%)',
      background: '#10b981', color: '#fff', padding: '10px 20px', borderRadius: '20px',
      zIndex: '9999', fontWeight: '600', boxShadow: '0 4px 12px rgba(0,0,0,.4)',
      transition: 'opacity .4s'
    });
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 400); }, 3000);
  }

  // ─── Route View Map (History Modal) ───────────────────────────────────────
  let viewMap = null;
  let currentViewRunId = null;
  let currentViewRoutePoints = [];

  window.viewRunRoute = async function (runId) {
    currentViewRunId = runId;
    currentViewRoutePoints = [];
    const modal = $('routeViewModal');
    if (!modal) return;

    const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
    bsModal.show();

    $('routeViewLoading').style.display = '';
    $('routeViewMapContainer').style.display = 'none';
    $('routeViewError').style.display = 'none';

    try {
      const resp = await fetch(`/api/run/${runId}/route`, {
        headers: { 'X-CSRFToken': csrfToken() }
      });
      if (!resp.ok) throw new Error('No route data');
      const data = await resp.json();
      const points = data.route || [];
      if (points.length < 2) throw new Error('Route too short');

      currentViewRoutePoints = points;

      $('routeViewLoading').style.display = 'none';
      $('routeViewMapContainer').style.display = '';

      if (!viewMap) {
        viewMap = L.map('routeViewMap', { zoomControl: true });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors', maxZoom: 19
        }).addTo(viewMap);
      } else {
        viewMap.eachLayer(layer => { if (!(layer instanceof L.TileLayer)) viewMap.removeLayer(layer); });
      }

      const latlngs = points.map(p => [p.lat, p.lng]);

      // Glowing trail casing
      L.polyline(latlngs, {
        color: 'rgba(16, 185, 129, 0.35)',
        weight: 9,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(viewMap);

      // Core athletic trail line
      const poly = L.polyline(latlngs, {
        color: '#10b981',
        weight: 5,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(viewMap);

      // Start & Finish Markers
      createStartMarker(latlngs[0][0], latlngs[0][1]).addTo(viewMap);
      createFinishMarker(latlngs[latlngs.length - 1][0], latlngs[latlngs.length - 1][1]).addTo(viewMap);

      // Kilometer split markers
      const splits = getKmSplitPoints(points);
      splits.forEach(s => {
        createSplitMarker(s.km, s.lat, s.lng).addTo(viewMap);
      });

      viewMap.fitBounds(poly.getBounds(), { padding: [40, 40] });
      setTimeout(() => viewMap.invalidateSize(), 200);

      // Stats
      $('rvDistance').textContent = (data.total_distance_km || 0).toFixed(2) + ' km';
      $('rvPoints').textContent = points.length + ' GPS points';

    } catch (err) {
      $('routeViewLoading').style.display = 'none';
      $('routeViewError').style.display = '';
      console.warn('[LiveRun] Route view error:', err);
    }
  };

  // Invalidate map size when modal is shown
  document.addEventListener('shown.bs.modal', function (e) {
    if (e.target.id === 'routeViewModal' && viewMap) {
      setTimeout(() => viewMap.invalidateSize(), 150);
    }
  });

  // Handle GPS route deletion from route modal
  document.addEventListener('DOMContentLoaded', function () {
    const deleteBtn = $('deleteRouteBtn');
    if (deleteBtn) {
      deleteBtn.onclick = async () => {
        if (!currentViewRunId) return;
        if (!confirm('Are you sure you want to permanently delete the GPS route for this run? Running distance and duration will remain saved.')) {
          return;
        }
        deleteBtn.disabled = true;
        deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Deleting…';
        try {
          const resp = await fetch(`/api/run/${currentViewRunId}/route`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken() }
          });
          const res = await resp.json();
          if (resp.ok && res.success) {
            routeCache[currentViewRunId] = false;
            const mapBtn = document.querySelector(`.run-map-btn[data-run-id="${currentViewRunId}"]`);
            if (mapBtn) mapBtn.style.setProperty('display', 'none', 'important');
            const modalEl = document.getElementById('routeViewModal');
            if (modalEl) {
              const m = bootstrap.Modal.getInstance(modalEl);
              if (m) m.hide();
            }
            showToast('GPS route deleted.');
          } else {
            alert(res.error || 'Failed to delete route.');
          }
        } catch (err) {
          alert('Error deleting route.');
        } finally {
          deleteBtn.disabled = false;
          deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete GPS Route';
        }
      };
    }
  });

  // Auto-show Map button when run card expands
  const routeCache = {};
  document.addEventListener('show.bs.collapse', function (e) {
    const el = e.target;
    if (!el || !el.id || !el.id.startsWith('runCardDetails-')) return;
    const runId = parseInt(el.id.replace('runCardDetails-', ''), 10);
    if (!runId) return;

    if (routeCache[runId] !== undefined) {
      if (routeCache[runId]) showMapBtn(runId);
      return;
    }

    fetch(`/api/run/${runId}/route`, {
      headers: { 'X-CSRFToken': csrfToken() }
    }).then(r => {
      routeCache[runId] = r.ok;
      if (r.ok) showMapBtn(runId);
    }).catch(() => { routeCache[runId] = false; });
  });

  function showMapBtn(runId) {
    const btn = document.querySelector(`.run-map-btn[data-run-id="${runId}"]`);
    if (btn) btn.style.setProperty('display', 'flex', 'important');
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // ─── TRAIL SHARE MODAL & MAP SHAPES (Thumb, Heart, Square, Oval) ───────────
  // ═══════════════════════════════════════════════════════════════════════════

  function generateTrailSvg(points, w, h) {
    w = w || 400;
    h = h || 400;

    if (!points || points.length < 2) {
      return `<svg width="100%" height="100%" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
        <rect width="${w}" height="${h}" fill="#080d14"/>
        <path d="M 100 280 C 120 180, 200 120, 280 200 S 320 100, 260 80" fill="none" stroke="#10b981" stroke-width="6" stroke-linecap="round"/>
        <circle cx="100" cy="280" r="8" fill="#10b981"/>
        <circle cx="260" cy="80" r="8" fill="#ef4444"/>
      </svg>`;
    }

    let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
    points.forEach(p => {
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lng < minLng) minLng = p.lng;
      if (p.lng > maxLng) maxLng = p.lng;
    });

    const avgLat = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const cosLat = Math.cos(avgLat);

    const dLat = Math.max(0.0001, maxLat - minLat);
    const dLng = Math.max(0.0001, (maxLng - minLng) * cosLat);

    // Keep trail within central 65% so it's fully visible in Heart, Thumb, Oval, Square
    const usableW = w * 0.65;
    const usableH = h * 0.65;
    const scale = Math.min(usableW / dLng, usableH / dLat);

    const cx = w / 2;
    const cy = h / 2;
    const centerLat = (minLat + maxLat) / 2;
    const centerLng = (minLng + maxLng) / 2;

    function toScreen(lat, lng) {
      const x = cx + (lng - centerLng) * cosLat * scale;
      const y = cy - (lat - centerLat) * scale;
      return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
    }

    const screenCoords = points.map(p => toScreen(p.lat, p.lng));
    const pathD = screenCoords.map((c, i) => (i === 0 ? `M ${c[0]} ${c[1]}` : `L ${c[0]} ${c[1]}`)).join(' ');

    const startPt = screenCoords[0];
    const endPt = screenCoords[screenCoords.length - 1];

    const splits = getKmSplitPoints(points);
    const splitSvg = splits.map(s => {
      const [sx, sy] = toScreen(s.lat, s.lng);
      return `<g transform="translate(${sx},${sy})">
        <circle r="10" fill="#111827" stroke="#10b981" stroke-width="2"/>
        <text y="3.5" font-size="9" font-weight="800" fill="#10b981" text-anchor="middle" font-family="'Inter', sans-serif">${s.km}</text>
      </g>`;
    }).join('');

    return `<svg width="100%" height="100%" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="tBgGrad_${w}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#080e16"/>
          <stop offset="100%" stop-color="#101924"/>
        </linearGradient>
        <pattern id="tGrid_${w}" width="36" height="36" patternUnits="userSpaceOnUse">
          <path d="M 36 0 L 0 0 0 36" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
        </pattern>
        <filter id="tGlow_${w}" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="5" result="blur"/>
          <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
      </defs>

      <rect width="${w}" height="${h}" fill="url(#tBgGrad_${w})"/>
      <rect width="${w}" height="${h}" fill="url(#tGrid_${w})"/>

      <circle cx="${w/2}" cy="${h/2}" r="${w*0.35}" fill="none" stroke="rgba(16,185,129,0.06)" stroke-width="1.5" stroke-dasharray="4 6"/>
      <circle cx="${w/2}" cy="${h/2}" r="${w*0.2}" fill="none" stroke="rgba(16,185,129,0.06)" stroke-width="1.5" stroke-dasharray="4 6"/>

      <!-- Glowing casing line -->
      <path d="${pathD}" fill="none" stroke="rgba(16, 185, 129, 0.45)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" filter="url(#tGlow_${w})"/>
      <!-- Core neon line -->
      <path d="${pathD}" fill="none" stroke="#10b981" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>

      <!-- Splits -->
      ${splitSvg}

      <!-- Start Marker -->
      <g transform="translate(${startPt[0]},${startPt[1]})">
        <circle r="12" fill="rgba(16,185,129,0.3)"/>
        <circle r="7" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
        <text y="-13" font-size="9" font-weight="800" fill="#10b981" text-anchor="middle" font-family="'Inter', sans-serif">START</text>
      </g>

      <!-- Finish Marker -->
      <g transform="translate(${endPt[0]},${endPt[1]})">
        <circle r="12" fill="rgba(239,68,68,0.3)"/>
        <circle r="7" fill="#ef4444" stroke="#ffffff" stroke-width="2"/>
        <text y="-13" font-size="9" font-weight="800" fill="#ef4444" text-anchor="middle" font-family="'Inter', sans-serif">FINISH</text>
      </g>
    </svg>`;
  }

  window.openTrailShareModal = function (data) {
    if (!data || !data.points || data.points.length === 0) {
      alert('No GPS trail points available to share for this run.');
      return;
    }

    trailShareData = data;
    selectedTrailShape = selectedTrailShape || 'thumb';

    // Populate Modal Preview Data
    const username = data.username || (document.getElementById('profileUsername')?.textContent?.trim() || 'runner').replace('@', '');
    const dateStr = data.date || new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

    if ($('tscRunnerName')) $('tscRunnerName').textContent = '@' + username;
    if ($('tscRunDate')) $('tscRunDate').textContent = dateStr;
    if ($('tscDist')) $('tscDist').textContent = Number(data.distKm).toFixed(2);
    if ($('tscTime')) $('tscTime').textContent = data.timeStr || '00:00';
    if ($('tscPace')) $('tscPace').textContent = data.paceStr || '--:--';
    if ($('tscCal')) $('tscCal').textContent = data.cal || '0';

    // Populate Export Container Data
    if ($('exportRunnerName')) $('exportRunnerName').textContent = '@' + username;
    if ($('exportRunDate')) $('exportRunDate').textContent = dateStr;
    if ($('exportDist')) $('exportDist').textContent = Number(data.distKm).toFixed(2);
    if ($('exportTime')) $('exportTime').textContent = data.timeStr || '00:00';
    if ($('exportPace')) $('exportPace').textContent = data.paceStr || '--:--';
    if ($('exportCal')) $('exportCal').textContent = data.cal || '0';

    // Inject SVG Trail
    const previewSvg = generateTrailSvg(data.points, 400, 400);
    const exportSvg = generateTrailSvg(data.points, 640, 640);

    if ($('trailSvgContainer')) $('trailSvgContainer').innerHTML = previewSvg;
    if ($('exportSvgContainer')) $('exportSvgContainer').innerHTML = exportSvg;

    // Apply active shape
    applyTrailShape(selectedTrailShape);

    // Show modal
    const overlay = $('trailShareOverlay');
    if (overlay) overlay.classList.add('active');
  };

  function applyTrailShape(shape) {
    selectedTrailShape = shape;

    // Update Pill Buttons
    const buttons = document.querySelectorAll('#trailShapeSelector .btn-shape-pill');
    buttons.forEach(btn => {
      if (btn.getAttribute('data-shape') === shape) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update Preview Container Class
    const frame = $('trailMapFrame');
    if (frame) {
      frame.className = `trail-frame-${shape}`;
    }

    // Update Export Container Style
    const expFrame = $('exportMapFrame');
    if (expFrame) {
      if (shape === 'thumb') {
        expFrame.style.borderRadius = '280px 280px 60px 60px';
        expFrame.style.border = '6px solid rgba(16, 185, 129, 0.85)';
        expFrame.style.boxShadow = '0 0 50px rgba(16, 185, 129, 0.4)';
        expFrame.style.clipPath = '';
        expFrame.style.filter = '';
      } else if (shape === 'heart') {
        expFrame.style.borderRadius = '0';
        expFrame.style.border = 'none';
        expFrame.style.boxShadow = '';
        expFrame.style.clipPath = "path('M 320,566 C 320,566, 56,378, 56,188 C 56,86, 132,36, 224,36 C 278,36, 306,68, 320,86 C 334,68, 362,36, 416,36 C 508,36, 584,86, 584,188 C 584,378, 320,566, 320,566 Z')";
        expFrame.style.filter = 'drop-shadow(0 0 35px rgba(239, 68, 68, 0.75))';
      } else if (shape === 'square') {
        expFrame.style.borderRadius = '48px';
        expFrame.style.border = '6px solid rgba(14, 165, 233, 0.85)';
        expFrame.style.boxShadow = '0 0 50px rgba(14, 165, 233, 0.4)';
        expFrame.style.clipPath = '';
        expFrame.style.filter = '';
      } else if (shape === 'oval') {
        expFrame.style.borderRadius = '50%';
        expFrame.style.border = '6px solid rgba(245, 158, 11, 0.85)';
        expFrame.style.boxShadow = '0 0 50px rgba(245, 158, 11, 0.4)';
        expFrame.style.clipPath = '';
        expFrame.style.filter = '';
      }
    }
  }

  window.selectTrailShareShape = function (shape) {
    if (typeof shape !== 'string') {
      if (shape && shape.target) {
        const btn = shape.target.closest('[data-shape]');
        shape = btn ? btn.getAttribute('data-shape') : null;
      } else if (this && this.getAttribute) {
        shape = this.getAttribute('data-shape');
      }
    }
    if (shape && typeof shape === 'string') {
      applyTrailShape(shape);
    }
  };

  window.closeTrailShareModal = function () {
    const overlay = $('trailShareOverlay');
    if (overlay) overlay.classList.remove('active');
  };

  window.closeTrailShareBackdrop = function (e) {
    if (e.target && e.target.id === 'trailShareOverlay') {
      window.closeTrailShareModal();
    }
  };

  // Launch Share Modal from Live Run Review
  window.openTrailShareFromLiveRun = function () {
    const distKm = parseFloat($('lrtRevDist')?.dataset?.distKm || totalDistanceKm || 0);
    const ms = elapsedMs();
    const timeStr = $('lrtRevTime')?.textContent || fmtDuration(ms);
    const paceStr = $('lrtRevPace')?.textContent || fmtPace(distKm, ms);
    const cal = $('lrtRevCal')?.textContent?.replace(/\D/g, '') || Math.round((ms / 60000) * 8.2);

    openTrailShareModal({
      points: routePoints,
      distKm: distKm,
      timeStr: timeStr,
      paceStr: paceStr,
      cal: cal,
      date: new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    });
  };

  // Launch Share Modal from Route History Modal
  window.shareTrailFromRouteModal = function () {
    if (!currentViewRoutePoints || currentViewRoutePoints.length === 0) {
      alert('Route data still loading or unavailable.');
      return;
    }
    const distText = $('rvDistance')?.textContent?.replace(' km', '') || '0';
    openTrailShareModal({
      points: currentViewRoutePoints,
      distKm: parseFloat(distText),
      timeStr: '--:--',
      paceStr: '--:--',
      cal: Math.round(parseFloat(distText) * 65),
      date: 'Saved Run'
    });
  };

  // Capture canvas and generate blob helper
  async function captureTrailCardBlob() {
    if (typeof html2canvas === 'undefined') {
      throw new Error('html2canvas library is not loaded');
    }
    const el = $('trailShareExportContainer');
    if (!el) throw new Error('Export container not found');

    const canvas = await html2canvas(el, {
      width: 1080,
      height: 1350,
      scale: 1,
      useCORS: true,
      backgroundColor: '#090d14',
      logging: false
    });

    return new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  }

  // Execute Web Share API or download fallback
  window.executeTrailShare = async function () {
    const btn = $('trailShareActionBtn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sharing…';
    }

    try {
      const blob = await captureTrailCardBlob();
      const file = new File([blob], `runrush_trail_${selectedTrailShape}.png`, { type: 'image/png' });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          title: 'My RunRush Trail',
          text: `Crushed a ${trailShareData.distKm} km run on RunRush! ⚡🏃`,
          files: [file]
        });
      } else {
        // Fallback to direct download
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `runrush_trail_${selectedTrailShape}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 200);
        showToast('Story card downloaded! Ready to share.');
      }
    } catch (err) {
      console.warn('[LiveRun] Share canceled or failed:', err);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-share-nodes me-2"></i>Share Story';
      }
    }
  };

  // Download PNG directly
  window.downloadTrailCard = async function () {
    const btn = $('trailDownloadActionBtn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Rendering…';
    }

    try {
      const blob = await captureTrailCardBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `runrush_trail_${selectedTrailShape}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 200);
      showToast('Trail card saved to your device!');
    } catch (err) {
      console.error('[LiveRun] Download failed:', err);
      alert('Could not generate image. Please try again.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-download me-2"></i>Download PNG';
      }
    }
  };

  // ─── Expose Global Actions ───────────────────────────────────────────────
  window.RR_ACTIONS = window.RR_ACTIONS || {};
  window.RR_ACTIONS.closeLiveRunTracker = function() { if (window.closeLiveRunTracker) window.closeLiveRunTracker(); };
  window.RR_ACTIONS.startLiveRun = function() { if (window.startLiveRun) window.startLiveRun(); };
  window.RR_ACTIONS.toggleLiveRunPause = function() { if (window.toggleLiveRunPause) window.toggleLiveRunPause(); };
  window.RR_ACTIONS.finishLiveRun = function() { if (window.finishLiveRun) window.finishLiveRun(); };
  window.RR_ACTIONS.saveLiveRun = function() { if (window.saveLiveRun) window.saveLiveRun(); };
  window.RR_ACTIONS.discardLiveRun = function() { if (window.discardLiveRun) window.discardLiveRun(); };
  window.RR_ACTIONS.toggleReviewDrawer = function() { if (window.toggleReviewDrawer) window.toggleReviewDrawer(); };
  window.RR_ACTIONS.resumeLiveRunFromReview = function() { if (window.resumeLiveRunFromReview) window.resumeLiveRunFromReview(); };
  window.RR_ACTIONS.fitLiveRunTrail = function() { if (window.fitLiveRunTrail) window.fitLiveRunTrail(); };
  window.RR_ACTIONS.recenterLiveRunMap = function() { if (window.recenterLiveRunMap) window.recenterLiveRunMap(); };
  window.RR_ACTIONS.simulateLiveRunDemo = function() { if (window.simulateLiveRunDemo) window.simulateLiveRunDemo(); };
  window.RR_ACTIONS.viewRunRoute = function(runId) { if (window.viewRunRoute) window.viewRunRoute(runId); };

  // Trail Share Actions
  window.RR_ACTIONS.openTrailShareFromLiveRun = function() { if (window.openTrailShareFromLiveRun) window.openTrailShareFromLiveRun(); };
  window.RR_ACTIONS.shareTrailFromRouteModal = function() { if (window.shareTrailFromRouteModal) window.shareTrailFromRouteModal(); };
  window.RR_ACTIONS.selectTrailShareShape = function(arg1, arg2) {
    var shape = null;
    if (typeof arg1 === 'string') {
      shape = arg1;
    } else if (typeof arg2 === 'string') {
      shape = arg2;
    } else if (this && this.getAttribute) {
      shape = this.getAttribute('data-shape') || (this.dataset ? this.dataset.shape : null);
    }
    if (!shape && arg1 && arg1.target && arg1.target.closest) {
      var btn = arg1.target.closest('[data-shape]');
      if (btn) shape = btn.getAttribute('data-shape');
    }
    if (shape && window.selectTrailShareShape) {
      window.selectTrailShareShape(shape);
    }
  };
  window.RR_ACTIONS.closeTrailShareModal = function() { if (window.closeTrailShareModal) window.closeTrailShareModal(); };
  window.RR_ACTIONS.closeTrailShareBackdrop = function(e) { if (window.closeTrailShareBackdrop) window.closeTrailShareBackdrop(e); };
  window.RR_ACTIONS.executeTrailShare = function() { if (window.executeTrailShare) window.executeTrailShare(); };
  window.RR_ACTIONS.downloadTrailCard = function() { if (window.downloadTrailCard) window.downloadTrailCard(); };

})();
