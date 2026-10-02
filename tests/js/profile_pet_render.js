// Loads the real static/js/profile.js in a stubbed DOM and runs loadProfilePet()
// against a payload given on argv[2]. Prints {sectionDisplay, html} as JSON.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const payload = JSON.parse(process.argv[2]);
const els = {};
function el(id) {
  if (!els[id]) els[id] = { style: {}, innerHTML: '', textContent: '', classList: { add() {}, remove() {} } };
  return els[id];
}

const sandbox = {
  document: { getElementById: el, title: '' },
  console,
  setTimeout, clearTimeout,
  encodeURIComponent,
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(payload) }),
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'profile.js'), 'utf8'), sandbox);
vm.runInContext("loadProfilePet('someone')", sandbox);

setTimeout(() => {
  console.log(JSON.stringify({
    sectionDisplay: el('profile-pet-section').style.display || null,
    html: el('profile-pet-grid').innerHTML,
  }));
}, 50);
