"""
MindMath Trainer – Flask application.
All routes live here.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import random
from datetime import datetime
from fractions import Fraction
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify)

from config import (CATEGORIES, TEST_QUESTIONS, TEST_DURATION,
                    PRACTICE_QUESTION_TIME, PRACTICE_FEEDBACK_DELAY,
                    CORRECT_STREAK_FOR_UPGRADE, WRONG_STREAK_FOR_DOWNGRADE)
from question_engine import get_validated_question, generate_test_questions
from scoring import compute_practice_stats, compute_test_stats

app = Flask(__name__)

_flask_env = os.environ.get('FLASK_ENV', 'production')
if _flask_env == 'development':
    app.secret_key = os.environ.get('SECRET_KEY', 'mindmath-dev-secret-change-in-prod')
else:
    _secret = os.environ.get('SECRET_KEY')
    if not _secret:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. Set it before deploying."
        )
    app.secret_key = _secret

FLAGGED_FILE = os.path.join(os.path.dirname(__file__), 'flagged_questions.json')


# ─── home ─────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')


# ─── session start ────────────────────────────────────────────────────────────

@app.route('/start', methods=['POST'])
def start():
    mode = request.form.get('mode', 'practice')
    difficulty = request.form.get('difficulty', 'normal')
    timer_str = request.form.get('timer_duration', '10')
    answer_mode = request.form.get('answer_mode', 'open')

    session.clear()

    if mode == 'practice':
        if timer_str == 'unlimited':
            question_time = 0  # 0 = unlimited sentinel
        else:
            try:
                question_time = int(timer_str)
            except ValueError:
                question_time = 10

        session['mode'] = 'practice'
        session['difficulty'] = difficulty
        session['level_modifier'] = 0
        session['correct_streak'] = 0
        session['wrong_streak'] = 0
        session['question_time'] = question_time
        session['answer_mode'] = answer_mode
        session['stats'] = {
            'total': 0,
            'correct': 0,
            'wrong': 0,
            'skipped': 0,
            'total_time': 0.0,
            'by_category': {cat: [0, 0] for cat in CATEGORIES},
        }
        first_q = _next_practice_question()
        session['current_q'] = first_q
        return redirect(url_for('practice'))

    if mode == 'test':
        seed = random.randint(0, 999_999)
        session['mode'] = 'test'
        session['difficulty'] = difficulty
        session['seed'] = seed
        # Generate all 80 questions now; store compactly
        questions = generate_test_questions(seed, difficulty, TEST_QUESTIONS)
        session['test_questions'] = questions
        session['start_time'] = time.time()
        return redirect(url_for('test'))

    return redirect(url_for('home'))


# ─── practice ─────────────────────────────────────────────────────────────────

@app.route('/practice')
def practice():
    if session.get('mode') != 'practice':
        return redirect(url_for('home'))
    q = session.get('current_q', {})
    question_time = session.get('question_time', PRACTICE_QUESTION_TIME)
    answer_mode = session.get('answer_mode', 'open')
    return render_template(
        'practice.html',
        question=q,
        question_time=question_time,
        feedback_delay=PRACTICE_FEEDBACK_DELAY,
        difficulty=session.get('difficulty', 'normal'),
        answer_mode=answer_mode,
    )


@app.route('/next-question')
def next_question():
    if session.get('mode') != 'practice':
        return jsonify({'error': 'not in practice mode'}), 400
    q = _next_practice_question()
    session['current_q'] = q
    session.modified = True
    return jsonify(q)


@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    if session.get('mode') != 'practice':
        return jsonify({'error': 'not in practice mode'}), 400

    data = request.get_json(force=True)
    user_ans = str(data.get('answer', '')).strip()
    time_taken = float(data.get('time_taken', 0))
    skipped = bool(data.get('skipped', False))

    current_q = session.get('current_q', {})
    correct_answer = current_q.get('answer')
    display_answer = current_q.get('display_answer', str(correct_answer))
    category = current_q.get('category', 'integers')

    stats = session.get('stats', {})
    by_cat = stats.setdefault('by_category', {cat: [0, 0] for cat in CATEGORIES})

    stats['total'] = stats.get('total', 0) + 1
    if category in by_cat:
        by_cat[category][0] += 1

    is_rounded = False
    if skipped:
        stats['skipped'] = stats.get('skipped', 0) + 1
        result = 'skipped'
    else:
        # Support MC submissions (index comparison bypasses text matching)
        mc_selected = data.get('mc_selected_index')
        mc_correct_idx = data.get('mc_correct_index')
        if mc_selected is not None and mc_correct_idx is not None:
            is_correct = (int(mc_selected) == int(mc_correct_idx))
        else:
            check = _check_answer(user_ans, correct_answer)
            is_correct = check['correct']
            is_rounded = check['rounded']

        stats['total_time'] = stats.get('total_time', 0.0) + time_taken

        if is_correct:
            stats['correct'] = stats.get('correct', 0) + 1
            if category in by_cat:
                by_cat[category][1] += 1
            result = 'correct'
            streak = session.get('correct_streak', 0) + 1
            session['correct_streak'] = streak
            session['wrong_streak'] = 0
            if streak >= CORRECT_STREAK_FOR_UPGRADE:
                session['level_modifier'] = min(session.get('level_modifier', 0) + 1, 5)
                session['correct_streak'] = 0
        else:
            stats['wrong'] = stats.get('wrong', 0) + 1
            result = 'wrong'
            streak = session.get('wrong_streak', 0) + 1
            session['wrong_streak'] = streak
            session['correct_streak'] = 0
            if streak >= WRONG_STREAK_FOR_DOWNGRADE:
                session['level_modifier'] = max(session.get('level_modifier', 0) - 1, -3)
                session['wrong_streak'] = 0

    session['stats'] = stats
    session.modified = True

    exact_answer_display = None
    if is_rounded:
        try:
            exact_answer_display = f'{float(str(correct_answer)):.6f}'.rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            exact_answer_display = display_answer

    return jsonify({
        'result': result,
        'display_answer': display_answer,
        'time_taken': round(time_taken, 1),
        'rounded': is_rounded,
        'exact_answer': exact_answer_display,
    })


@app.route('/end-session', methods=['POST'])
def end_session():
    if session.get('mode') != 'practice':
        return jsonify({'redirect': url_for('home')}), 200
    stats = session.get('stats', {})
    session['results'] = compute_practice_stats(stats)
    session['mode'] = 'results'
    session.modified = True
    return jsonify({'redirect': url_for('results')})


# ─── test ─────────────────────────────────────────────────────────────────────

@app.route('/test')
def test():
    if session.get('mode') != 'test':
        return redirect(url_for('home'))
    questions = session.get('test_questions', [])
    start_time = session.get('start_time', time.time())
    difficulty = session.get('difficulty', 'normal')
    return render_template(
        'test.html',
        questions_json=json.dumps(questions),
        total_questions=TEST_QUESTIONS,
        test_duration=TEST_DURATION,
        start_time=start_time,
        difficulty=difficulty,
    )


@app.route('/end-test', methods=['POST'])
def end_test():
    if session.get('mode') != 'test':
        return jsonify({'redirect': url_for('home')}), 200

    data = request.get_json(force=True)
    chosen_answers = data.get('answers', [])   # list of int (option index) or null
    elapsed = float(data.get('elapsed', TEST_DURATION))

    questions = session.get('test_questions', [])
    results = compute_test_stats(questions, chosen_answers, elapsed)

    session['results'] = results
    session['mode'] = 'results'
    session.modified = True
    return jsonify({'redirect': url_for('results')})


# ─── results ──────────────────────────────────────────────────────────────────

@app.route('/results')
def results():
    if session.get('mode') != 'results':
        return redirect(url_for('home'))
    return render_template('results.html', results=session.get('results', {}))


# ─── flagging ─────────────────────────────────────────────────────────────────

@app.route('/flag', methods=['POST'])
def flag():
    data = request.get_json(force=True)
    record = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'game_mode': data.get('game_mode', 'unknown'),
        'difficulty': data.get('difficulty', 'unknown'),
        'question_text': data.get('question_text', ''),
        'correct_answer': data.get('correct_answer', ''),
        'category': data.get('category', 'unknown'),
        'user_comment': data.get('user_comment', ''),
    }
    try:
        existing = []
        if os.path.exists(FLAGGED_FILE):
            with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.append(record)
        with open(FLAGGED_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@app.route('/quit')
def quit_game():
    session.clear()
    return redirect(url_for('home'))


@app.route('/flags')
def flags():
    try:
        if os.path.exists(FLAGGED_FILE):
            with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data = list(reversed(data))
        else:
            data = []
    except Exception:
        data = []
    return render_template('flags.html', flags=data)


# ─── internal helpers ─────────────────────────────────────────────────────────

def _next_practice_question():
    """Pick a category (equal distribution) and return a validated question."""
    category = random.choice(CATEGORIES)
    difficulty = session.get('difficulty', 'normal')
    level_modifier = session.get('level_modifier', 0)
    use_mc = session.get('answer_mode', 'open') == 'mc'
    return get_validated_question(category, difficulty,
                                   level_modifier=level_modifier,
                                   multiple_choice=use_mc)


def _is_terminating_by_decimal_check(v) -> bool:
    """True if v × 10^n is an integer for n = 0..4 (up to 4 decimal places)."""
    try:
        for n in range(5):
            scaled = v * (10 ** n)
            if abs(scaled - round(scaled)) < 1e-6:
                return True
        return False
    except Exception:
        return False


def is_repeating(correct_value) -> bool:
    """Return True if correct_value has a repeating (non-terminating) decimal.

    Two-stage check to avoid float-noise false positives:
    1. If v × 10^n is an integer for n = 0..4, it is terminating → return False.
    2. Otherwise use fraction analysis on a noise-reduced float.
    """
    try:
        v = float(str(correct_value))
        if _is_terminating_by_decimal_check(v):
            return False
        rounded = float(f"{v:.9g}")
        frac = Fraction(rounded).limit_denominator(100000)
        denom = frac.denominator
        while denom % 2 == 0:
            denom //= 2
        while denom % 5 == 0:
            denom //= 5
        return denom != 1
    except Exception:
        return False


def _check_answer(user: str, correct) -> dict:
    """Returns {'correct': bool, 'rounded': bool}.

    Exact match: within 0.2% relative tolerance.
    Rounded match: within 0.005 absolute tolerance — ONLY for repeating
    decimals (e.g. 1/3, 1/6). Terminating decimals (e.g. 0.375) must be
    entered exactly; a rounded value is counted as wrong.
    Also handles fraction strings like '3/4'.
    """
    try:
        user_clean = user.strip().replace(',', '.')
        if '/' in user_clean and not any(c in user_clean for c in ['+', 'x', '*']):
            parts = user_clean.split('/')
            if len(parts) == 2:
                u = float(parts[0].strip()) / float(parts[1].strip())
            else:
                u = float(user_clean)
        else:
            u = float(user_clean)
        c = float(str(correct))
        diff = abs(u - c)
        # Exact match: within 0.2% relative tolerance
        if c == 0:
            is_exact = diff < 1e-6
        else:
            is_exact = diff / max(abs(c), 1e-9) < 0.002
        if is_exact:
            return {'correct': True, 'rounded': False}
        # Rounded match: only for repeating decimals
        if is_repeating(correct) and diff <= 0.005:
            return {'correct': True, 'rounded': True}
        return {'correct': False, 'rounded': False}
    except (ValueError, AttributeError, ZeroDivisionError):
        exact = user.strip() == str(correct).strip()
        return {'correct': exact, 'rounded': False}


def _answers_match(user: str, correct) -> bool:
    """Tolerant numeric comparison (used by test mode)."""
    return _check_answer(user, correct)['correct']


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_ENV') == 'development')
