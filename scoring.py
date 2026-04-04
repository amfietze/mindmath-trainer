"""
Score calculation and per-session statistics helpers.
"""

from config import CATEGORIES, CATEGORY_LABELS, TEST_PASS_THRESHOLD


def compute_practice_stats(stats):
    """
    Turn raw session stats dict into a results dict for the results template.
    stats = {
        total, correct, wrong, skipped, total_time,
        by_category: {cat: [total, correct], ...}
    }
    """
    total = max(stats.get('total', 0), 1)
    correct = stats.get('correct', 0)
    wrong = stats.get('wrong', 0)
    skipped = stats.get('skipped', 0)
    total_time = stats.get('total_time', 0.0)
    answered = correct + wrong
    avg_time = round(total_time / answered, 1) if answered > 0 else 0.0

    cat_rows = []
    for cat in CATEGORIES:
        vals = stats.get('by_category', {}).get(cat, [0, 0])
        cat_total, cat_correct = vals[0], vals[1]
        pct = round(cat_correct / cat_total * 100) if cat_total > 0 else None
        cat_rows.append({
            'label': CATEGORY_LABELS[cat],
            'total': cat_total,
            'correct': cat_correct,
            'pct': pct,
        })

    return {
        'mode': 'practice',
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'skipped': skipped,
        'correct_pct': round(correct / total * 100),
        'wrong_pct': round(wrong / total * 100),
        'skipped_pct': round(skipped / total * 100),
        'avg_time': avg_time,
        'categories': cat_rows,
    }


def compute_test_stats(questions, chosen_answers, total_time):
    """
    Compute test results.
    questions     – list of 80 question dicts (with correct_index)
    chosen_answers – list of 80 chosen option indices (int) or None for skip
    total_time    – seconds elapsed
    Returns results dict for the results template.
    """
    n = len(questions)
    correct = 0
    wrong = 0
    skipped = 0
    score = 0

    cat_counts = {cat: [0, 0] for cat in CATEGORIES}  # [total, correct]

    for i, q in enumerate(questions):
        cat = q.get('category', 'integers')
        chosen = chosen_answers[i] if i < len(chosen_answers) else None

        if cat in cat_counts:
            cat_counts[cat][0] += 1

        if chosen is None:
            skipped += 1
            # score += 0
        elif chosen == q.get('correct_index'):
            correct += 1
            score += 1
            if cat in cat_counts:
                cat_counts[cat][1] += 1
        else:
            wrong += 1
            score -= 1

    answered = correct + wrong
    avg_time = round(total_time / n, 1) if n > 0 else 0.0

    cat_rows = []
    for cat in CATEGORIES:
        ct, cc = cat_counts[cat]
        pct = round(cc / ct * 100) if ct > 0 else None
        cat_rows.append({
            'label': CATEGORY_LABELS[cat],
            'total': ct,
            'correct': cc,
            'pct': pct,
        })

    return {
        'mode': 'test',
        'total': n,
        'correct': correct,
        'wrong': wrong,
        'skipped': skipped,
        'score': score,
        'max_score': n,
        'pass_threshold': TEST_PASS_THRESHOLD,
        'passed': score >= TEST_PASS_THRESHOLD,
        'avg_time': avg_time,
        'categories': cat_rows,
    }
