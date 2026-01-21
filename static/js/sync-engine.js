/* 
 * Sync Engine - Automatic sync of offline runs
 * Handles syncing when internet is restored
 */

let isSyncing = false;
let syncRetryTimeout = null;

// Check if online
function isOnline() {
    return navigator.onLine;
}

// Sync all pending offline runs
async function syncOfflineRuns() {
    if (!isOnline()) {
        console.log('Cannot sync: offline');
        return { success: false, reason: 'offline' };
    }

    if (isSyncing) {
        console.log('Sync already in progress');
        return { success: false, reason: 'already_syncing' };
    }

    isSyncing = true;
    updateSyncUI('syncing');

    try {
        const pendingRuns = await getPendingRuns();

        if (pendingRuns.length === 0) {
            console.log('No pending runs to sync');
            isSyncing = false;
            updateSyncUI('idle');
            return { success: true, synced: 0 };
        }

        let successCount = 0;
        let failCount = 0;

        for (const run of pendingRuns) {
            try {
                const result = await syncSingleRun(run);

                if (result.success) {
                    await markAsSynced(run.tempId);
                    // Delete after successful sync
                    await deleteOfflineRun(run.tempId);
                    successCount++;
                } else {
                    await markAsFailed(run.tempId, result.error);
                    failCount++;
                }
            } catch (error) {
                console.error('Sync error for run:', run.tempId, error);
                await markAsFailed(run.tempId, error.message);
                failCount++;
            }

            // Small delay between syncs to avoid overwhelming server
            await new Promise(resolve => setTimeout(resolve, 200));
        }

        isSyncing = false;
        updateSyncUI('idle');
        updateOfflineRunsUI();

        // Reload page to show synced runs
        if (successCount > 0) {
            showSyncNotification(`✅ ${successCount} run(s) synced successfully!`);
            setTimeout(() => window.location.reload(), 1500);
        }

        if (failCount > 0) {
            showSyncNotification(`⚠️ ${failCount} run(s) failed to sync. Tap to retry.`, 'warning');
        }

        return { success: true, synced: successCount, failed: failCount };

    } catch (error) {
        console.error('Sync engine error:', error);
        isSyncing = false;
        updateSyncUI('error');
        return { success: false, reason: error.message };
    }
}

// Sync a single run to backend
async function syncSingleRun(run) {
    try {
        const response = await fetch('/api/sync-run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tempId: run.tempId,
                date: run.date,
                distance: run.distance,
                time: run.time,
                notes: run.notes,
                hash: run.hash,
                createdAt: run.createdAt
            })
        });

        if (response.ok) {
            const data = await response.json();
            return { success: true, data };
        } else {
            const error = await response.json();
            return { success: false, error: error.error || 'Sync failed' };
        }
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// Schedule retry with exponential backoff
function scheduleRetry(attempt = 1) {
    if (syncRetryTimeout) {
        clearTimeout(syncRetryTimeout);
    }

    const maxAttempts = 3;
    if (attempt > maxAttempts) {
        console.log('Max retry attempts reached');
        return;
    }

    // Exponential backoff: 5s, 10s, 20s
    const delay = Math.min(5000 * Math.pow(2, attempt - 1), 20000);

    console.log(`Scheduling retry attempt ${attempt} in ${delay}ms`);

    syncRetryTimeout = setTimeout(async () => {
        const result = await syncOfflineRuns();

        if (!result.success && result.reason !== 'offline') {
            scheduleRetry(attempt + 1);
        }
    }, delay);
}

// Update sync UI indicator
function updateSyncUI(state) {
    const syncButton = document.getElementById('syncNowBtn');
    const syncStatus = document.getElementById('syncStatus');

    if (!syncButton || !syncStatus) return;

    switch (state) {
        case 'syncing':
            syncButton.disabled = true;
            syncButton.innerHTML = '🔄 Syncing...';
            syncStatus.textContent = 'Syncing offline runs...';
            break;
        case 'idle':
            syncButton.disabled = false;
            syncButton.innerHTML = '🔄 Sync Now';
            syncStatus.textContent = '';
            break;
        case 'error':
            syncButton.disabled = false;
            syncButton.innerHTML = '⚠️ Retry Sync';
            syncStatus.textContent = 'Sync failed. Click to retry.';
            break;
    }
}

// Show sync notification
function showSyncNotification(message, type = 'success') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'success' ? 'success' : 'warning'} position-fixed top-0 start-50 translate-middle-x mt-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Listen for online event
window.addEventListener('online', () => {
    console.log('Network restored, attempting sync...');
    updateNetworkStatus(true);

    // Debounce: wait 2 seconds before syncing
    setTimeout(() => {
        if (isOnline()) {
            syncOfflineRuns();
        }
    }, 2000);
});

// Listen for offline event
window.addEventListener('offline', () => {
    console.log('Network lost');
    updateNetworkStatus(false);
});

// Update network status indicator
function updateNetworkStatus(online) {
    const statusIndicator = document.getElementById('networkStatus');
    if (!statusIndicator) return;

    if (online) {
        statusIndicator.innerHTML = '🟢 Online';
        statusIndicator.className = 'badge bg-success';
    } else {
        statusIndicator.innerHTML = '🔴 Offline';
        statusIndicator.className = 'badge bg-danger';
    }
}

// Manual sync trigger
async function syncNow() {
    await syncOfflineRuns();
}

// Initialize on page load
window.addEventListener('load', async () => {
    // Set initial network status
    updateNetworkStatus(isOnline());

    // Update offline runs UI
    await updateOfflineRunsUI();

    // Auto-sync if online
    if (isOnline()) {
        const pendingCount = await getPendingCount();
        if (pendingCount > 0) {
            console.log(`Found ${pendingCount} pending runs, syncing...`);
            setTimeout(() => syncOfflineRuns(), 1000);
        }
    }
});
