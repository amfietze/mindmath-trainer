"""
Association Engine — loads verbal analogy question bank, serves questions,
attaches shuffled multiple-choice options, validates answers.
"""

import json
import os
import copy

# Module-level cache: { 'en': [...], 'de': [...] }
_BANK_CACHE: dict = {}

_DATA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'data')


def load_bank(language: str = 'en') -> list:
    """Load and return the full question list for the given language.

    Results are cached in _BANK_CACHE so the JSON file is only read once
    per language per process lifetime.

    Args:
        language: 'en' or 'de'

    Returns:
        List of question dicts.

    Raises:
        FileNotFoundError: if the question bank file does not exist.
        ValueError: if the language code is unsupported.
    """
    if language not in ('en', 'de', 'fr'):
        raise ValueError(f"Unsupported language '{language}'. Use 'en', 'de', or 'fr'.")

    if language in _BANK_CACHE:
        return _BANK_CACHE[language]

    filename = f'associations_{language}.json'
    filepath = os.path.join(_DATA_DIR, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Question bank not found: {filepath}. "
            f"Expected file data/associations_{language}.json in the project directory."
        )

    with open(filepath, 'r', encoding='utf-8') as f:
        bank = json.load(f)

    _BANK_CACHE[language] = bank
    return bank


def get_association_question(language: str, rng, exclude_ids: list = None) -> dict:
    """Select a random question, attach shuffled MC options, and return.

    Args:
        language: 'en' or 'de'
        rng: a random.Random instance (for reproducibility / seeding)
        exclude_ids: list of question IDs to skip (already used in session).
                     If all IDs are excluded, resets and starts over.

    Returns:
        A copy of the question dict with an added 'options' key
        (list of 4 strings: answer + 3 distractors, shuffled) and a
        'correct_index' key (int, position of correct answer in options).
    """
    bank = load_bank(language)

    if exclude_ids is None:
        exclude_ids = []

    # Find available questions
    available = [q for q in bank if q['id'] not in exclude_ids]

    # If all exhausted, reset and use full bank
    if not available:
        available = bank

    question = rng.choice(available)
    return _attach_options(question, rng)


def _attach_options(question: dict, rng) -> dict:
    """Return a copy of the question with 'options' and 'correct_index' added.

    Options = [answer] + distractors[:3], then shuffled.
    """
    q = copy.deepcopy(question)

    answer = q['answer']
    distractors = q.get('distractors', [])[:3]

    # Build the 4-option list
    options = [answer] + distractors
    # Ensure exactly 4 options (pad with empty strings if somehow fewer)
    while len(options) < 4:
        options.append('—')

    rng.shuffle(options)

    q['options'] = options
    q['correct_index'] = options.index(answer)
    return q


def check_association_answer(user_answer: str, correct_answer: str) -> bool:
    """Case-insensitive exact string match after stripping whitespace.

    Args:
        user_answer: the answer string chosen by the user
        correct_answer: the correct answer string from the question dict

    Returns:
        True if the answers match (case-insensitive, whitespace-stripped).
    """
    return user_answer.strip().lower() == correct_answer.strip().lower()
