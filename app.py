"""
MindMath Trainer – Flask application.
All routes live here.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import json
import time
import random
from datetime import datetime
from fractions import Fraction
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify)

from config import (CATEGORIES, BASE_CATEGORIES, TEST_QUESTIONS, TEST_DURATION,
                    PRACTICE_QUESTION_TIME, PRACTICE_FEEDBACK_DELAY,
                    CORRECT_STREAK_FOR_UPGRADE, WRONG_STREAK_FOR_DOWNGRADE)
from question_engine import get_validated_question, generate_test_questions
from scoring import compute_practice_stats, compute_test_stats
from sequence_engine import get_sequence_question, attach_sequence_options
from association_engine import load_bank, get_association_question, check_association_answer

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


# ─── home (game launcher) ─────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')


# ─── arithmetic settings ──────────────────────────────────────────────────────

@app.route('/arithmetic')
def arithmetic():
    return render_template('arithmetic.html')


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
        session['question_log'] = []
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
        session['question_log'] = []
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

    # Append to question log
    if skipped:
        log_user_answer = '—'
    elif mc_selected is not None:
        options = current_q.get('options', [])
        mc_idx = int(mc_selected)
        log_user_answer = options[mc_idx] if mc_idx < len(options) else str(mc_selected)
    else:
        log_user_answer = user_ans if user_ans else '—'

    q_log = session.get('question_log', [])
    q_log.append({
        'number': stats.get('total', 0),
        'question_text': current_q.get('text', ''),
        'category': current_q.get('category', ''),
        'difficulty': session.get('difficulty', 'normal'),
        'user_answer': log_user_answer,
        'correct_answer': str(display_answer),
        'result': result,
        'time_taken': round(time_taken, 1),
    })
    session['question_log'] = q_log
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

    # Build question log for test mode
    difficulty = session.get('difficulty', 'normal')
    question_log = []
    for i, q in enumerate(questions):
        chosen_idx = chosen_answers[i] if i < len(chosen_answers) else None
        correct_idx = q.get('correct_index')
        options = q.get('options', [])
        correct_display = (options[correct_idx]
                           if correct_idx is not None and correct_idx < len(options)
                           else str(q.get('display_answer', '')))
        if chosen_idx is None:
            q_result = 'skipped'
            user_answer = '—'
        elif chosen_idx == correct_idx:
            q_result = 'correct'
            user_answer = options[chosen_idx] if chosen_idx < len(options) else str(chosen_idx)
        else:
            q_result = 'wrong'
            user_answer = options[chosen_idx] if chosen_idx < len(options) else str(chosen_idx)
        question_log.append({
            'number': i + 1,
            'question_text': q.get('text', ''),
            'category': q.get('category', ''),
            'difficulty': difficulty,
            'user_answer': user_answer,
            'correct_answer': correct_display,
            'result': q_result,
            'time_taken': None,
        })
    session['question_log'] = question_log
    session['results'] = results
    session['mode'] = 'results'
    session.modified = True
    return jsonify({'redirect': url_for('results')})


# ─── results ──────────────────────────────────────────────────────────────────

@app.route('/results')
def results():
    if session.get('mode') != 'results':
        return redirect(url_for('home'))
    res = session.get('results', {})
    # Inject difficulty into results dict for template use (flagging, display)
    if 'difficulty' not in res:
        res = dict(res, difficulty=session.get('difficulty', 'normal'))
    return render_template('results.html',
                           results=res,
                           question_log=session.get('question_log', []))


@app.route('/restart', methods=['POST'])
def restart():
    """Re-start arithmetic session with the same settings that were used."""
    prev = session.get('results', {})
    diff = prev.get('difficulty', session.get('difficulty', 'normal'))
    mode = prev.get('mode', 'practice')
    qt = session.get('question_time', PRACTICE_QUESTION_TIME)
    answer_mode = session.get('answer_mode', 'open')

    session.clear()
    if mode == 'test':
        seed = random.randint(0, 999_999)
        questions = generate_test_questions(seed, diff, TEST_QUESTIONS)
        session['mode'] = 'test'
        session['difficulty'] = diff
        session['seed'] = seed
        session['test_questions'] = questions
        session['question_log'] = []
        session['start_time'] = time.time()
        return redirect(url_for('test'))
    else:
        session['mode'] = 'practice'
        session['difficulty'] = diff
        session['level_modifier'] = 0
        session['correct_streak'] = 0
        session['wrong_streak'] = 0
        session['question_time'] = qt
        session['answer_mode'] = answer_mode
        session['stats'] = {
            'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0,
            'total_time': 0.0, 'by_category': {cat: [0, 0] for cat in CATEGORIES},
        }
        session['question_log'] = []
        first_q = _next_practice_question()
        session['current_q'] = first_q
        return redirect(url_for('practice'))


# ─── flagging ─────────────────────────────────────────────────────────────────

@app.route('/flag', methods=['POST'])
def flag():
    data = request.get_json(force=True)
    record = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'game_mode': str(data.get('game_mode', 'unknown')),
        'difficulty': str(data.get('difficulty', 'unknown')),
        'question_text': str(data.get('question_text', '')),
        'correct_answer': str(data.get('correct_answer', '')),
        'category': str(data.get('category', 'unknown')),
        'user_comment': str(data.get('user_comment', '')),
    }
    try:
        existing = []
        if os.path.exists(FLAGGED_FILE):
            try:
                with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except json.JSONDecodeError as exc:
                print(f'WARNING: flagged_questions.json malformed, starting fresh: {exc}',
                      file=sys.stderr)
                existing = []
        existing.append(record)
        tmp_path = FLAGGED_FILE + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, FLAGGED_FILE)
        return jsonify({'success': True})
    except Exception as exc:
        print(f'ERROR: /flag write failed: {exc}', file=sys.stderr)
        return jsonify({'error': str(exc)}), 500


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
    except json.JSONDecodeError as exc:
        print(f'ERROR: flagged_questions.json malformed: {exc}', file=sys.stderr)
        data = []
    except Exception as exc:
        print(f'ERROR: reading flagged_questions.json: {exc}', file=sys.stderr)
        data = []
    return render_template('flags.html', flags=data)


@app.route('/flags/delete', methods=['POST'])
def flags_delete():
    data = request.get_json(force=True)
    try:
        idx = int(data.get('index', -1))
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid index'}), 400

    if idx < 0:
        return jsonify({'error': 'invalid index'}), 400

    try:
        if not os.path.exists(FLAGGED_FILE):
            return jsonify({'success': True, 'remaining': 0})

        with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)

        # The page shows flags in reverse order; idx 0 = newest = last in file
        rev = list(reversed(existing))
        if idx >= len(rev):
            return jsonify({'error': 'index out of range'}), 400

        del rev[idx]
        existing = list(reversed(rev))

        with open(FLAGGED_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        return jsonify({'success': True, 'remaining': len(existing)})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ─── sequences ────────────────────────────────────────────────────────────────

@app.route('/sequences')
def sequences():
    return render_template('sequence_home.html')


@app.route('/sequences/start', methods=['POST'])
def sequences_start():
    difficulty = request.form.get('difficulty', 'normal')
    answer_mode = request.form.get('answer_mode', 'mc')
    mode = request.form.get('mode', 'practice')

    if mode == 'test':
        session['seq_difficulty'] = difficulty
        session['seq_mode'] = 'test'
        session['seq_test_score'] = 0
        session['seq_test_total'] = 0
        session['seq_test_correct'] = 0
        session['seq_test_wrong'] = 0
        session['seq_test_skipped'] = 0
        session['seq_question_log'] = []
        session.modified = True
        return redirect(url_for('sequences_test'))

    session['seq_difficulty'] = difficulty
    session['seq_answer_mode'] = answer_mode
    session['seq_mode'] = 'practice'
    session['seq_stats'] = {
        'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0,
        'total_time': 0.0, 'by_type': {},
    }
    session['seq_question_log'] = []
    session['seq_current'] = _next_seq_question()
    session.modified = True
    return redirect(url_for('sequences_play'))


@app.route('/sequences/play')
def sequences_play():
    if 'seq_current' not in session:
        return redirect(url_for('sequences'))
    return render_template(
        'sequence.html',
        question=session['seq_current'],
        stats=session.get('seq_stats', {}),
        difficulty=session.get('seq_difficulty', 'normal'),
        answer_mode=session.get('seq_answer_mode', 'mc'),
    )


@app.route('/sequences/next', methods=['POST'])
def sequences_next():
    if 'seq_difficulty' not in session:
        return jsonify({'error': 'no active sequence session'}), 400
    q = _next_seq_question()
    session['seq_current'] = q
    session.modified = True
    return jsonify(q)


@app.route('/sequences/submit', methods=['POST'])
def sequences_submit():
    if 'seq_difficulty' not in session:
        return jsonify({'error': 'no active sequence session'}), 400

    data = request.get_json(force=True)
    skipped = bool(data.get('skipped', False))
    time_taken = float(data.get('time_taken', 0))

    current_q = session.get('seq_current', {})
    correct_answer = current_q.get('answer', '')
    seq_type = current_q.get('sequence_type', 'unknown')
    seq_display = current_q.get('sequence_display', [])

    stats = session.get('seq_stats', {})
    by_type = stats.setdefault('by_type', {})

    stats['total'] = stats.get('total', 0) + 1

    if skipped:
        stats['skipped'] = stats.get('skipped', 0) + 1
        result = 'skipped'
        log_user_answer = '—'
    else:
        mc_selected = data.get('mc_selected_index')
        mc_correct = data.get('mc_correct_index')
        if mc_selected is not None and mc_correct is not None:
            is_correct = (int(mc_selected) == int(mc_correct))
            options = current_q.get('options', [])
            log_user_answer = (options[int(mc_selected)]
                               if int(mc_selected) < len(options)
                               else str(mc_selected))
        else:
            user_ans = str(data.get('user_answer', '')).strip()
            is_correct = _check_sequence_answer(user_ans, correct_answer)
            log_user_answer = user_ans if user_ans else '—'

        stats['total_time'] = stats.get('total_time', 0.0) + time_taken

        if is_correct:
            stats['correct'] = stats.get('correct', 0) + 1
            result = 'correct'
        else:
            stats['wrong'] = stats.get('wrong', 0) + 1
            result = 'wrong'

        # Track by sequence type (only non-skipped answers)
        if seq_type not in by_type:
            by_type[seq_type] = [0, 0]
        by_type[seq_type][0] += 1
        if is_correct:
            by_type[seq_type][1] += 1

    session['seq_stats'] = stats

    # Append to question log
    q_log = session.get('seq_question_log', [])
    q_log.append({
        'number': stats.get('total', 0),
        'sequence_display': seq_display,
        'sequence_type': seq_type,
        'category': current_q.get('category', ''),
        'rule_description': current_q.get('rule_description', ''),
        'user_answer': log_user_answer,
        'correct_answer': correct_answer,
        'result': result,
        'time_taken': round(time_taken, 1) if not skipped else None,
    })
    session['seq_question_log'] = q_log
    session.modified = True

    return jsonify({'result': result, 'correct_answer': correct_answer})


@app.route('/sequences/end', methods=['POST'])
def sequences_end():
    stats = session.get('seq_stats', {})
    total = stats.get('total', 0)
    answered = total - stats.get('skipped', 0)
    total_time = stats.get('total_time', 0.0)
    avg_time = round(total_time / answered, 1) if answered > 0 else None

    session['seq_results'] = {
        'mode': 'practice',
        'total': total,
        'correct': stats.get('correct', 0),
        'wrong': stats.get('wrong', 0),
        'skipped': stats.get('skipped', 0),
        'avg_time': avg_time,
        'by_type': stats.get('by_type', {}),
        'difficulty': session.get('seq_difficulty', 'normal'),
        'answer_mode': session.get('seq_answer_mode', 'mc'),
    }
    session.modified = True
    return jsonify({'redirect': url_for('sequences_results')})


@app.route('/sequences/results')
def sequences_results():
    if 'seq_results' not in session:
        return redirect(url_for('sequences'))
    return render_template(
        'sequence_results.html',
        results=session.get('seq_results', {}),
        question_log=session.get('seq_question_log', []),
    )


@app.route('/sequences/restart', methods=['POST'])
def sequences_restart():
    """Re-start sequences session with the same settings."""
    prev = session.get('seq_results', {})
    diff = prev.get('difficulty', session.get('seq_difficulty', 'normal'))
    mode = prev.get('mode', 'practice')
    answer_mode = prev.get('answer_mode', session.get('seq_answer_mode', 'mc'))

    if mode == 'test':
        session['seq_difficulty'] = diff
        session['seq_mode'] = 'test'
        session['seq_test_score'] = 0
        session['seq_test_total'] = 0
        session['seq_test_correct'] = 0
        session['seq_test_wrong'] = 0
        session['seq_test_skipped'] = 0
        session['seq_question_log'] = []
        # Clear old results so the test screen guard passes
        session.pop('seq_results', None)
        session.modified = True
        return redirect(url_for('sequences_test'))
    else:
        session['seq_difficulty'] = diff
        session['seq_answer_mode'] = answer_mode
        session['seq_mode'] = 'practice'
        session['seq_stats'] = {
            'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0,
            'total_time': 0.0, 'by_type': {},
        }
        session['seq_question_log'] = []
        session['seq_current'] = _next_seq_question()
        session.pop('seq_results', None)
        session.modified = True
        return redirect(url_for('sequences_play'))


# ─── sequences test mode ──────────────────────────────────────────────────────

SEQ_TEST_DURATION = 480  # 8 minutes in seconds


@app.route('/sequences/test')
def sequences_test():
    if session.get('seq_mode') != 'test' or 'seq_difficulty' not in session:
        return redirect(url_for('sequences'))
    first_q = _next_seq_test_question()
    session['seq_test_start'] = time.time()
    session['seq_current'] = first_q
    session.modified = True
    return render_template(
        'sequence_test.html',
        question=first_q,
        difficulty=session.get('seq_difficulty', 'normal'),
        test_duration=SEQ_TEST_DURATION,
        start_time=session['seq_test_start'],
    )


@app.route('/sequences/test/next', methods=['POST'])
def sequences_test_next():
    if session.get('seq_mode') != 'test':
        return jsonify({'error': 'not in sequence test mode'}), 400
    q = _next_seq_test_question()
    session['seq_current'] = q
    session.modified = True
    return jsonify(q)


@app.route('/sequences/test/submit', methods=['POST'])
def sequences_test_submit():
    if session.get('seq_mode') != 'test':
        return jsonify({'error': 'not in sequence test mode'}), 400

    data = request.get_json(force=True)
    is_correct = bool(data.get('is_correct', False))
    skipped = bool(data.get('skipped', False))
    question_data = data.get('question_data', {})

    total = session.get('seq_test_total', 0) + 1
    score = session.get('seq_test_score', 0)
    correct = session.get('seq_test_correct', 0)
    wrong = session.get('seq_test_wrong', 0)
    skipped_count = session.get('seq_test_skipped', 0)

    if skipped:
        skipped_count += 1
        result = 'skipped'
        log_user_answer = '—'
    elif is_correct:
        score += 1
        correct += 1
        result = 'correct'
        options = question_data.get('options', [])
        mc_idx = data.get('mc_selected_index')
        log_user_answer = (options[int(mc_idx)] if mc_idx is not None and int(mc_idx) < len(options)
                           else str(data.get('answer', '—')))
    else:
        score -= 1
        wrong += 1
        result = 'wrong'
        options = question_data.get('options', [])
        mc_idx = data.get('mc_selected_index')
        log_user_answer = (options[int(mc_idx)] if mc_idx is not None and int(mc_idx) < len(options)
                           else str(data.get('answer', '—')))

    session['seq_test_total'] = total
    session['seq_test_score'] = score
    session['seq_test_correct'] = correct
    session['seq_test_wrong'] = wrong
    session['seq_test_skipped'] = skipped_count

    # Append to question log
    q_log = session.get('seq_question_log', [])
    q_log.append({
        'number': total,
        'sequence_display': question_data.get('sequence_display', []),
        'sequence_type': question_data.get('sequence_type', ''),
        'category': question_data.get('category', ''),
        'rule_description': question_data.get('rule_description', ''),
        'user_answer': log_user_answer,
        'correct_answer': question_data.get('answer', ''),
        'result': result,
        'time_taken': None,
    })
    session['seq_question_log'] = q_log
    session.modified = True

    return jsonify({
        'score': score,
        'total': total,
        'correct': correct,
        'wrong': wrong,
    })


@app.route('/sequences/test/end', methods=['POST'])
def sequences_test_end():
    if session.get('seq_mode') != 'test':
        return jsonify({'redirect': url_for('sequences')}), 200

    score = session.get('seq_test_score', 0)
    total = session.get('seq_test_total', 0)
    correct = session.get('seq_test_correct', 0)
    wrong = session.get('seq_test_wrong', 0)
    skipped = session.get('seq_test_skipped', 0)
    difficulty = session.get('seq_difficulty', 'normal')

    # Performance band
    if score >= 40:
        performance = 'Excellent'
        perf_class = 'perf-excellent'
    elif score >= 30:
        performance = 'Great'
        perf_class = 'perf-great'
    elif score >= 20:
        performance = 'Good'
        perf_class = 'perf-good'
    elif score >= 10:
        performance = 'Getting there'
        perf_class = 'perf-getting'
    else:
        performance = 'Keep practising'
        perf_class = 'perf-keep'

    session['seq_results'] = {
        'mode': 'test',
        'score': score,
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'skipped': skipped,
        'avg_time': None,
        'by_type': {},
        'difficulty': difficulty,
        'answer_mode': 'mc',
        'performance': performance,
        'perf_class': perf_class,
    }
    session.modified = True
    return jsonify({'redirect': url_for('sequences_results')})


# ─── internal helpers ─────────────────────────────────────────────────────────

def _next_practice_question():
    """Pick a category (equal distribution) and return a validated question.

    Normal/Hard draw from all categories, including the Normal/Hard-only
    exponents_roots and ratios_proportions categories; Easy/Medium draw
    from BASE_CATEGORIES only.
    """
    difficulty = session.get('difficulty', 'normal')
    pool = CATEGORIES if difficulty in ('normal', 'hard') else BASE_CATEGORIES
    category = random.choice(pool)
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


def _next_seq_question() -> dict:
    """Generate a sequence question (with MC options if needed)."""
    difficulty = session.get('seq_difficulty', 'normal')
    answer_mode = session.get('seq_answer_mode', 'mc')
    rng = random.Random()
    q = get_sequence_question(difficulty, rng)
    if answer_mode == 'mc':
        q = attach_sequence_options(q, rng)
    return q


def _next_seq_test_question() -> dict:
    """Generate a sequence question for test mode (always MC)."""
    difficulty = session.get('seq_difficulty', 'normal')
    rng = random.Random()
    q = get_sequence_question(difficulty, rng)
    q = attach_sequence_options(q, rng)
    return q


def _check_sequence_answer(user: str, correct: str) -> bool:
    """Exact match for sequence answers — no repeating-decimal tolerance."""
    user = user.strip().upper()
    correct = correct.strip().upper()
    if user == correct:
        return True
    try:
        return abs(float(user) - float(correct)) < 0.001
    except (ValueError, TypeError):
        return False


# ─── word associations ────────────────────────────────────────────────────────

@app.route('/associations')
def associations():
    return render_template('association_home.html')


@app.route('/associations/start', methods=['POST'])
def associations_start():
    language = request.form.get('language', 'en')
    if language not in ('en', 'de', 'fr'):
        language = 'en'

    session['assoc_language'] = language
    session['assoc_used_ids'] = []
    session['assoc_stats'] = {'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0}
    session['assoc_question_log'] = []

    rng = random.Random()
    q = get_association_question(language, rng, exclude_ids=[])
    session['assoc_current'] = q
    session['assoc_used_ids'] = [q['id']]
    session.modified = True
    return redirect(url_for('associations_play'))


@app.route('/associations/play')
def associations_play():
    if 'assoc_current' not in session:
        return redirect(url_for('associations'))
    return render_template(
        'association.html',
        question=session['assoc_current'],
        stats=session.get('assoc_stats', {}),
        language=session.get('assoc_language', 'en'),
    )


@app.route('/associations/next', methods=['POST'])
def associations_next():
    if 'assoc_language' not in session:
        return jsonify({'error': 'no active association session'}), 400

    language = session['assoc_language']
    used_ids = session.get('assoc_used_ids', [])
    rng = random.Random()
    q = get_association_question(language, rng, exclude_ids=used_ids)

    # Append new ID (reset detection: if bank was exhausted, used_ids may not contain it)
    if q['id'] not in used_ids:
        used_ids.append(q['id'])
    else:
        # Bank was exhausted and restarted — clear used list, start fresh
        used_ids = [q['id']]

    session['assoc_current'] = q
    session['assoc_used_ids'] = used_ids
    session.modified = True
    return jsonify(q)


@app.route('/associations/submit', methods=['POST'])
def associations_submit():
    if 'assoc_language' not in session:
        return jsonify({'error': 'no active association session'}), 400

    data = request.get_json(force=True)
    user_answer = str(data.get('user_answer', '')).strip()
    time_taken = data.get('time_taken')
    skipped = bool(data.get('skipped', False))

    current_q = session.get('assoc_current', {})
    correct_answer = current_q.get('answer', '')

    stats = session.get('assoc_stats', {'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0})
    stats['total'] = stats.get('total', 0) + 1

    if skipped:
        stats['skipped'] = stats.get('skipped', 0) + 1
        result = 'skipped'
        log_user_answer = '—'
    else:
        is_correct = check_association_answer(user_answer, correct_answer)
        if is_correct:
            stats['correct'] = stats.get('correct', 0) + 1
            result = 'correct'
        else:
            stats['wrong'] = stats.get('wrong', 0) + 1
            result = 'wrong'
        log_user_answer = user_answer if user_answer else '—'

    session['assoc_stats'] = stats

    q_log = session.get('assoc_question_log', [])
    q_log.append({
        'number': stats['total'],
        'prompt_a1': current_q.get('prompt_a1', ''),
        'prompt_a2': current_q.get('prompt_a2', ''),
        'prompt_b1': current_q.get('prompt_b1', ''),
        'answer': correct_answer,
        'user_answer': log_user_answer,
        'result': result,
        'relationship': current_q.get('relationship', ''),
        'category': current_q.get('category', ''),
        'time_taken': round(float(time_taken), 1) if time_taken is not None else None,
    })
    session['assoc_question_log'] = q_log
    session.modified = True

    return jsonify({'correct': result == 'correct', 'correct_answer': correct_answer, 'result': result})


@app.route('/associations/end', methods=['POST'])
def associations_end():
    stats = session.get('assoc_stats', {})
    session['assoc_results'] = {
        'total': stats.get('total', 0),
        'correct': stats.get('correct', 0),
        'wrong': stats.get('wrong', 0),
        'skipped': stats.get('skipped', 0),
        'language': session.get('assoc_language', 'en'),
    }
    session.modified = True
    return jsonify({'redirect': url_for('associations_results')})


@app.route('/associations/restart', methods=['POST'])
def associations_restart():
    """Re-start word associations session with the same language."""
    prev = session.get('assoc_results', {})
    language = prev.get('language', session.get('assoc_language', 'en'))
    if language not in ('en', 'de', 'fr'):
        language = 'en'

    session['assoc_language'] = language
    session['assoc_used_ids'] = []
    session['assoc_stats'] = {'total': 0, 'correct': 0, 'wrong': 0, 'skipped': 0}
    session['assoc_question_log'] = []
    session.pop('assoc_results', None)

    rng = random.Random()
    q = get_association_question(language, rng, exclude_ids=[])
    session['assoc_current'] = q
    session['assoc_used_ids'] = [q['id']]
    session.modified = True
    return redirect(url_for('associations_play'))


@app.route('/associations/results')
def associations_results():
    if 'assoc_results' not in session:
        return redirect(url_for('associations'))

    # Build category breakdown from question log
    q_log = session.get('assoc_question_log', [])
    by_category = {}
    for entry in q_log:
        cat = entry.get('category', 'unknown')
        if cat not in by_category:
            by_category[cat] = [0, 0]  # [total, correct]
        by_category[cat][0] += 1
        if entry.get('result') == 'correct':
            by_category[cat][1] += 1

    return render_template(
        'association_results.html',
        results=session.get('assoc_results', {}),
        question_log=q_log,
        by_category=by_category,
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_ENV') == 'development')
