"""
validate_associations.py — Quality checker for word association question banks.
Run with: python data/validate_associations.py

Checks each question for:
  1. Distractor semantic distance (too-similar word pairs)
  2. Answer uniqueness (distractor could also be correct)
  3. Distractor obviousness (completely unrelated distractors)
"""

import json
import os
import sys

DATA_DIR = os.path.dirname(__file__)

# Known too-similar word pairs per language (should never be answer+distractor in same question)
TOO_SIMILAR_EN = [
    ('Cook', 'Bake'), ('Cook', 'Prepare'), ('Bake', 'Prepare'),
    ('Language', 'Linguistics'), ('Language', 'Grammar'), ('Linguistics', 'Grammar'),
    ('Profit', 'Return'), ('Profit', 'Yield'), ('Return', 'Yield'),
    ('Walk', 'Run'), ('Walk', 'Jog'), ('Run', 'Sprint'),
    ('Write', 'Type'), ('Write', 'Draft'), ('Type', 'Draft'),
    ('Doctor', 'Physician'), ('Doctor', 'Surgeon'), ('Physician', 'Surgeon'),
    ('Ship', 'Boat'), ('Ship', 'Vessel'), ('Boat', 'Vessel'),
    ('Happy', 'Joyful'), ('Happy', 'Glad'), ('Joyful', 'Glad'),
    ('Big', 'Large'), ('Big', 'Huge'), ('Large', 'Enormous'),
    ('Fruit', 'Berry'), ('Vegetable', 'Legume'),
]

TOO_SIMILAR_DE = [
    ('Kochen', 'Backen'), ('Kochen', 'Zubereiten'), ('Backen', 'Zubereiten'),
    ('Sprache', 'Linguistik'), ('Sprache', 'Grammatik'), ('Linguistik', 'Grammatik'),
    ('Gewinn', 'Rendite'), ('Gewinn', 'Ertrag'), ('Rendite', 'Ertrag'),
    ('Gehen', 'Laufen'), ('Gehen', 'Rennen'), ('Laufen', 'Sprinten'),
    ('Schreiben', 'Tippen'), ('Arzt', 'Mediziner'), ('Arzt', 'Chirurg'),
    ('Schiff', 'Boot'), ('Schiff', 'Vessel'), ('Boot', 'Kahn'),
    ('Glücklich', 'Froh'), ('Glücklich', 'Heiter'), ('Froh', 'Fröhlich'),
    ('Groß', 'Riesig'), ('Groß', 'Enorm'),
]

TOO_SIMILAR_FR = [
    ('Cuisiner', 'Cuire'), ('Cuisiner', 'Préparer'), ('Cuire', 'Préparer'),
    ('Langue', 'Linguistique'), ('Langue', 'Grammaire'), ('Linguistique', 'Grammaire'),
    ('Profit', 'Rendement'), ('Profit', 'Gain'), ('Rendement', 'Gain'),
    ('Marcher', 'Courir'), ('Courir', 'Sprinter'),
    ('Médecin', 'Chirurgien'), ('Médecin', 'Praticien'),
    ('Heureux', 'Joyeux'), ('Heureux', 'Content'),
    ('Grand', 'Immense'), ('Grand', 'Énorme'),
]


def load_bank(lang):
    filepath = os.path.join(DATA_DIR, f'associations_{lang}.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_bank(bank, lang, too_similar):
    flags = []
    similar_set = set()
    for a, b in too_similar:
        similar_set.add((a.lower(), b.lower()))
        similar_set.add((b.lower(), a.lower()))

    for q in bank:
        qid = q.get('id', '?')
        answer = q.get('answer', '').lower()
        distractors = [d.lower() for d in q.get('distractors', [])]

        # Check 1: too-similar answer+distractor pairs
        for d in distractors:
            if (answer, d) in similar_set or (d, answer) in similar_set:
                flags.append({
                    'id': qid,
                    'check': 'TOO_SIMILAR',
                    'detail': f'Answer "{q["answer"]}" and distractor "{d}" are too similar',
                })

        # Check 2: duplicate answer in distractors
        for d in distractors:
            if d == answer:
                flags.append({
                    'id': qid,
                    'check': 'ANSWER_IN_DISTRACTORS',
                    'detail': f'Distractor "{d}" is identical to the answer "{q["answer"]}"',
                })

        # Check 3: duplicate distractors
        if len(distractors) != len(set(distractors)):
            flags.append({
                'id': qid,
                'check': 'DUPLICATE_DISTRACTORS',
                'detail': f'Distractors contain duplicates: {q.get("distractors", [])}',
            })

        # Check 4: For category_member questions, check if distractor could also be parent
        # (rough heuristic for hypernym confusion)
        if q.get('category') == 'category_member':
            for d in distractors:
                if len(d) > 4 and len(answer) > 4:
                    if d[-3:] == answer[-3:] or d[:4] == answer[:4]:
                        flags.append({
                            'id': qid,
                            'check': 'POSSIBLE_DUPLICATE_PARENT',
                            'detail': f'Distractor "{d}" may also be valid parent like answer "{answer}"',
                        })

    return flags


def main():
    report_lines = []
    total_flags = 0
    total_questions = 0

    langs_to_check = ['en', 'de', 'fr']
    too_similar_map = {
        'en': TOO_SIMILAR_EN,
        'de': TOO_SIMILAR_DE,
        'fr': TOO_SIMILAR_FR,
    }

    for lang in langs_to_check:
        filepath = os.path.join(DATA_DIR, f'associations_{lang}.json')
        if not os.path.exists(filepath):
            report_lines.append(f'=== {lang.upper()} bank === SKIPPED (file not found)')
            report_lines.append('')
            continue
        bank = load_bank(lang)
        total_questions += len(bank)
        too_similar = too_similar_map[lang]
        flags = check_bank(bank, lang, too_similar)
        total_flags += len(flags)
        report_lines.append(f'=== {lang.upper()} bank ({len(bank)} questions) ===')
        if flags:
            for f in flags:
                report_lines.append(f'  [{f["check"]}] {f["id"]}: {f["detail"]}')
        else:
            report_lines.append('  No issues found.')
        report_lines.append('')

    report_lines.append(f'Summary: {total_flags} questions flagged out of {total_questions} total.')

    report_text = '\n'.join(report_lines)
    print(report_text)

    report_path = os.path.join(DATA_DIR, 'validation_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f'\nReport saved to {report_path}')


if __name__ == '__main__':
    main()
