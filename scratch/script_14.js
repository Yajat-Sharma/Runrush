
    let currentParsedData = null;

    function handleCsvFileSelected(input) {
      const file = input?.files[0];
      const fnEl = document.getElementById('selectedFileName');
      const errEl = document.getElementById('parseErrorAlert');
      if (file) {
        fnEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        fnEl.style.display = 'block';
        if (errEl) errEl.style.display = 'none';
      } else {
        if (fnEl) fnEl.style.display = 'none';
      }
    }

    async function uploadAndParseCsv() {
      const input = document.getElementById('stravaCsvInput');
      const file = input?.files[0];
      const errorEl = document.getElementById('parseErrorAlert');
      const parseBtn = document.getElementById('parseCsvBtn');

      if (!file) {
        errorEl.textContent = 'Please select a CSV file first.';
        errorEl.style.display = 'block';
        return;
      }

      const formData = new FormData();
      formData.append('file', file);

      parseBtn.disabled = true;
      parseBtn.textContent = 'Parsing...';
      errorEl.style.display = 'none';

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/parse-import', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: formData
        });
        const res = await resp.json();

        parseBtn.disabled = false;
        parseBtn.textContent = 'Parse & Preview';

        if (!resp.ok || !res.success) {
          errorEl.textContent = `${res.error || 'Failed to parse file'}`;
          errorEl.style.display = 'block';
          return;
        }

        currentParsedData = res.data;
        renderImportPreview(currentParsedData);

      } catch (err) {
        parseBtn.disabled = false;
        parseBtn.textContent = 'Parse & Preview';
        errorEl.textContent = `Network/Server error: ${err.message}`;
        errorEl.style.display = 'block';
      }
    }

    function renderImportPreview(data) {
      document.getElementById('importStepUpload').style.display = 'none';
      document.getElementById('importStepPreview').style.display = 'block';
      document.getElementById('parseCsvBtn').style.display = 'none';
      document.getElementById('importBackBtn').style.display = 'inline-block';
      
      const confirmBtn = document.getElementById('confirmImportBtn');
      confirmBtn.style.display = 'inline-block';

      document.getElementById('cntTotal').textContent = data.total_rows;
      document.getElementById('cntValid').textContent = data.valid_count;
      document.getElementById('cntDup').textContent = data.duplicate_count;
      document.getElementById('cntSkipped').textContent = data.skipped_non_run_count + data.invalid_count;

      const tbody = document.getElementById('importPreviewTbody');
      tbody.innerHTML = '';

      if (data.valid_count === 0) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'No Valid Runs to Import';
      } else {
        confirmBtn.disabled = false;
        confirmBtn.textContent = `Import ${data.valid_count} Valid Run(s)`;
      }

      data.valid_runs.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${r.date}</td>
          <td>${escapeHtml(r.name)}</td>
          <td>${r.distance} km</td>
          <td>${r.time} min</td>
          <td>${r.pace} min/km</td>
          <td><span class="badge bg-success">Ready</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.duplicates.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-secondary opacity-75';
        tr.innerHTML = `
          <td>${r.date}</td>
          <td>${escapeHtml(r.name)}</td>
          <td>${r.distance} km</td>
          <td>${r.time} min</td>
          <td>${r.pace} min/km</td>
          <td><span class="badge bg-warning text-dark">Duplicate</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.skipped.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-dark opacity-50';
        tr.innerHTML = `
          <td>-</td>
          <td>${escapeHtml(r.name)}</td>
          <td colspan="3"><small class="text-muted">${escapeHtml(r.reason)}</small></td>
          <td><span class="badge bg-secondary">Skipped</span></td>
        `;
        tbody.appendChild(tr);
      });

      data.invalids.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'table-danger opacity-75';
        tr.innerHTML = `
          <td>-</td>
          <td>${escapeHtml(r.name)}</td>
          <td colspan="3"><small class="text-danger">${escapeHtml(r.reason)}</small></td>
          <td><span class="badge bg-danger">Invalid</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function resetImportModal() {
      document.getElementById('importStepUpload').style.display = 'block';
      document.getElementById('importStepPreview').style.display = 'none';
      document.getElementById('parseCsvBtn').style.display = 'inline-block';
      document.getElementById('importBackBtn').style.display = 'none';
      document.getElementById('confirmImportBtn').style.display = 'none';
      document.getElementById('stravaCsvInput').value = '';
      const fnEl = document.getElementById('selectedFileName');
      if (fnEl) fnEl.style.display = 'none';
      const pErr = document.getElementById('parseErrorAlert');
      if (pErr) pErr.style.display = 'none';
      const cErr = document.getElementById('importConfirmAlert');
      if (cErr) cErr.style.display = 'none';
      currentParsedData = null;
    }

    async function confirmBatchImport() {
      if (!currentParsedData || !currentParsedData.valid_runs || currentParsedData.valid_runs.length === 0) {
        return;
      }

      const confirmBtn = document.getElementById('confirmImportBtn');
      const alertEl = document.getElementById('importConfirmAlert');

      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Importing...';
      alertEl.style.display = 'none';

      try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/api/confirm-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ runs: currentParsedData.valid_runs })
        });

        const res = await resp.json();

        if (!resp.ok || !res.success) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = `Import ${currentParsedData.valid_runs.length} Valid Run(s)`;
          alertEl.textContent = `${res.error || 'Import failed'}`;
          alertEl.style.display = 'block';
          return;
        }

        alertEl.className = 'alert alert-success mt-3';
        alertEl.textContent = `${res.message || 'Import successful!'}`;
        alertEl.style.display = 'block';

        setTimeout(() => {
          window.location.reload();
        }, 1500);

      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = `Import ${currentParsedData.valid_runs.length} Valid Run(s)`;
        alertEl.textContent = `Network/Server error: ${err.message}`;
        alertEl.style.display = 'block';
      }
    }
  