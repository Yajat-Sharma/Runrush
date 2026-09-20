
    function loadInsights() {
      const container = document.getElementById('insightsContainer');
      const loading = document.getElementById('insightsLoading');
      const empty = document.getElementById('insightsEmpty');
      if (!container) return;

      // Show loading state
      if (loading) loading.style.display = '';
      if (empty) empty.style.display = 'none';

      fetch('/api/analytics/insights', { cache: 'no-cache' })
        .then(r => r.json())
        .then(data => {
          if (loading) loading.style.display = 'none';
          const insights = data.insights || [];
          if (insights.length === 0) {
            container.innerHTML = '';
            if (empty) empty.style.display = '';
            return;
          }
          if (empty) empty.style.display = 'none';
          container.innerHTML = insights.map(i => `
            <div class="col-12 col-md-6">
              <div class="insight-item d-flex align-items-start gap-2">
                <span class="insight-icon">${i.icon}</span>
                <div>
                  <div class="insight-title">${i.title}</div>
                  <div class="insight-desc">${i.description}</div>
                </div>
              </div>
            </div>
          `).join('');
        })
        .catch(() => {
          if (loading) loading.style.display = 'none';
          container.innerHTML = '<div class="col-12 text-center text-muted py-2">Could not load insights.</div>';
        });
    }
  