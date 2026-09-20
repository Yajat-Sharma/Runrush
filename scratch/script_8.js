
    // ==========================================
    // DASHBOARD WIDGET SYSTEM
    // ==========================================
    let dashboardSortable = null;
    let dashboardLayout = [];
    
    async function loadDashboardLayout() {
      try {
        const res = await fetch('/api/dashboard-layout');
        if (!res.ok) return;
        dashboardLayout = await res.json();
        renderDashboardLayout();
      } catch (e) {
        console.error("Failed to load dashboard layout", e);
      }
    }
    
    function renderDashboardLayout(editMode = false) {
      const container = document.getElementById('dashboardWidgetContainer');
      const widgets = Array.from(container.children);
      
      // Detach all widgets temporarily
      widgets.forEach(w => w.remove());
      
      // Reattach based on layout order
      dashboardLayout.forEach(item => {
        const widgetEl = widgets.find(w => w.dataset.widget === item.widget_type);
        if (widgetEl) {
          container.appendChild(widgetEl);
          const toggle = widgetEl.querySelector('.widget-toggle');
          if (toggle) toggle.checked = item.visible;
          
          if (editMode) {
            widgetEl.style.display = 'block';
            widgetEl.querySelector('.widget-edit-controls').style.display = 'flex';
            // Optionally hide content for compact sorting
            // widgetEl.querySelector('.widget-content').style.display = 'none';
          } else {
            widgetEl.style.display = (item.visible || item.widget_type === 'quick_start') ? 'block' : 'none';
            widgetEl.querySelector('.widget-edit-controls').style.display = 'none';
            widgetEl.querySelector('.widget-content').style.display = 'block';
          }
        }
      });
      
      // Reattach any widgets not in layout at the bottom (fallback)
      widgets.forEach(w => {
        if (!dashboardLayout.find(item => item.widget_type === w.dataset.widget)) {
          container.appendChild(w);
          if (!editMode) w.style.display = (w.dataset.widget === 'quick_start') ? 'block' : 'none';
        }
      });
    }
    
    function toggleDashboardEditMode() {
      document.querySelector('.edit-dashboard-btn-container').style.display = 'none';
      document.querySelector('.edit-dashboard-actions').style.display = 'block';
      
      renderDashboardLayout(true);
      
      const container = document.getElementById('dashboardWidgetContainer');
      if (!dashboardSortable) {
        dashboardSortable = new Sortable(container, {
          handle: '.drag-handle',
          animation: 150,
          ghostClass: 'sortable-ghost'
        });
      }
    }
    
    function cancelDashboardEditMode() {
      document.querySelector('.edit-dashboard-btn-container').style.display = 'block';
      document.querySelector('.edit-dashboard-actions').style.display = 'none';
      
      if (dashboardSortable) {
        dashboardSortable.destroy();
        dashboardSortable = null;
      }
      
      // Revert to saved layout without saving
      renderDashboardLayout(false);
    }
    
    async function saveDashboardLayout() {
      const container = document.getElementById('dashboardWidgetContainer');
      const widgets = Array.from(container.children);
      
      const newLayout = widgets.map((w, index) => {
        const toggle = w.querySelector('.widget-toggle');
        return {
          widget_type: w.dataset.widget,
          visible: toggle ? toggle.checked : true,
          order: index
        };
      });
      
      try {
        const res = await fetch('/api/dashboard-layout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value
          },
          body: JSON.stringify(newLayout)
        });
        
        if (res.ok) {
          dashboardLayout = newLayout;
          cancelDashboardEditMode(); // exits mode & re-renders
        } else {
          alert('Failed to save layout.');
        }
      } catch (e) {
        console.error(e);
        alert('Error saving layout.');
      }
    }
    
    // Call load on startup
    document.addEventListener('DOMContentLoaded', () => {
      loadDashboardLayout();
    });

  