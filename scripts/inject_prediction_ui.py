import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Insert HTML
new_html_block = '''    <!-- PREDICTED NEXT RUN -->
    <div class="glass p-3 p-md-4 mb-4" id="predictionSection">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h4 class="mb-0">🔮 Predicted Next Run</h4>
      </div>
      <div class="text-center py-2">
        <div id="predictionValue" class="display-5 fw-bold text-info mb-2">-- km</div>
        <div id="predictionMessage" class="text-muted small">Loading prediction...</div>
      </div>
    </div>
'''

html = html.replace('    <!-- MILESTONE RINGS -->', new_html_block + '\n    <!-- MILESTONE RINGS -->')

# Insert JS
new_js_block = '''  async function fetchPrediction() {
    try {
      const res = await fetch('/api/predict-next-run');
      const data = await res.json();
      
      const valEl = document.getElementById('predictionValue');
      const msgEl = document.getElementById('predictionMessage');
      
      if (!valEl || !msgEl) return;
      
      if (data.error || data.prediction_km === null) {
        valEl.textContent = '-- km';
        msgEl.textContent = 'Log more runs to unlock predictions';
        return;
      }
      
      valEl.textContent = data.prediction_km + ' km';
      if (data.method === 'ml') {
        const mae = data.confidence_mae !== null ? data.confidence_mae : 0;
        msgEl.textContent = 'Based on your training pattern (±' + mae + ' km)';
      } else {
        msgEl.textContent = 'Estimate based on recent runs — log a few more for AI predictions';
      }
    } catch (e) {
      console.error('Error fetching prediction:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', fetchPrediction);
'''

html = html.replace('  function buildMilestoneRings(allTimeDist) {', new_js_block + '\n  function buildMilestoneRings(allTimeDist) {')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
