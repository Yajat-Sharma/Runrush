// Loads the real static/js/profile.js in a stubbed DOM and runs loadHeatmap().
// Simulates a scroll container narrower than its content (as on a phone) and
// prints the container's final scrollLeft/scrollWidth as JSON.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const days = Array.from({ length: 365 }, (_, i) => ({ date: '2026-01-01', km: i % 7 === 0 ? 4 : 0 }));
const container = { scrollWidth: 845, clientWidth: 317, scrollLeft: 0 };
const grid = { innerHTML: '', parentElement: container };

const sandbox = {
  document: { getElementById: (id) => (id === 'heatmap-grid' ? grid : { style: {} }) },
  console, setTimeout, clearTimeout, encodeURIComponent,
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ days }) }),
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'profile.js'), 'utf8'), sandbox);
vm.runInContext("loadHeatmap('someone')", sandbox);

setTimeout(() => {
  console.log(JSON.stringify({
    cells: (grid.innerHTML.match(/profile-hm-cell/g) || []).length,
    scrollLeft: container.scrollLeft,
    scrollWidth: container.scrollWidth,
  }));
}, 50);
