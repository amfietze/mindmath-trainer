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

# Set True to run a back-calculation self-test on first import; must be False in committed code.
PERCENTAGE_SELF_TEST = False

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

    # Check 2 — for percentages: back-calculation via _pct_meta;
    #            for all others: display_answer parses close to answer.
    if q.get('category') == 'percentages':
        meta = q.get('_pct_meta')
        if meta and not _pct_back_check(meta, ans_f):
            return False
    else:
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


# ---- percentage helpers ------------------------------------------------------

def _pct_back_check(meta, answer):
    """Return True if answer agrees with back-calculation from _pct_meta."""
    try:
        t = meta.get('type')
        if t == 'basic':
            expected = round(meta['pct'] / 100 * meta['base'], 2)
            return abs(expected - answer) < 0.01
        elif t == 'reverse':
            expected = round(float(meta['result']) / meta['base'] * 100, 2)
            return abs(expected - answer) < 0.01
        elif t == 'increase':
            expected = round(meta['original'] * (1 + meta['pct'] / 100), 2)
            return abs(expected - answer) < 0.01
        elif t == 'decrease':
            expected = round(meta['original'] * (1 - meta['pct'] / 100), 2)
            return abs(expected - answer) < 0.01
        elif t == 'compound':
            step1 = meta['original'] * (1 + meta['pct1'] / 100)
            expected = round(step1 * (1 - meta['pct2'] / 100), 2)
            return abs(expected - answer) < 0.01
        elif t == 'nested':
            expected = round(meta['pct1'] / 100 * meta['pct2'] / 100 * meta['base'], 2)
            return abs(expected - answer) < 0.01
        elif t == 'reverse_hard':
            # answer*(1+pct/100) should round to y (banker's rounding can land on .5)
            return abs(answer * (1 + meta['pct'] / 100) - meta['y']) <= 0.5
        elif t == 'find_base':
            expected = round(float(meta['result']) / (meta['pct'] / 100), 2)
            return abs(expected - answer) < 0.01
        elif t == 'triple_compound':
            step1 = meta['original'] * (1 + meta['pct1'] / 100)
            step2 = step1 * (1 - meta['pct2'] / 100)
            expected = round(step2 * (1 + meta['pct3'] / 100), 2)
            return abs(expected - answer) < 0.01
        return True
    except Exception:
        return True  # don't reject on unexpected meta shape


def _run_pct_self_test():
    failures = 0
    total = 0
    for diff in ['easy', 'medium', 'normal', 'hard']:
        for i in range(30):
            rng = random.Random(i * 1000 + hash(diff) % 10000)
            try:
                q = _gen_percentages(diff, rng)
                meta = q.get('_pct_meta')
                ans = float(q['answer'])
                if meta and not _pct_back_check(meta, ans):
                    print(
                        f"PCT FAIL: diff={diff} text={q['text']!r} "
                        f"ans={q['answer']} meta={meta}",
                        file=sys.stderr,
                    )
                    failures += 1
                total += 1
            except Exception as exc:
                print(f"PCT ERROR: diff={diff} i={i}: {exc}", file=sys.stderr)
                failures += 1
    print(f"PCT SELF-TEST: {total} tested, {failures} failures", file=sys.stderr)


# ---- internal builders -------------------------------------------------------

def _build(category, difficulty, rng, level_modifier, multiple_choice):
    generators = {
        'integers':            _gen_integers,
        'decimals':            _gen_decimals,
        'fractions':           _gen_fractions,
        'algebra':             _gen_algebra,
        'percentages':         _gen_percentages,
        'exponents_roots':     _gen_exponents_roots,
        'ratios_proportions':  _gen_ratios_proportions,
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
        kind = rng.choice(['mul2', 'add3', 'sub3', 'div2', 'chain_mul_add', 'triple_add'])
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
        if kind == 'div2':
            b = rng.randint(2, 20)
            ans = rng.randint(10, 60)
            return _q(f'{b * ans} : {b}', ans)
        if kind == 'chain_mul_add':
            a, b = rng.randint(5, 20), rng.randint(5, 20)
            c = rng.randint(10, 100)
            return _q(f'{a} x {b} + {c}', a * b + c)
        # triple_add
        a, b, c = rng.randint(10, 99), rng.randint(10, 99), rng.randint(10, 99)
        return _q(f'{a} + {b} + {c}', a + b + c)

    # hard
    kind = rng.choice(['big_mul', 'multi_step', 'chain', 'bracket_sub', 'div_group'])
    if kind == 'big_mul':
        a, b = rng.randint(100, 999), rng.randint(11, 99)
        return _q(f'{a} x {b}', a * b)
    if kind == 'multi_step':
        a, b = rng.randint(10, 60), rng.randint(10, 60)
        c = rng.randint(3, 15)
        return _q(f'({a} + {b}) x {c}', (a + b) * c)
    if kind == 'chain':
        a, b = rng.randint(10, 50), rng.randint(10, 50)
        c, d = rng.randint(2, 20), rng.randint(2, 20)
        return _q(f'{a} x {b} + {c} x {d}', a * b + c * d)
    if kind == 'bracket_sub':
        a = rng.randint(50, 200)
        b = rng.randint(10, a - 1)
        c = rng.randint(2, 15)
        return _q(f'({a} - {b}) x {c}', (a - b) * c)
    # div_group
    a, b = rng.randint(5, 20), rng.randint(5, 20)
    product = a * b
    divisors = [d for d in range(2, 21) if product % d == 0]
    c = rng.choice(divisors)
    return _q(f'({a} x {b}) : {c}', product // c)


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
        kind = rng.choice(['div_dec', 'mul2', 'add2', 'sub2', 'chain_add_sub', 'div_dec2'])
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
        if kind == 'sub2':
            a = _rand_dec2(rng, 300, 999)
            b = _rand_dec2(rng, 100, int(round(a * 100)) - 1)
            return _q(f'{a:.2f} - {b:.2f}', _trunc(a - b, 2))
        if kind == 'chain_add_sub':
            a = _rand_dec1(rng, 5, 20)
            b = _rand_dec1(rng, 1, 10)
            c = _rand_dec1(rng, 1, a + b - 0.1)
            return _q(f'{a} + {b} - {c}', _trunc(a + b - c, 1))
        # div_dec2
        b = rng.choice([0.12, 0.15, 0.24, 0.25, 0.4, 0.6, 0.75])
        ans = rng.randint(4, 40)
        a = _trunc(ans * b, 2)
        return _q(f'{_fmt(a)} : {_fmt(b)}', ans)

    # hard
    kind = rng.choice(['div_hard', 'mul_hard', 'chain_hard'])
    if kind == 'div_hard':
        ans = rng.randint(50, 800)
        b = rng.choice([0.09, 0.08, 0.07, 0.06, 0.04, 0.03, 0.05, 0.11, 0.12, 0.15])
        a = _trunc(ans * b, 2)
        return _q(f'{a:.2f} : {b}', ans)
    if kind == 'mul_hard':
        a = _rand_dec2(rng, 100, 999)
        b = _rand_dec2(rng, 100, 999)
        return _q(f'{a:.2f} x {b:.2f}', _trunc(a * b, 2))
    # chain_hard
    c = rng.choice([0.05, 0.08, 0.1, 0.2, 0.25])
    part = rng.randint(5, 40)
    b = _trunc(part * c, 2)
    a = _rand_dec1(rng, 1, 20)
    return _q(f'{a} + {_fmt(b)} : {_fmt(c)}', _trunc(a + part, 2))


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
        kind = rng.choice(['to_dec', 'frac_add', 'frac_mul', 'frac_sub',
                            'mixed_sub_light', 'three_frac_add'])
        if kind == 'mixed_sub_light':
            d = rng.choice([2, 4, 5, 8])
            w = rng.randint(2, 6)
            n1 = rng.randint(1, d - 1)
            n2 = rng.randint(1, d - 1)
            result = Fraction(w * d + n1, d) - Fraction(n2, d)
            return _q(f'{w} {n1}/{d} - {n2}/{d}', _clean_frac_ans(result), _frac_str(result))
        if kind == 'three_frac_add':
            d = rng.choice([3, 4, 5, 6, 8])
            n1 = rng.randint(1, d - 1)
            n2 = rng.randint(1, d - 1)
            n3 = rng.randint(1, d - 1)
            result = Fraction(n1 + n2 + n3, d)
            return _q(f'{n1}/{d} + {n2}/{d} + {n3}/{d}', _clean_frac_ans(result), _frac_str(result))
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
    kind = rng.choice(['mixed_add', 'frac_div', 'chain', 'mixed_sub', 'frac_mul_chain'])
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
    if kind == 'chain':
        d1, d2 = rng.choice([2, 3, 4, 6]), rng.choice([2, 3, 4, 6])
        n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
        mult = rng.randint(6, 24)
        result = (Fraction(n1, d1) + Fraction(n2, d2)) * mult
        return _q(f'({n1}/{d1} + {n2}/{d2}) x {mult}', _clean_frac_ans(result), _frac_str(result))
    if kind == 'mixed_sub':
        d = rng.choice([4, 8])
        w1 = rng.randint(3, 8)
        n1 = rng.randint(1, d - 1)
        w2 = rng.randint(1, w1 - 1)
        n2 = rng.randint(1, d - 1)
        result = Fraction(w1 * d + n1, d) - Fraction(w2 * d + n2, d)
        return _q(f'{w1} {n1}/{d} - {w2} {n2}/{d}', _clean_frac_ans(result), _frac_str(result))
    # frac_mul_chain
    d1, d2 = rng.choice([2, 3, 4, 5, 6]), rng.choice([2, 3, 4, 5, 6])
    n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
    integer = rng.randint(2, 10)
    result = Fraction(n1, d1) * Fraction(n2, d2) * integer
    return _q(f'({n1}/{d1}) x ({n2}/{d2}) x {integer}', _clean_frac_ans(result), _frac_str(result))


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
        kind = rng.choice(['two_step', 'frac_coeff', 'two_step_sub',
                            'div_after_mul', 'neg_coeff'])
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
        if kind == 'two_step_sub':
            a, x, b = rng.randint(2, 10), rng.randint(2, 15), rng.randint(2, 20)
            if neg: x = -x
            return _q(f'{a}x - {b} = {a * x - b}', x)
        if kind == 'div_after_mul':
            a = rng.randint(2, 9)
            x = rng.randint(2, 15)
            if neg: x = -x
            numerator = a * x
            divisors = [d for d in range(2, 10) if numerator % d == 0]
            b = rng.choice(divisors)
            c = numerator // b
            return _q(f'{a}x : {b} = {c}', x)
        # neg_coeff
        a = rng.randint(2, 10)
        x = rng.randint(2, 15)
        if neg: x = -x
        b = rng.randint(2, 20)
        c = -a * x + b
        return _q(f'-{a}x + {b} = {c}', x)

    # hard
    kind = rng.choice(['bracket', 'dec_coeff', 'two_eq', 'double_bracket', 'frac_eq'])
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
    if kind == 'two_eq':
        c = rng.randint(1, 5)
        a = c + rng.randint(1, 5)
        x = rng.randint(2, 15)
        if neg: x = -x
        b = rng.randint(1, 20)
        d = a * x + b - c * x
        return _q(f'{a}x + {b} = {c}x + {d}', x)
    if kind == 'double_bracket':
        a = rng.randint(2, 8)
        x = rng.randint(2, 15)
        if neg: x = -x
        b = rng.randint(1, 10)
        c = rng.randint(1, 20)
        d = a * (x + b) - c
        return _q(f'{a}(x + {b}) - {c} = {d}', x)
    # frac_eq
    b = rng.randint(2, 9)
    c = rng.randint(2, 15)
    x = rng.randint(2, b * c - 1)
    if neg: x = -x
    a = b * c - x
    return _q(f'(x + {a}) / {b} = {c}', x)


def _gen_percentages(difficulty, rng, level_modifier=0):
    # Round val to 2dp; store as int if whole, else float. Do NOT use _trunc here.
    def _r2(val):
        v = round(val, 2)
        return int(v) if v == int(v) else v

    if difficulty == 'easy':
        pct = rng.choice([10, 20, 25, 50, 75])
        base = rng.choice([20, 40, 60, 80, 100, 200, 400, 1000])
        answer = _r2(pct / 100 * base)
        q = _q(f'{pct}% of {base}', answer)
        q['_pct_meta'] = {'type': 'basic', 'pct': pct, 'base': base}
        return q

    if difficulty == 'medium':
        pct = rng.choice([10, 20, 25, 50, 75])
        base = rng.randint(10, 99)
        answer = _r2(pct / 100 * base)
        q = _q(f'{pct}% of {base}', answer)
        q['_pct_meta'] = {'type': 'basic', 'pct': pct, 'base': base}
        return q

    if difficulty == 'normal':
        kind = rng.choice(['decimal_pct', 'reverse', 'pct_increase', 'pct_decrease',
                            'find_base', 'sum_pct'])
        if kind == 'find_base':
            pct = rng.choice([10, 20, 25, 50, 75, 40])
            base = rng.randint(4, 40) * (100 // math.gcd(pct, 100))
            result = _r2(pct / 100 * base)
            q = _q(f'{pct}% of ? = {result}', base)
            q['_pct_meta'] = {'type': 'find_base', 'pct': pct, 'result': float(result)}
            return q
        if kind == 'sum_pct':
            pct = rng.choice([10, 20, 25, 50])
            a, b = rng.randint(10, 80), rng.randint(10, 80)
            base = a + b
            answer = _r2(pct / 100 * base)
            q = _q(f'{pct}% of ({a} + {b})', answer)
            q['_pct_meta'] = {'type': 'basic', 'pct': pct, 'base': base}
            return q
        if kind == 'decimal_pct':
            pct = rng.choice([15, 35, 12, 18, 22, 45, 8, 60, 65, 30])
            base = rng.randint(2, 20) * (100 // math.gcd(pct, 100))
            answer = _r2(pct * base / 100)
            q = _q(f'{pct}% of {base}', answer)
            q['_pct_meta'] = {'type': 'basic', 'pct': pct, 'base': base}
            return q
        if kind == 'reverse':
            pct = rng.choice([10, 20, 25, 30, 40, 50, 75])
            base = rng.randint(4, 20) * (100 // pct)
            # Compute result first from canonical formula; answer is pct.
            result = _r2(pct / 100 * base)
            q = _q(f'?% of {base} = {result}', pct)
            q['_pct_meta'] = {'type': 'reverse', 'result': float(result), 'base': base}
            return q
        if kind == 'pct_increase':
            original = rng.randint(50, 400)
            pct = rng.choice([10, 20, 25, 50, 15])
            answer = _r2(original * (1 + pct / 100))
            q = _q(f'{original} increased by {pct}% =', answer)
            q['_pct_meta'] = {'type': 'increase', 'original': original, 'pct': pct}
            return q
        # pct_decrease
        original = rng.randint(100, 500)
        pct = rng.choice([10, 20, 25, 50])
        answer = _r2(original * (1 - pct / 100))
        q = _q(f'{original} decreased by {pct}% =', answer)
        q['_pct_meta'] = {'type': 'decrease', 'original': original, 'pct': pct}
        return q

    # hard
    kind = rng.choice(['compound', 'nested', 'reverse_hard', 'triple_compound', 'pct_of_diff'])
    if kind == 'triple_compound':
        original = rng.choice([100, 200, 400, 500, 1000])
        p1 = rng.choice([10, 15, 20, 25])
        p2 = rng.choice([10, 15, 20, 25])
        p3 = rng.choice([10, 15, 20, 25])
        step1 = original * (1 + p1 / 100)
        step2 = step1 * (1 - p2 / 100)
        answer = _r2(step2 * (1 + p3 / 100))
        q = _q(f'{original}: +{p1}% then -{p2}% then +{p3}%', answer)
        q['_pct_meta'] = {'type': 'triple_compound', 'original': original,
                           'pct1': p1, 'pct2': p2, 'pct3': p3}
        return q
    if kind == 'pct_of_diff':
        pct = rng.choice([15, 35, 12, 18, 22, 45, 8, 60, 65, 30])
        a = rng.randint(200, 900)
        b = rng.randint(50, a - 50)
        base = a - b
        answer = _r2(pct / 100 * base)
        q = _q(f'{pct}% of ({a} - {b})', answer)
        q['_pct_meta'] = {'type': 'basic', 'pct': pct, 'base': base}
        return q
    if kind == 'compound':
        original = rng.choice([100, 200, 400, 500, 1000])
        pct1 = rng.choice([10, 20, 25, 15])
        pct2 = rng.choice([10, 20, 25, 15])
        step1 = original * (1 + pct1 / 100)
        answer = _r2(step1 * (1 - pct2 / 100))
        q = _q(f'{original}: +{pct1}% then -{pct2}%', answer)
        q['_pct_meta'] = {'type': 'compound', 'original': original, 'pct1': pct1, 'pct2': pct2}
        return q
    if kind == 'nested':
        pct1 = rng.choice([20, 25, 40, 50])
        pct2 = rng.choice([20, 25, 40, 50])
        base = rng.choice([100, 200, 400, 500, 1000])
        answer = _r2(pct1 / 100 * pct2 / 100 * base)
        q = _q(f'{pct1}% of ({pct2}% of {base})', answer)
        q['_pct_meta'] = {'type': 'nested', 'pct1': pct1, 'pct2': pct2, 'base': base}
        return q
    # reverse_hard
    pct = rng.choice([10, 20, 25, 50])
    x = rng.randint(50, 400)
    y = round(x * (1 + pct / 100))
    q = _q(f'After +{pct}%, result is {y}. Original =', x)
    q['_pct_meta'] = {'type': 'reverse_hard', 'pct': pct, 'y': y}
    return q


def _gen_exponents_roots(difficulty, rng, level_modifier=0):
    """Normal/Hard only — no Easy/Medium variant exists (deliberate scope)."""
    if difficulty == 'hard':
        kind = rng.choice(['cbrt_perfect', 'mixed_expr', 'large_power', 'irrational_sqrt'])
        if kind == 'cbrt_perfect':
            n = rng.randint(2, 12)
            return _q(f'∛{n ** 3} = ?', n)
        if kind == 'mixed_expr':
            a, b = rng.randint(2, 12), rng.randint(2, 12)
            return _q(f'{a}^2 + {b}^2 = ?', a * a + b * b)
        if kind == 'large_power':
            base = rng.randint(2, 6)
            exp = rng.randint(3, 6)
            return _q(f'{base}^{exp} = ?', base ** exp)
        # irrational_sqrt — non-perfect square, rounded 3dp answer.
        # Relies on app.py's is_repeating()/Fraction-tolerance path for open-answer
        # acceptance, since the true value is irrational (see session summary).
        perfect = {i * i for i in range(1, 11)}
        n = rng.randint(2, 99)
        while n in perfect:
            n = rng.randint(2, 99)
        answer = round(math.sqrt(n), 3)
        return _q(f'√{n} = ? (3 d.p.)', answer)

    # normal (default)
    kind = rng.choice(['square', 'cube', 'sqrt_perfect', 'power_simple'])
    if kind == 'square':
        a = rng.randint(10, 99)
        return _q(f'{a}^2 = ?', a * a)
    if kind == 'cube':
        a = rng.randint(2, 10)
        return _q(f'{a}^3 = ?', a ** 3)
    if kind == 'sqrt_perfect':
        n = rng.randint(2, 20)
        return _q(f'√{n * n} = ?', n)
    # power_simple
    base = rng.randint(2, 5)
    exp = rng.randint(2, 5)
    return _q(f'{base}^{exp} = ?', base ** exp)


def _gen_ratios_proportions(difficulty, rng, level_modifier=0):
    """Normal/Hard only — no Easy/Medium variant exists (deliberate scope).

    'simplify' answers are expressed as simplified fractions (reusing the
    existing fraction-answer parsing/distractor path unmodified); all other
    sub-patterns solve for a single missing number and reuse the plain
    numeric-answer path. See session summary for the rationale.
    """
    if difficulty == 'hard':
        kind = rng.choice(['multi_term', 'inverse'])
        if kind == 'multi_term':
            r1, r2, r3 = rng.randint(1, 9), rng.randint(1, 9), rng.randint(1, 9)
            k = rng.randint(2, 15)
            total = (r1 + r2 + r3) * k
            term_choice = rng.choice(['first', 'second', 'third'])
            value = {'first': r1 * k, 'second': r2 * k, 'third': r3 * k}[term_choice]
            return _q(f'Divide {total} in the ratio {r1} : {r2} : {r3}. '
                      f'Find the {term_choice} share.', value)
        # inverse
        a = rng.randint(2, 12)
        b = rng.randint(2, 20)
        product = a * b
        divisors = [d for d in range(2, 21) if product % d == 0 and d != a]
        c = rng.choice(divisors) if divisors else a
        x = product // c
        return _q(f'Inverse proportion: {a} workers → {b} days. '
                  f'{c} workers → ? days.', x)

    # normal (default)
    kind = rng.choice(['simplify', 'solve_proportion'])
    if kind == 'simplify':
        p, q_ = 2, 3
        for _ in range(20):
            p, q_ = rng.randint(2, 8), rng.randint(2, 8)
            if p != q_ and math.gcd(p, q_) == 1:
                break
        g = rng.randint(2, 8)
        a, b = p * g, q_ * g
        result = Fraction(a, b)
        return _q(f'Simplify the ratio {a} : {b}', _clean_frac_ans(result), _frac_str(result))
    # solve_proportion
    a, b = rng.randint(2, 15), rng.randint(2, 15)
    m = rng.randint(2, 8)
    c, x = a * m, b * m
    return _q(f'{a} : {b} = {c} : x, x = ?', x)


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
    """Generate plausible numeric distractors using a multi-strategy pool."""
    try:
        ans_f = float(answer)
    except (TypeError, ValueError):
        return ['0', '1', '2']

    # Decimal places to match the correct answer format
    if isinstance(answer, int):
        places = 0
    else:
        ref_s = _auto_display(answer)
        places = len(ref_s.split('.')[1]) if '.' in ref_s else 0

    abs_a = abs(ans_f)

    def _candidate():
        strategy = rng.randint(0, 4)
        if strategy == 0:
            # Off by a small percentage
            pct = rng.choice([0.05, 0.1, 0.15, 0.2, -0.05, -0.1, -0.15, -0.2])
            return round(ans_f * (1 + pct), places)
        elif strategy == 1:
            # Magnitude-scaled plausible arithmetic error
            if abs_a < 10:
                offset = rng.choice([1, 2, 3])
            elif abs_a < 100:
                offset = rng.choice([2, 5, 10])
            elif abs_a < 1000:
                offset = rng.choice([5, 10, 20, 50])
            else:
                offset = rng.choice([10, 50, 100])
            return round(ans_f + rng.choice([-1, 1]) * offset, places)
        elif strategy == 2:
            # Common mental math mistake
            kind = rng.randint(0, 1)
            if kind == 0:
                # Round to nearest 5 or 10
                target = rng.choice([5.0, 10.0])
                return round(round(ans_f / target) * target, places)
            else:
                # Apply a percentage error twice (compound mistake)
                pct = rng.choice([0.05, 0.1, 0.15, -0.05, -0.1, -0.15])
                return round(ans_f * (1 + pct) * (1 + pct), places)
        elif strategy == 3:
            # Plausible neighbour in 70%–130% of answer range
            if abs_a > 0.001:
                lo = min(ans_f * 0.7, ans_f * 1.3)
                hi = max(ans_f * 0.7, ans_f * 1.3)
            else:
                lo, hi = ans_f - 5.0, ans_f + 5.0
            if abs(hi - lo) < 0.01:
                lo, hi = ans_f - 1.0, ans_f + 1.0
            return round(lo + rng.random() * (hi - lo), places)
        else:
            # Sign flip
            return round(-ans_f, places)

    seen = {correct_display}
    results = []
    sign_flips = 0

    # Negative correct answer: force at least one positive distractor to test sign awareness
    if ans_f < 0 and abs_a > 0.001:
        pos_d = round(abs_a * rng.uniform(0.8, 1.2), places)
        s = _distractor_fmt(pos_d, answer)
        if s not in seen:
            seen.add(s)
            results.append(s)

    attempts = 0
    while len(results) < n and attempts < 300:
        attempts += 1
        d = _candidate()

        # Must differ from correct answer by at least 2% of magnitude or 0.001
        min_diff = max(abs_a * 0.02, 0.001)
        if abs(d - ans_f) < min_diff:
            continue

        # Reject if 10× or more different from correct (obviously eliminable)
        if abs_a > 0.001 and abs(d) > 0.001:
            ratio = abs(d) / abs_a
            if ratio > 9.0 or ratio < 0.111:
                continue

        # Positive correct answer: at most 1 sign-flipped (negative) distractor
        if ans_f > 0 and d < 0 and sign_flips >= 1:
            continue

        s = _distractor_fmt(d, answer)
        if s in seen or s == correct_display:
            continue

        # Must differ from already-chosen distractors
        too_close = False
        for existing in results:
            try:
                if abs(float(existing) - d) < 0.001:
                    too_close = True
                    break
            except ValueError:
                pass
        if too_close:
            continue

        seen.add(s)
        results.append(s)
        if ans_f > 0 and d < 0:
            sign_flips += 1

    # Fallback: simple scaled offsets
    for step in range(1, 30):
        if len(results) >= n:
            break
        for sgn in [1, -1]:
            if len(results) >= n:
                break
            offset = step * max(abs_a * 0.1, 1)
            d = round(ans_f + sgn * offset, places)
            s = _distractor_fmt(d, answer)
            if s not in seen:
                seen.add(s)
                results.append(s)

    return results[:n]


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


# ---- percentage self-test (triggered at module load when flag is True) --------

if PERCENTAGE_SELF_TEST:
    _run_pct_self_test()
