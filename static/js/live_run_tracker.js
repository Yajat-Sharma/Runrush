/**
 * live_run_tracker.js — Live GPS Run Tracker for RunRush
 * Uses navigator.geolocation + Leaflet.js (OpenStreetMap) for free route mapping.
 * Saves route GPS coordinates with the run for viewing in run history.
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
  let routePoints = [];   // [{lat, lng, ts}]
  let totalDistanceKm = 0;
  let leafletMap = null;
  let routePolyline = null;
  let currentMarker = null;
  let mapInitialised = false;
  let pendingRunId = null;  // run_id returned from /add after finishing
  let wakeLock = null;

  // ─── DOM refs (resolved on open) ─────────────────────────────────────────
  const $ = id => document.getElementById(id);

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  // ─── Screen Wake Lock (prevents phone from sleeping/locking while running) ─
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

  // ─── Format helpers ───────────────────────────────────────────────────────
  function fmtDuration(ms) {
    const totalSec = Math.floor(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }

  function fmtPace(distKm, ms) {
    if (distKm < 0.01) return '--:--';
    const minPerKm = ms / 60000 / distKm;
    const m = Math.floor(minPerKm);
    const s = Math.round((minPerKm - m) * 60);
    return `${m}:${String(s).padStart(2,'0')}`;
  }

  function elapsedMs() {
    if (!startTime) return 0;
    const now = isPaused ? pausedAt : Date.now();
    return now - startTime - totalPausedMs;
  }

  // ─── Leaflet map ──────────────────────────────────────────────────────────
  function initMap() {
    if (mapInitialised) return;
    mapInitialised = true;

    leafletMap = L.map('liveRunMap', { zoomControl: true, attributionControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19
    }).addTo(leafletMap);

    routePolyline = L.polyline([], { color: '#28a745', weight: 5, opacity: 0.85 }).addTo(leafletMap);

    // Default world view until we get a GPS fix
    leafletMap.setView([20, 0], 2);
  }

  function addPointToMap(lat, lng) {
    routePolyline.addLatLng([lat, lng]);

    // Update / create current position marker
    if (!currentMarker) {
      const icon = L.divIcon({
        html: '<div style="width:14px;height:14px;background:#28a745;border:3px solid #fff;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,.4)"></div>',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
        className: ''
      });
      currentMarker = L.marker([lat, lng], { icon }).addTo(leafletMap);
    } else {
      currentMarker.setLatLng([lat, lng]);
    }

    leafletMap.panTo([lat, lng]);

    // Auto-zoom to fit the route if it's large enough
    if (routePoints.length > 5) {
      leafletMap.fitBounds(routePolyline.getBounds(), { padding: [24, 24], maxZoom: 17 });
    } else {
      leafletMap.setView([lat, lng], 17);
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

    const { latitude: lat, longitude: lng, accuracy } = pos.coords;
    const ts = Date.now();

    // Filter out noisy fixes (accuracy > 50 m for first point is okay; afterwards skip huge jumps)
    if (routePoints.length > 0) {
      const prev = routePoints[routePoints.length - 1];
      const d = haversineKm(prev.lat, prev.lng, lat, lng);
      // Skip implausibly large jumps (> 0.5 km in one tick) as GPS noise
      if (d > 0.5) return;
      totalDistanceKm += d;
    }

    routePoints.push({ lat, lng, ts });
    addPointToMap(lat, lng);
    updateUI();

    // Hide the "waiting for GPS" notice
    const waiting = $('lrtWaitingGps');
    if (waiting) waiting.style.display = 'none';
  }

  function onGpsError(err) {
    console.warn('[LiveRun] GPS error:', err.message);
    const el = $('lrtWaitingGps');
    if (el) el.textContent = '⚠️ GPS unavailable — move to an open area';
  }

  // ─── Start ────────────────────────────────────────────────────────────────
  function startTracking() {
    if (!navigator.geolocation) {
      alert('GPS not supported on this device/browser.');
      return;
    }

    isRunning = true;
    isPaused = false;
    startTime = Date.now();
    totalPausedMs = 0;
    routePoints = [];
    totalDistanceKm = 0;
    pendingRunId = null;

    // Reset map
    if (routePolyline) routePolyline.setLatLngs([]);
    if (currentMarker) { currentMarker.remove(); currentMarker = null; }

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

    // Invalidate map size (it may have been hidden)
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

  // ─── Finish ───────────────────────────────────────────────────────────────
  window.finishLiveRun = function () {
    if (!isRunning) return;

    // Stop tracking
    isRunning = false;
    isPaused = false;
    releaseWakeLock();
    if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
    clearInterval(timerInterval);

    const ms = elapsedMs();
    const distKm = totalDistanceKm;
    const timeMin = ms / 60000;

    // Basic sanity: must have at least 10 m
    if (distKm < 0.01) {
      alert('Not enough distance recorded. Try running a bit longer!');
      reopenTracker();
      return;
    }

    // Populate review overlay
    $('lrtRevDist').textContent = distKm.toFixed(2) + ' km';
    $('lrtRevTime').textContent = fmtDuration(ms);
    $('lrtRevPace').textContent = fmtPace(distKm, ms) + ' /km';
    const cal = Math.round(timeMin * 7.5); // ~7.5 cal/min rough estimate
    $('lrtRevCal').textContent = cal + ' kcal';

    // Store values for save
    $('lrtRevDist').dataset.distKm = distKm;
    $('lrtRevDist').dataset.timeMin = timeMin;

    // Show review
    $('lrtReviewOverlay').style.display = 'flex';
  };

  function reopenTracker() {
    isRunning = true;
    requestWakeLock();
    watchId = navigator.geolocation.watchPosition(onPosition, onGpsError, {
      enableHighAccuracy: true, maximumAge: 2000, timeout: 10000
    });
    timerInterval = setInterval(updateUI, 1000);
    $('lrtReviewOverlay').style.display = 'none';
  }

  window.discardLiveRun = function () {
    resetTracker();
    closeLiveRunTracker();
  };

  window.saveLiveRun = async function () {
    const distKm = parseFloat($('lrtRevDist').dataset.distKm);
    const timeMin = parseFloat($('lrtRevDist').dataset.timeMin);
    const today = new Date().toISOString().split('T')[0];

    const saveBtn = $('lrtSaveBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
      // 1. Save the run via existing /add endpoint
      const formData = new FormData();
      formData.append('date', today);
      formData.append('distance', distKm.toFixed(4));
      formData.append('time', timeMin.toFixed(4));
      formData.append('run_type', 'easy');
      formData.append('notes', 'Recorded with Live GPS Tracker 🗺️');
      formData.append('route_json', JSON.stringify(routePoints));

      const addResp = await fetch('/add', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: formData,
        redirect: 'follow'
      });

      // /add does a redirect — extract run ID from the redirect URL query param `open`
      const finalUrl = addResp.url || '';
      const openMatch = finalUrl.match(/[?&]open=(\d+)/);
      const runId = openMatch ? parseInt(openMatch[1]) : null;

      // 2. Save route if we got a run ID
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
          console.warn('[LiveRun] Route save failed (non-critical):', routeErr);
        }
      }

      resetTracker();
      closeLiveRunTracker();

      // Reload runs tab
      if (typeof loadRuns === 'function') loadRuns();

      showToast('🎉 Run saved! Check your history for the route map.');

    } catch (err) {
      console.error('[LiveRun] Save error:', err);
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Run';
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

    // Initialise map after overlay is visible so dimensions are correct
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
    if (isRunning) {
      if (!confirm('Stop tracking and discard this run?')) return;
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
    releaseWakeLock();
    watchId = null;
    timerInterval = null;
    startTime = null;
    pausedAt = null;
    totalPausedMs = 0;
    routePoints = [];
    totalDistanceKm = 0;

    if ($('lrtElapsed')) $('lrtElapsed').textContent = '00:00';
    if ($('lrtDistance')) $('lrtDistance').textContent = '0.00';
    if ($('lrtPace')) $('lrtPace').textContent = '--:--';
    if ($('lrtWaitingGps')) { $('lrtWaitingGps').style.display = ''; $('lrtWaitingGps').textContent = '📡 Waiting for GPS fix…'; }
    if ($('lrtStartBtn')) $('lrtStartBtn').style.display = '';
    if ($('lrtPauseBtn')) { $('lrtPauseBtn').style.display = 'none'; $('lrtPauseBtn').innerHTML = '<i class="fa-solid fa-pause"></i> Pause'; $('lrtPauseBtn').classList.replace('btn-success', 'btn-warning'); }
    if ($('lrtFinishBtn')) $('lrtFinishBtn').style.display = 'none';
    if ($('lrtReviewOverlay')) $('lrtReviewOverlay').style.display = 'none';
    if (routePolyline) routePolyline.setLatLngs([]);
    if (currentMarker) { currentMarker.remove(); currentMarker = null; }
  }

  window.startLiveRun = function () { startTracking(); };

  // ─── Toast helper (reuse if defined elsewhere) ────────────────────────────
  function showToast(msg) {
    if (typeof window.showSuccessToast === 'function') { window.showSuccessToast(msg); return; }
    // Fallback simple toast
    const t = document.createElement('div');
    t.textContent = msg;
    Object.assign(t.style, {
      position:'fixed', bottom:'80px', left:'50%', transform:'translateX(-50%)',
      background:'#28a745', color:'#fff', padding:'10px 20px', borderRadius:'20px',
      zIndex:'9999', fontWeight:'600', boxShadow:'0 4px 12px rgba(0,0,0,.3)',
      transition:'opacity .4s'
    });
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; setTimeout(() => t.remove(), 400); }, 3000);
  }

  // ─── Route View Map (run history) ─────────────────────────────────────────
  let viewMap = null;
  let currentViewRunId = null;

  
  window.RR_ACTIONS = window.RR_ACTIONS || {};
  window.RR_ACTIONS.closeLiveRunTracker = function() { if (window.closeLiveRunTracker) window.closeLiveRunTracker(); };
  window.RR_ACTIONS.startLiveRun = function() { if (window.startLiveRun) window.startLiveRun(); };
  window.RR_ACTIONS.toggleLiveRunPause = function() { if (window.toggleLiveRunPause) window.toggleLiveRunPause(); };
  window.RR_ACTIONS.finishLiveRun = function() { if (window.finishLiveRun) window.finishLiveRun(); };
  window.RR_ACTIONS.saveLiveRun = function() { if (window.saveLiveRun) window.saveLiveRun(); };
  window.RR_ACTIONS.discardLiveRun = function() { if (window.discardLiveRun) window.discardLiveRun(); };
  window.RR_ACTIONS.viewRunRoute = function(runId) { if (window.viewRunRoute) window.viewRunRoute(runId); };

  window.viewRunRoute = async function (runId) {
    currentViewRunId = runId;
    const modal = $('routeViewModal');
    if (!modal) return;

    // Show modal (Bootstrap)
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

      // Init or reuse map
      if (!viewMap) {
        viewMap = L.map('routeViewMap', { zoomControl: true });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors', maxZoom: 19
        }).addTo(viewMap);
      } else {
        viewMap.eachLayer(layer => { if (!(layer instanceof L.TileLayer)) viewMap.removeLayer(layer); });
      }

      const latlngs = points.map(p => [p.lat, p.lng]);
      const poly = L.polyline(latlngs, { color: '#28a745', weight: 5 }).addTo(viewMap);

      // Start / End markers
      L.circleMarker(latlngs[0], { radius: 8, color: '#fff', fillColor: '#28a745', fillOpacity: 1, weight: 3 })
        .bindTooltip('Start').addTo(viewMap);
      L.circleMarker(latlngs[latlngs.length - 1], { radius: 8, color: '#fff', fillColor: '#dc3545', fillOpacity: 1, weight: 3 })
        .bindTooltip('Finish').addTo(viewMap);

      viewMap.fitBounds(poly.getBounds(), { padding: [24, 24] });
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

  // Invalidate map size when modal is shown (Bootstrap event)
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

  // ─── Auto-show Map button when run card expands ────────────────────────────
  // We observe Bootstrap 'show.bs.collapse' events on runCardDetails elements
  // and check if the run has a saved route. If yes, reveal the hidden map btn.
  const routeCache = {};  // runId -> true/false

  document.addEventListener('show.bs.collapse', function (e) {
    const el = e.target;
    if (!el || !el.id || !el.id.startsWith('runCardDetails-')) return;
    const runId = parseInt(el.id.replace('runCardDetails-', ''), 10);
    if (!runId) return;

    if (routeCache[runId] !== undefined) {
      if (routeCache[runId]) showMapBtn(runId);
      return;
    }

    // Probe the route endpoint
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

})();
