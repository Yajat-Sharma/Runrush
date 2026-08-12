/*
 * PWA Registration & Install Prompt
 * Registers the service worker and handles the "Add to Home Screen" prompt.
 */

// ─── Service Worker Registration ────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/static/sw.js', {
        scope: '/'
      });
      console.log('[PWA] Service Worker registered, scope:', registration.scope);

      // Listen for SW updates
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'activated' && navigator.serviceWorker.controller) {
            // New SW activated — show update banner
            showUpdateBanner();
          }
        });
      });
    } catch (error) {
      console.error('[PWA] Service Worker registration failed:', error);
    }
  });

  // Listen for messages from SW (e.g. background sync trigger)
  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data?.type === 'SYNC_OFFLINE_RUNS') {
      console.log('[PWA] Background sync message received from SW');
      if (typeof syncOfflineRuns === 'function') {
        syncOfflineRuns();
      }
    }
  });
}

// ─── Install Prompt ─────────────────────────────────────────
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (event) => {
  // Prevent the default mini-infobar
  event.preventDefault();
  deferredPrompt = event;

  // Show custom install banner
  showInstallBanner();
});

window.addEventListener('appinstalled', () => {
  console.log('[PWA] App installed successfully');
  deferredPrompt = null;
  hideInstallBanner();
});

// Expose manual install function
window.triggerInstallPrompt = async function() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log('[PWA] Manual install prompt outcome:', outcome);
    if (outcome === 'accepted') {
      deferredPrompt = null;
      hideInstallBanner();
    }
  } else {
    alert("App is already installed or install prompt is not available.");
  }
};

function showInstallBanner() {
  // Don't show if user previously dismissed
  if (localStorage.getItem('pwa-install-dismissed') === 'true') return;

  // Remove existing banner if any
  const existing = document.getElementById('pwaInstallBanner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'pwaInstallBanner';
  banner.innerHTML = `
    <div style="
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 10000;
      background: linear-gradient(135deg, #0a0c10 0%, #141820 100%);
      border: 1px solid rgba(0, 242, 255, 0.3);
      border-radius: 16px;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 242, 255, 0.1);
      max-width: 420px;
      width: calc(100% - 32px);
      font-family: 'Inter', sans-serif;
      animation: pwaSlideUp 0.4s ease-out;
    ">
      <div style="font-size: 2rem; line-height: 1;">&#9889;</div>
      <div style="flex: 1; min-width: 0;">
        <div style="color: #fff; font-weight: 700; font-size: 0.95rem;">Install RunRush</div>
        <div style="color: rgba(255,255,255,0.6); font-size: 0.8rem; margin-top: 2px;">Add to your home screen for the best experience</div>
      </div>
      <button id="pwaInstallBtn" style="
        background: linear-gradient(135deg, #00f2ff, #00c4cc);
        color: #0a0c10;
        border: none;
        border-radius: 10px;
        padding: 8px 16px;
        font-weight: 700;
        font-size: 0.85rem;
        cursor: pointer;
        white-space: nowrap;
        transition: transform 0.15s;
      ">Install</button>
      <button id="pwaInstallDismiss" style="
        background: none;
        border: none;
        color: rgba(255,255,255,0.4);
        font-size: 1.2rem;
        cursor: pointer;
        padding: 4px;
        line-height: 1;
      ">&times;</button>
    </div>
  `;

  // Add animation keyframes
  if (!document.getElementById('pwaAnimStyles')) {
    const style = document.createElement('style');
    style.id = 'pwaAnimStyles';
    style.textContent = `
      @keyframes pwaSlideUp {
        from { opacity: 0; transform: translateX(-50%) translateY(30px); }
        to   { opacity: 1; transform: translateX(-50%) translateY(0); }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(banner);

  // Install button handler
  document.getElementById('pwaInstallBtn').addEventListener('click', async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log('[PWA] Install prompt outcome:', outcome);
    deferredPrompt = null;
    hideInstallBanner();
  });

  // Dismiss button handler
  document.getElementById('pwaInstallDismiss').addEventListener('click', () => {
    hideInstallBanner();
    localStorage.setItem('pwa-install-dismissed', 'true');
  });
}

function hideInstallBanner() {
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.style.transition = 'opacity 0.3s';
    banner.style.opacity = '0';
    setTimeout(() => banner.remove(), 300);
  }
}

// ─── Update Banner ──────────────────────────────────────────
function showUpdateBanner() {
  const existing = document.getElementById('pwaUpdateBanner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'pwaUpdateBanner';
  banner.innerHTML = `
    <div style="
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 10000;
      background: linear-gradient(135deg, #0a0c10 0%, #141820 100%);
      border: 1px solid rgba(176, 255, 79, 0.3);
      border-radius: 12px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
      max-width: 380px;
      width: calc(100% - 32px);
      font-family: 'Inter', sans-serif;
    ">
      <div style="flex: 1; color: #fff; font-size: 0.85rem;">
        A new version of RunRush is available!
      </div>
      <button onclick="window.location.reload()" style="
        background: linear-gradient(135deg, #b0ff4f, #8cd43f);
        color: #0a0c10;
        border: none;
        border-radius: 8px;
        padding: 6px 14px;
        font-weight: 700;
        font-size: 0.8rem;
        cursor: pointer;
      ">Update</button>
    </div>
  `;

  document.body.appendChild(banner);
}
