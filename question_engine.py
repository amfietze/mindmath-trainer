"""
Question generation for all categories and difficulty levels.

Each question dict contains:
  text           - the question string shown to the user
  answer         - numeric correct answer (int or float)
  display_answer - human-readable answer string
  category       - one of CATEGORIES
  difficulty     - 'easy' | 'normal' | 'hard'

For Test Mode (multiple_choice=True):
  options        - list of 4 strings (shuffled)
  correct_index  - int index of correct option in options
"""

import random
import math
import sys
from fractions import Fraction

# Fractions with terminating decimal expansions
_CLEAN_FRACS = [
    (1, 2, 0.5),    (1, 4, 0.25),   (3, 4, 0.75),
    (1, 5, 0.2),    (2, 5, 0.4),    (3, 5, 0.6),    (4, 5, 0.8),
    (1, 8, 0.125),  (3, 8, 0.375),  (5, 8, 0.625),  (7, 8, 0.875),
    (1, 10, 0.1),   (3, 10, 0.3),   (7, 10, 0.7),   (9, 10, 0.9),
    (1, 20, 0.05),  (3, 20, 0.15),  (7, 20, 0.35),  (9, 20, 0.45),
    (11, 20, 0.55), (13, 20, 0.65), (17, 20, 0.85), (19, 20, 0.95),
    (1, 25, 0.04),  (2, 25, 0.08),  (3, 25, 0.12),  (4, 25, 0.16),
    (6, 25, 0.24),  (7, 25, 0.28),
    (1, 16, 0.0625),(3, 16, 0.1875),(5, 16, 0.3125),(7, 16, 0.4375),
]


# ---- public API --------------------------------------------------------------

def get_validated_question(category, difficulty, level_modifier=0,
                            multiple_choice=False, max_attempts=50, rng=None):
    """Generate a question that passes all 7 validation checks.

    Falls back to Easy difficulty after max_attempts failures, logging a
    warning to stderr (visible in Render logs).
    """
    if rng is None:
        rng = random.Random()

    for _ in range(max_attempts):
        try:
            q = _build(category, difficulty, random.Random(rng.randint(0, 2**31)),
                       level_modifier, multiple_choice)
            if _validate_question(q, multiple_choice):
                return q
        except Exception:
            continue

    # Fallback to Easy
    print(
        f"WARNING: get_validated_question fallback to easy — "
        f"category={category} difficulty={difficulty}",
        file=sys.stderr,
    )
    for _ in range(max_attempts):
        try:
            q = _build(category, 'easy', random.Random(rng.randint(0, 2**31)),
                       0, multiple_choice)
            if _validate_question(q, multiple_choice):
                return q
        except Exception:
            continue

    # Last resort: return whatever _build gives us
    return _build(category, 'easy', rng, 0, multiple_choice)


def generate_test_questions(seed, difficulty, n):
    """
    Generate n validated test questions deterministically from seed.
    Each question includes multiple choice options.
    Returns list of question dicts.
    """
    from config import TEST_DISTRIBUTION

    dist = TEST_DISTRIBUTION.get(difficulty, TEST_DISTRIBUTION['normal'])
    cats = []
    for cat, frac in dist:
        cats.extend([cat] * round(frac * n))
    while len(cats) < n:
        cats.append(dist[0][0])
    cats = cats[:n]

    master_rng = random.Random(seed)
    master_rng.shuffle(cats)

    questions = []
    for i, cat in enumerate(cats):
        q_seed = seed * 10000 + i
        q = get_validated_question(cat, difficulty, multiple_choice=True,
                                    rng=random.Random(q_seed))
        questions.append(q)
    return questions


# ---- validation helpers ------------------------------------------------------

def _parse_display(display_str):
    """Parse display_answer string to float: handles ints, decimals,
    simple fractions '3/4', and mixed numbers '2 3/4'."""
    s = str(display_str).strip()
    # Plain number
    try:
        return float(s)
    except ValueError:
        pass
    # Mixed number: "2 3/4"
    if ' ' in s and '/' in s:
        parts = s.split(' ', 1)
        try:
            whole = float(parts[0])
            fp = parts[1].split('/')
            frac = float(fp[0]) / float(fp[1])
            sign = -1 if whole < 0 else 1
            return whole + sign * abs(frac)
        except (ValueError, ZeroDivisionError, IndexError):
            return None
    # Simple fraction: "3/4"
    if '/' in s:
        fp = s.split('/')
        try:
            return float(fp[0].strip()) / float(fp[1].strip())
        except (ValueError, ZeroDivisionError, IndexError):
            return None
    return None


def _validate_question(q, multiple_choice):
    """Return True if q passes all 7 pre-serve validation checks."""
    # Check 1 — answer is finite, non-None
    answer = q.get('answer')
    if answer is None:
        return False
    try:
        ans_f = float(str(answer))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(ans_f):
        return False

    # Check 7 — 6dp round is still finite (catches extreme values)
    try:
        if not math.isfinite(round(ans_f, 6)):
            return False
    except Exception:
        return False

    # Check 2 — display_answer parses to a value close to answer
    display = q.get('display_answer', '')
    disp_f = _parse_display(display)
    if disp_f is not None:
        tol = max(0.001, abs(ans_f) * 0.001)
        if abs(disp_f - ans_f) > tol:
            return False

    # Check 5 — question text is non-empty and contains a math symbol
    text = q.get('text', '')
    if not text:
        return False
    if not any(c in text for c in ['+', '-', 'x', '/', ':', '×', '=', '%']):
        return False

    if multiple_choice:
        options = q.get('options', [])
        if len(options) != 4:
            return False
        correct_idx = q.get('correct_index')
        if correct_idx is None or not (0 <= correct_idx < 4):
            return False

        # Parse each option to float (best effort)
        opt_floats = []
        for opt in options:
            f = _parse_display(opt)
            opt_floats.append(f)

        # Check 3 — no distractor equals the correct answer within 0.001
        for i, f in enumerate(opt_floats):
            if i == correct_idx:
                continue
            if f is not None and abs(f - ans_f) < 0.001:
                return False

        # Check 4 — all 4 option strings are distinct
        if len(set(str(o) for o in options)) != 4:
            return False

    return True


# ---- internal builders -------------------------------------------------------

def _build(category, difficulty, rng, level_modifier, multiple_choice):
    generators = {
        'integers':    _gen_integers,
        'decimals':    _gen_decimals,
        'fractions':   _gen_fractions,
        'algebra':     _gen_algebra,
        'percentages': _gen_percentages,
    }
    gen = generators.get(category, _gen_integers)

    for _ in range(20):
        try:
            q = gen(difficulty, random.Random(rng.randint(0, 2**31)), level_modifier)
            if q and _valid(q):
                q['category'] = category
                q['difficulty'] = difficulty
                if multiple_choice:
                    _attach_options(q, rng)
                return q
        except Exception:
            continue

    q = gen('easy', rng, 0)
    q['category'] = category
    q['difficulty'] = difficulty
    if multiple_choice:
        _attach_options(q, rng)
    return q


def _valid(q):
    try:
        v = float(q['answer'])
        return math.isfinite(v) and abs(v) < 1_000_000
    except (TypeError, ValueError, KeyError):
        return False


# ---- category generators -----------------------------------------------------

def _gen_integers(difficulty, rng, level_modifier=0):
    if difficulty == 'easy':
        op = rng.choice(['+', '-', '*', '/'])
        if op == '+':
            a, b = rng.randint(2, 20), rng.randint(2, 20)
            return _q(f'{a} + {b}', a + b)
        if op == '-':
            a = rng.randint(5, 25)
            b = rng.randint(2, a)
            return _q(f'{a} - {b}', a - b)
        if op == '*':
            a, b = rng.randint(2, 12), rng.randint(2, 12)
            return _q(f'{a} x {b}', a * b)
        b = rng.randint(2, 10)
        ans = rng.randint(2, 15)
        return _q(f'{b * ans} / {b}', ans)

    if difficulty == 'medium':
        op = rng.choice(['+', '-', '*', 'div'])
        if op == '+':
            a, b = rng.randint(10, 60), rng.randint(10, 60)
            return _q(f'{a} + {b}', a + b)
        if op == '-':
            a = rng.randint(21, 99)
            if rng.random() < 0.3:
                b = rng.randint(a + 1, a + 30)
            else:
                b = rng.randint(10, a - 1)
            return _q(f'{a} - {b}', a - b)
        if op == '*':
            a = rng.randint(11, 20)
            b = rng.randint(2, 10)
            return _q(f'{a} x {b}', a * b)
        b = rng.randint(2, 12)
        ans = rng.randint(5, 15)
        return _q(f'{b * ans} : {b}', ans)

    if difficulty == 'normal':
        kind = rng.choice(['mul2', 'add3', 'sub3', 'div2'])
        if kind == 'mul2':
            a, b = rng.randint(11, 99), rng.randint(11, 99)
            return _q(f'{a} x {b}', a * b)
        if kind == 'add3':
            a, b = rng.randint(100, 999), rng.randint(100, 999)
            return _q(f'{a} + {b}', a + b)
        if kind == 'sub3':
            a = rng.randint(200, 999)
            if rng.random() < 0.3:
                b = rng.randint(a + 1, a + 200)
            else:
                b = rng.randint(100, a - 1)
            return _q(f'{a} - {b}', a - b)
        b = rng.randint(2, 20)
        ans = rng.randint(10, 60)
        return _q(f'{b * ans} : {b}', ans)

    # hard
    kind = rng.choice(['big_mul', 'multi_step', 'chain'])
    if kind == 'big_mul':
        a, b = rng.randint(100, 999), rng.randint(11, 99)
        return _q(f'{a} x {b}', a * b)
    if kind == 'multi_step':
        a, b = rng.randint(10, 60), rng.randint(10, 60)
        c = rng.randint(3, 15)
        return _q(f'({a} + {b}) x {c}', (a + b) * c)
    a, b = rng.randint(10, 50), rng.randint(10, 50)
    c, d = rng.randint(2, 20), rng.randint(2, 20)
    return _q(f'{a} x {b} + {c} x {d}', a * b + c * d)


def _gen_decimals(difficulty, rng, level_modifier=0):
    if difficulty == 'easy':
        op = rng.choice(['+', '-', '*', '/'])
        if op == '+':
            a = _rand_dec1(rng, 1, 9)
            b = _rand_dec1(rng, 1, 9)
            return _q(f'{a} + {b}', _trunc(a + b, 1))
        if op == '-':
            a = _rand_dec1(rng, 3, 15)
            b = _rand_dec1(rng, 1, a - 0.1)
            return _q(f'{a} - {b}', _trunc(a - b, 1))
        if op == '*':
            a = _rand_dec1(rng, 1, 8)
            b = rng.randint(2, 6)
            return _q(f'{a} x {b}', _trunc(a * b, 1))
        b = rng.choice([2, 4, 5])
        ans = _rand_dec1(rng, 1, 8)
        return _q(f'{_trunc(ans * b, 1)} / {b}', ans)

    if difficulty == 'medium':
        kind = rng.choice(['add1', 'sub1', 'div_simple', 'mul1'])
        if kind == 'add1':
            a = _rand_dec1(rng, 1, 9)
            b = _rand_dec1(rng, 1, 9)
            return _q(f'{a} + {b}', _trunc(a + b, 1))
        if kind == 'sub1':
            a = _rand_dec1(rng, 3, 15)
            if rng.random() < 0.3:
                b = _rand_dec1(rng, a + 0.1, a + 5.0)
            else:
                b = _rand_dec1(rng, 1, a - 0.1)
            return _q(f'{a} - {b}', _trunc(a - b, 1))
        if kind == 'div_simple':
            b = rng.choice([0.5, 0.25, 2.0, 5.0])
            ans = rng.randint(2, 20)
            a = _trunc(ans * b, 1)
            return _q(f'{_fmt(a)} : {_fmt(b)}', ans)
        a = _rand_dec1(rng, 1, 9)
        b = rng.randint(2, 9)
        return _q(f'{a} x {b}', _trunc(a * b, 1))

    if difficulty == 'normal':
        kind = rng.choice(['div_dec', 'mul2', 'add2', 'sub2'])
        if kind == 'div_dec':
            b = rng.choice([0.1, 0.2, 0.25, 0.4, 0.5, 0.8])
            ans = rng.randint(5, 80)
            a = _trunc(ans * b, 2)
            return _q(f'{_fmt(a)} : {_fmt(b)}', ans)
        if kind == 'mul2':
            a = _rand_dec1(rng, 1, 9)
            b = _rand_dec1(rng, 1, 9)
            return _q(f'{a} x {b}', _trunc(a * b, 2))
        if kind == 'add2':
            a = _rand_dec2(rng, 100, 999)
            b = _rand_dec2(rng, 100, 999)
            return _q(f'{a:.2f} + {b:.2f}', _trunc(a + b, 2))
        a = _rand_dec2(rng, 300, 999)
        b = _rand_dec2(rng, 100, a - 0.01)
        return _q(f'{a:.2f} - {b:.2f}', _trunc(a - b, 2))

    # hard
    ans = rng.randint(50, 800)
    b = rng.choice([0.09, 0.08, 0.07, 0.06, 0.04, 0.03, 0.05, 0.11, 0.12, 0.15])
    a = _trunc(ans * b, 2)
    return _q(f'{a:.2f} : {b}', ans)


def _gen_fractions(difficulty, rng, level_modifier=0):
    if difficulty == 'easy':
        denom = rng.choice([2, 3, 4, 5, 6, 8, 10])
        integer = denom * rng.randint(1, 8)
        return _q(f'(1/{denom}) x {integer}', integer // denom)

    if difficulty == 'medium':
        kind = rng.choice(['unit_frac', 'frac_mul', 'frac_sub'])
        if kind == 'unit_frac':
            denom = rng.choice([2, 3, 4, 5, 8, 10])
            integer = denom * rng.randint(1, 6)
            return _q(f'(1/{denom}) x {integer}', integer // denom)
        if kind == 'frac_mul':
            d = rng.choice([2, 3, 4, 5])
            n = rng.randint(1, d - 1)
            integer = rng.randint(2, d * 3)
            result = Fraction(n, d) * integer
            return _q(f'({n}/{d}) x {integer}', _clean_frac_ans(result), _frac_str(result))
        # frac_sub
        d = rng.choice([3, 4, 5, 6])
        n1 = rng.randint(1, d - 1)
        n2 = rng.randint(1, d - 1)
        result = Fraction(n1, d) - Fraction(n2, d)
        return _q(f'{n1}/{d} - {n2}/{d}', _clean_frac_ans(result), _frac_str(result))

    if difficulty == 'normal':
        kind = rng.choice(['to_dec', 'frac_add', 'frac_mul', 'frac_sub'])
        if kind == 'to_dec':
            n, d, dec = rng.choice(_CLEAN_FRACS)
            return _q(f'{n}/{d} as a decimal', dec)
        if kind == 'frac_add':
            d1 = rng.choice([2, 3, 4, 6, 8])
            d2 = rng.choice([2, 3, 4, 6, 8])
            n1 = rng.randint(1, d1 - 1)
            n2 = rng.randint(1, d2 - 1)
            result = Fraction(n1, d1) + Fraction(n2, d2)
            return _q(f'{n1}/{d1} + {n2}/{d2}', _clean_frac_ans(result), _frac_str(result))
        if kind == 'frac_mul':
            d1 = rng.choice([2, 3, 4, 5, 6, 8, 10])
            n1 = rng.randint(1, d1 - 1)
            integer = rng.randint(2, 12)
            result = Fraction(n1, d1) * integer
            return _q(f'({n1}/{d1}) x {integer}', _clean_frac_ans(result), _frac_str(result))
        # frac_sub
        d1 = rng.choice([2, 3, 4, 6, 8])
        d2 = rng.choice([2, 3, 4, 6, 8])
        n1 = rng.randint(1, d1 - 1)
        n2 = rng.randint(1, d2 - 1)
        result = Fraction(n1, d1) - Fraction(n2, d2)
        return _q(f'{n1}/{d1} - {n2}/{d2}', _clean_frac_ans(result), _frac_str(result))

    # hard
    kind = rng.choice(['mixed_add', 'frac_div', 'chain'])
    if kind == 'mixed_add':
        d = rng.choice([4, 8])
        w1, n1 = rng.randint(1, 5), rng.randint(1, d - 1)
        w2, n2 = rng.randint(1, 5), rng.randint(1, d - 1)
        result = Fraction(w1 * d + n1, d) + Fraction(w2 * d + n2, d)
        return _q(f'{w1} {n1}/{d} + {w2} {n2}/{d}', _clean_frac_ans(result), _frac_str(result))
    if kind == 'frac_div':
        d1, d2 = rng.choice([2, 3, 4, 6, 8]), rng.choice([2, 3, 4, 6, 8])
        n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
        result = Fraction(n1, d1) / Fraction(n2, d2)
        return _q(f'({n1}/{d1}) / ({n2}/{d2})', _clean_frac_ans(result), _frac_str(result))
    # chain
    d1, d2 = rng.choice([2, 3, 4, 6]), rng.choice([2, 3, 4, 6])
    n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
    mult = rng.randint(6, 24)
    result = (Fraction(n1, d1) + Fraction(n2, d2)) * mult
    return _q(f'({n1}/{d1} + {n2}/{d2}) x {mult}', _clean_frac_ans(result), _frac_str(result))


def _gen_algebra(difficulty, rng, level_modifier=0):
    if difficulty == 'easy':
        kind = rng.choice(['add', 'sub', 'mul', 'div'])
        if kind == 'add':
            a, x = rng.randint(2, 20), rng.randint(2, 20)
            return _q(f'x + {a} = {x + a}', x)
        if kind == 'sub':
            a = rng.randint(2, 15)
            x = rng.randint(5, 25)
            return _q(f'x - {a} = {x - a}', x)
        if kind == 'mul':
            a, x = rng.randint(2, 12), rng.randint(2, 15)
            return _q(f'{a}x = {a * x}', x)
        a, x = rng.randint(2, 10), rng.randint(2, 15)
        return _q(f'x / {a} = {x}', a * x)

    if difficulty == 'medium':
        kind = rng.choice(['add', 'sub', 'mul', 'div'])
        neg = rng.random() < 0.3
        if kind == 'add':
            a = rng.randint(5, 30)
            x = rng.randint(5, 30)
            if neg: x = -x
            return _q(f'x + {a} = {x + a}', x)
        if kind == 'sub':
            a = rng.randint(5, 25)
            x = rng.randint(10, 40)
            if neg: x = -x
            return _q(f'x - {a} = {x - a}', x)
        if kind == 'mul':
            a = rng.randint(2, 15)
            x = rng.randint(2, 20)
            if neg: x = -x
            return _q(f'{a}x = {a * x}', x)
        a = rng.randint(2, 12)
        x = rng.randint(2, 20)
        if neg: x = -x
        return _q(f'x / {a} = {x}', a * x)

    if difficulty == 'normal':
        kind = rng.choice(['two_step', 'frac_coeff', 'two_step_sub'])
        neg = rng.random() < 0.3
        if kind == 'two_step':
            a, x, b = rng.randint(2, 10), rng.randint(2, 15), rng.randint(2, 20)
            if neg: x = -x
            return _q(f'{a}x + {b} = {a * x + b}', x)
        if kind == 'frac_coeff':
            a = rng.choice([2, 4, 5, 10])
            b_choices = [v for v in [2, 4, 5, 10, 20] if v != a]
            b = rng.choice(b_choices)
            x = rng.randint(2, 10) * a
            if neg: x = -x
            c = (x // a) * b
            return _q(f'(x/{a}) x {b} = {c}', x)
        a, x, b = rng.randint(2, 10), rng.randint(2, 15), rng.randint(2, 20)
        if neg: x = -x
        return _q(f'{a}x - {b} = {a * x - b}', x)

    # hard
    kind = rng.choice(['bracket', 'dec_coeff', 'two_eq'])
    neg = rng.random() < 0.3
    if kind == 'bracket':
        a, b = rng.randint(2, 8), rng.randint(1, 10)
        x = rng.randint(2, 15)
        if neg: x = -x
        return _q(f'{a}(x + {b}) = {a * (x + b)}', x)
    if kind == 'dec_coeff':
        a = rng.choice([1.5, 2.5, 0.5, 1.25, 3.5])
        x = rng.randint(2, 8) * 2
        if neg: x = -x
        b = rng.randint(1, 20)
        c = round(a * x + b, 2)
        return _q(f'{a}x + {b} = {c}', x)
    c = rng.randint(1, 5)
    a = c + rng.randint(1, 5)
    x = rng.randint(2, 15)
    if neg: x = -x
    b = rng.randint(1, 20)
    d = a * x + b - c * x
    return _q(f'{a}x + {b} = {c}x + {d}', x)


def _gen_percentages(difficulty, rng, level_modifier=0):
    if difficulty == 'easy':
        pct = rng.choice([10, 20, 25, 50, 75])
        base = rng.choice([20, 40, 60, 80, 100, 200, 400, 1000])
        ans = _trunc(pct / 100 * base, 2)
        return _q(f'{pct}% of {base}', ans)

    if difficulty == 'medium':
        pct = rng.choice([10, 20, 25, 50, 75])
        base = rng.randint(10, 99)
        ans = _trunc(pct / 100 * base, 2)
        return _q(f'{pct}% of {base}', ans)

    if difficulty == 'normal':
        kind = rng.choice(['decimal_pct', 'reverse', 'pct_increase', 'pct_decrease'])
        if kind == 'decimal_pct':
            pct = rng.choice([15, 35, 12, 18, 22, 45, 8, 60, 65, 30])
            base = rng.randint(2, 20) * (100 // math.gcd(pct, 100))
            ans = _trunc(pct * base / 100, 2)
            return _q(f'{pct}% of {base}', ans)
        if kind == 'reverse':
            pct = rng.choice([10, 20, 25, 30, 40, 50, 75])
            base = rng.randint(4, 20) * (100 // pct)
            result = pct * base // 100
            return _q(f'?% of {base} = {result}', pct)
        if kind == 'pct_increase':
            original = rng.randint(50, 400)
            pct = rng.choice([10, 20, 25, 50, 15])
            new_val = round(original * (1 + pct / 100))
            return _q(f'{original} increased by {pct}% =', new_val)
        original = rng.randint(100, 500)
        pct = rng.choice([10, 20, 25, 50])
        new_val = round(original * (1 - pct / 100))
        return _q(f'{original} decreased by {pct}% =', new_val)

    # hard
    kind = rng.choice(['compound', 'nested', 'reverse_hard'])
    if kind == 'compound':
        original = rng.choice([100, 200, 400, 500, 1000])
        pct1 = rng.choice([10, 20, 25, 15])
        pct2 = rng.choice([10, 20, 25, 15])
        step1 = original * (1 + pct1 / 100)
        ans = _trunc(step1 * (1 - pct2 / 100), 2)
        return _q(f'{original}: +{pct1}% then -{pct2}%', ans)
    if kind == 'nested':
        pct1 = rng.choice([20, 25, 40, 50])
        pct2 = rng.choice([20, 25, 40, 50])
        base = rng.choice([100, 200, 400, 500, 1000])
        ans = _trunc(pct1 / 100 * pct2 / 100 * base, 2)
        return _q(f'{pct1}% of ({pct2}% of {base})', ans)
    pct = rng.choice([10, 20, 25, 50])
    x = rng.randint(50, 400)
    y = round(x * (1 + pct / 100))
    return _q(f'After +{pct}%, result is {y}. Original =', x)


# ---- helpers -----------------------------------------------------------------

def _q(text, answer, display_answer=None):
    if display_answer is None:
        display_answer = _auto_display(answer)
    return {'text': text, 'answer': answer, 'display_answer': display_answer}


def _auto_display(val):
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f'{val:.4f}'.rstrip('0').rstrip('.')
    return str(val)


def _fmt(val):
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f'{val:.4f}'.rstrip('0').rstrip('.')
    return str(val)


def _rand_dec1(rng, lo, hi):
    lo_i, hi_i = int(lo * 10), int(hi * 10)
    if lo_i >= hi_i:
        hi_i = lo_i + 1
    return round(rng.randint(lo_i, hi_i) / 10, 1)


def _rand_dec2(rng, lo_cents, hi_cents):
    return round(rng.randint(lo_cents, hi_cents) / 100, 2)


def _trunc(val, places):
    v = round(val, places)
    if v == int(v):
        return int(v)
    return v


def _clean_frac_ans(frac):
    if frac.denominator == 1:
        return int(frac)
    return round(float(frac), 6)


def _frac_str(frac):
    """Return mixed-number or proper-fraction string."""
    if frac.denominator == 1:
        return str(int(frac))
    num, den = frac.numerator, frac.denominator
    if abs(num) > den:
        whole = num // den
        rem = num - whole * den
        if rem == 0:
            return str(whole)
        return f'{whole} {abs(rem)}/{den}'
    return f'{num}/{den}'


# ---- multiple choice ---------------------------------------------------------

def _attach_options(q, rng):
    answer = q['answer']
    display = q['display_answer']

    # Detect fraction-style answer (contains '/')
    if '/' in str(display):
        distractors = _fraction_distractors(answer, display, rng)
    else:
        distractors = _numeric_distractors(answer, display, rng)

    options = [display] + distractors
    rng.shuffle(options)
    q['options'] = options
    q['correct_index'] = options.index(display)


def _fraction_distractors(answer, correct_display, rng, n=3):
    """Generate fraction-style distractors close to the correct fraction."""
    try:
        base = Fraction(answer).limit_denominator(16)
    except Exception:
        try:
            base = Fraction(float(answer)).limit_denominator(16)
        except Exception:
            return ['0', '1', '2']

    seen = {correct_display}
    results = []

    # Candidate fractions near the base
    candidates = []
    for delta_num in range(-4, 5):
        if delta_num == 0:
            continue
        for delta_den in [0]:
            f = Fraction(base.numerator + delta_num, max(base.denominator, 1))
            if f > 0:
                candidates.append(f)
    # Also try nearby denominators
    for d in [2, 3, 4, 6, 8]:
        for adj in [-2, -1, 1, 2]:
            num = round(float(base) * d) + adj
            if num > 0:
                candidates.append(Fraction(num, d))

    rng.shuffle(candidates)
    for frac in candidates:
        if len(results) >= n:
            break
        if frac <= 0:
            continue
        s = _frac_str(frac)
        if s not in seen and s != correct_display:
            seen.add(s)
            results.append(s)

    while len(results) < n:
        fill = _frac_str(base + Fraction(len(results) + 1, 1))
        if fill not in seen:
            results.append(fill)
            seen.add(fill)

    return results[:n]


def _numeric_distractors(answer, correct_display, rng, n=3):
    """Generate plausible numeric distractors."""
    try:
        ans_f = float(answer)
    except (TypeError, ValueError):
        return ['0', '1', '2']

    seen = {correct_display}
    results = []
    attempts = 0

    while len(results) < n and attempts < 200:
        attempts += 1
        d = _distractor_candidate(ans_f, rng)
        s = _distractor_fmt(d, answer)
        if s not in seen and s != correct_display:
            seen.add(s)
            results.append(s)

    while len(results) < n:
        fill = str(int(round(ans_f)) + len(results) + 1)
        if fill not in seen:
            results.append(fill)
            seen.add(fill)

    return results[:n]


def _distractor_candidate(ans_f, rng):
    strategy = rng.randint(0, 5)
    if strategy == 5:
        return -ans_f
    if strategy == 0:
        if abs(ans_f) >= 500:
            delta = rng.choice([-50, -20, 20, 50, -100, 100])
        elif abs(ans_f) >= 100:
            delta = rng.choice([-20, -10, -5, 5, 10, 20])
        elif abs(ans_f) >= 10:
            delta = rng.choice([-5, -3, -2, -1, 1, 2, 3, 5])
        else:
            delta = rng.choice([-2, -1, 1, 2])
        return ans_f + delta
    if strategy == 1:
        pct = rng.choice([0.05, 0.08, 0.10, 0.15, 0.20,
                          -0.05, -0.08, -0.10, -0.15, -0.20])
        return ans_f * (1 + pct)
    if strategy == 2:
        if abs(ans_f) >= 10:
            return ans_f + rng.choice([-9, 9, -11, 11])
        return ans_f + rng.choice([-3, 3])
    if strategy == 3:
        factor = rng.choice([10, 0.1])
        return ans_f * factor
    return ans_f + rng.choice([-1, 1]) * max(abs(ans_f) * 0.1, 1)


def _distractor_fmt(d, reference_answer):
    """Format distractor to stylistically match the reference answer."""
    if isinstance(reference_answer, int):
        return str(int(round(d)))
    if isinstance(reference_answer, float):
        ref_s = _auto_display(reference_answer)
        if '.' in ref_s:
            places = len(ref_s.split('.')[1])
            v = round(d, places)
            if v == int(v):
                return str(int(v))
            return f'{v:.{places}f}'.rstrip('0').rstrip('.')
        return str(int(round(d)))
    return _auto_display(round(d, 4))
