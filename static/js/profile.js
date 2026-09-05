var _toastTimer;
function profileShowToast(msg, type) {
  type = type || 'success';
  var t = document.getElementById('profile-toast') || document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'rr-toast ' + type + ' show';
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function() { t.classList.remove('show'); }, 3000);
}

function fmtPace(pace) {
  if (!pace || pace <= 0) return '-';
  var m = Math.floor(pace);
  var s = Math.round((pace - m) * 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtTime(min) {
  if (!min || min <= 0) return '-';
  var h = Math.floor(min / 60);
  var m = Math.round(min % 60);
  return h > 0 ? h + 'h ' + m + 'm' : m + 'm';
}

function fmtDate(str) {
  if (!str) return '';
  try { return new Date(str).toLocaleDateString('en-GB', {month:'short', year:'numeric'}); }
  catch(e) { return str; }
}

function initials(name) {
  if (!name) return '?';
  return name.split(' ').map(function(w) { return w[0]; }).join('').slice(0,2).toUpperCase();
}

function loadProfile(username, isOwnProfile) {
  fetch('/api/user/' + encodeURIComponent(username) + '/public-profile')
    .then(function(res) {
      if (!res.ok) { document.getElementById('profile-display-name').textContent = 'Profile not found'; return null; }
      return res.json();
    })
    .then(function(d) {
      if (!d) return;
      var pageTitle = document.getElementById('page-title');
      if (pageTitle) {
        document.title = d.display_name + ' (@' + d.username + ') - RunRush';
      }
      
      document.getElementById('profile-display-name').textContent = d.display_name;
      document.getElementById('profile-handle').textContent = '@' + d.username;
      
      var bioEl = document.getElementById('profile-bio');
      if (d.bio) {
        bioEl.textContent = d.bio;
        bioEl.style.display = '';
      } else {
        bioEl.style.display = 'none';
      }
      
      var nextRaceContainer = document.getElementById('next-race-container');
      if (d.next_race) {
        document.getElementById('next-race-text').textContent = d.next_race;
        nextRaceContainer.style.display = '';
      } else {
        nextRaceContainer.style.display = 'none';
      }
      
      var initEl = document.getElementById('avatar-initials');
      initEl.textContent = initials(d.display_name);
      initEl.style.display = ''; // Reset display in case of modal reopen with different user
      
      var img = document.getElementById('avatar-img');
      img.classList.remove('loaded');
      if (d.has_avatar) {
        img.src = '/avatar/' + encodeURIComponent(username) + '?t=' + Date.now();
        img.onload = function() { img.classList.add('loaded'); initEl.style.display = 'none'; };
      }
      
      document.getElementById('run-count').textContent = d.run_count;
      document.getElementById('follower-count').textContent = d.follower_count;
      document.getElementById('following-count').textContent = d.following_count;
      document.getElementById('stat-distance').textContent = d.total_distance_km;
      document.getElementById('stat-time').textContent = fmtTime(d.total_time_min);
      document.getElementById('stat-pace').textContent = fmtPace(d.avg_pace_min_per_km);
      document.getElementById('stat-longest').textContent = d.longest_run_km;
      
      renderPB(d.personal_bests);
      renderBadges(d.badges, d.total_distance_km);
      
      if (isOwnProfile) {
        var bi = document.getElementById('edit-bio');
        var ri = document.getElementById('edit-next-race');
        if (bi) { bi.value = d.bio || ''; document.getElementById('bio-count').textContent = bi.value.length; }
        if (ri) { ri.value = d.next_race || ''; document.getElementById('race-count').textContent = ri.value.length; }
      }
    })
    .catch(function(e) { console.error(e); });
}

function renderPB(pb) {
  var items = [
    { icon: '&#127885;', label: 'Fastest 5K',
      val: pb.fastest_5k ? fmtTime(pb.fastest_5k.time_min) : '-',
      sub: pb.fastest_5k ? fmtPace(pb.fastest_5k.pace) + '/km' : 'No 5K run yet' },
    { icon: '&#127919;', label: 'Fastest 10K',
      val: pb.fastest_10k ? fmtTime(pb.fastest_10k.time_min) : '-',
      sub: pb.fastest_10k ? fmtPace(pb.fastest_10k.pace) + '/km' : 'No 10K run yet' },
    { icon: '&#128207;', label: 'Longest Run',
      val: pb.longest_distance ? pb.longest_distance.distance_km + ' km' : '-',
      sub: pb.longest_distance ? fmtDate(pb.longest_distance.date) : 'No runs yet' },
    { icon: '&#9889;', label: 'Best Pace',
      val: pb.best_pace ? fmtPace(pb.best_pace.pace) + '/km' : '-',
      sub: pb.best_pace ? pb.best_pace.distance_km + ' km' : 'No qualifying run' },
  ];
  document.getElementById('pb-grid').innerHTML = items.map(function(item) {
    return '<div class="pb-card"><div class="pb-icon">' + item.icon + '</div><div>' +
      '<div class="pb-val">' + item.val + '</div>' +
      '<div class="pb-label">' + item.label + '</div>' +
      '<div class="pb-date">' + item.sub + '</div></div></div>';
  }).join('');
}

function renderBadges(badges, totalKm) {
  document.getElementById('badge-grid').innerHTML = badges.map(function(b) {
    var earned = b.earned;
    var progressHtml = '';
    if (!earned && b.progress !== undefined) {
      var pct = Math.round((b.progress / b.progress_target) * 100);
      progressHtml = '<div class="badge-progress-bar"><div class="badge-progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="badge-progress-text">' + b.progress.toFixed(1) + '/' + b.progress_target + ' km</div>';
    }
    var dateStr = earned && b.unlocked_at ? '<div class="badge-date">Earned ' + fmtDate(b.unlocked_at) + '</div>' : '';
    return '<div class="badge-card ' + (earned ? 'earned' : 'locked') + '" title="' + b.description + '">' +
      '<span class="badge-icon">' + b.icon + '</span>' +
      '<div class="badge-name">' + b.name + '</div>' +
      '<div class="badge-desc">' + b.description + '</div>' +
      progressHtml + dateStr + '</div>';
  }).join('');
}

function loadHeatmap(username) {
  fetch('/api/user/' + encodeURIComponent(username) + '/heatmap')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (!data) return;
      var grid = document.getElementById('heatmap-grid');
      grid.innerHTML = data.days.map(function(d) {
        var km = d.km;
        var level = km === 0 ? 0 : km < 3 ? 1 : km < 6 ? 2 : km < 10 ? 3 : 4;
        return '<div class="heatmap-cell" data-level="' + level + '" title="' + d.date + ': ' + km + ' km"></div>';
      }).join('');
    })
    .catch(function() {});
}

function initProfileEvents(username) {
  var followBtn = document.getElementById('follow-btn');
  if (followBtn) {
    followBtn.addEventListener('click', function() {
      var following = followBtn.dataset.following === 'true';
      var action = following ? 'unfollow' : 'follow';
      var followUser = followBtn.dataset.username;
      fetch('/' + action + '/' + encodeURIComponent(followUser), { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success !== undefined || data.following !== undefined) {
            var nowFollowing = action === 'follow';
            followBtn.dataset.following = String(nowFollowing);
            followBtn.textContent = nowFollowing ? 'Unfollow' : 'Follow';
            followBtn.classList.toggle('following', nowFollowing);
            var fc = document.getElementById('follower-count');
            var n = parseInt(fc.textContent) || 0;
            fc.textContent = nowFollowing ? n + 1 : Math.max(0, n - 1);
            profileShowToast(nowFollowing ? 'Following ' + followUser : 'Unfollowed ' + followUser);
          }
        })
        .catch(function() { profileShowToast('Something went wrong', 'error'); });
    });
  }

  var saveBtn = document.getElementById('save-profile-btn');
  if (saveBtn) {
    var bioInput = document.getElementById('edit-bio');
    var raceInput = document.getElementById('edit-next-race');
    bioInput.addEventListener('input', function() {
      document.getElementById('bio-count').textContent = bioInput.value.length;
    });
    raceInput.addEventListener('input', function() {
      document.getElementById('race-count').textContent = raceInput.value.length;
    });
    saveBtn.addEventListener('click', function() {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';
      var csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
      fetch('/api/profile/details', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ bio: bioInput.value, next_race: raceInput.value })
      })
        .then(async function(r) { 
          if (!r.ok) {
            var isJson = r.headers.get('content-type')?.includes('application/json');
            if (isJson) {
              var errData = await r.json();
              throw new Error(errData.error || 'Server returned ' + r.status);
            } else {
              throw new Error('Server error ' + r.status + ' (Non-JSON response)');
            }
          }
          return r.json(); 
        })
        .then(function(d) {
          if (d.success) {
            profileShowToast('Profile updated!');
            var bioEl = document.getElementById('profile-bio');
            bioEl.textContent = bioInput.value;
            bioEl.style.display = bioInput.value ? '' : 'none';
            if (raceInput.value) {
              document.getElementById('next-race-text').textContent = raceInput.value;
              document.getElementById('next-race-container').style.display = '';
            } else {
              document.getElementById('next-race-container').style.display = 'none';
            }
          } else {
            profileShowToast(d.error || 'Failed to save', 'error');
          }
        })
        .catch(function(err) { 
          console.error('Error saving details:', err);
          profileShowToast('Failed to save: ' + err.message, 'error'); 
        })
        .finally(function() { saveBtn.disabled = false; saveBtn.textContent = 'Save Changes'; });
    });
  }

  var avatarInput = document.getElementById('avatar-file-input');
  if (avatarInput) {
    avatarInput.addEventListener('change', function() {
      var file = avatarInput.files[0];
      if (!file) return;
      var fd = new FormData();
      fd.append('avatar', file);
      fetch('/api/profile/avatar', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (d.success) {
            profileShowToast('Avatar updated!');
            var img = document.getElementById('avatar-img');
            img.src = '/avatar/' + encodeURIComponent(username) + '?t=' + Date.now();
            img.onload = function() {
              img.classList.add('loaded');
              document.getElementById('avatar-initials').style.display = 'none';
            };
          } else {
            profileShowToast(d.error || 'Upload failed', 'error');
          }
        })
        .catch(function() { profileShowToast('Upload failed', 'error'); })
        .finally(function() { avatarInput.value = ''; });
    });
  }
}
