
    let pendingImportTab = 'csv';

    // ── Open import modal and store target tab to initialize on show ──
    function openImportTab(tab) {
      pendingImportTab = tab;
    }

    document.addEventListener('DOMContentLoaded', () => {

      // Auto-load on initial view
      loadWeeklyGoal();

      const importModal = document.getElementById('importRunsModal');
      if (importModal) {
        importModal.addEventListener('show.bs.modal', () => {
          const targetTab = pendingImportTab || 'csv';
          const csvBtn = document.getElementById('csvTabBtn');
          const ssBtn = document.getElementById('screenshotTabBtn');
          const csvPane = document.getElementById('csvTabPane');
          const ssPane = document.getElementById('screenshotTabPane');

          if (targetTab === 'screenshot') {
            csvBtn.classList.remove('active');
            csvBtn.setAttribute('aria-selected', 'false');
            ssBtn.classList.add('active');
            ssBtn.setAttribute('aria-selected', 'true');

            csvPane.classList.remove('show', 'active');
            ssPane.classList.add('show', 'active');

            resetScreenshotModal();
          } else {
            ssBtn.classList.remove('active');
            ssBtn.setAttribute('aria-selected', 'false');
            csvBtn.classList.add('active');
            csvBtn.setAttribute('aria-selected', 'true');

            ssPane.classList.remove('show', 'active');
            csvPane.classList.add('show', 'active');

            resetImportModal();
          }
        });
      }

      // ── Drag & Drop Event Handlers ──
      setupDragAndDrop('csvDropZone', 'stravaCsvInput', handleCsvFileSelected);
      setupDragAndDrop('screenshotDropZone', 'screenshotInput', handleScreenshotSelected);
    });

    function setupDragAndDrop(zoneId, inputId, onFileSelected) {
      const zone = document.getElementById(zoneId);
      const input = document.getElementById(inputId);
      if (!zone || !input) return;

      ['dragenter', 'dragover'].forEach(eventName => {
        zone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.add('drag-active');
        }, false);
      });

      ['dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.remove('drag-active');
        }, false);
      });

      zone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
          input.files = files;
          onFileSelected(input);
        }
      }, false);
    }

    // ── Screenshot step state ──
    function ssShowStep(step) {
      // steps: 'upload' | 'loading' | 'preview' | 'error'
      ['ssStepUpload','ssStepLoading','ssStepPreview','ssStepError'].forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
      document.getElementById('ssStep' + step.charAt(0).toUpperCase() + step.slice(1)).style.display = '';
    }

    function handleScreenshotSelected(input) {
      const file = input?.files[0];
      const el   = document.getElementById('ssSelectedFileName');
      const errEl = document.getElementById('ssUploadError');
      if (file) {
        el.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        el.style.display = 'block';
        if (errEl) errEl.style.display = 'none';
      } else {
        el.style.display = 'none';
      }
    }

    async function uploadAndParseScreenshot() {
      const input = document.getElementById('screenshotInput');
      const file  = input?.files[0];
      const errEl = document.getElementById('ssUploadError');

      if (!file) {
        errEl.textContent = 'Please select an image file first.';
        errEl.style.display = 'block';
        return;
      }

      const parseBtn = document.getElementById('ssParseBtn');
      parseBtn.disabled = true;
      parseBtn.textContent = 'Uploading...';
      ssShowStep('loading');

      const formData = new FormData();
      formData.append('file', file);

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/parse-screenshot', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: formData
        });
        const res = await resp.json();

        parseBtn.disabled = false;
        parseBtn.textContent = 'Analyse Screenshot';

        if (!resp.ok || !res.success) {
          document.getElementById('ssErrorMsg').textContent = res.error || 'Failed to analyse screenshot.';
          ssShowStep('error');
          return;
        }

        // Populate editable preview form
        const d = res.data;
        document.getElementById('ssDistanceKm').value = d.distance_km ?? '';
        document.getElementById('ssTimeMin').value     = d.time_min    ?? '';
        document.getElementById('ssDate').value        = d.date        ?? '';
        document.getElementById('ssPace').value        = d.pace_per_km ?? '';
        document.getElementById('ssCalories').value   = d.calories     ?? '';
        document.getElementById('ssHeartRate').value  = d.average_heart_rate ?? '';
        document.getElementById('ssElevation').value  = d.elevation_gain_m   ?? '';
        document.getElementById('ssSourceApp').value  = d.source_app   ?? 'unknown';

        ssShowStep('preview');
        document.getElementById('ssBackBtn').style.display    = 'inline-block';
        document.getElementById('ssParseBtn').style.display   = 'none';
        document.getElementById('ssConfirmBtn').style.display = 'inline-block';

      } catch (err) {
        parseBtn.disabled = false;
        parseBtn.textContent = 'Analyse Screenshot';
        document.getElementById('ssErrorMsg').textContent = `Network/Server error: ${err.message}`;
        ssShowStep('error');
      }
    }

    async function confirmScreenshotImport() {
      const confirmBtn = document.getElementById('ssConfirmBtn');
      const alertEl   = document.getElementById('ssConfirmError');

      const distance_km = parseFloat(document.getElementById('ssDistanceKm').value);
      const time_min    = parseFloat(document.getElementById('ssTimeMin').value);

      if (!distance_km || !time_min || distance_km <= 0 || time_min <= 0) {
        alertEl.textContent = 'Distance and Duration are required.';
        alertEl.style.display = 'block';
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      alertEl.style.display = 'none';

      const payload = {
        distance_km,
        time_min,
        date:        document.getElementById('ssDate').value        || null,
        run_type:    document.getElementById('ssRunType').value      || 'easy',
        notes:       document.getElementById('ssNotes').value        || '',
        source_app:  document.getElementById('ssSourceApp').value   || 'unknown',
      };

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/confirm-screenshot-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify(payload)
        });
        const res = await resp.json();

        if (!resp.ok || !res.success) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Import This Run';
          alertEl.textContent = `${res.error || 'Import failed'}`;
          alertEl.style.display = 'block';
          return;
        }

        alertEl.className = 'alert alert-success mt-3';
        alertEl.textContent = `${res.message || 'Run imported!'}`;
        alertEl.style.display = 'block';

        setTimeout(() => { window.location.reload(); }, 1500);

      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Import This Run';
        alertEl.textContent = `Network/Server error: ${err.message}`;
        alertEl.style.display = 'block';
      }
    }

    function resetScreenshotModal() {
      document.getElementById('screenshotInput').value = '';
      document.getElementById('ssSelectedFileName').style.display = 'none';
      document.getElementById('ssUploadError').style.display     = 'none';
      document.getElementById('ssConfirmError').style.display    = 'none';
      document.getElementById('ssBackBtn').style.display         = 'none';
      document.getElementById('ssParseBtn').style.display        = 'inline-block';
      document.getElementById('ssParseBtn').disabled             = false;
      document.getElementById('ssParseBtn').textContent          = 'Analyse Screenshot';
      document.getElementById('ssConfirmBtn').style.display      = 'none';
      ssShowStep('upload');
    }
  