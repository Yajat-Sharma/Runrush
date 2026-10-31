(() => {
  const status = document.getElementById('pushStatus');
  const enableButton = document.getElementById('enablePushButton');
  const disableButton = document.getElementById('disablePushButton');
  const testButton = document.getElementById('testPushButton');
  if (!status || !enableButton || !disableButton || !testButton) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ||
    document.querySelector('input[name="csrf_token"]')?.value;
  let registration;

  function setState(message, state) {
    status.textContent = message;
    status.dataset.state = state || '';
  }

  function urlBase64ToUint8Array(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const raw = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, (character) => character.charCodeAt(0));
  }

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, ...(options.headers || {}) }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Push notification request failed (HTTP ${response.status}).`);
    }
    return data;
  }

  async function refresh() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      setState('Push notifications are not supported in this browser.', 'unsupported');
      enableButton.hidden = true;
      disableButton.hidden = true;
      testButton.hidden = true;
      return;
    }
    const config = await request('/api/push/config', { headers: {} });
    if (!config.publicKey) {
      setState('Push notifications are not configured on this server.', 'disabled');
      enableButton.hidden = true;
      disableButton.hidden = true;
      testButton.hidden = true;
      return;
    }
    registration = await window.RunRushPWA.registrationPromise;
    const subscription = await registration.pushManager.getSubscription();
    const serverStatus = await request('/api/push/status', { headers: {} });
    const enabled = Boolean(subscription && serverStatus.subscribed);
    if (subscription && !serverStatus.subscribed) {
      setState('Browser permission is enabled, but this browser is not registered with RunRush. Click Enable to repair it.', 'error');
    } else {
      setState(enabled ? 'Push notifications are enabled.' : 'Push notifications are disabled.', enabled ? 'enabled' : 'disabled');
    }
    enableButton.hidden = enabled;
    disableButton.hidden = !enabled;
    testButton.hidden = !enabled;
  }

  enableButton.addEventListener('click', async () => {
    enableButton.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'Notifications are blocked in browser settings.' : 'Notification permission was dismissed.', 'error');
        return;
      }
      const config = await request('/api/push/config', { headers: {} });
      if (!registration) {
        registration = await window.RunRushPWA.registrationPromise;
      }
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(config.publicKey)
        });
      }
      await request('/api/push/subscribe', {
        method: 'POST',
        body: JSON.stringify(subscription.toJSON())
      });
      await refresh();
    } catch (error) {
      setState(error.message, 'error');
    } finally {
      enableButton.disabled = false;
    }
  });

  disableButton.addEventListener('click', async () => {
    disableButton.disabled = true;
    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await request('/api/push/unsubscribe', {
          method: 'POST',
          body: JSON.stringify({ endpoint: subscription.endpoint })
        });
        await subscription.unsubscribe();
      }
      await refresh();
    } catch (error) {
      setState(error.message, 'error');
    } finally {
      disableButton.disabled = false;
    }
  });

  testButton.addEventListener('click', async () => {
    testButton.disabled = true;
    try {
      const result = await request('/api/push/test', { method: 'POST', body: '{}' });
      setState(`Test notification sent (${result.sent}).`, 'enabled');
    } catch (error) {
      setState(error.message, 'error');
    } finally {
      testButton.disabled = false;
    }
  });

  refresh().catch((error) => setState(error.message, 'error'));
})();
