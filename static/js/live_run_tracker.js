/**
 * live_run_tracker.js — Live GPS Run Tracker & Trail Mapping for RunRush
 * Uses navigator.geolocation + Leaflet.js (OpenStreetMap) for route mapping.
 * Visualizes the route as an athletic running trail with start/finish badges,
 * kilometer splits, and an interactive post-run review drawer.
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
        // Prompt or automatically show finished trail
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

  window.viewRunRoute = async function (runId) {
    currentViewRunId = runId;
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

})();
