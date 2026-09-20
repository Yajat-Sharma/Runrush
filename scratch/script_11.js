
  (function () {
    const notesTextarea = document.querySelector('textarea[name="notes"]');
    if (!notesTextarea) return;

    let dropdown = null;
    let debounceTimer = null;
    let activeIndex = -1;
    let currentItems = [];
    let mentionStart = -1;  // caret position where '@' was typed

    // ── Create dropdown element ──
    function createDropdown() {
      if (dropdown) dropdown.remove();
      dropdown = document.createElement('div');
      dropdown.className = 'mention-dropdown';
      document.body.appendChild(dropdown);
    }

    // ── Position dropdown near caret ──
    function positionDropdown() {
      if (!dropdown) return;
      const rect = notesTextarea.getBoundingClientRect();
      dropdown.style.top  = (rect.bottom + window.scrollY + 4) + 'px';
      dropdown.style.left = (rect.left  + window.scrollX)      + 'px';
    }

    // ── Render suggestions ──
    function renderDropdown(users) {
      if (!dropdown) return;
      dropdown.innerHTML = '';
      activeIndex = -1;
      currentItems = users;

      if (!users.length) {
        closeDropdown();
        return;
      }

      users.forEach((u, i) => {
        const item = document.createElement('div');
        item.className = 'mention-dropdown-item';
        item.innerHTML =
          `<span>👤 <strong>${escHtml(u.display_name)}</strong></span>` +
          `<span class="mdi-username">@${escHtml(u.username)}</span>`;
        item.addEventListener('mousedown', (e) => {
          e.preventDefault();  // prevent textarea blur
          insertMention(u.username);
        });
        dropdown.appendChild(item);
      });

      positionDropdown();
    }

    // ── Insert @username into textarea ──
    function insertMention(username) {
      const val   = notesTextarea.value;
      const caret = notesTextarea.selectionStart;
      // Replace from '@' position to caret with '@username '
      const before = val.slice(0, mentionStart);
      const after  = val.slice(caret);
      const insert = '@' + username + ' ';
      notesTextarea.value = before + insert + after;
      // Move caret after the inserted mention
      const newPos = mentionStart + insert.length;
      notesTextarea.setSelectionRange(newPos, newPos);
      notesTextarea.focus();
      closeDropdown();
    }

    // ── Close dropdown ──
    function closeDropdown() {
      if (dropdown) { dropdown.remove(); dropdown = null; }
      currentItems = [];
      activeIndex = -1;
      mentionStart = -1;
    }

    // ── HTML-escape helper (prevents XSS in dropdown) ──
    function escHtml(str) {
      return (str || '').replace(/[&<>"']/g, c =>
        ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
    }

    // ── Fetch matching users from API (debounced, 300ms) ──
    function searchUsers(query) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetch(`/api/users/search?q=${encodeURIComponent(query)}`)
          .then(r => r.ok ? r.json() : { users: [] })
          .then(data => renderDropdown(data.users || []))
          .catch(() => closeDropdown());
      }, 300);
    }

    // ── Main input handler ──
    notesTextarea.addEventListener('input', function () {
      const val   = this.value;
      const caret = this.selectionStart;

      // Find the last '@' before the caret that starts a word
      let atPos = -1;
      for (let i = caret - 1; i >= 0; i--) {
        const ch = val[i];
        if (ch === '@') { atPos = i; break; }
        // Stop if we hit whitespace without finding '@'
        if (/\s/.test(ch)) break;
      }

      if (atPos === -1) { closeDropdown(); return; }

      const fragment = val.slice(atPos + 1, caret);  // text between '@' and caret
      if (/\s/.test(fragment) || fragment.length === 0) { closeDropdown(); return; }

      mentionStart = atPos;

      // Only create dropdown on first need
      if (!dropdown) createDropdown();
      searchUsers(fragment);
    });

    // ── Keyboard navigation within dropdown ──
    notesTextarea.addEventListener('keydown', function (e) {
      if (!dropdown || !currentItems.length) return;
      const items = dropdown.querySelectorAll('.mention-dropdown-item');

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % items.length;
        items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + items.length) % items.length;
        items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (activeIndex >= 0 && currentItems[activeIndex]) {
          e.preventDefault();
          insertMention(currentItems[activeIndex].username);
        }
      } else if (e.key === 'Escape') {
        closeDropdown();
      }
    });

    // Close on outside click
    document.addEventListener('mousedown', function (e) {
      if (dropdown && !dropdown.contains(e.target) && e.target !== notesTextarea) {
        closeDropdown();
      }
    });

    // Reposition on scroll/resize
    window.addEventListener('scroll', positionDropdown, { passive: true });
    window.addEventListener('resize', positionDropdown, { passive: true });
  })();
  