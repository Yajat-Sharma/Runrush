
  document.querySelectorAll('.run-notes-preview').forEach(el => {
    el.addEventListener('click', function () {
      const full = this.dataset.full || '';
      if (this.dataset.expanded === 'true') {
        const short = full.slice(0, 60) + (full.length > 60 ? '\u2026' : '');
        this.textContent = short;
        this.dataset.expanded = 'false';
      } else {
        this.textContent = full;
        this.dataset.expanded = 'true';
      }
    });
  });
  