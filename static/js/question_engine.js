// question_engine.js — offline arithmetic question generation (MC only)
// Ports question_engine.py exactly; always returns a question with options + correct_index.

'use strict';
(function (root, factory) {
  if (typeof module !== 'undefined') module.exports = factory(require('./rng.js'));
  else root.QE = factory({ RNG, floorDiv, pyMod, gcd, trunc, r2, isRepeating });
}(typeof globalThis !== 'undefined' ? globalThis : this, function (rngMod) {

const { floorDiv, gcd, trunc, r2 } = rngMod;

// ─── Fraction helper ──────────────────────────────────────────────────────────

class Frac {
  constructor(n, d) {
    if (d === 0) throw new Error('zero denominator');
    if (d < 0) { n = -n; d = -d; }
    const g = gcd(Math.abs(n), d) || 1;
    this.n = Math.trunc(n / g);
    this.d = Math.trunc(d / g);
  }
  add(o) { return new Frac(this.n * o.d + o.n * this.d, this.d * o.d); }
  sub(o) { return new Frac(this.n * o.d - o.n * this.d, this.d * o.d); }
  mul(o) { return new Frac(this.n * o.n, this.d * o.d); }
  div(o) { return new Frac(this.n * o.d, this.d * o.n); }
  mulInt(k) { return new Frac(this.n * k, this.d); }
  toFloat() { return this.n / this.d; }
}

// ─── Clean fracs table ────────────────────────────────────────────────────────

const CLEAN_FRACS = [
  [1,2,0.5],   [1,4,0.25],  [3,4,0.75],
  [1,5,0.2],   [2,5,0.4],   [3,5,0.6],   [4,5,0.8],
  [1,8,0.125], [3,8,0.375], [5,8,0.625], [7,8,0.875],
  [1,10,0.1],  [3,10,0.3],  [7,10,0.7],  [9,10,0.9],
  [1,20,0.05], [3,20,0.15], [7,20,0.35], [9,20,0.45],
  [11,20,0.55],[13,20,0.65],[17,20,0.85],[19,20,0.95],
  [1,25,0.04], [2,25,0.08], [3,25,0.12], [4,25,0.16],
  [6,25,0.24], [7,25,0.28],
  [1,16,0.0625],[3,16,0.1875],[5,16,0.3125],[7,16,0.4375],
];

// ─── Formatting helpers ───────────────────────────────────────────────────────

function _autoDisplay(val) {
  if (Number.isInteger(val)) return String(val);
  if (val === Math.trunc(val)) return String(Math.trunc(val));
  return val.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
}
const _fmt = _autoDisplay;

function _randDec1(rng, lo, hi) {
  let loI = Math.trunc(lo * 10), hiI = Math.trunc(hi * 10);
  if (loI >= hiI) hiI = loI + 1;
  return parseFloat((rng.randint(loI, hiI) / 10).toFixed(1));
}

function _randDec2(rng, loCents, hiCents) {
  return parseFloat((rng.randint(loCents, hiCents) / 100).toFixed(2));
}

function _cleanFracAns(frac) {
  if (frac.d === 1) return frac.n;
  return Math.round(frac.toFloat() * 1e6) / 1e6;
}

function _fracStr(frac) {
  if (frac.d === 1) return String(frac.n);
  const num = frac.n, den = frac.d;
  if (Math.abs(num) > den) {
    const whole = Math.trunc(num / den);
    const rem = num - whole * den;
    if (rem === 0) return String(whole);
    return `${whole} ${Math.abs(rem)}/${den}`;
  }
  return `${num}/${den}`;
}

function _q(text, answer, displayAnswer) {
  if (displayAnswer === undefined) displayAnswer = _autoDisplay(answer);
  return { text, answer, display_answer: displayAnswer };
}

function _valid(q) {
  try {
    const v = parseFloat(q.answer);
    if (!(isFinite(v) && Math.abs(v) < 1e6)) return false;
    if (q._pct_meta && !_pctBackCheck(q._pct_meta, v)) return false;
    return true;
  } catch (e) { return false; }
}

// Port of question_engine.py's _pct_back_check(): confirms the stored answer
// agrees with back-calculation from the generator's _pct_meta.
function _pctBackCheck(meta, answer) {
  try {
    const t = meta.type;
    if (t === 'basic') {
      const expected = r2(meta.pct / 100 * meta.base);
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'reverse') {
      const expected = r2(meta.result / meta.base * 100);
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'increase') {
      const expected = r2(meta.original * (1 + meta.pct / 100));
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'decrease') {
      const expected = r2(meta.original * (1 - meta.pct / 100));
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'compound') {
      const step1 = meta.original * (1 + meta.pct1 / 100);
      const expected = r2(step1 * (1 - meta.pct2 / 100));
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'nested') {
      const expected = r2(meta.pct1 / 100 * meta.pct2 / 100 * meta.base);
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'reverse_hard') {
      return Math.abs(answer * (1 + meta.pct / 100) - meta.y) <= 0.5;
    } else if (t === 'find_base') {
      const expected = r2(meta.result / (meta.pct / 100));
      return Math.abs(expected - answer) < 0.01;
    } else if (t === 'triple_compound') {
      const step1 = meta.original * (1 + meta.pct1 / 100);
      const step2 = step1 * (1 - meta.pct2 / 100);
      const expected = r2(step2 * (1 + meta.pct3 / 100));
      return Math.abs(expected - answer) < 0.01;
    }
    return true;
  } catch (e) {
    return true; // don't reject on unexpected meta shape
  }
}

// ─── Integer generator ────────────────────────────────────────────────────────

function _genIntegers(difficulty, rng) {
  if (difficulty === 'easy') {
    const op = rng.choice(['+', '-', '*', '/']);
    if (op === '+') { const a = rng.randint(2,20), b = rng.randint(2,20); return _q(`${a} + ${b}`, a+b); }
    if (op === '-') { const a = rng.randint(5,25), b = rng.randint(2,a); return _q(`${a} - ${b}`, a-b); }
    if (op === '*') { const a = rng.randint(2,12), b = rng.randint(2,12); return _q(`${a} x ${b}`, a*b); }
    const b = rng.randint(2,10), ans = rng.randint(2,15); return _q(`${b*ans} / ${b}`, ans);
  }
  if (difficulty === 'medium') {
    const op = rng.choice(['+', '-', '*', 'div']);
    if (op === '+') { const a = rng.randint(10,60), b = rng.randint(10,60); return _q(`${a} + ${b}`, a+b); }
    if (op === '-') {
      const a = rng.randint(21,99);
      const b = rng.random() < 0.3 ? rng.randint(a+1, a+30) : rng.randint(10, a-1);
      return _q(`${a} - ${b}`, a-b);
    }
    if (op === '*') { const a = rng.randint(11,20), b = rng.randint(2,10); return _q(`${a} x ${b}`, a*b); }
    const b = rng.randint(2,12), ans = rng.randint(5,15); return _q(`${b*ans} : ${b}`, ans);
  }
  if (difficulty === 'normal') {
    const kind = rng.choice(['mul2','add3','sub3','div2']);
    if (kind === 'mul2') { const a = rng.randint(11,99), b = rng.randint(11,99); return _q(`${a} x ${b}`, a*b); }
    if (kind === 'add3') { const a = rng.randint(100,999), b = rng.randint(100,999); return _q(`${a} + ${b}`, a+b); }
    if (kind === 'sub3') {
      const a = rng.randint(200,999);
      const b = rng.random() < 0.3 ? rng.randint(a+1,a+200) : rng.randint(100,a-1);
      return _q(`${a} - ${b}`, a-b);
    }
    const b = rng.randint(2,20), ans = rng.randint(10,60); return _q(`${b*ans} : ${b}`, ans);
  }
  // hard
  const kind = rng.choice(['big_mul','multi_step','chain']);
  if (kind === 'big_mul') { const a = rng.randint(100,999), b = rng.randint(11,99); return _q(`${a} x ${b}`, a*b); }
  if (kind === 'multi_step') {
    const a = rng.randint(10,60), b = rng.randint(10,60), c = rng.randint(3,15);
    return _q(`(${a} + ${b}) x ${c}`, (a+b)*c);
  }
  const a = rng.randint(10,50), b = rng.randint(10,50), c = rng.randint(2,20), d = rng.randint(2,20);
  return _q(`${a} x ${b} + ${c} x ${d}`, a*b + c*d);
}

// ─── Decimal generator ────────────────────────────────────────────────────────

function _genDecimals(difficulty, rng) {
  if (difficulty === 'easy') {
    const op = rng.choice(['+', '-', '*', '/']);
    if (op === '+') { const a = _randDec1(rng,1,9), b = _randDec1(rng,1,9); return _q(`${a} + ${b}`, trunc(a+b,1)); }
    if (op === '-') { const a = _randDec1(rng,3,15), b = _randDec1(rng,1,a-0.1); return _q(`${a} - ${b}`, trunc(a-b,1)); }
    if (op === '*') { const a = _randDec1(rng,1,8), b = rng.randint(2,6); return _q(`${a} x ${b}`, trunc(a*b,1)); }
    const b = rng.choice([2,4,5]), ans = _randDec1(rng,1,8);
    return _q(`${_fmt(trunc(ans*b,1))} / ${b}`, ans);
  }
  if (difficulty === 'medium') {
    const kind = rng.choice(['add1','sub1','div_simple','mul1']);
    if (kind === 'add1') { const a = _randDec1(rng,1,9), b = _randDec1(rng,1,9); return _q(`${a} + ${b}`, trunc(a+b,1)); }
    if (kind === 'sub1') {
      const a = _randDec1(rng,3,15);
      const b = rng.random() < 0.3 ? _randDec1(rng,a+0.1,a+5.0) : _randDec1(rng,1,a-0.1);
      return _q(`${a} - ${b}`, trunc(a-b,1));
    }
    if (kind === 'div_simple') {
      const b = rng.choice([0.5,0.25,2.0,5.0]), ans = rng.randint(2,20);
      const a = trunc(ans*b,1);
      return _q(`${_fmt(a)} : ${_fmt(b)}`, ans);
    }
    const a = _randDec1(rng,1,9), b = rng.randint(2,9); return _q(`${a} x ${b}`, trunc(a*b,1));
  }
  if (difficulty === 'normal') {
    const kind = rng.choice(['div_dec','mul2','add2','sub2']);
    if (kind === 'div_dec') {
      const b = rng.choice([0.1,0.2,0.25,0.4,0.5,0.8]), ans = rng.randint(5,80);
      const a = trunc(ans*b,2);
      return _q(`${_fmt(a)} : ${_fmt(b)}`, ans);
    }
    if (kind === 'mul2') { const a = _randDec1(rng,1,9), b = _randDec1(rng,1,9); return _q(`${a} x ${b}`, trunc(a*b,2)); }
    if (kind === 'add2') {
      const a = _randDec2(rng,100,999), b = _randDec2(rng,100,999);
      return _q(`${a.toFixed(2)} + ${b.toFixed(2)}`, trunc(a+b,2));
    }
    const a = _randDec2(rng,300,999), b = _randDec2(rng,100,a*100-1);
    return _q(`${a.toFixed(2)} - ${b.toFixed(2)}`, trunc(a-b,2));
  }
  // hard
  const ans = rng.randint(50,800);
  const b = rng.choice([0.09,0.08,0.07,0.06,0.04,0.03,0.05,0.11,0.12,0.15]);
  const a = trunc(ans*b,2);
  return _q(`${a.toFixed(2)} : ${b}`, ans);
}

// ─── Fraction generator ───────────────────────────────────────────────────────

function _genFractions(difficulty, rng) {
  if (difficulty === 'easy') {
    const denom = rng.choice([2,3,4,5,6,8,10]);
    const integer = denom * rng.randint(1,8);
    return _q(`(1/${denom}) x ${integer}`, Math.trunc(integer / denom));
  }
  if (difficulty === 'medium') {
    const kind = rng.choice(['unit_frac','frac_mul','frac_sub']);
    if (kind === 'unit_frac') {
      const denom = rng.choice([2,3,4,5,8,10]), integer = denom * rng.randint(1,6);
      return _q(`(1/${denom}) x ${integer}`, Math.trunc(integer / denom));
    }
    if (kind === 'frac_mul') {
      const d = rng.choice([2,3,4,5]), n = rng.randint(1,d-1), integer = rng.randint(2,d*3);
      const result = new Frac(n,d).mulInt(integer);
      return _q(`(${n}/${d}) x ${integer}`, _cleanFracAns(result), _fracStr(result));
    }
    const d = rng.choice([3,4,5,6]), n1 = rng.randint(1,d-1), n2 = rng.randint(1,d-1);
    const result = new Frac(n1,d).sub(new Frac(n2,d));
    return _q(`${n1}/${d} - ${n2}/${d}`, _cleanFracAns(result), _fracStr(result));
  }
  if (difficulty === 'normal') {
    const kind = rng.choice(['to_dec','frac_add','frac_mul','frac_sub']);
    if (kind === 'to_dec') {
      const [n,d,dec] = rng.choice(CLEAN_FRACS);
      return _q(`${n}/${d} as a decimal`, dec);
    }
    if (kind === 'frac_add') {
      const d1 = rng.choice([2,3,4,6,8]), d2 = rng.choice([2,3,4,6,8]);
      const n1 = rng.randint(1,d1-1), n2 = rng.randint(1,d2-1);
      const result = new Frac(n1,d1).add(new Frac(n2,d2));
      return _q(`${n1}/${d1} + ${n2}/${d2}`, _cleanFracAns(result), _fracStr(result));
    }
    if (kind === 'frac_mul') {
      const d1 = rng.choice([2,3,4,5,6,8,10]), n1 = rng.randint(1,d1-1), integer = rng.randint(2,12);
      const result = new Frac(n1,d1).mulInt(integer);
      return _q(`(${n1}/${d1}) x ${integer}`, _cleanFracAns(result), _fracStr(result));
    }
    const d1 = rng.choice([2,3,4,6,8]), d2 = rng.choice([2,3,4,6,8]);
    const n1 = rng.randint(1,d1-1), n2 = rng.randint(1,d2-1);
    const result = new Frac(n1,d1).sub(new Frac(n2,d2));
    return _q(`${n1}/${d1} - ${n2}/${d2}`, _cleanFracAns(result), _fracStr(result));
  }
  // hard
  const kind = rng.choice(['mixed_add','frac_div','chain']);
  if (kind === 'mixed_add') {
    const d = rng.choice([4,8]);
    const w1 = rng.randint(1,5), n1 = rng.randint(1,d-1);
    const w2 = rng.randint(1,5), n2 = rng.randint(1,d-1);
    const result = new Frac(w1*d+n1,d).add(new Frac(w2*d+n2,d));
    return _q(`${w1} ${n1}/${d} + ${w2} ${n2}/${d}`, _cleanFracAns(result), _fracStr(result));
  }
  if (kind === 'frac_div') {
    const d1 = rng.choice([2,3,4,6,8]), d2 = rng.choice([2,3,4,6,8]);
    const n1 = rng.randint(1,d1-1), n2 = rng.randint(1,d2-1);
    const result = new Frac(n1,d1).div(new Frac(n2,d2));
    return _q(`(${n1}/${d1}) / (${n2}/${d2})`, _cleanFracAns(result), _fracStr(result));
  }
  // chain
  const d1 = rng.choice([2,3,4,6]), d2 = rng.choice([2,3,4,6]);
  const n1 = rng.randint(1,d1-1), n2 = rng.randint(1,d2-1), mult = rng.randint(6,24);
  const result = new Frac(n1,d1).add(new Frac(n2,d2)).mulInt(mult);
  return _q(`(${n1}/${d1} + ${n2}/${d2}) x ${mult}`, _cleanFracAns(result), _fracStr(result));
}

// ─── Algebra generator ────────────────────────────────────────────────────────

function _genAlgebra(difficulty, rng) {
  if (difficulty === 'easy') {
    const kind = rng.choice(['add','sub','mul','div']);
    if (kind === 'add') { const a = rng.randint(2,20), x = rng.randint(2,20); return _q(`x + ${a} = ${x+a}`, x); }
    if (kind === 'sub') { const a = rng.randint(2,15), x = rng.randint(5,25); return _q(`x - ${a} = ${x-a}`, x); }
    if (kind === 'mul') { const a = rng.randint(2,12), x = rng.randint(2,15); return _q(`${a}x = ${a*x}`, x); }
    const a = rng.randint(2,10), x = rng.randint(2,15); return _q(`x / ${a} = ${x}`, a*x);
  }
  if (difficulty === 'medium') {
    const kind = rng.choice(['add','sub','mul','div']);
    const neg = rng.random() < 0.3;
    if (kind === 'add') {
      const a = rng.randint(5,30); let x = rng.randint(5,30); if (neg) x = -x;
      return _q(`x + ${a} = ${x+a}`, x);
    }
    if (kind === 'sub') {
      const a = rng.randint(5,25); let x = rng.randint(10,40); if (neg) x = -x;
      return _q(`x - ${a} = ${x-a}`, x);
    }
    if (kind === 'mul') {
      const a = rng.randint(2,15); let x = rng.randint(2,20); if (neg) x = -x;
      return _q(`${a}x = ${a*x}`, x);
    }
    const a = rng.randint(2,12); let x = rng.randint(2,20); if (neg) x = -x;
    return _q(`x / ${a} = ${x}`, a*x);
  }
  if (difficulty === 'normal') {
    const kind = rng.choice(['two_step','frac_coeff','two_step_sub']);
    const neg = rng.random() < 0.3;
    if (kind === 'two_step') {
      const a = rng.randint(2,10), b = rng.randint(2,20); let x = rng.randint(2,15); if (neg) x = -x;
      return _q(`${a}x + ${b} = ${a*x+b}`, x);
    }
    if (kind === 'frac_coeff') {
      const a = rng.choice([2,4,5,10]);
      const b = rng.choice([2,4,5,10,20].filter(v => v !== a));
      let x = rng.randint(2,10) * a; if (neg) x = -x;
      const c = Math.trunc(x / a) * b;
      return _q(`(x/${a}) x ${b} = ${c}`, x);
    }
    const a = rng.randint(2,10), b = rng.randint(2,20); let x = rng.randint(2,15); if (neg) x = -x;
    return _q(`${a}x - ${b} = ${a*x-b}`, x);
  }
  // hard
  const kind = rng.choice(['bracket','dec_coeff','two_eq']);
  const neg = rng.random() < 0.3;
  if (kind === 'bracket') {
    const a = rng.randint(2,8), b = rng.randint(1,10); let x = rng.randint(2,15); if (neg) x = -x;
    return _q(`${a}(x + ${b}) = ${a*(x+b)}`, x);
  }
  if (kind === 'dec_coeff') {
    const a = rng.choice([1.5,2.5,0.5,1.25,3.5]);
    let x = rng.randint(2,8) * 2; if (neg) x = -x;
    const b = rng.randint(1,20), c = parseFloat((a*x+b).toFixed(2));
    return _q(`${a}x + ${b} = ${c}`, x);
  }
  const cv = rng.randint(1,5), av = cv + rng.randint(1,5);
  let x = rng.randint(2,15); if (neg) x = -x;
  const b = rng.randint(1,20), dv = av*x + b - cv*x;
  return _q(`${av}x + ${b} = ${cv}x + ${dv}`, x);
}

// ─── Percentage generator ─────────────────────────────────────────────────────

function _genPercentages(difficulty, rng) {
  if (difficulty === 'easy') {
    const pct = rng.choice([10,20,25,50,75]);
    const base = rng.choice([20,40,60,80,100,200,400,1000]);
    const answer = r2(pct / 100 * base);
    const q = _q(`${pct}% of ${base}`, answer);
    q._pct_meta = { type: 'basic', pct, base };
    return q;
  }
  if (difficulty === 'medium') {
    const pct = rng.choice([10,20,25,50,75]);
    const base = rng.randint(10,99);
    const answer = r2(pct / 100 * base);
    const q = _q(`${pct}% of ${base}`, answer);
    q._pct_meta = { type: 'basic', pct, base };
    return q;
  }
  if (difficulty === 'normal') {
    const kind = rng.choice(['decimal_pct','reverse','pct_increase','pct_decrease']);
    if (kind === 'decimal_pct') {
      const pct = rng.choice([15,35,12,18,22,45,8,60,65,30]);
      const base = rng.randint(2,20) * Math.trunc(100 / gcd(pct, 100));
      const answer = r2(pct * base / 100);
      const q = _q(`${pct}% of ${base}`, answer);
      q._pct_meta = { type: 'basic', pct, base };
      return q;
    }
    if (kind === 'reverse') {
      const pct = rng.choice([10,20,25,30,40,50,75]);
      const base = rng.randint(4,20) * Math.trunc(100 / pct);
      const result = r2(pct / 100 * base);
      const q = _q(`?% of ${base} = ${result}`, pct);
      q._pct_meta = { type: 'reverse', result: parseFloat(result), base };
      return q;
    }
    if (kind === 'pct_increase') {
      const original = rng.randint(50,400), pct = rng.choice([10,20,25,50,15]);
      const answer = r2(original * (1 + pct / 100));
      const q = _q(`${original} increased by ${pct}% =`, answer);
      q._pct_meta = { type: 'increase', original, pct };
      return q;
    }
    const original = rng.randint(100,500), pct = rng.choice([10,20,25,50]);
    const answer = r2(original * (1 - pct / 100));
    const q = _q(`${original} decreased by ${pct}% =`, answer);
    q._pct_meta = { type: 'decrease', original, pct };
    return q;
  }
  // hard
  const kind = rng.choice(['compound','nested','reverse_hard']);
  if (kind === 'compound') {
    const original = rng.choice([100,200,400,500,1000]);
    const pct1 = rng.choice([10,20,25,15]), pct2 = rng.choice([10,20,25,15]);
    const step1 = original * (1 + pct1 / 100);
    const answer = r2(step1 * (1 - pct2 / 100));
    const q = _q(`${original}: +${pct1}% then -${pct2}%`, answer);
    q._pct_meta = { type: 'compound', original, pct1, pct2 };
    return q;
  }
  if (kind === 'nested') {
    const pct1 = rng.choice([20,25,40,50]), pct2 = rng.choice([20,25,40,50]);
    const base = rng.choice([100,200,400,500,1000]);
    const answer = r2(pct1 / 100 * pct2 / 100 * base);
    const q = _q(`${pct1}% of (${pct2}% of ${base})`, answer);
    q._pct_meta = { type: 'nested', pct1, pct2, base };
    return q;
  }
  // reverse_hard
  const pct = rng.choice([10,20,25,50]);
  const x = rng.randint(50,400);
  const y = Math.round(x * (1 + pct / 100));
  const q = _q(`After +${pct}%, result is ${y}. Original =`, x);
  q._pct_meta = { type: 'reverse_hard', pct, y };
  return q;
}

// ─── MC option attachment ─────────────────────────────────────────────────────

function _attachOptions(q, rng) {
  const display = q.display_answer;
  let distractors;
  if (String(display).includes('/')) {
    distractors = _fractionDistractors(q.answer, display, rng);
  } else {
    distractors = _numericDistractors(q.answer, display, rng);
  }
  const options = [display].concat(distractors);
  rng.shuffle(options);
  q.options = options;
  q.correct_index = options.indexOf(display);
}

function _distractorFmt(d, refAnswer) {
  if (Number.isInteger(refAnswer)) return String(Math.round(d));
  const refS = _autoDisplay(refAnswer);
  if (refS.includes('.')) {
    const places = refS.split('.')[1].length;
    const v = parseFloat(d.toFixed(places));
    return v === Math.trunc(v) ? String(Math.trunc(v)) : v.toFixed(places).replace(/0+$/, '').replace(/\.$/, '');
  }
  return String(Math.round(d));
}

function _limitDen(x, maxD) {
  // Minimal continued-fraction rational approximation for fraction distractors
  let p0=0,q0=1,p1=1,q1=0, rem=x;
  for (let i=0;i<200;i++) {
    const a=Math.floor(rem), p2=a*p1+p0, q2=a*q1+q0;
    if (q2>maxD) break;
    [p0,q0,p1,q1]=[p1,q1,p2,q2];
    const diff=rem-a; if (Math.abs(diff)<1e-12) break; rem=1/diff;
  }
  return q1===0?[Math.round(x),1]:[p1,q1];
}

function _fractionDistractors(answer, correctDisplay, rng) {
  const [bn, bd] = _limitDen(Math.abs(typeof answer==='number'?answer:parseFloat(answer)), 16);
  const base = new Frac(bn, bd);
  const seen = new Set([correctDisplay]);
  const results = [];
  const candidates = [];
  for (let dn = -4; dn <= 4; dn++) {
    if (dn === 0) continue;
    try { const f = new Frac(base.n + dn, base.d); if (f.n > 0) candidates.push(f); } catch(e){}
  }
  for (const d of [2,3,4,6,8]) {
    for (const adj of [-2,-1,1,2]) {
      const num = Math.round(base.toFloat() * d) + adj;
      if (num > 0) try { candidates.push(new Frac(num, d)); } catch(e){}
    }
  }
  rng.shuffle(candidates);
  for (const frac of candidates) {
    if (results.length >= 3) break;
    if (frac.n <= 0) continue;
    const s = _fracStr(frac);
    if (!seen.has(s)) { seen.add(s); results.push(s); }
  }
  let fill = 1;
  while (results.length < 3) {
    try { const s = _fracStr(new Frac(base.n + fill, base.d)); if (!seen.has(s)) { results.push(s); seen.add(s); } } catch(e){}
    fill++;
  }
  return results.slice(0, 3);
}

function _numericDistractors(answer, correctDisplay, rng) {
  const ansF = parseFloat(answer);
  if (!isFinite(ansF)) return ['0','1','2'];
  const places = Number.isInteger(answer) ? 0 :
    (_autoDisplay(answer).includes('.') ? _autoDisplay(answer).split('.')[1].length : 0);
  const absA = Math.abs(ansF);

  function candidate() {
    const s = rng.randint(0,4);
    if (s === 0) {
      const pct = rng.choice([0.05,0.1,0.15,0.2,-0.05,-0.1,-0.15,-0.2]);
      return parseFloat((ansF*(1+pct)).toFixed(places));
    }
    if (s === 1) {
      const off = absA<10?rng.choice([1,2,3]):absA<100?rng.choice([2,5,10]):absA<1000?rng.choice([5,10,20,50]):rng.choice([10,50,100]);
      return parseFloat((ansF + rng.choice([-1,1])*off).toFixed(places));
    }
    if (s === 2) {
      if (rng.randint(0,1)===0) { const t=rng.choice([5,10]); return parseFloat((Math.round(ansF/t)*t).toFixed(places)); }
      const p=rng.choice([0.05,0.1,0.15,-0.05,-0.1,-0.15]);
      return parseFloat((ansF*(1+p)*(1+p)).toFixed(places));
    }
    if (s === 3) {
      const lo=Math.min(ansF*0.7,ansF*1.3), hi=Math.max(ansF*0.7,ansF*1.3);
      const range = (Math.abs(hi-lo)<0.01)?2:hi-lo;
      return parseFloat((lo + rng.random()*range).toFixed(places));
    }
    return parseFloat((-ansF).toFixed(places));
  }

  const seen = new Set([correctDisplay]);
  const results = [];
  let signFlips = 0;

  if (ansF < 0 && absA > 0.001) {
    const pos = parseFloat((absA * (0.8 + rng.random()*0.4)).toFixed(places));
    const s = _distractorFmt(pos, answer);
    if (!seen.has(s)) { seen.add(s); results.push(s); }
  }

  for (let att = 0; att < 300 && results.length < 3; att++) {
    const d = candidate();
    const minDiff = Math.max(absA * 0.02, 0.001);
    if (Math.abs(d - ansF) < minDiff) continue;
    if (absA > 0.001 && Math.abs(d) > 0.001) {
      const ratio = Math.abs(d) / absA;
      if (ratio > 9 || ratio < 0.111) continue;
    }
    if (ansF > 0 && d < 0 && signFlips >= 1) continue;
    const s = _distractorFmt(d, answer);
    if (seen.has(s) || s === correctDisplay) continue;
    let tooClose = false;
    for (const ex of results) {
      if (Math.abs(parseFloat(ex) - d) < 0.001) { tooClose=true; break; }
    }
    if (tooClose) continue;
    seen.add(s); results.push(s);
    if (ansF > 0 && d < 0) signFlips++;
  }

  for (let step=1; step<=30 && results.length<3; step++) {
    for (const sgn of [1,-1]) {
      if (results.length >= 3) break;
      const off = step * Math.max(absA * 0.1, 1);
      const d = parseFloat((ansF + sgn*off).toFixed(places));
      const s = _distractorFmt(d, answer);
      if (!seen.has(s)) { seen.add(s); results.push(s); }
    }
  }
  return results.slice(0, 3);
}

// ─── Public API ───────────────────────────────────────────────────────────────

const CATEGORIES = ['integers','decimals','fractions','algebra','percentages'];
const _GENS = {
  integers:    _genIntegers,
  decimals:    _genDecimals,
  fractions:   _genFractions,
  algebra:     _genAlgebra,
  percentages: _genPercentages,
};

function getQuestion(category, difficulty, rng) {
  const gen = _GENS[category] || _genIntegers;
  for (let i = 0; i < 20; i++) {
    try {
      const q = gen(difficulty, rng);
      if (q && _valid(q)) {
        q.category = category;
        q.difficulty = difficulty;
        _attachOptions(q, rng);
        if (q.options.length === 4 && new Set(q.options).size === 4) return q;
      }
    } catch (e) {}
  }
  // Fallback: easy
  const q = gen('easy', rng);
  q.category = category || 'integers';
  q.difficulty = 'easy';
  _attachOptions(q, rng);
  return q;
}

return { getQuestion, CATEGORIES };

}));
