
    var profileModalEl = document.getElementById('profileModal');
    if (profileModalEl) {
      profileModalEl.addEventListener('show.bs.modal', function () {
        loadProfile('0', false);
        loadHeatmap('0');
      });
    }
  