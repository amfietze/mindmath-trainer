// rng.js — seeded PRNG + shared math helpers (offline mode)
// Mulberry32 PRNG; all helpers port the exact Python equivalents used by the engine files.

class RNG {
  constructor(seed) {
    this._s = (seed >>> 0) || 1;
  }

  _next() {
    this._s = (this._s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(this._s ^ (this._s >>> 15), 1 | this._s);
    t = Math.imul(t ^ (t >>> 7), 61 | t) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  random()       { return this._next(); }
  randint(a, b)  { return Math.floor(this._next() * (b - a + 1)) + a; }
  choice(arr)    { return arr[this.randint(0, arr.length - 1)]; }

  shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = this.randint(0, i);
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  }

  sample(arr, k) {
    const c = arr.slice();
    for (let i = 0; i < k; i++) {
      const j = this.randint(i, c.length - 1);
      [c[i], c[j]] = [c[j], c[i]];
    }
    return c.slice(0, k);
  }
}

// Python's floor division (floors toward -∞, unlike JS which truncates toward 0)
function floorDiv(a, b) { return Math.floor(a / b); }

// Python's modulo (always non-negative when b > 0)
function pyMod(a, b) { return ((a % b) + b) % b; }

function gcd(a, b) {
  a = Math.abs(a); b = Math.abs(b);
  while (b) { [a, b] = [b, a % b]; }
  return a || 1;
}

// Port of Python _trunc(val, places): round to `places` dp, return int if whole
function trunc(val, places) {
  const v = parseFloat(val.toFixed(places));
  return (v === Math.trunc(v)) ? Math.trunc(v) : v;
}

// Convenience: round to 2dp, int if whole (port of _r2 in question_engine.py)
function r2(val) { return trunc(val, 2); }

// ─── isRepeating ─────────────────────────────────────────────────────────────
// Port of Python is_repeating(): returns true iff val's decimal expansion repeats.
// Used by answer-validation logic (offline practice open-answer mode).

function _limitDenominator(x, maxDen) {
  // Best rational approximation to x with denominator <= maxDen (continued fractions).
  if (maxDen < 1) return [Math.round(x), 1];
  let p0 = 0, q0 = 1, p1 = 1, q1 = 0;
  let rem = parseFloat(x.toFixed(9)); // reduce float noise (port of f"{v:.9g}")
  for (let i = 0; i < 200; i++) {
    const a = Math.floor(rem);
    const p2 = a * p1 + p0, q2 = a * q1 + q0;
    if (q2 > maxDen) break;
    [p0, q0, p1, q1] = [p1, q1, p2, q2];
    const diff = rem - a;
    if (Math.abs(diff) < 1e-12) break;
    rem = 1 / diff;
  }
  return q1 === 0 ? [Math.round(x), 1] : [p1, q1];
}

function isRepeating(val) {
  const v = Math.abs(val);
  // Stage 1: terminating check (v × 10^n is integer for n = 0..4)
  for (let n = 0; n <= 4; n++) {
    const scaled = v * Math.pow(10, n);
    if (Math.abs(scaled - Math.round(scaled)) < 1e-6) return false;
  }
  // Stage 2: fraction approximation — strip factors of 2 and 5 from denominator
  let d = _limitDenominator(v, 100000)[1];
  while (d % 2 === 0) d = Math.trunc(d / 2);
  while (d % 5 === 0) d = Math.trunc(d / 5);
  return d !== 1;
}

if (typeof module !== 'undefined') module.exports = { RNG, floorDiv, pyMod, gcd, trunc, r2, isRepeating };
