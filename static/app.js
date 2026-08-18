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

// Queue a flag payload (same shape as the POST /flag body) to localStorage
// so it can be retried by syncPendingFlags() once back online.
function queuePendingFlag(flag) {
  var stored;
  try { stored = JSON.parse(localStorage.getItem('pending_flags') || '[]'); } catch(e) { stored = []; }
  stored.push(flag);
  localStorage.setItem('pending_flags', JSON.stringify(stored));
}

// Brief non-blocking confirmation that a flag was queued for later sync.
// If a generic offline toast is already showing (e.g. from _goOffline()),
// its text is overwritten so the flag-specific confirmation is still seen
// rather than being silently swallowed by the earlier toast's guard.
function showFlagQueuedToast() {
  var existing = document.getElementById('offline-toast');
  if (existing) { existing.textContent = '🚩 Flag saved — will sync when back online'; return; }
  var t = document.createElement('div');
  t.id = 'offline-toast';
  t.className = 'offline-toast';
  t.textContent = '🚩 Flag saved — will sync when back online';
  document.body.appendChild(t);
  setTimeout(function() { t.classList.add('offline-toast--visible'); }, 50);
  setTimeout(function() {
    t.classList.remove('offline-toast--visible');
    setTimeout(function() { t.remove(); }, 400);
  }, 3000);
}

// Show a brief "⚡ Playing offline" toast (once per page load)
function showOfflineToast() {
  if (document.getElementById('offline-toast')) return;
  var t = document.createElement('div');
  t.id = 'offline-toast';
  t.className = 'offline-toast';
  t.textContent = '⚡ Playing offline';
  document.body.appendChild(t);
  setTimeout(function() { t.classList.add('offline-toast--visible'); }, 50);
  setTimeout(function() {
    t.classList.remove('offline-toast--visible');
    setTimeout(function() { t.remove(); }, 400);
  }, 3000);
}

// Show a full-screen offline results overlay
function showOfflineResults(stats, onPlayAgain) {
  var ov = document.createElement('div');
  ov.className = 'offline-results-overlay';
  ov.innerHTML =
    '<p class="stat-mini" style="color:var(--text-dim)">⚡ Offline session</p>' +
    '<div class="offline-results-stats">' +
      '<span>✓ ' + stats.correct + '</span>' +
      '<span>✗ ' + stats.wrong + '</span>' +
      '<span>— ' + stats.skipped + '</span>' +
    '</div>' +
    (stats.score !== undefined
      ? '<p style="font-size:1.4rem;font-weight:700">Score: ' + stats.score + '</p>'
      : '') +
    '<p style="color:var(--text-dim);font-size:0.85rem">' +
      (stats.pendingFlags ? 'Flags will sync when back online.' : '') +
    '</p>' +
    '<div class="result-btn-row">' +
      '<button class="btn-secondary home-btn">🏠 Home</button>' +
      '<button class="btn-primary again-btn">🔄 Play Again</button>' +
    '</div>';
  ov.querySelector('.home-btn').addEventListener('touchend', function(e) {
    e.preventDefault(); window.location.href = '/';
  }, { passive: false });
  ov.querySelector('.home-btn').addEventListener('click', function() {
    window.location.href = '/';
  });
  ov.querySelector('.again-btn').addEventListener('touchend', function(e) {
    e.preventDefault(); ov.remove(); onPlayAgain();
  }, { passive: false });
  ov.querySelector('.again-btn').addEventListener('click', function() {
    ov.remove(); onPlayAgain();
  });
  document.body.appendChild(ov);
}
