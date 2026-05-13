"""
sequence_engine.py — Sequence question generation for MindMath Trainer.

Public interface:
  get_sequence_question(difficulty, rng) -> dict
  attach_sequence_options(q, rng) -> q

Question dict keys:
  sequence_display  list[str]  e.g. ['2','4','?','16','32']
  answer            str        correct value for the '?' position
  rule_description  str        user-facing plain-language rule explanation
  category          str        'number_sequence' | 'letter_sequence'
  difficulty        str        as passed in
  blank_position    int        index of '?' in sequence_display
  sequence_type     str        e.g. 'arithmetic', 'geometric', 'fibonacci'
  options           list[str]  added by attach_sequence_options (MC mode)
  correct_index     int        added by attach_sequence_options (MC mode)
"""

import math
import sys

ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
VOWELS = list('AEIOU')
CONSONANTS = [c for c in ALPHABET if c not in 'AEIOU']
QWERTY_ROWS = ['QWERTYUIOP', 'ASDFGHJKL', 'ZXCVBNM']
PRIMES_10 = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
FIBS_8 = [1, 2, 3, 5, 8, 13, 21, 34]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _lpos(ch: str) -> int:
    """Letter → 0-based position (A=0). Case-insensitive."""
    return ALPHABET.index(ch.upper())


def _lch(pos: int) -> str:
    """0-based position → letter, with modular wrap."""
    return ALPHABET[pos % 26]


def _fmt(val, reference=None) -> str:
    """Format a number to a clean string matching the precision of reference."""
    if isinstance(val, float) and val == int(val):
        val = int(val)
    if isinstance(reference, float) and reference == int(reference):
        reference = int(reference)
    if isinstance(val, int):
        return str(val)
    if reference is not None and isinstance(reference, float):
        ref_str = str(reference)
        if '.' in ref_str:
            dp = len(ref_str.rstrip('0').split('.')[1])
            return f"{val:.{dp}f}"
    return str(val)


def _digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))


def _digital_root(n: int) -> int:
    if n == 0:
        return 0
    r = n % 9
    return r if r != 0 else 9


# ─── Number generators — Easy ─────────────────────────────────────────────────

def _num_arith_easy(rng):
    d = rng.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
    start = rng.randint(10, 30) if d < 0 else rng.randint(1, 20)
    terms = [start + d * i for i in range(5)]
    direction = 'increases' if d > 0 else 'decreases'
    rule = f"Each term {direction} by {abs(d)}."
    return terms, 'arithmetic', rule


def _num_double_easy(rng):
    op = rng.choice(['double', 'halve'])
    if op == 'double':
        start = rng.randint(1, 8)
        terms = [start * (2 ** i) for i in range(5)]
        rule_type = 'geometric_x2'
        rule = "Each term is doubled."
    else:
        start = rng.choice([16, 32, 48, 64])
        terms = [start // (2 ** i) for i in range(5)]
        rule_type = 'geometric_div2'
        rule = "Each term is halved."
    return terms, rule_type, rule


def _num_count10_easy(rng):
    start = rng.choice([10, 20, 30, 40, 50, 60, 70])
    terms = [start + 10 * i for i in range(5)]
    rule = "Count up by 10 each step."
    return terms, 'count_by_10', rule


def _num_even_easy(rng):
    start = rng.choice([2, 4, 6, 8, 10, 12])
    terms = [start + 2 * i for i in range(5)]
    rule = "Consecutive even numbers."
    return terms, 'even_numbers', rule


def _num_odd_easy(rng):
    start = rng.choice([1, 3, 5, 7, 9, 11])
    terms = [start + 2 * i for i in range(5)]
    rule = "Consecutive odd numbers."
    return terms, 'odd_numbers', rule


# ─── Number generators — Medium ───────────────────────────────────────────────

def _num_arith_medium(rng):
    d = rng.choice([-20, -15, -10, -8, -6, -5, 5, 6, 7, 8, 10, 15, 20])
    start = rng.randint(50, 150) if d < 0 else rng.randint(5, 50)
    length = rng.choice([5, 6])
    terms = [start + d * i for i in range(length)]
    direction = 'increases' if d > 0 else 'decreases'
    rule = f"Each term {direction} by {abs(d)}."
    return terms, 'arithmetic', rule


def _num_geom_medium(rng):
    op = rng.choice(['x3', 'x4', 'div3'])
    if op == 'x3':
        s = rng.randint(1, 5)
        terms = [s * (3 ** i) for i in range(5)]
        rule = "Each term is multiplied by 3."
    elif op == 'x4':
        s = rng.randint(1, 3)
        terms = [s * (4 ** i) for i in range(5)]
        rule = "Each term is multiplied by 4."
    else:
        s = rng.choice([243, 486, 729])
        terms = [s // (3 ** i) for i in range(5)]
        rule = "Each term is divided by 3."
    return terms, f'geometric_{op}', rule


def _num_squares_medium(rng):
    offset = rng.randint(1, 5)
    terms = [(offset + i) ** 2 for i in range(5)]
    rule = f"Consecutive perfect squares starting from {offset}²."
    return terms, 'squares', rule


def _num_triangular_medium(rng):
    n0 = rng.randint(1, 4)
    terms = [n * (n + 1) // 2 for n in range(n0, n0 + 5)]
    rule = "Triangular numbers: each term is n×(n+1)÷2."
    return terms, 'triangular', rule


def _num_prime_medium(rng):
    start = rng.randint(0, 5)
    terms = PRIMES_10[start:start + 5]
    rule = "Consecutive prime numbers."
    return terms, 'primes', rule


def _num_alt_sign_medium(rng):
    n = rng.randint(1, 3)
    terms = [i * ((-1) ** (i + 1)) * n for i in range(1, 6)]
    rule = f"Terms alternate between positive and negative, increasing in magnitude: {n}, −{2*n}, {3*n}..."
    return terms, 'alternating_sign', rule


def _num_cumsum_medium(rng):
    start = rng.randint(1, 6)
    d0 = rng.randint(1, 3)
    terms = [start]
    d = d0
    for _ in range(4):
        terms.append(terms[-1] + d)
        d += 1
    rule = f"Each term adds one more than the previous increase: +{d0}, +{d0+1}, +{d0+2}..."
    return terms, 'cumulative_sum', rule


def _num_digit_sum_medium(rng):
    # Terms differing by 9 often keep the same digit sum
    target_sum = rng.randint(5, 12)
    if target_sum <= 9:
        start = target_sum
    else:
        start = (target_sum - 9) * 10 + 9
    terms = [start + 9 * i for i in range(5)]
    if not all(_digit_sum(t) == target_sum for t in terms):
        start = target_sum
        terms = [start + 9 * i for i in range(5)]
    rule = f"The digits of each term sum to {target_sum}."
    return terms, 'digit_sum', rule


def _num_pow2_medium(rng):
    n0 = rng.randint(0, 2)
    terms = [2 ** (n0 + i) for i in range(6)]
    rule = "Each term is double the previous (powers of 2)."
    return terms, 'powers_of_2', rule


def _num_pow3_medium(rng):
    n0 = rng.randint(0, 1)
    terms = [3 ** (n0 + i) for i in range(5)]
    rule = "Each term is triple the previous (powers of 3)."
    return terms, 'powers_of_3', rule


def _num_multiples_medium(rng):
    base = rng.choice([3, 4, 6, 7])
    start = rng.randint(1, 3)
    terms = [base * (start + i) for i in range(6)]
    rule = f"Multiples of {base}."
    return terms, 'multiples', rule


def _num_collatz_medium(rng):
    # Find a seed that gives 5-6 clean steps without cycling back to 1 too quickly
    # and without exceeding ~200
    seeds = [6, 10, 12, 14, 18, 20, 24, 26, 28]
    seed = rng.choice(seeds)
    terms = [seed]
    for _ in range(5):
        n = terms[-1]
        if n % 2 == 0:
            terms.append(n // 2)
        else:
            terms.append(3 * n + 1)
        if len(terms) > 6:
            break
    # Ensure we have exactly 6 terms and they're reasonable
    if len(terms) < 6:
        terms = [12, 6, 3, 10, 5, 16]
    terms = terms[:6]
    rule = "If even, halve it. If odd, multiply by 3 and add 1 (Collatz rule)."
    return terms, 'collatz', rule


# ─── Number generators — Normal ───────────────────────────────────────────────

def _num_fibonacci_normal(rng):
    a, b = rng.randint(1, 5), rng.randint(1, 8)
    terms = [a, b]
    for _ in range(4):
        terms.append(terms[-1] + terms[-2])
    rule = f"Each term is the sum of the two preceding terms (starts {a}, {b})."
    return terms, 'fibonacci', rule


def _num_alternating_normal(rng):
    a0 = rng.randint(1, 5)
    b0 = rng.randint(8, 15)
    da = rng.randint(1, 3)
    db = -rng.randint(1, 3)
    terms = []
    for i in range(3):
        terms.append(a0 + da * i)
        terms.append(b0 + db * i)
    rule = (f"Two interleaved sequences: odd positions increase by {da}, "
            f"even positions decrease by {abs(db)}.")
    return terms, 'alternating', rule


def _num_inc_diff_normal(rng):
    start = rng.randint(1, 10)
    d0 = rng.randint(1, 3)
    terms = [start]
    for i in range(5):
        terms.append(terms[-1] + d0 + i)
    rule = f"Differences between consecutive terms increase by 1 each step: {d0}, {d0+1}, {d0+2}..."
    return terms, 'increasing_differences', rule


def _num_arith_neg_normal(rng):
    start = rng.randint(10, 20)
    d = -rng.randint(3, 7)
    terms = [start + d * i for i in range(6)]
    rule = f"Each term decreases by {abs(d)}, crossing zero."
    return terms, 'arithmetic', rule


def _num_geom_alt_sign_normal(rng):
    r = rng.choice([2, 3])
    start = rng.randint(1, 4)
    terms = [start * (r ** i) * ((-1) ** i) for i in range(5)]
    rule = f"Each term is multiplied by −{r}, alternating sign."
    return terms, 'geometric_alt_sign', rule


def _num_square_offset_normal(rng):
    c = rng.randint(0, 3)
    n0 = rng.randint(1, 3)
    terms = [(n0 + i) ** 2 + c for i in range(5)]
    if c > 0:
        rule = f"Each term is n² + {c} for consecutive n starting at {n0}."
    else:
        rule = f"Consecutive perfect squares starting from {n0}²."
    return terms, 'square_offset', rule


def _num_alt_two_step_normal(rng):
    start = rng.randint(1, 5)
    d1 = rng.choice([2, 3, 4])
    d2 = rng.choice([d for d in [2, 3, 4, 5] if d != d1])
    terms = [start]
    for i in range(6):
        if i % 2 == 0:
            terms.append(terms[-1] + d1)
        else:
            terms.append(terms[-1] + d2)
    rule = f"Alternating steps: +{d1} then +{d2}, repeating."
    return terms, 'alternating_step', rule


def _num_cubes_normal(rng):
    n0 = rng.randint(1, 3)
    terms = [(n0 + i) ** 3 for i in range(5)]
    rule = f"Consecutive cube numbers starting from {n0}³."
    return terms, 'cubes', rule


def _num_second_order_normal(rng):
    start = rng.randint(1, 8)
    d0 = rng.randint(1, 3)
    k = rng.randint(1, 2)
    terms = [start]
    d = d0
    for _ in range(6):
        terms.append(terms[-1] + d)
        d += k
    rule = f"Differences between terms increase by {k} each step: {d0}, {d0+k}, {d0+2*k}..."
    return terms, 'second_order_arithmetic', rule


def _num_lucas_normal(rng):
    # Lucas numbers: 2, 1, 3, 4, 7, 11, 18...
    terms = [2, 1, 3, 4, 7, 11, 18]
    # Optionally start a few steps in
    start = rng.randint(0, 2)
    terms = terms[start:start + 6]
    rule = "Each term is the sum of the two preceding terms (Lucas sequence, starting 2, 1)."
    return terms, 'lucas', rule


def _num_catalan_normal(rng):
    # Catalan numbers: 1, 1, 2, 5, 14, 42
    terms = [1, 1, 2, 5, 14, 42]
    rule = "Catalan numbers: 1, 1, 2, 5, 14, 42..."
    return terms, 'catalan', rule


# ─── Number generators — Hard ─────────────────────────────────────────────────

def _num_alt_op_hard(rng):
    mult = rng.choice([2, 3])
    add = rng.randint(2, 6)
    start = rng.randint(1, 5)
    terms = [start]
    for i in range(6):
        if i % 2 == 0:
            terms.append(terms[-1] * mult)
        else:
            terms.append(terms[-1] + add)
    rule = f"Alternating operations: ×{mult} then +{add}, repeating."
    return terms, 'alternating_op', rule


def _num_power_offset_hard(rng):
    c = rng.randint(1, 4)
    n0 = rng.randint(0, 2)
    terms = [2 ** n + c for n in range(n0, n0 + 6)]
    rule = f"Each term is a power of 2 plus {c}: 2¹+{c}, 2²+{c}, 2³+{c}..."
    return terms, 'power_offset', rule


def _num_factorial_hard(rng):
    n0 = rng.randint(1, 2)
    terms = [math.factorial(n0 + i) for i in range(5)]
    rule = f"Each term is a factorial: {n0}!, {n0+1}!, {n0+2}!..."
    return terms, 'factorial', rule


def _num_recursive_hard(rng):
    start = rng.randint(1, 4)
    c = rng.randint(1, 3)
    terms = [start]
    for _ in range(5):
        terms.append(terms[-1] * 2 + c)
    rule = f"Each term equals the previous term doubled, plus {c}."
    return terms, 'recursive_double', rule


def _num_interleaved_geom_hard(rng):
    # Powers of 3 at even indices, powers of 2 at odd indices
    # 1, 2, 3, 4, 9, 8, 27, 16
    n0 = rng.randint(0, 1)
    terms = []
    for i in range(4):
        terms.append(3 ** (n0 + i))
        terms.append(2 ** (n0 + i + 1))
    rule = "Two geometric sequences interleaved: powers of 3 and powers of 2."
    return terms, 'interleaved_geometric', rule


def _num_digital_root_hard(rng):
    dr = rng.randint(1, 9)
    if dr <= 9:
        start = dr
    else:
        start = (dr - 9) * 10 + 9
    terms = [start + 9 * i for i in range(5)]
    if not all(_digital_root(t) == dr for t in terms):
        terms = [dr + 9 * i for i in range(5)]
    rule = f"Each term has a digital root of {dr} (repeated digit-sum reduces to {dr})."
    return terms, 'digital_root', rule


def _num_recaman_hard(rng):
    # Recaman sequence: 0, 1, 3, 6, 2, 7, 13, 20, 12, 21...
    seq = [0]
    seen = {0}
    for n in range(1, 11):
        candidate = seq[-1] - n
        if candidate > 0 and candidate not in seen:
            seq.append(candidate)
        else:
            seq.append(seq[-1] + n)
        seen.add(seq[-1])
    # Use 7 terms, blank at position 6, 7, or 8
    length = rng.choice([8, 9])
    terms = seq[:length]
    rule = "Recaman: subtract n if result is positive and not yet in sequence, else add n."
    return terms, 'recaman', rule


def _num_sylvester_hard(rng):
    # Sylvester: each term = product of all previous + 1
    # 2, 3, 7, 43, 1807...
    terms = [2, 3, 7, 43, 1807]
    rule = "Each term equals the product of all previous terms, plus 1."
    return terms, 'sylvester', rule


def _num_look_say_hard(rng):
    # Look-and-say: 1, 11, 21, 1211, 111221, 312211
    terms = [1, 11, 21, 1211, 111221, 312211]
    rule = "Describe the previous term digit by digit: count consecutive identical digits."
    return terms, 'look_and_say', rule


def _num_padovan_hard(rng):
    # Padovan: P(n) = P(n-2) + P(n-3), starts 1,1,1,2,2,3,4,5,7,9,12,16...
    start = rng.randint(0, 3)
    full = [1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12, 16]
    terms = full[start:start + 8]
    if len(terms) < 7:
        terms = [1, 1, 1, 2, 2, 3, 4, 5, 7]
    terms = terms[:8]
    rule = "Each term equals the term two steps back plus the term three steps back (Padovan)."
    return terms, 'padovan', rule


def _num_tribonacci_hard(rng):
    a, b, c = rng.randint(1, 3), rng.randint(1, 3), rng.randint(1, 4)
    terms = [a, b, c]
    for _ in range(5):
        terms.append(terms[-1] + terms[-2] + terms[-3])
    rule = f"Each term is the sum of the three preceding terms (Tribonacci, starts {a}, {b}, {c})."
    return terms, 'tribonacci', rule


def _num_generalized_recurrence_hard(rng):
    a = rng.choice([1, 2, 3])
    b = rng.choice([1, 2])
    c = rng.choice([0, 1, 2])
    # Ensure not plain Fibonacci (a=1, b=1, c=0)
    if a == 1 and b == 1 and c == 0:
        a = 2
    t1 = rng.randint(1, 3)
    t2 = rng.randint(2, 5)
    terms = [t1, t2]
    for _ in range(5):
        terms.append(a * terms[-1] + b * terms[-2] + c)
    b_part = f" + {b}× the term before that" if b > 1 else " + the term before that"
    c_part = f" + {c}" if c else ""
    rule = f"Each term = {a}× previous{b_part}{c_part}."
    return terms, 'generalized_recurrence', rule


def _num_interleaved_two_rules_hard(rng):
    a_start = rng.randint(2, 8)
    a_step = rng.randint(2, 5)
    g_start = rng.randint(1, 3)
    g_ratio = rng.choice([2, 3])
    terms = []
    for i in range(4):
        terms.append(a_start + a_step * i)
        terms.append(g_start * (g_ratio ** i))
    rule = (f"Two interleaved sequences: odd positions form an arithmetic sequence (+{a_step}), "
            f"even positions form a geometric sequence (×{g_ratio}).")
    return terms, 'interleaved_two_rules', rule


def _num_second_diff_geometric_hard(rng):
    r = rng.choice([2, 3])
    d0 = rng.randint(1, 2)
    start = rng.randint(1, 5)
    terms = [start]
    d = d0
    for _ in range(6):
        terms.append(terms[-1] + d)
        d *= r
    rule = (f"Differences between consecutive terms multiply by {r} each step: "
            f"{d0}, {d0*r}, {d0*r**2}...")
    return terms, 'second_diff_geometric', rule


def _num_weighted_fibonacci_hard(rng):
    a = rng.choice([2, 3])
    b = rng.choice([1, 2])
    t1 = rng.randint(1, 3)
    t2 = rng.randint(2, 5)
    terms = [t1, t2]
    for _ in range(5):
        terms.append(a * terms[-1] + b * terms[-2])
    rule = f"Each term = {a}× previous term + {b}× the term before that."
    return terms, 'weighted_fibonacci', rule


def _num_alternating_recurrence_hard(rng):
    d1 = rng.randint(3, 8)
    r = rng.choice([2, 3])
    t0 = rng.randint(1, 5)
    t1 = rng.randint(1, 3)
    terms = [t0, t1]
    for i in range(2, 8):
        if i % 2 == 0:
            terms.append(terms[-2] + d1)
        else:
            terms.append(terms[-2] * r)
    rule = (f"Two interleaved sequences: positions 1,3,5… each add {d1} to the previous odd-position term; "
            f"positions 2,4,6… each multiply the previous even-position term by {r}.")
    return terms, 'alternating_recurrence', rule


# ─── Letter generators — Easy ─────────────────────────────────────────────────

def _let_step1_easy(rng):
    s = rng.randint(0, 20)
    rule = "Each letter advances 1 position in the alphabet."
    return [_lch(s + i) for i in range(5)], 'alphabet_step', rule


def _let_step2_easy(rng):
    s = rng.randint(0, 15)
    rule = "Each letter advances 2 positions in the alphabet."
    return [_lch(s + i * 2) for i in range(5)], 'alphabet_step', rule


def _let_rev1_easy(rng):
    s = rng.randint(5, 25)
    rule = "Each letter goes back 1 position in the alphabet."
    return [_lch(s - i) for i in range(5)], 'alphabet_step', rule


def _let_vowel_easy(rng):
    rule = "The sequence is the five vowels in alphabetical order: A, E, I, O, U."
    return list('AEIOU'), 'vowels', rule


def _let_rev_skip_easy(rng):
    # Z, X, V, T, R — every other letter from Z backwards
    s = rng.randint(20, 25)
    terms = [_lch(s - i * 2) for i in range(5)]
    rule = "Every other letter going backwards through the alphabet."
    return terms, 'alphabet_step', rule


# ─── Letter generators — Medium ───────────────────────────────────────────────

def _let_alt_step_medium(rng):
    s = rng.randint(0, 12)
    terms = [_lch(s)]
    pos = s
    steps = [2, 3]
    for i in range(5):
        pos += steps[i % 2]
        terms.append(_lch(pos))
    rule = "Letters alternate between +2 and +3 steps through the alphabet."
    return terms, 'alternating', rule


def _let_rev2_medium(rng):
    s = rng.randint(10, 25)
    rule = "Each letter goes back 2 positions in the alphabet."
    return [_lch(s - i * 2) for i in range(6)], 'alphabet_step', rule


def _let_skip_wrap_medium(rng):
    # Two interleaved sequences: one descending, one ascending
    a = rng.randint(18, 24)
    b = rng.randint(1, 5)
    terms = []
    for i in range(3):
        terms.append(_lch(a - i * 2))
        terms.append(_lch(b + i * 2))
    rule = ("Two interleaved sequences: odd positions descend by 2, "
            "even positions ascend by 2.")
    return terms, 'alternating', rule


def _let_alt_ends_medium(rng):
    # A, Z, B, Y, C, X, ? → D  (alternating from start and end of alphabet)
    n = rng.randint(0, 4)
    terms = []
    for i in range(3):
        terms.append(_lch(n + i))
        terms.append(_lch(25 - n - i))
    rule = "Alternating letters from the beginning and end of the alphabet."
    return terms, 'alternating_ends', rule


def _let_consonant_medium(rng):
    start = rng.randint(0, len(CONSONANTS) - 6)
    terms = list(CONSONANTS[start:start + 5])
    rule = "Consecutive consonants in alphabetical order (vowels skipped)."
    return terms, 'consonants', rule


def _let_prime_pos_medium(rng):
    start = rng.randint(0, 4)
    chosen = PRIMES_10[start:start + 5]
    terms = [_lch(p - 1) for p in chosen]
    rule = "Letters at prime positions in the alphabet: B(2), C(3), E(5), G(7), K(11)..."
    return terms, 'prime_positions', rule


# ─── Letter generators — Normal ───────────────────────────────────────────────

def _let_positional_normal(rng):
    # Gaps: 2, 3, 4, 5, 6
    s = rng.randint(0, 3)
    terms = [_lch(s)]
    pos = s
    for i in range(5):
        pos += (i + 2)
        terms.append(_lch(pos))
    rule = "Gaps between letters increase by 1 each step: 2, 3, 4, 5, 6..."
    return terms, 'positional', rule


def _let_two_letter_normal(rng):
    s = rng.randint(0, 16)
    pairs = []
    for i in range(5):
        p = s + i * 2
        pairs.append(_lch(p) + _lch(p + 1))
    rule = "Consecutive alphabet letter pairs: AB, CD, EF..."
    return pairs, 'two_letter', rule


def _let_keyboard_row_normal(rng):
    row = rng.choice(QWERTY_ROWS)
    max_start = len(row) - 5
    if max_start < 0:
        max_start = 0
    start = rng.randint(0, max_start)
    terms = list(row[start:start + 5])
    row_names = {QWERTY_ROWS[0]: 'top', QWERTY_ROWS[1]: 'middle', QWERTY_ROWS[2]: 'bottom'}
    row_name = row_names.get(row, 'QWERTY')
    rule = f"Consecutive letters from the {row_name} row of a QWERTY keyboard."
    return terms, 'keyboard_row', rule


def _let_diagonal_grid_normal(rng):
    # 5×5 grid (A-Y), main diagonal: A(0), G(6), M(12), S(18), Y(24)
    # Other diagonals shift start by 1-4
    diag = rng.randint(0, 4)
    terms = [_lch(diag + i * 6) for i in range(5) if diag + i * 6 < 26]
    if len(terms) < 5:
        terms = [_lch(i * 6) for i in range(5)]  # fallback: main diagonal
    rule = "Letters read along a diagonal of a 5×5 alphabet grid, stepping 6 each time."
    return terms, 'diagonal_grid', rule


def _let_two_seq_merge_normal(rng):
    # Forward pairs (AB, CD, EF) interleaved with reverse singles (Z, Y, X)
    n = rng.randint(0, 3)
    terms = []
    for i in range(3):
        terms.append(_lch(n + i * 2))
        terms.append(_lch(n + i * 2 + 1))
        terms.append(_lch(25 - n - i))
    rule = "Alternating: two forward letters (AB, CD...) then one reverse letter (Z, Y, X...)."
    return terms, 'two_seq_merge', rule


# ─── Letter generators — Hard ─────────────────────────────────────────────────

def _let_wrap_hard(rng):
    s = rng.randint(0, 25)
    step = rng.choice([3, 4, 5])
    rule = f"Each letter advances {step} positions, wrapping from Z back to A."
    return [_lch(s + i * step) for i in range(6)], 'alphabet_wrap', rule


def _let_complex_hard(rng):
    s = rng.randint(0, 4)
    gaps = [rng.randint(1, 2), rng.randint(2, 3), rng.randint(3, 4),
            rng.randint(4, 5), rng.randint(5, 6)]
    terms = [_lch(s)]
    pos = s
    for g in gaps:
        pos += g
        terms.append(_lch(pos))
    rule = "Gaps between letters increase irregularly."
    return terms, 'complex_positional', rule


def _let_caesar_hard(rng):
    # Cumulative shifts: +1, +2, +3, +4...  positions
    start = rng.randint(0, 10)
    terms = [_lch(start)]
    pos = start
    for i in range(1, 5):
        pos = (pos + i) % 26
        terms.append(_lch(pos))
    rule = "Each letter is shifted by an increasing amount: +1, +2, +3, +4... (Caesar cipher)."
    return terms, 'caesar_shift', rule


def _let_fibonacci_pos_hard(rng):
    start = rng.randint(0, 3)
    chosen = FIBS_8[start:start + 5]
    terms = [_lch(f - 1) for f in chosen]
    rule = "Letters at Fibonacci number positions in the alphabet: A(1), B(2), C(3), E(5), H(8)..."
    return terms, 'fibonacci_positions', rule


def _let_modular_hard(rng):
    # Each position = (prev × 2 + 1) mod 26
    start = rng.randint(0, 5)
    pos = start
    positions = [pos]
    for _ in range(4):
        pos = (pos * 2 + 1) % 26
        positions.append(pos)
    terms = [_lch(p) for p in positions]
    rule = "Each position is doubled and incremented (×2+1), wrapping mod 26."
    return terms, 'modular_arithmetic', rule


def _let_interleaved_hard(rng):
    step1 = rng.choice([2, 3, 4])
    step2 = rng.choice([d for d in [2, 3, 4, 5] if d != step1])
    start1 = rng.randint(0, 10)
    start2 = rng.randint(0, 10)
    terms = []
    for i in range(3):
        terms.append(_lch(start1 + step1 * i))
        terms.append(_lch(start2 + step2 * i))
    rule = (f"Two interleaved letter sequences: odd positions advance by {step1}, "
            f"even positions advance by {step2}.")
    return terms, 'interleaved_letters', rule


# ─── Generator registries ──────────────────────────────────────────────────────

_NUM_GEN = {
    'easy':   [_num_arith_easy, _num_double_easy,
               _num_count10_easy, _num_even_easy, _num_odd_easy],
    'medium': [_num_arith_medium, _num_geom_medium, _num_squares_medium,
               _num_triangular_medium, _num_prime_medium, _num_alt_sign_medium,
               _num_pow2_medium, _num_pow3_medium, _num_multiples_medium,
               _num_collatz_medium, _num_digit_sum_medium],
    'normal': [_num_fibonacci_normal, _num_alternating_normal, _num_inc_diff_normal,
               _num_arith_neg_normal, _num_geom_alt_sign_normal, _num_square_offset_normal,
               _num_alt_two_step_normal, _num_cubes_normal,
               _num_second_order_normal, _num_lucas_normal, _num_catalan_normal,
               _num_cumsum_medium,  # moved from medium: second-order pattern
               _num_factorial_hard, _num_digital_root_hard],  # moved from hard: not genuinely hard
    'hard':   [_num_alt_op_hard, _num_power_offset_hard,
               _num_recursive_hard, _num_interleaved_geom_hard,
               _num_recaman_hard, _num_sylvester_hard, _num_look_say_hard,
               _num_padovan_hard,
               _num_tribonacci_hard, _num_generalized_recurrence_hard,
               _num_interleaved_two_rules_hard, _num_second_diff_geometric_hard,
               _num_weighted_fibonacci_hard, _num_alternating_recurrence_hard],
}

_LET_GEN = {
    'easy':   [_let_step1_easy, _let_step2_easy, _let_rev1_easy,
               _let_vowel_easy, _let_rev_skip_easy],
    'medium': [_let_alt_step_medium, _let_rev2_medium, _let_skip_wrap_medium,
               _let_alt_ends_medium, _let_consonant_medium, _let_prime_pos_medium],
    'normal': [_let_positional_normal, _let_two_letter_normal,
               _let_keyboard_row_normal, _let_diagonal_grid_normal,
               _let_two_seq_merge_normal],
    'hard':   [_let_wrap_hard, _let_complex_hard, _let_caesar_hard,
               _let_fibonacci_pos_hard, _let_modular_hard, _let_interleaved_hard],
}


# ─── Blank position ────────────────────────────────────────────────────────────

def _blank_pos(length: int, difficulty: str, rng) -> int:
    if difficulty == 'easy':
        return length - 1
    elif difficulty == 'medium':
        return rng.choice([length - 1, length - 2])
    elif difficulty == 'normal':
        return rng.randint(1, length - 1)
    else:  # hard
        return rng.randint(0, length - 1)


# ─── Validation ────────────────────────────────────────────────────────────────

def _valid(q: dict) -> bool:
    if not q.get('answer'):
        return False
    disp = q.get('sequence_display', [])
    if len(disp) < 5:
        return False
    bp = q.get('blank_position', -1)
    if bp < 0 or bp >= len(disp):
        return False
    if disp[bp] != '?':
        return False
    for i, t in enumerate(disp):
        if i != bp and (t is None or t == ''):
            return False
    # Letter sequences: single letter (except two_letter and two_seq_merge pairs)
    multi_char_types = {'two_letter', 'two_seq_merge'}
    if (q.get('category') == 'letter_sequence'
            and q.get('sequence_type') not in multi_char_types):
        if len(q['answer']) != 1:
            return False
    return True


# ─── Core generator ────────────────────────────────────────────────────────────

def _generate_one(difficulty: str, rng) -> dict:
    category = rng.choice(['number', 'letter'])
    if category == 'number':
        gen = rng.choice(_NUM_GEN.get(difficulty, _NUM_GEN['easy']))
        terms, seq_type, rule = gen(rng)
        terms_str = [_fmt(t) for t in terms]
        cat_key = 'number_sequence'
    else:
        gen = rng.choice(_LET_GEN.get(difficulty, _LET_GEN['easy']))
        terms, seq_type, rule = gen(rng)
        terms_str = [str(t) for t in terms]
        cat_key = 'letter_sequence'

    bp = _blank_pos(len(terms_str), difficulty, rng)
    answer = terms_str[bp]
    display = terms_str[:]
    display[bp] = '?'

    return {
        'sequence_display': display,
        'answer': answer,
        'rule_description': rule,
        'category': cat_key,
        'difficulty': difficulty,
        'blank_position': bp,
        'sequence_type': seq_type,
    }


# ─── Public: get question ──────────────────────────────────────────────────────

def get_sequence_question(difficulty: str, rng) -> dict:
    """Generate a validated sequence question. Falls back to Easy arithmetic."""
    for _ in range(30):
        try:
            q = _generate_one(difficulty, rng)
            if _valid(q):
                return q
        except Exception:
            pass

    print(
        f"WARNING: sequence generation failed 30 attempts at {difficulty}, "
        "falling back to easy arithmetic",
        file=sys.stderr,
    )
    # Guaranteed fallback
    d = rng.choice([2, 3, 4, 5])
    start = rng.randint(1, 10)
    terms = [start + d * i for i in range(5)]
    display = [str(t) for t in terms]
    display[-1] = '?'
    return {
        'sequence_display': display,
        'answer': str(terms[-1]),
        'rule_description': f'Each term increases by {d}.',
        'category': 'number_sequence',
        'difficulty': 'easy',
        'blank_position': 4,
        'sequence_type': 'arithmetic',
    }


# ─── Public: attach MC options ─────────────────────────────────────────────────

def attach_sequence_options(q: dict, rng) -> dict:
    """Add 'options' (list of 4 str) and 'correct_index' to the question dict."""
    correct = q['answer']
    cat = q['category']
    seq_type = q.get('sequence_type', '')

    multi_char_types = {'two_letter', 'two_seq_merge'}
    if cat == 'number_sequence':
        distractors = _num_distractors(correct, q, rng)
    elif seq_type in multi_char_types:
        distractors = _two_letter_distractors(correct, rng)
    else:
        distractors = _letter_distractors(correct, rng)

    options = [correct] + distractors[:3]
    while len(options) < 4:
        options.append(correct + '?')  # last-resort padding (should never happen)
    rng.shuffle(options)
    q['options'] = options
    q['correct_index'] = options.index(correct)
    return q


# ─── Distractor generators ─────────────────────────────────────────────────────

def _is_integer_sequence(q: dict) -> bool:
    """Return True if ALL non-blank terms in the sequence are integers (no decimal point)."""
    disp = q.get('sequence_display', [])
    bp = q.get('blank_position', -1)
    for i, t in enumerate(disp):
        if i == bp:
            continue
        s = str(t).strip()
        if '.' in s:
            return False
        try:
            int(s)
        except ValueError:
            return False
    return True


def _num_distractors(correct_str: str, q: dict, rng) -> list:
    try:
        cv = float(correct_str)
    except ValueError:
        return [correct_str + '1', correct_str + '2', correct_str + '3']

    force_int = _is_integer_sequence(q)
    seen = {cv}
    result = []

    def _add_candidate(c: float) -> bool:
        """Format c, deduplicate, and append to result. Returns True if appended."""
        if force_int:
            c = round(c)
            c_key = float(c)
        else:
            c_key = c
        if abs(c_key - cv) > 0.001 and c_key not in seen:
            seen.add(c_key)
            result.append(_fmt_num(float(c), cv if not force_int else float(int(cv))))
            return True
        return False

    # Estimate typical step from visible terms
    disp = q.get('sequence_display', [])
    bp = q.get('blank_position', -1)
    visible = []
    for i, t in enumerate(disp):
        if i != bp:
            try:
                visible.append(float(t))
            except ValueError:
                pass

    if len(visible) >= 2:
        diffs = [abs(visible[j + 1] - visible[j]) for j in range(len(visible) - 1)]
        avg_d = sum(diffs) / len(diffs) if diffs else 1
        candidates = [
            cv + avg_d, cv - avg_d,
            cv + avg_d * 2, cv - avg_d * 2,
            cv + 1, cv - 1,
        ]
        for c in candidates:
            if _add_candidate(c) and len(result) >= 3:
                return result

    # Fill with nearby offsets
    for off in rng.sample([-3, -2, -1, 1, 2, 3, -5, 5, -4, 4], 10):
        c = cv + off
        if _add_candidate(c) and len(result) >= 3:
            return result

    return result[:3]


def _fmt_num(val: float, ref: float) -> str:
    if val == int(val) and (ref == int(ref) or ref == round(ref)):
        return str(int(val))
    ref_str = str(ref)
    if '.' in ref_str:
        dp = len(ref_str.split('.')[1].rstrip('0')) or 1
        return f"{val:.{dp}f}"
    return str(int(val)) if val == int(val) else str(val)


def _letter_distractors(correct: str, rng) -> list:
    pos = ALPHABET.find(correct.upper())
    if pos == -1:
        return ['X', 'Y', 'Z']
    seen = {pos}
    result = []
    offsets = list(range(-5, 6))
    offsets.remove(0)
    rng.shuffle(offsets)
    for off in offsets:
        np_ = (pos + off) % 26
        if np_ not in seen:
            seen.add(np_)
            result.append(ALPHABET[np_])
            if len(result) >= 3:
                break
    return result[:3]


def _two_letter_distractors(correct: str, rng) -> list:
    if len(correct) < 2:
        return _letter_distractors(correct, rng)
    start = ALPHABET.find(correct[0].upper())
    if start == -1:
        return ['XY', 'YZ', 'WX']
    seen = {correct.upper()}
    result = []
    for off in rng.sample([-4, -2, 2, 4, -6, 6, -8, 8], 8):
        np_ = start + off
        if 0 <= np_ <= 24:
            pair = ALPHABET[np_] + ALPHABET[np_ + 1]
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
                if len(result) >= 3:
                    break
    return result[:3]
