/* 
 * Offline UI Management
 * Handles UI updates for offline runs and sync status
 */

// Update offline runs UI panel
async function updateOfflineRunsUI() {
    const panel = document.getElementById('offlineRunsPanel');
    const runsList = document.getElementById('offlineRunsList');

    if (!panel || !runsList) return;

    try {
        const allRuns = await getAllOfflineRuns();
        const pendingRuns = allRuns.filter(r => r.syncStatus === 'pending' || r.syncStatus === 'failed');

        if (pendingRuns.length === 0) {
            panel.style.display = 'none';
            return;
        }

        panel.style.display = 'block';

        // Build runs list HTML
        let html = '<div class="list-group">';

        for (const run of pendingRuns) {
            const statusBadge = run.syncStatus === 'pending'
                ? '<span class="badge bg-warning">⏳ Pending</span>'
                : '<span class="badge bg-danger">❌ Failed</span>';

            const retryBtn = run.syncStatus === 'failed'
                ? `<button class="btn btn-sm btn-outline-danger" onclick="retrySync('${run.tempId}')">Retry</button>`
                : '';

            html += `
        <div class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center">
          <div>
            <strong>${run.distance} km</strong> in ${run.time} min
            <br>
            <small class="text-muted">${run.date}</small>
            ${run.errorMessage ? `<br><small class="text-danger">${run.errorMessage}</small>` : ''}
          </div>
          <div>
            ${statusBadge}
            ${retryBtn}
          </div>
        </div>
      `;
        }

        html += '</div>';
        runsList.innerHTML = html;

    } catch (error) {
        console.error('Error updating offline runs UI:', error);
    }
}

// Retry failed sync for a specific run
async function retrySync(tempId) {
    try {
        const run = await getRunByTempId(tempId);
        if (!run) return;

        // Reset status to pending
        run.syncStatus = 'pending';
        run.errorMessage = null;
        await updateRun(run);

        // Trigger sync
        await syncOfflineRuns();

    } catch (error) {
        console.error('Retry sync error:', error);
        showSyncNotification('Failed to retry sync', 'warning');
    }
}

// Get run by temp ID
async function getRunByTempId(tempId) {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.get(tempId);

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// Update run in IndexedDB
async function updateRun(run) {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.put(run);

        request.onsuccess = () => resolve(run);
        request.onerror = () => reject(request.error);
    });
}
