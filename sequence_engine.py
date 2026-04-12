"""
sequence_engine.py — Sequence question generation for MindMath Trainer.

Public interface:
  get_sequence_question(difficulty, rng) -> dict
  attach_sequence_options(q, rng) -> q

Question dict keys:
  sequence_display  list[str]  e.g. ['2','4','?','16','32']
  answer            str        correct value for the '?' position
  rule_description  str        internal debug description
  category          str        'number_sequence' | 'letter_sequence'
  difficulty        str        as passed in
  blank_position    int        index of '?' in sequence_display
  sequence_type     str        e.g. 'arithmetic', 'geometric', 'fibonacci'
  options           list[str]  added by attach_sequence_options (MC mode)
  correct_index     int        added by attach_sequence_options (MC mode)
"""

import sys

ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


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


# ─── Number generators — Easy ─────────────────────────────────────────────────

def _num_arith_easy(rng):
    d = rng.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
    start = rng.randint(10, 30) if d < 0 else rng.randint(1, 20)
    terms = [start + d * i for i in range(5)]
    return terms, 'arithmetic', f'arithmetic d={d}'


def _num_double_easy(rng):
    op = rng.choice(['double', 'halve'])
    if op == 'double':
        start = rng.randint(1, 8)
        terms = [start * (2 ** i) for i in range(5)]
        rule = 'geometric_x2'
    else:
        start = rng.choice([16, 32, 48, 64])
        terms = [start // (2 ** i) for i in range(5)]
        rule = 'geometric_div2'
    return terms, rule, f'×2 or ÷2 starting {start}'


# ─── Number generators — Medium ───────────────────────────────────────────────

def _num_arith_medium(rng):
    d = rng.choice([-20, -15, -10, -8, -6, -5, 5, 6, 7, 8, 10, 15, 20])
    start = rng.randint(50, 150) if d < 0 else rng.randint(5, 50)
    length = rng.choice([5, 6])
    terms = [start + d * i for i in range(length)]
    return terms, 'arithmetic', f'arithmetic d={d}'


def _num_geom_medium(rng):
    op = rng.choice(['x3', 'x4', 'div3'])
    if op == 'x3':
        s = rng.randint(1, 5)
        terms = [s * (3 ** i) for i in range(5)]
    elif op == 'x4':
        s = rng.randint(1, 3)
        terms = [s * (4 ** i) for i in range(5)]
    else:
        s = rng.choice([243, 486, 729])
        terms = [s // (3 ** i) for i in range(5)]
    return terms, f'geometric_{op}', f'geometric {op}'


def _num_squares_medium(rng):
    offset = rng.randint(1, 5)
    terms = [(offset + i) ** 2 for i in range(5)]
    return terms, 'squares', f'squares from {offset}²'


def _num_triangular_medium(rng):
    n0 = rng.randint(1, 4)
    terms = [n * (n + 1) // 2 for n in range(n0, n0 + 5)]
    return terms, 'triangular', f'triangular numbers from T({n0})'


# ─── Number generators — Normal ───────────────────────────────────────────────

def _num_fibonacci_normal(rng):
    a, b = rng.randint(1, 5), rng.randint(1, 8)
    terms = [a, b]
    for _ in range(4):
        terms.append(terms[-1] + terms[-2])
    return terms, 'fibonacci', f'fibonacci a={a} b={b}'


def _num_alternating_normal(rng):
    a0 = rng.randint(1, 5)
    b0 = rng.randint(8, 15)
    da = rng.randint(1, 3)
    db = -rng.randint(1, 3)
    terms = []
    for i in range(3):
        terms.append(a0 + da * i)
        terms.append(b0 + db * i)
    return terms, 'alternating', f'interleaved a={a0}+{da} b={b0}{db}'


def _num_inc_diff_normal(rng):
    start = rng.randint(1, 10)
    d0 = rng.randint(1, 3)
    terms = [start]
    for i in range(5):
        terms.append(terms[-1] + d0 + i)
    return terms, 'increasing_differences', f'diffs starting at {d0}'


def _num_arith_neg_normal(rng):
    start = rng.randint(10, 20)
    d = -rng.randint(3, 7)
    terms = [start + d * i for i in range(6)]
    return terms, 'arithmetic', f'arithmetic d={d} (crosses zero)'


# ─── Number generators — Hard ─────────────────────────────────────────────────

def _num_diff2_hard(rng):
    start = rng.randint(1, 5)
    d1 = rng.randint(1, 3)
    d2 = rng.randint(1, 2)
    terms = [start]
    d = d1
    for _ in range(6):
        terms.append(terms[-1] + d)
        d += d2
    return terms, 'diff_of_diffs', f'2nd-order arithmetic d1={d1} d2={d2}'


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
    return terms, 'alternating_op', f'×{mult} +{add} alternating'


def _num_power_offset_hard(rng):
    c = rng.randint(1, 4)
    n0 = rng.randint(0, 2)
    terms = [2 ** n + c for n in range(n0, n0 + 6)]
    return terms, 'power_offset', f'2^n + {c}'


def _num_mixed_hard(rng):
    start = rng.randint(1, 5)
    d0 = rng.choice([2, 3, 4])
    dd = rng.choice([2, 3])
    terms = [start]
    d = d0
    for _ in range(6):
        terms.append(terms[-1] + d)
        d += dd
    return terms, 'mixed_geom_arith', f'start={start} d0={d0} dd={dd}'


# ─── Letter generators — Easy ─────────────────────────────────────────────────

def _let_step1_easy(rng):
    s = rng.randint(0, 20)
    return [_lch(s + i) for i in range(5)], 'alphabet_step', 'alphabet +1'


def _let_step2_easy(rng):
    s = rng.randint(0, 15)
    return [_lch(s + i * 2) for i in range(5)], 'alphabet_step', 'alphabet +2'


def _let_rev1_easy(rng):
    s = rng.randint(5, 25)
    return [_lch(s - i) for i in range(5)], 'alphabet_step', 'reverse alphabet -1'


# ─── Letter generators — Medium ───────────────────────────────────────────────

def _let_alt_step_medium(rng):
    s = rng.randint(0, 12)
    terms = [_lch(s)]
    pos = s
    steps = [2, 3]
    for i in range(5):
        pos += steps[i % 2]
        terms.append(_lch(pos))
    return terms, 'alternating', 'alternating +2+3'


def _let_rev2_medium(rng):
    s = rng.randint(10, 25)
    return [_lch(s - i * 2) for i in range(6)], 'alphabet_step', 'reverse alphabet -2'


def _let_skip_wrap_medium(rng):
    # Two interleaved sequences: A descending by 2, B ascending by 2
    # e.g. Y=24, B=1, W=22, D=3, U=20, F=5
    a = rng.randint(18, 24)
    b = rng.randint(1, 5)
    terms = []
    for i in range(3):
        terms.append(_lch(a - i * 2))
        terms.append(_lch(b + i * 2))
    return terms, 'alternating', 'two interleaved letter sequences'


# ─── Letter generators — Normal ───────────────────────────────────────────────

def _let_positional_normal(rng):
    # Gaps: 2, 3, 4, 5, 6  e.g. A,C,F,J,O,U
    s = rng.randint(0, 3)
    terms = [_lch(s)]
    pos = s
    for i in range(5):
        pos += (i + 2)
        terms.append(_lch(pos))
    return terms, 'positional', 'increasing gaps 2,3,4,5,6'


def _let_two_letter_normal(rng):
    # AB, CD, EF, GH, IJ  (consecutive letter pairs stepping by 2)
    s = rng.randint(0, 16)
    pairs = []
    for i in range(5):
        p = s + i * 2
        pairs.append(_lch(p) + _lch(p + 1))
    return pairs, 'two_letter', 'consecutive letter pairs +2'


# ─── Letter generators — Hard ─────────────────────────────────────────────────

def _let_wrap_hard(rng):
    # e.g. W,Z,C,F,I,L  (+3 with modular wrap)
    s = rng.randint(0, 25)
    step = rng.choice([3, 4, 5])
    return [_lch(s + i * step) for i in range(6)], 'alphabet_wrap', f'alphabet wrap +{step}'


def _let_complex_hard(rng):
    # Increasing irregular gaps (like triangular offsets)
    s = rng.randint(0, 4)
    gaps = [rng.randint(1, 2), rng.randint(2, 3), rng.randint(3, 4),
            rng.randint(4, 5), rng.randint(5, 6)]
    terms = [_lch(s)]
    pos = s
    for g in gaps:
        pos += g
        terms.append(_lch(pos))
    return terms, 'complex_positional', 'increasing irregular gaps'


# ─── Generator registries ──────────────────────────────────────────────────────

_NUM_GEN = {
    'easy':   [_num_arith_easy, _num_double_easy],
    'medium': [_num_arith_medium, _num_geom_medium, _num_squares_medium, _num_triangular_medium],
    'normal': [_num_fibonacci_normal, _num_alternating_normal, _num_inc_diff_normal, _num_arith_neg_normal],
    'hard':   [_num_diff2_hard, _num_alt_op_hard, _num_power_offset_hard, _num_mixed_hard],
}

_LET_GEN = {
    'easy':   [_let_step1_easy, _let_step2_easy, _let_rev1_easy],
    'medium': [_let_alt_step_medium, _let_rev2_medium, _let_skip_wrap_medium],
    'normal': [_let_positional_normal, _let_two_letter_normal],
    'hard':   [_let_wrap_hard, _let_complex_hard],
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
    # Letter sequences: single letter (except two_letter pairs)
    if q.get('category') == 'letter_sequence' and q.get('sequence_type') != 'two_letter':
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
        'rule_description': f'arithmetic d={d} (fallback)',
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

    if cat == 'number_sequence':
        distractors = _num_distractors(correct, q, rng)
    elif seq_type == 'two_letter':
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

def _num_distractors(correct_str: str, q: dict, rng) -> list:
    try:
        cv = float(correct_str)
    except ValueError:
        return [correct_str + '1', correct_str + '2', correct_str + '3']

    seen = {cv}
    result = []

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
            if abs(c - cv) > 0.001 and c not in seen:
                seen.add(c)
                result.append(_fmt_num(c, cv))
                if len(result) >= 3:
                    return result

    # Fill with nearby offsets
    for off in rng.sample([-3, -2, -1, 1, 2, 3, -5, 5, -4, 4], 10):
        c = cv + off
        if abs(c - cv) > 0.001 and c not in seen:
            seen.add(c)
            result.append(_fmt_num(c, cv))
            if len(result) >= 3:
                return result

    return result[:3]


def _fmt_num(val: float, ref: float) -> str:
    if val == int(val) and ref == int(ref):
        return str(int(val))
    ref_str = str(ref)
    if '.' in ref_str:
        dp = len(ref_str.split('.')[1].rstrip('0')) or 1
        return f"{val:.{dp}f}"
    return str(val)


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
