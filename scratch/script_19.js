
    // Pace Pet Logic
    function getPetIcon(type, level) {
      let icon = 'fa-egg';
      if (level > 1) {
        if (type === 'dog') icon = 'fa-dog';
        else if (type === 'bird') icon = 'fa-crow';
        else if (type === 'dragon') icon = 'fa-dragon';
      }
      return `<i class="fas ${icon}"></i>`;
    }

    function selectPetType(type, elem) {
      document.querySelectorAll('.pet-choice').forEach(el => {
        el.style.background = 'transparent';
        el.style.boxShadow = 'none';
        el.classList.remove('border-info');
        el.classList.add('border-secondary');
      });
      elem.style.background = 'rgba(0, 242, 255, 0.1)';
      elem.style.boxShadow = '0 0 10px rgba(0, 242, 255, 0.2)';
      elem.classList.remove('border-secondary');
      elem.classList.add('border-info');
      document.getElementById('adoptPetType').value = type;
    }

    async function submitAdoption() {
      const type = document.getElementById('adoptPetType').value;
      const name = document.getElementById('adoptPetName').value;
      if (!name) return alert('Please enter a name for your pet!');
      
      const res = await fetch('/api/adopt-pet', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ pet_name: name, pet_type: type })
      });
      
      if (res.ok) {
        const modal = bootstrap.Modal.getInstance(document.getElementById('adoptPetModal'));
        if (modal) modal.hide();
        // If collection modal is open, hide it too
        const colModal = bootstrap.Modal.getInstance(document.getElementById('petCollectionModal'));
        if (colModal) colModal.hide();
        
        loadPetStatus();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to adopt pet.');
      }
    }

    let currentPetLevel = null;

    async function loadPetStatus() {
      const res = await fetch('/api/pet-status?_t=' + Date.now());
      if (!res.ok) return;
      const data = await res.json();
      
      if (!data.has_pet) {
        document.getElementById('pacePetWidget').style.display = 'none';
        const modal = new bootstrap.Modal(document.getElementById('adoptPetModal'));
        modal.show();
        return;
      }
      
      // Evolution Check
      if (currentPetLevel !== null && data.level > currentPetLevel) {
        // Trigger evolution modal
        document.getElementById('evoPetName').innerText = data.pet_name;
        document.getElementById('evoPetStage').innerText = data.level_name;
        
        const evoVisual = document.getElementById('evoPetVisual');
        evoVisual.innerHTML = getPetIcon(data.pet_type, data.level);
        let evoClasses = `pet-icon pet-lvl-${data.level} pet-anim-bounce`;
        if (data.level > 1) evoClasses += ` pet-color-${data.pet_type}`;
        evoVisual.className = evoClasses;
        
        const evoModal = new bootstrap.Modal(document.getElementById('petEvolutionModal'));
        evoModal.show();
      }
      currentPetLevel = data.level;
      
      // Update widget
      document.getElementById('pacePetWidget').style.display = 'block';
      document.getElementById('petNameDisplay').innerText = data.pet_name;
      document.getElementById('petLevelDisplay').innerText = data.level;
      document.getElementById('petHealthDisplay').innerText = data.health_status;
      document.getElementById('petKmsDisplay').innerText = data.total_km_fed;
      document.getElementById('petNextKmsDisplay').innerText = data.km_until_next_evolution;
      
      const visual = document.getElementById('petVisual');
      visual.innerHTML = getPetIcon(data.pet_type, data.level);
      
      let baseClasses = `pet-icon pet-lvl-${data.level}`;
      if (data.level > 1) baseClasses += ` pet-color-${data.pet_type}`;
      
      if (data.health_status === 'waiting for you' || data.health_status === 'sleepy') {
        visual.className = `${baseClasses} pet-anim-sway`;
      } else {
        visual.className = `${baseClasses} pet-anim-bounce`;
      }
      
      if (data.next_threshold) {
        const currentLevelStart = data.current_threshold || 0;
        const progress = ((data.total_km_fed - currentLevelStart) / (data.next_threshold - currentLevelStart)) * 100;
        document.getElementById('petProgressBar').style.width = Math.min(100, Math.max(0, progress)) + '%';
      } else {
        document.getElementById('petProgressBar').style.width = '100%';
        document.getElementById('petNextKmsDisplay').innerText = '0';
      }
    }

    async function openPetCollection() {
      const res = await fetch('/api/pet-collection');
      if (!res.ok) return;
      const data = await res.json();
      
      const grid = document.getElementById('petCollectionGrid');
      grid.innerHTML = '';
      
      // Render unlocked/owned pets first
      data.collection.forEach(pet => {
        let baseClasses = `pet-icon pet-lvl-${pet.level}`;
        if (pet.level > 1) baseClasses += ` pet-color-${pet.pet_type}`;
        
        let actionBtn = pet.is_active 
          ? `<button class="btn btn-sm btn-success w-100 disabled"><i class="fas fa-check"></i> Active</button>`
          : `<button class="btn btn-sm btn-outline-info w-100" onclick="switchPet(${pet.id})"><i class="fas fa-exchange-alt"></i> Switch to ${pet.pet_name}</button>`;

        grid.innerHTML += `
          <div class="col-12 col-md-6">
            <div class="card bg-card border-subtle h-100 p-3 text-center ${pet.is_active ? 'border-info' : ''}">
              <div class="mb-3 ${baseClasses}" style="transform: scale(0.7);">${getPetIcon(pet.pet_type, pet.level)}</div>
              <h5>${pet.pet_name}</h5>
              <p class="text-muted small mb-2">${pet.level_name} (Lvl ${pet.level})</p>
              <div class="progress mb-3" style="height: 5px;">
                <div class="progress-bar bg-info" style="width: ${pet.next_threshold ? ((pet.total_km_fed - (pet.current_threshold||0)) / (pet.next_threshold - (pet.current_threshold||0))) * 100 : 100}%"></div>
              </div>
              ${actionBtn}
            </div>
          </div>
        `;
      });
      
      // Render locked / adoptable pet types
      const types = data.pet_types || {};
      for (const [t, info] of Object.entries(types)) {
        // If user already owns this type, skip it in the adoptable list
        if (data.collection.find(p => p.pet_type === t)) continue;
        
        if (info.unlocked) {
          // Adoptable
          grid.innerHTML += `
            <div class="col-12 col-md-6">
              <div class="card bg-card border-subtle h-100 p-3 text-center" style="border-style: dashed !important;">
                <div class="mb-3 text-muted" style="font-size: 2rem;"><i class="fas fa-egg"></i></div>
                <h5>Adopt ${info.definition.name}</h5>
                <p class="text-muted small mb-2">${info.definition.description}</p>
                <button class="btn btn-sm btn-outline-primary w-100" onclick="openAdoptModal('${t}')">Adopt</button>
              </div>
            </div>
          `;
        } else {
          // Locked
          grid.innerHTML += `
            <div class="col-12 col-md-6">
              <div class="card bg-card border-subtle h-100 p-3 text-center" style="opacity: 0.5;">
                <div class="mb-3 text-muted" style="font-size: 2rem;"><i class="fas fa-lock"></i></div>
                <h5>???</h5>
                <p class="text-muted small mb-2">Unlocks at ${info.unlock_distance || '?'} km lifetime</p>
                <button class="btn btn-sm btn-outline-secondary w-100 disabled">Locked</button>
              </div>
            </div>
          `;
        }
      }
      
      const modal = new bootstrap.Modal(document.getElementById('petCollectionModal'));
      modal.show();
    }
    
    function openAdoptModal(type) {
      document.getElementById('adoptPetName').value = '';
      selectPetType(type, document.querySelector(`.pet-choice[onclick*="${type}"]`));
      const modal = new bootstrap.Modal(document.getElementById('adoptPetModal'));
      modal.show();
    }
    
    async function switchPet(collectionId) {
      const res = await fetch('/api/pet/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ collection_id: collectionId })
      });
      
      if (res.ok) {
        const modal = bootstrap.Modal.getInstance(document.getElementById('petCollectionModal'));
        if (modal) modal.hide();
        loadPetStatus();
      } else {
        alert('Failed to switch pet.');
      }
    }
    
    window.addEventListener('DOMContentLoaded', () => {
      loadPetStatus();
      if(document.getElementById("monthly-progress-title")){
          fetchMonthlyProgress();
      }
    });

  