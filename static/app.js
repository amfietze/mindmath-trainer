// app.js – shared utilities (most game logic is inline in each template)
// This file is loaded by base.html for any global convenience helpers.

// Prevent double-tap zoom on iOS for game buttons
document.addEventListener('touchend', function(e) {
  const tag = e.target.tagName;
  if (tag === 'BUTTON' || e.target.classList.contains('option-btn')) {
    e.preventDefault();
  }
}, { passive: false });

// Sync any flags queued while offline back to the server once online
function syncPendingFlags() {
  if (!navigator.onLine) return;
  var stored;
  try { stored = JSON.parse(localStorage.getItem('pending_flags') || '[]'); } catch(e) { return; }
  if (!stored.length) return;
  var remaining = [];
  var done = 0;
  stored.forEach(function(flag) {
    fetch('/flag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(flag),
    }).then(function(r) {
      if (!r.ok) remaining.push(flag);
    }).catch(function() {
      remaining.push(flag);
    }).finally(function() {
      done++;
      if (done === stored.length) {
        localStorage.setItem('pending_flags', JSON.stringify(remaining));
      }
    });
  });
}

// Attempt sync on every page load when online
window.addEventListener('load', syncPendingFlags);
window.addEventListener('online', syncPendingFlags);
