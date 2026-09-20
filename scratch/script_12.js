
  (function () {
    // Server passes whether the user has run today
    const ranToday = 0;
    const REMINDER_KEY        = 'rr_reminder_enabled';
    const LAST_NOTIFIED_KEY   = 'rr_last_notified';
    const REMINDER_HOUR       = 20;  // 8 PM local time

    const toggle = document.getElementById('reminderToggle');
    if (!toggle) return;

    // ── Load saved preference ──
    const isEnabled = localStorage.getItem(REMINDER_KEY) === 'true';
    toggle.checked = isEnabled;

    // ── Toggle handler ──
    toggle.addEventListener('change', function () {
      const enable = this.checked;
      if (enable) {
        // Request permission first
        if (!('Notification' in window)) {
          alert('Your browser does not support notifications.');
          this.checked = false;
          return;
        }
        Notification.requestPermission().then(perm => {
          if (perm === 'granted') {
            localStorage.setItem(REMINDER_KEY, 'true');
            scheduleReminder();
          } else {
            this.checked = false;
            alert('Notification permission denied. Please allow notifications in your browser settings.');
          }
        });
      } else {
        localStorage.setItem(REMINDER_KEY, 'false');
      }
    });

    // ── Schedule the 8pm check ──
    function scheduleReminder() {
      if (localStorage.getItem(REMINDER_KEY) !== 'true') return;
      if (!('Notification' in window) || Notification.permission !== 'granted') return;

      const now      = new Date();
      const target   = new Date();
      target.setHours(REMINDER_HOUR, 0, 0, 0);

      // If 8pm already passed today, don't schedule (would be tomorrow)
      const msUntil8pm = target - now;
      if (msUntil8pm <= 0) return;

      setTimeout(() => {
        // Re-check at the moment the timer fires
        if (localStorage.getItem(REMINDER_KEY) !== 'true') return;

        // Avoid duplicate notifications on the same day
        const today       = new Date().toDateString();
        const lastNotified = localStorage.getItem(LAST_NOTIFIED_KEY);
        if (lastNotified === today) return;

        // Only notify if user hasn't run today
        // ranToday reflects state at page load; if they ran after load, no big deal
        if (ranToday) return;

        try {
          const n = new Notification('⚡ RunRush Reminder', {
            body: "Don't break your streak! Log today's run before midnight.",
            icon: '/static/favicon.png',
            tag:  'runrush-streak',     // prevents duplicate system notifications
            requireInteraction: false
          });
          n.onclick = () => { window.focus(); n.close(); };
          localStorage.setItem(LAST_NOTIFIED_KEY, today);
        } catch (e) {
          // Silently fail (e.g. notification blocked)
        }
      }, msUntil8pm);
    }

    // Auto-schedule on page load if reminders are enabled
    if (isEnabled && 'Notification' in window && Notification.permission === 'granted') {
      scheduleReminder();
    }
  })();
  