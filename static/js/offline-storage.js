/* 
 * Offline Storage Module - IndexedDB
 * Handles local storage of runs when offline
 */

const DB_NAME = 'RunRushDB';
const DB_VERSION = 1;
const STORE_NAME = 'offline_runs';

let db = null;

// Initialize IndexedDB
async function initOfflineDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            db = request.result;
            resolve(db);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;

            // Create object store if it doesn't exist
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                const objectStore = db.createObjectStore(STORE_NAME, { keyPath: 'tempId' });

                // Create indexes
                objectStore.createIndex('syncStatus', 'syncStatus', { unique: false });
                objectStore.createIndex('createdAt', 'createdAt', { unique: false });
                objectStore.createIndex('date', 'date', { unique: false });
            }
        };
    });
}

// Generate unique temporary ID
function generateTempId() {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 9);
    return `offline_${timestamp}_${random}`;
}

// Generate hash for duplicate detection
async function generateRunHash(date, distance, time) {
    const data = `${date}${distance}${time}`;
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(data);
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Save run to IndexedDB
async function saveOfflineRun(runData) {
    if (!db) await initOfflineDB();

    const hash = await generateRunHash(runData.date, runData.distance, runData.time);

    const offlineRun = {
        tempId: generateTempId(),
        date: runData.date,
        distance: parseFloat(runData.distance),
        time: parseFloat(runData.time),
        notes: runData.notes || '',
        createdAt: Date.now(),
        syncStatus: 'pending',
        errorMessage: null,
        hash: hash,
        retryCount: 0
    };

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.add(offlineRun);

        request.onsuccess = () => resolve(offlineRun);
        request.onerror = () => reject(request.error);
    });
}

// Get all pending runs
async function getPendingRuns() {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const objectStore = transaction.objectStore(STORE_NAME);
        const index = objectStore.index('syncStatus');
        const request = index.getAll('pending');

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// Get all runs (any status)
async function getAllOfflineRuns() {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.getAll();

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// Mark run as synced
async function markAsSynced(tempId) {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.get(tempId);

        request.onsuccess = () => {
            const run = request.result;
            if (run) {
                run.syncStatus = 'synced';
                run.errorMessage = null;
                const updateRequest = objectStore.put(run);
                updateRequest.onsuccess = () => resolve(run);
                updateRequest.onerror = () => reject(updateRequest.error);
            } else {
                reject(new Error('Run not found'));
            }
        };
        request.onerror = () => reject(request.error);
    });
}

// Mark run as failed
async function markAsFailed(tempId, errorMessage) {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.get(tempId);

        request.onsuccess = () => {
            const run = request.result;
            if (run) {
                run.syncStatus = 'failed';
                run.errorMessage = errorMessage;
                run.retryCount = (run.retryCount || 0) + 1;
                const updateRequest = objectStore.put(run);
                updateRequest.onsuccess = () => resolve(run);
                updateRequest.onerror = () => reject(updateRequest.error);
            } else {
                reject(new Error('Run not found'));
            }
        };
        request.onerror = () => reject(request.error);
    });
}

// Delete run from IndexedDB
async function deleteOfflineRun(tempId) {
    if (!db) await initOfflineDB();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const objectStore = transaction.objectStore(STORE_NAME);
        const request = objectStore.delete(tempId);

        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}

// Clear all synced runs (cleanup)
async function clearSyncedRuns() {
    if (!db) await initOfflineDB();

    const allRuns = await getAllOfflineRuns();
    const syncedRuns = allRuns.filter(run => run.syncStatus === 'synced');

    for (const run of syncedRuns) {
        await deleteOfflineRun(run.tempId);
    }

    return syncedRuns.length;
}

// Get count of pending runs
async function getPendingCount() {
    const pending = await getPendingRuns();
    return pending.length;
}

// Initialize on load
if (typeof window !== 'undefined') {
    window.addEventListener('load', () => {
        initOfflineDB().catch(err => {
            console.error('Failed to initialize offline database:', err);
        });
    });
}
