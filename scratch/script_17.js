
    // Dynamic Filter/Sort
    function resetFilters() {
      document.getElementById('filterAll').checked = true;
      document.getElementById('sortDate').checked = true;
    }

    async function applyFiltersDynamic() {
      const filterOpt = document.querySelector('input[name="filterOpt"]:checked').value;
      const sortOpt = document.querySelector('input[name="sortOpt"]:checked').value;
      const spinner = document.getElementById('filterSpinner');
      
      // Close modal
      const filterModalEl = document.getElementById('filterModal');
      const filterModal = bootstrap.Modal.getInstance(filterModalEl) || new bootstrap.Modal(filterModalEl);
      filterModal.hide();
      
      spinner.style.display = 'inline-block';
      try {
        const response = await fetch(`/dashboard?filter=${filterOpt}&sort=${sortOpt}`);
        const html = await response.text();
        
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        
        // Update table body
        const newTbody = doc.querySelector('#runsTable tbody');
        const currentTbody = document.querySelector('#runsTable tbody');
        
        if (newTbody && currentTbody) {
          const runRows = newTbody.querySelectorAll('tr.runs-table-row');
          if (runRows.length === 0) {
            currentTbody.innerHTML = `<tr><td colspan="9" class="text-center py-5 text-muted empty-state-container">
              <div class="fs-1 mb-2">🏃</div>
              No runs match your selected filters.<br>Try changing your filter or resetting it.
            </td></tr>`;
          } else {
            currentTbody.innerHTML = newTbody.innerHTML;
          }
        }
        
        // Update cards view
        const newCardView = doc.querySelector('#runsCardView');
        const currentCardView = document.querySelector('#runsCardView');
        if (newCardView && currentCardView) {
            currentCardView.innerHTML = newCardView.innerHTML;
            formatMonthHeaders();
        }
        
        // Update run count
        const newCount = doc.querySelector('#runCount');
        const currentCount = document.querySelector('#runCount');
        if (newCount && currentCount) {
          currentCount.textContent = newCount.textContent;
        }
      } catch (err) {
        console.error("Failed to fetch filtered runs", err);
      } finally {
        spinner.style.display = 'none';
      }
    }

    // Runs View Switcher
    function setRunsView(view) {
      const cardView = document.getElementById('runsCardView');
      const listView = document.getElementById('runsListView');
      const btnCards = document.getElementById('btnCardsView');
      const btnList = document.getElementById('btnListView');
      
      if (!cardView || !listView) return;

      if (view === 'list') {
        cardView.style.display = 'none';
        listView.style.display = 'block';
        if (btnList) btnList.classList.add('active');
        if (btnCards) btnCards.classList.remove('active');
      } else {
        cardView.style.display = 'block';
        listView.style.display = 'none';
        if (btnCards) btnCards.classList.add('active');
        if (btnList) btnList.classList.remove('active');
      }
      localStorage.setItem('runrush_runs_view', view);
    }

    function initRunsView() {
      const savedView = localStorage.getItem('runrush_runs_view') || 'cards';
      setRunsView(savedView);
      formatMonthHeaders();
    }

    function toggleRunCard(runId) {
      const details = document.getElementById(`runCardDetails-${runId}`);
      const chevron = document.getElementById(`chevron-${runId}`);
      if (!details) return;

      if (details.classList.contains('show')) {
        const bsCollapse = bootstrap.Collapse.getInstance(details);
        if (bsCollapse) bsCollapse.hide();
        if (chevron) chevron.style.transform = 'rotate(0deg)';
      } else {
        const bsCollapse = new bootstrap.Collapse(details) || bootstrap.Collapse.getInstance(details);
        bsCollapse.show();
        if (chevron) chevron.style.transform = 'rotate(180deg)';
      }
    }

    function formatMonthHeaders() {
      const months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
      document.querySelectorAll('.month-header-raw').forEach(el => {
        const raw = el.getAttribute('data-month'); // e.g. "2026-09"
        if (raw && raw.length >= 7) {
          const parts = raw.split('-');
          if (parts.length >= 2) {
            const year = parts[0];
            const monthIdx = parseInt(parts[1], 10) - 1;
            if (monthIdx >= 0 && monthIdx < 12) {
              el.textContent = `${months[monthIdx]} ${year}`;
              el.classList.remove('month-header-raw');
            }
          }
        }
      });
    }

    document.addEventListener('DOMContentLoaded', initRunsView);
  