"""
MindMath Trainer – Flask application.
All routes live here.
"""

import os
import json
import time
import random
from datetime import datetime
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify)

from config import (CATEGORIES, TEST_QUESTIONS, TEST_DURATION,
                    PRACTICE_QUESTION_TIME, PRACTICE_FEEDBACK_DELAY,
                    CORRECT_STREAK_FOR_UPGRADE, WRONG_STREAK_FOR_DOWNGRADE)
from question_engine import generate_question, generate_test_questions
from scoring import compute_practice_stats, compute_test_stats

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mindmath-dev-secret-change-in-prod')

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

    session.clear()

    if mode == 'practice':
        session['mode'] = 'practice'
        session['difficulty'] = difficulty
        session['level_modifier'] = 0
        session['correct_streak'] = 0
        session['wrong_streak'] = 0
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
    return render_template(
        'practice.html',
        question=q,
        question_time=PRACTICE_QUESTION_TIME,
        feedback_delay=PRACTICE_FEEDBACK_DELAY,
        difficulty=session.get('difficulty', 'normal'),
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

    if skipped:
        stats['skipped'] = stats.get('skipped', 0) + 1
        result = 'skipped'
    else:
        is_correct = _answers_match(user_ans, correct_answer)
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

    return jsonify({
        'result': result,
        'display_answer': display_answer,
        'time_taken': round(time_taken, 1),
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
    """Pick a category (equal distribution for now) and generate a question."""
    category = random.choice(CATEGORIES)
    difficulty = session.get('difficulty', 'normal')
    level_modifier = session.get('level_modifier', 0)
    return generate_question(category, difficulty,
                             level_modifier=level_modifier,
                             multiple_choice=False)


def _answers_match(user: str, correct) -> bool:
    """Tolerant numeric comparison."""
    try:
        u = float(user.replace(',', '.'))
        c = float(str(correct))
        if c == 0:
            return abs(u) < 1e-6
        return abs(u - c) / max(abs(c), 1e-9) < 0.002
    except (ValueError, AttributeError):
        return user.strip() == str(correct).strip()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
