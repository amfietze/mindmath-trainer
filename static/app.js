// app.js – shared utilities (most game logic is inline in each template)
// This file is loaded by base.html for any global convenience helpers.

// Prevent double-tap zoom on iOS for game buttons
document.addEventListener('touchend', function(e) {
  const tag = e.target.tagName;
  if (tag === 'BUTTON' || e.target.classList.contains('option-btn')) {
    e.preventDefault();
  }
}, { passive: false });
