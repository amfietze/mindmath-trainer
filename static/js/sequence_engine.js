// sequence_engine.js — offline sequence question generation (MC only)
// Ports the updated sequence_engine.py exactly (post session-13 recalibration).

'use strict';
(function (root, factory) {
  if (typeof module !== 'undefined') module.exports = factory(require('./rng.js'));
  else root.SE = factory({ RNG, floorDiv, pyMod, gcd, trunc, r2, isRepeating });
}(typeof globalThis !== 'undefined' ? globalThis : this, function (rngMod) {

const { floorDiv, pyMod } = rngMod;

// ─── Constants ────────────────────────────────────────────────────────────────

const ALPHABET    = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const VOWELS      = Array.from('AEIOU');
const CONSONANTS  = Array.from(ALPHABET).filter(c => !VOWELS.includes(c));
const QWERTY_ROWS = ['QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM'];
const PRIMES_10   = [2,3,5,7,11,13,17,19,23,29];
const FIBS_8      = [1,2,3,5,8,13,21,34];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function _lpos(ch) { return ALPHABET.indexOf(ch.toUpperCase()); }
function _lch(pos) { return ALPHABET[pyMod(pos, 26)]; }

function _fmt(val) {
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return String(val);
    if (val === Math.trunc(val)) return String(Math.trunc(val));
    return String(val);
  }
  return String(val);
}

function _digitSum(n) {
  return String(Math.abs(Math.trunc(n))).split('').reduce((s, d) => s + parseInt(d), 0);
}

function _digitalRoot(n) {
  if (n === 0) return 0;
  const r = pyMod(n, 9);
  return r !== 0 ? r : 9;
}

function _factorial(n) {
  let r = 1;
  for (let i = 2; i <= n; i++) r *= i;
  return r;
}

// ─── Number generators — Easy ─────────────────────────────────────────────────

function _numArithEasy(rng) {
  const d = rng.choice([-5,-4,-3,-2,-1,1,2,3,4,5]);
  const start = d < 0 ? rng.randint(10,30) : rng.randint(1,20);
  const terms = Array.from({length:5}, (_,i) => start + d*i);
  const dir = d>0?'increases':'decreases';
  return [terms, 'arithmetic', `Each term ${dir} by ${Math.abs(d)}.`];
}

function _numDoubleEasy(rng) {
  const op = rng.choice(['double','halve']);
  if (op === 'double') {
    const s = rng.randint(1,8);
    return [Array.from({length:5}, (_,i) => s*(2**i)), 'geometric_x2', 'Each term is doubled.'];
  }
  const s = rng.choice([16,32,48,64]);
  return [Array.from({length:5}, (_,i) => s/(2**i)), 'geometric_div2', 'Each term is halved.'];
}

function _numCount10Easy(rng) {
  const s = rng.choice([10,20,30,40,50,60,70]);
  return [Array.from({length:5}, (_,i) => s+10*i), 'count_by_10', 'Count up by 10 each step.'];
}

function _numEvenEasy(rng) {
  const s = rng.choice([2,4,6,8,10,12]);
  return [Array.from({length:5}, (_,i) => s+2*i), 'even_numbers', 'Consecutive even numbers.'];
}

function _numOddEasy(rng) {
  const s = rng.choice([1,3,5,7,9,11]);
  return [Array.from({length:5}, (_,i) => s+2*i), 'odd_numbers', 'Consecutive odd numbers.'];
}

// ─── Number generators — Medium ───────────────────────────────────────────────

function _numArithMedium(rng) {
  const d = rng.choice([-20,-15,-10,-8,-6,-5,5,6,7,8,10,15,20]);
  const start = d<0 ? rng.randint(50,150) : rng.randint(5,50);
  const length = rng.choice([5,6]);
  const terms = Array.from({length}, (_,i) => start+d*i);
  const dir = d>0?'increases':'decreases';
  return [terms, 'arithmetic', `Each term ${dir} by ${Math.abs(d)}.`];
}

function _numGeomMedium(rng) {
  const op = rng.choice(['x3','x4','div3']);
  if (op==='x3') { const s=rng.randint(1,5); return [Array.from({length:5},(_,i)=>s*(3**i)),'geometric_x3','Each term is multiplied by 3.']; }
  if (op==='x4') { const s=rng.randint(1,3); return [Array.from({length:5},(_,i)=>s*(4**i)),'geometric_x4','Each term is multiplied by 4.']; }
  const s=rng.choice([243,486,729]);
  return [Array.from({length:5},(_,i)=>s/(3**i)),'geometric_div3','Each term is divided by 3.'];
}

function _numSquaresMedium(rng) {
  const off = rng.randint(1,5);
  return [Array.from({length:5},(_,i)=>(off+i)**2),'squares',`Consecutive perfect squares starting from ${off}².`];
}

function _numTriangularMedium(rng) {
  const n0 = rng.randint(1,4);
  const terms = Array.from({length:5}, (_,i) => { const n=n0+i; return n*(n+1)/2; });
  return [terms, 'triangular', 'Triangular numbers: each term is n×(n+1)÷2.'];
}

function _numPrimeMedium(rng) {
  const s = rng.randint(0,5);
  return [PRIMES_10.slice(s,s+5), 'primes', 'Consecutive prime numbers.'];
}

function _numAltSignMedium(rng) {
  const n = rng.randint(1,3);
  const terms = Array.from({length:5}, (_,i) => (i+1)*((-1)**(i+1))*n);
  return [terms, 'alternating_sign', `Terms alternate between positive and negative, increasing in magnitude: ${n}, −${2*n}, ${3*n}...`];
}

function _numPow2Medium(rng) {
  const n0 = rng.randint(0,2);
  return [Array.from({length:6},(_,i)=>2**(n0+i)), 'powers_of_2', 'Each term is double the previous (powers of 2).'];
}

function _numPow3Medium(rng) {
  const n0 = rng.randint(0,1);
  return [Array.from({length:5},(_,i)=>3**(n0+i)), 'powers_of_3', 'Each term is triple the previous (powers of 3).'];
}

function _numMultiplesMedium(rng) {
  const base = rng.choice([3,4,6,7]), start = rng.randint(1,3);
  return [Array.from({length:6},(_,i)=>base*(start+i)), 'multiples', `Multiples of ${base}.`];
}

function _numCollatzMedium(rng) {
  const seed = rng.choice([6,10,12,14,18,20,24,26,28]);
  const terms = [seed];
  for (let i=0; i<5; i++) {
    const n=terms[terms.length-1];
    terms.push(n%2===0 ? n/2 : 3*n+1);
    if (terms.length>6) break;
  }
  if (terms.length < 6) return [[12,6,3,10,5,16],'collatz','If even, halve it. If odd, multiply by 3 and add 1 (Collatz rule).'];
  return [terms.slice(0,6), 'collatz', 'If even, halve it. If odd, multiply by 3 and add 1 (Collatz rule).'];
}

function _numDigitSumMedium(rng) {
  const target = rng.randint(5,12);
  let start = target <= 9 ? target : (target-9)*10+9;
  let terms = Array.from({length:5}, (_,i) => start+9*i);
  if (!terms.every(t => _digitSum(t) === target)) {
    start = target;
    terms = Array.from({length:5}, (_,i) => target+9*i);
  }
  return [terms, 'digit_sum', `The digits of each term sum to ${target}.`];
}

// ─── Number generators — Normal ───────────────────────────────────────────────

function _numFibonacciNormal(rng) {
  const a = rng.randint(1,5), b = rng.randint(1,8);
  const terms = [a,b];
  for (let i=0;i<4;i++) terms.push(terms[terms.length-1]+terms[terms.length-2]);
  return [terms, 'fibonacci', `Each term is the sum of the two preceding terms (starts ${a}, ${b}).`];
}

function _numAlternatingNormal(rng) {
  const a0=rng.randint(1,5), b0=rng.randint(8,15), da=rng.randint(1,3), db=-rng.randint(1,3);
  const terms = [];
  for (let i=0;i<3;i++) { terms.push(a0+da*i); terms.push(b0+db*i); }
  return [terms, 'alternating', `Two interleaved sequences: odd positions increase by ${da}, even positions decrease by ${Math.abs(db)}.`];
}

function _numIncDiffNormal(rng) {
  const start=rng.randint(1,10), d0=rng.randint(1,3);
  const terms=[start];
  for (let i=0;i<5;i++) terms.push(terms[terms.length-1]+d0+i);
  return [terms,'increasing_differences',`Differences between consecutive terms increase by 1 each step: ${d0}, ${d0+1}, ${d0+2}...`];
}

function _numArithNegNormal(rng) {
  const start=rng.randint(10,20), d=-rng.randint(3,7);
  return [Array.from({length:6},(_,i)=>start+d*i), 'arithmetic', `Each term decreases by ${Math.abs(d)}, crossing zero.`];
}

function _numGeomAltSignNormal(rng) {
  const r=rng.choice([2,3]), start=rng.randint(1,4);
  return [Array.from({length:5},(_,i)=>start*(r**i)*((-1)**i)), 'geometric_alt_sign', `Each term is multiplied by −${r}, alternating sign.`];
}

function _numSquareOffsetNormal(rng) {
  const c=rng.randint(0,3), n0=rng.randint(1,3);
  const terms=Array.from({length:5},(_,i)=>(n0+i)**2+c);
  const rule=c>0?`Each term is n² + ${c} for consecutive n starting at ${n0}.`:`Consecutive perfect squares starting from ${n0}².`;
  return [terms,'square_offset',rule];
}

function _numAltTwoStepNormal(rng) {
  const start=rng.randint(1,5), d1=rng.choice([2,3,4]);
  const d2=rng.choice([2,3,4,5].filter(d=>d!==d1));
  const terms=[start];
  for (let i=0;i<6;i++) terms.push(terms[terms.length-1]+(i%2===0?d1:d2));
  return [terms,'alternating_step',`Alternating steps: +${d1} then +${d2}, repeating.`];
}

function _numCubesNormal(rng) {
  const n0=rng.randint(1,3);
  return [Array.from({length:5},(_,i)=>(n0+i)**3),'cubes',`Consecutive cube numbers starting from ${n0}³.`];
}

function _numSecondOrderNormal(rng) {
  const start=rng.randint(1,8), d0=rng.randint(1,3), k=rng.randint(1,2);
  const terms=[start]; let d=d0;
  for (let i=0;i<6;i++) { terms.push(terms[terms.length-1]+d); d+=k; }
  return [terms,'second_order_arithmetic',`Differences between terms increase by ${k} each step: ${d0}, ${d0+k}, ${d0+2*k}...`];
}

function _numLucasNormal(rng) {
  const full=[2,1,3,4,7,11,18];
  const s=rng.randint(0,2);
  return [full.slice(s,s+6),'lucas','Each term is the sum of the two preceding terms (Lucas sequence, starting 2, 1).'];
}

function _numCatalanNormal(rng) {
  return [[1,1,2,5,14,42],'catalan','Catalan numbers: 1, 1, 2, 5, 14, 42...'];
}

function _numCumsumMedium(rng) {
  const start=rng.randint(1,6), d0=rng.randint(1,3);
  const terms=[start]; let d=d0;
  for (let i=0;i<4;i++) { terms.push(terms[terms.length-1]+d); d+=1; }
  return [terms,'cumulative_sum',`Each term adds one more than the previous increase: +${d0}, +${d0+1}, +${d0+2}...`];
}

function _numFactorialHard(rng) {
  const n0=rng.randint(1,2);
  return [Array.from({length:5},(_,i)=>_factorial(n0+i)),'factorial',`Each term is a factorial: ${n0}!, ${n0+1}!, ${n0+2}!...`];
}

function _numDigitalRootHard(rng) {
  const dr=rng.randint(1,9);
  const start=dr<=9?dr:(dr-9)*10+9;
  let terms=Array.from({length:5},(_,i)=>start+9*i);
  if (!terms.every(t=>_digitalRoot(t)===dr)) terms=Array.from({length:5},(_,i)=>dr+9*i);
  return [terms,'digital_root',`Each term has a digital root of ${dr} (repeated digit-sum reduces to ${dr}).`];
}

// ─── Number generators — Hard ─────────────────────────────────────────────────

function _numAltOpHard(rng) {
  const mult=rng.choice([2,3]), add=rng.randint(2,6), start=rng.randint(1,5);
  const terms=[start];
  for (let i=0;i<6;i++) terms.push(i%2===0?terms[terms.length-1]*mult:terms[terms.length-1]+add);
  return [terms,'alternating_op',`Alternating operations: ×${mult} then +${add}, repeating.`];
}

function _numPowerOffsetHard(rng) {
  const c=rng.randint(1,4), n0=rng.randint(0,2);
  return [Array.from({length:6},(_,i)=>2**(n0+i)+c),'power_offset',`Each term is a power of 2 plus ${c}: 2¹+${c}, 2²+${c}, 2³+${c}...`];
}

function _numRecursiveHard(rng) {
  const start=rng.randint(1,4), c=rng.randint(1,3);
  const terms=[start];
  for (let i=0;i<5;i++) terms.push(terms[terms.length-1]*2+c);
  return [terms,'recursive_double',`Each term equals the previous term doubled, plus ${c}.`];
}

function _numInterleavedGeomHard(rng) {
  const n0=rng.randint(0,1);
  const terms=[];
  for (let i=0;i<4;i++) { terms.push(3**(n0+i)); terms.push(2**(n0+i+1)); }
  return [terms,'interleaved_geometric','Two geometric sequences interleaved: powers of 3 and powers of 2.'];
}

function _numRecamanHard(rng) {
  const seq=[0]; const seen=new Set([0]);
  for (let n=1;n<=10;n++) {
    const c=seq[seq.length-1]-n;
    if (c>0&&!seen.has(c)) seq.push(c); else seq.push(seq[seq.length-1]+n);
    seen.add(seq[seq.length-1]);
  }
  const length=rng.choice([8,9]);
  return [seq.slice(0,length),'recaman','Recaman: subtract n if result is positive and not yet in sequence, else add n.'];
}

function _numSylvesterHard(rng) {
  return [[2,3,7,43,1807],'sylvester','Each term equals the product of all previous terms, plus 1.'];
}

function _numLookSayHard(rng) {
  return [[1,11,21,1211,111221,312211],'look_and_say','Describe the previous term digit by digit: count consecutive identical digits.'];
}

function _numPadovanHard(rng) {
  const full=[1,1,1,2,2,3,4,5,7,9,12,16];
  const s=rng.randint(0,3);
  let terms=full.slice(s,s+8);
  if (terms.length<7) terms=[1,1,1,2,2,3,4,5,7];
  return [terms.slice(0,8),'padovan','Each term equals the term two steps back plus the term three steps back (Padovan).'];
}

function _numTribonacciHard(rng) {
  const a=rng.randint(1,3), b=rng.randint(1,3), c=rng.randint(1,4);
  const terms=[a,b,c];
  for (let i=0;i<5;i++) terms.push(terms[terms.length-1]+terms[terms.length-2]+terms[terms.length-3]);
  return [terms,'tribonacci',`Each term is the sum of the three preceding terms (Tribonacci, starts ${a}, ${b}, ${c}).`];
}

function _numGeneralizedRecurrenceHard(rng) {
  let a=rng.choice([1,2,3]), b=rng.choice([1,2]), c=rng.choice([0,1,2]);
  if (a===1&&b===1&&c===0) a=2;
  const t1=rng.randint(1,3), t2=rng.randint(2,5);
  const terms=[t1,t2];
  for (let i=0;i<5;i++) terms.push(a*terms[terms.length-1]+b*terms[terms.length-2]+c);
  const bPart=b>1?` + ${b}× the term before that`:' + the term before that';
  const cPart=c?` + ${c}`:'';
  return [terms,'generalized_recurrence',`Each term = ${a}× previous${bPart}${cPart}.`];
}

function _numInterleavedTwoRulesHard(rng) {
  const aStart=rng.randint(2,8), aStep=rng.randint(2,5);
  const gStart=rng.randint(1,3), gRatio=rng.choice([2,3]);
  const terms=[];
  for (let i=0;i<4;i++) { terms.push(aStart+aStep*i); terms.push(gStart*(gRatio**i)); }
  return [terms,'interleaved_two_rules',
    `Two interleaved sequences: odd positions form an arithmetic sequence (+${aStep}), even positions form a geometric sequence (×${gRatio}).`];
}

function _numSecondDiffGeometricHard(rng) {
  const r=rng.choice([2,3]), d0=rng.randint(1,2), start=rng.randint(1,5);
  const terms=[start]; let d=d0;
  for (let i=0;i<6;i++) { terms.push(terms[terms.length-1]+d); d*=r; }
  return [terms,'second_diff_geometric',
    `Differences between consecutive terms multiply by ${r} each step: ${d0}, ${d0*r}, ${d0*r**2}...`];
}

function _numWeightedFibonacciHard(rng) {
  const a=rng.choice([2,3]), b=rng.choice([1,2]);
  const t1=rng.randint(1,3), t2=rng.randint(2,5);
  const terms=[t1,t2];
  for (let i=0;i<5;i++) terms.push(a*terms[terms.length-1]+b*terms[terms.length-2]);
  return [terms,'weighted_fibonacci',`Each term = ${a}× previous term + ${b}× the term before that.`];
}

function _numAlternatingRecurrenceHard(rng) {
  const d1=rng.randint(3,8), r=rng.choice([2,3]);
  const t0=rng.randint(1,5), t1=rng.randint(1,3);
  const terms=[t0,t1];
  for (let i=2;i<8;i++) terms.push(i%2===0?terms[terms.length-2]+d1:terms[terms.length-2]*r);
  return [terms,'alternating_recurrence',
    `Two interleaved sequences: positions 1,3,5… each add ${d1} to the previous odd-position term; positions 2,4,6… each multiply the previous even-position term by ${r}.`];
}

// ─── Letter generators — Easy ─────────────────────────────────────────────────

function _letStep1Easy(rng) {
  const s=rng.randint(0,20);
  return [Array.from({length:5},(_,i)=>_lch(s+i)),'alphabet_step','Each letter advances 1 position in the alphabet.'];
}
function _letStep2Easy(rng) {
  const s=rng.randint(0,15);
  return [Array.from({length:5},(_,i)=>_lch(s+i*2)),'alphabet_step','Each letter advances 2 positions in the alphabet.'];
}
function _letRev1Easy(rng) {
  const s=rng.randint(5,25);
  return [Array.from({length:5},(_,i)=>_lch(s-i)),'alphabet_step','Each letter goes back 1 position in the alphabet.'];
}
function _letVowelEasy(rng) {
  return [Array.from('AEIOU'),'vowels','The sequence is the five vowels in alphabetical order: A, E, I, O, U.'];
}
function _letRevSkipEasy(rng) {
  const s=rng.randint(20,25);
  return [Array.from({length:5},(_,i)=>_lch(s-i*2)),'alphabet_step','Every other letter going backwards through the alphabet.'];
}

// ─── Letter generators — Medium ───────────────────────────────────────────────

function _letAltStepMedium(rng) {
  const s=rng.randint(0,12);
  const terms=[_lch(s)]; let pos=s;
  const steps=[2,3];
  for (let i=0;i<5;i++) { pos+=steps[i%2]; terms.push(_lch(pos)); }
  return [terms,'alternating','Letters alternate between +2 and +3 steps through the alphabet.'];
}
function _letRev2Medium(rng) {
  const s=rng.randint(10,25);
  return [Array.from({length:6},(_,i)=>_lch(s-i*2)),'alphabet_step','Each letter goes back 2 positions in the alphabet.'];
}
function _letSkipWrapMedium(rng) {
  const a=rng.randint(18,24), b=rng.randint(1,5);
  const terms=[];
  for (let i=0;i<3;i++) { terms.push(_lch(a-i*2)); terms.push(_lch(b+i*2)); }
  return [terms,'alternating','Two interleaved sequences: odd positions descend by 2, even positions ascend by 2.'];
}
function _letAltEndsMedium(rng) {
  const n=rng.randint(0,4);
  const terms=[];
  for (let i=0;i<3;i++) { terms.push(_lch(n+i)); terms.push(_lch(25-n-i)); }
  return [terms,'alternating_ends','Alternating letters from the beginning and end of the alphabet.'];
}
function _letConsonantMedium(rng) {
  const s=rng.randint(0,CONSONANTS.length-6);
  return [CONSONANTS.slice(s,s+5),'consonants','Consecutive consonants in alphabetical order (vowels skipped).'];
}
function _letPrimePosMedium(rng) {
  const s=rng.randint(0,4);
  return [PRIMES_10.slice(s,s+5).map(p=>_lch(p-1)),'prime_positions','Letters at prime positions in the alphabet: B(2), C(3), E(5), G(7), K(11)...'];
}

// ─── Letter generators — Normal ───────────────────────────────────────────────

function _letPositionalNormal(rng) {
  const s=rng.randint(0,3);
  const terms=[_lch(s)]; let pos=s;
  for (let i=0;i<5;i++) { pos+=(i+2); terms.push(_lch(pos)); }
  return [terms,'positional','Gaps between letters increase by 1 each step: 2, 3, 4, 5, 6...'];
}
function _letTwoLetterNormal(rng) {
  const s=rng.randint(0,16);
  return [Array.from({length:5},(_,i)=>_lch(s+i*2)+_lch(s+i*2+1)),'two_letter','Consecutive alphabet letter pairs: AB, CD, EF...'];
}
function _letKeyboardRowNormal(rng) {
  const row=rng.choice(QWERTY_ROWS);
  const maxStart=Math.max(0,row.length-5);
  const s=rng.randint(0,maxStart);
  const terms=Array.from(row.slice(s,s+5));
  const names={[QWERTY_ROWS[0]]:'top',[QWERTY_ROWS[1]]:'middle',[QWERTY_ROWS[2]]:'bottom'};
  return [terms,'keyboard_row',`Consecutive letters from the ${names[row]||'QWERTY'} row of a QWERTY keyboard.`];
}
function _letDiagonalGridNormal(rng) {
  const diag=rng.randint(0,4);
  let terms=Array.from({length:5},(_,i)=>diag+i*6).filter(p=>p<26).map(_lch);
  if (terms.length<5) terms=Array.from({length:5},(_,i)=>_lch(i*6));
  return [terms,'diagonal_grid','Letters read along a diagonal of a 5×5 alphabet grid, stepping 6 each time.'];
}
function _letTwoSeqMergeNormal(rng) {
  const n=rng.randint(0,3);
  const terms=[];
  for (let i=0;i<3;i++) { terms.push(_lch(n+i*2)); terms.push(_lch(n+i*2+1)); terms.push(_lch(25-n-i)); }
  return [terms,'two_seq_merge','Alternating: two forward letters (AB, CD...) then one reverse letter (Z, Y, X...).'];
}

// ─── Letter generators — Hard ─────────────────────────────────────────────────

function _letWrapHard(rng) {
  const s=rng.randint(0,25), step=rng.choice([3,4,5]);
  return [Array.from({length:6},(_,i)=>_lch(s+i*step)),'alphabet_wrap',`Each letter advances ${step} positions, wrapping from Z back to A.`];
}
function _letComplexHard(rng) {
  const s=rng.randint(0,4);
  const gaps=[rng.randint(1,2),rng.randint(2,3),rng.randint(3,4),rng.randint(4,5),rng.randint(5,6)];
  const terms=[_lch(s)]; let pos=s;
  for (const g of gaps) { pos+=g; terms.push(_lch(pos)); }
  return [terms,'complex_positional','Gaps between letters increase irregularly.'];
}
function _letCaesarHard(rng) {
  const s=rng.randint(0,10);
  const terms=[_lch(s)]; let pos=s;
  for (let i=1;i<5;i++) { pos=pyMod(pos+i,26); terms.push(_lch(pos)); }
  return [terms,'caesar_shift','Each letter is shifted by an increasing amount: +1, +2, +3, +4... (Caesar cipher).'];
}
function _letFibonacciPosHard(rng) {
  const s=rng.randint(0,3);
  return [FIBS_8.slice(s,s+5).map(f=>_lch(f-1)),'fibonacci_positions','Letters at Fibonacci number positions in the alphabet: A(1), B(2), C(3), E(5), H(8)...'];
}
function _letModularHard(rng) {
  const s=rng.randint(0,5);
  const positions=[s]; let pos=s;
  for (let i=0;i<4;i++) { pos=pyMod(pos*2+1,26); positions.push(pos); }
  return [positions.map(_lch),'modular_arithmetic','Each position is doubled and incremented (×2+1), wrapping mod 26.'];
}
function _letInterleavedHard(rng) {
  const step1=rng.choice([2,3,4]);
  const step2=rng.choice([2,3,4,5].filter(d=>d!==step1));
  const s1=rng.randint(0,10), s2=rng.randint(0,10);
  const terms=[];
  for (let i=0;i<3;i++) { terms.push(_lch(s1+step1*i)); terms.push(_lch(s2+step2*i)); }
  return [terms,'interleaved_letters',
    `Two interleaved letter sequences: odd positions advance by ${step1}, even positions advance by ${step2}.`];
}

// ─── Generator registries ──────────────────────────────────────────────────────

const NUM_GEN = {
  easy:   [_numArithEasy, _numDoubleEasy, _numCount10Easy, _numEvenEasy, _numOddEasy],
  medium: [_numArithMedium, _numGeomMedium, _numSquaresMedium, _numTriangularMedium,
           _numPrimeMedium, _numAltSignMedium, _numPow2Medium, _numPow3Medium,
           _numMultiplesMedium, _numCollatzMedium, _numDigitSumMedium],
  normal: [_numFibonacciNormal, _numAlternatingNormal, _numIncDiffNormal, _numArithNegNormal,
           _numGeomAltSignNormal, _numSquareOffsetNormal, _numAltTwoStepNormal, _numCubesNormal,
           _numSecondOrderNormal, _numLucasNormal, _numCatalanNormal, _numCumsumMedium,
           _numFactorialHard, _numDigitalRootHard],
  hard:   [_numAltOpHard, _numPowerOffsetHard, _numRecursiveHard, _numInterleavedGeomHard,
           _numRecamanHard, _numSylvesterHard, _numLookSayHard, _numPadovanHard,
           _numTribonacciHard, _numGeneralizedRecurrenceHard, _numInterleavedTwoRulesHard,
           _numSecondDiffGeometricHard, _numWeightedFibonacciHard, _numAlternatingRecurrenceHard],
};

const LET_GEN = {
  easy:   [_letStep1Easy, _letStep2Easy, _letRev1Easy, _letVowelEasy, _letRevSkipEasy],
  medium: [_letAltStepMedium, _letRev2Medium, _letSkipWrapMedium,
           _letAltEndsMedium, _letConsonantMedium, _letPrimePosMedium],
  normal: [_letPositionalNormal, _letTwoLetterNormal, _letKeyboardRowNormal,
           _letDiagonalGridNormal, _letTwoSeqMergeNormal],
  hard:   [_letWrapHard, _letComplexHard, _letCaesarHard,
           _letFibonacciPosHard, _letModularHard, _letInterleavedHard],
};

// ─── Blank position ────────────────────────────────────────────────────────────

function _blankPos(length, difficulty, rng) {
  if (difficulty === 'easy')   return length - 1;
  if (difficulty === 'medium') return rng.choice([length-1, length-2]);
  if (difficulty === 'normal') return rng.randint(1, length-1);
  return rng.randint(0, length-1);
}

// ─── Validation ────────────────────────────────────────────────────────────────

const MULTI_CHAR = new Set(['two_letter','two_seq_merge']);

function _valid(q) {
  if (!q.answer) return false;
  const disp = q.sequence_display || [];
  if (disp.length < 5) return false;
  const bp = q.blank_position;
  if (bp < 0 || bp >= disp.length || disp[bp] !== '?') return false;
  for (let i=0; i<disp.length; i++) {
    if (i !== bp && (disp[i] == null || disp[i] === '')) return false;
  }
  if (q.category === 'letter_sequence' && !MULTI_CHAR.has(q.sequence_type)) {
    if (q.answer.length !== 1) return false;
  }
  return true;
}

// ─── Core generator ────────────────────────────────────────────────────────────

function _generateOne(difficulty, rng) {
  const isNum = rng.choice(['number','letter']) === 'number';
  let terms, seqType, rule, terms_str, catKey;
  if (isNum) {
    const gen = rng.choice(NUM_GEN[difficulty] || NUM_GEN.easy);
    [terms, seqType, rule] = gen(rng);
    terms_str = terms.map(_fmt);
    catKey = 'number_sequence';
  } else {
    const gen = rng.choice(LET_GEN[difficulty] || LET_GEN.easy);
    [terms, seqType, rule] = gen(rng);
    terms_str = terms.map(String);
    catKey = 'letter_sequence';
  }
  const bp = _blankPos(terms_str.length, difficulty, rng);
  const answer = terms_str[bp];
  const display = terms_str.slice();
  display[bp] = '?';
  return {
    sequence_display: display, answer, rule_description: rule,
    category: catKey, difficulty, blank_position: bp, sequence_type: seqType,
  };
}

// ─── Distractor generation ─────────────────────────────────────────────────────

function _isIntegerSequence(q) {
  const disp = q.sequence_display || [];
  const bp = q.blank_position;
  for (let i=0; i<disp.length; i++) {
    if (i===bp) continue;
    const s = String(disp[i]).trim();
    if (s.includes('.')) return false;
    if (isNaN(parseInt(s))) return false;
  }
  return true;
}

function _fmtNum(val, ref) {
  if (val === Math.trunc(val) && (ref === Math.trunc(ref))) return String(Math.trunc(val));
  const refStr = String(ref);
  if (refStr.includes('.')) {
    const dp = refStr.split('.')[1].replace(/0+$/,'').length || 1;
    return parseFloat(val.toFixed(dp)).toString();
  }
  return val === Math.trunc(val) ? String(Math.trunc(val)) : String(val);
}

function _numDistractors(correctStr, q, rng) {
  const cv = parseFloat(correctStr);
  if (!isFinite(cv)) return [correctStr+'1', correctStr+'2', correctStr+'3'];
  const forceInt = _isIntegerSequence(q);
  const seen = new Set([cv]);
  const result = [];

  function addCandidate(c) {
    if (forceInt) c = Math.round(c);
    const key = forceInt ? Math.round(c) : c;
    if (Math.abs(key - cv) > 0.001 && !seen.has(key)) {
      seen.add(key);
      result.push(_fmtNum(forceInt ? Math.round(c) : c, forceInt ? Math.trunc(cv) : cv));
      return true;
    }
    return false;
  }

  const disp = q.sequence_display || [];
  const bp = q.blank_position;
  const visible = [];
  for (let i=0; i<disp.length; i++) {
    if (i!==bp) { const v=parseFloat(disp[i]); if (isFinite(v)) visible.push(v); }
  }

  if (visible.length >= 2) {
    const diffs = visible.slice(1).map((v,i)=>Math.abs(v-visible[i]));
    const avgD = diffs.length ? diffs.reduce((a,b)=>a+b)/diffs.length : 1;
    for (const c of [cv+avgD,cv-avgD,cv+avgD*2,cv-avgD*2,cv+1,cv-1]) {
      if (addCandidate(c) && result.length >= 3) return result;
    }
  }

  const offsets = rng.sample([-3,-2,-1,1,2,3,-5,5,-4,4], 10);
  for (const off of offsets) {
    if (addCandidate(cv+off) && result.length >= 3) return result;
  }
  return result.slice(0, 3);
}

function _letterDistractors(correct, rng) {
  const pos = ALPHABET.indexOf(correct.toUpperCase());
  if (pos === -1) return ['X','Y','Z'];
  const seen = new Set([pos]);
  const result = [];
  const offsets = [-5,-4,-3,-2,-1,1,2,3,4,5];
  rng.shuffle(offsets);
  for (const off of offsets) {
    const np = pyMod(pos+off, 26);
    if (!seen.has(np)) { seen.add(np); result.push(ALPHABET[np]); if (result.length>=3) break; }
  }
  return result.slice(0,3);
}

function _twoLetterDistractors(correct, rng) {
  if (correct.length < 2) return _letterDistractors(correct, rng);
  const start = ALPHABET.indexOf(correct[0].toUpperCase());
  if (start === -1) return ['XY','YZ','WX'];
  const seen = new Set([correct.toUpperCase()]);
  const result = [];
  const pool = rng.sample([-4,-2,2,4,-6,6,-8,8], 8);
  for (const off of pool) {
    const np = start + off;
    if (np >= 0 && np <= 24) {
      const pair = ALPHABET[np]+ALPHABET[np+1];
      if (!seen.has(pair)) { seen.add(pair); result.push(pair); if (result.length>=3) break; }
    }
  }
  return result.slice(0,3);
}

// ─── Public API ───────────────────────────────────────────────────────────────

function getSequenceQuestion(difficulty, rng) {
  for (let i=0; i<30; i++) {
    try {
      const q = _generateOne(difficulty, rng);
      if (_valid(q)) return q;
    } catch(e) {}
  }
  // Fallback: easy arithmetic
  const d = rng.choice([2,3,4,5]), start = rng.randint(1,10);
  const terms = Array.from({length:5}, (_,i) => start+d*i);
  const display = terms.map(String); display[display.length-1] = '?';
  return {
    sequence_display: display, answer: String(terms[terms.length-1]),
    rule_description: `Each term increases by ${d}.`,
    category: 'number_sequence', difficulty: 'easy',
    blank_position: 4, sequence_type: 'arithmetic',
  };
}

function attachSequenceOptions(q, rng) {
  const correct = q.answer;
  let distractors;
  if (q.category === 'number_sequence') {
    distractors = _numDistractors(correct, q, rng);
  } else if (MULTI_CHAR.has(q.sequence_type)) {
    distractors = _twoLetterDistractors(correct, rng);
  } else {
    distractors = _letterDistractors(correct, rng);
  }
  const options = [correct].concat(distractors.slice(0,3));
  while (options.length < 4) options.push(correct + '?');
  rng.shuffle(options);
  q.options = options;
  q.correct_index = options.indexOf(correct);
  return q;
}

return { getSequenceQuestion, attachSequenceOptions };

}));
