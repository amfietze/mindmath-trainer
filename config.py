"""
Constants: difficulty params, timing, scoring.
"""

CATEGORIES = ['integers', 'decimals', 'fractions', 'algebra', 'percentages']

# Test Mode
TEST_QUESTIONS = 80
TEST_DURATION = 480          # 8 minutes in seconds
TEST_PASS_THRESHOLD = 56     # points needed to pass

# Practice Mode
PRACTICE_QUESTION_TIME = 10  # seconds per question
PRACTICE_FEEDBACK_DELAY = 1500  # ms before auto-advancing

# Difficulty progression thresholds in Practice Mode
CORRECT_STREAK_FOR_UPGRADE = 5
WRONG_STREAK_FOR_DOWNGRADE = 3

# Question category distribution for Test Mode
TEST_DISTRIBUTION = {
    'easy': [
        ('integers',    0.40),
        ('decimals',    0.20),
        ('fractions',   0.20),
        ('algebra',     0.10),
        ('percentages', 0.10),
    ],
    'medium': [
        ('integers',    0.35),
        ('decimals',    0.22),
        ('fractions',   0.22),
        ('algebra',     0.10),
        ('percentages', 0.11),
    ],
    'normal': [
        ('integers',    0.30),
        ('decimals',    0.25),
        ('fractions',   0.25),
        ('algebra',     0.10),
        ('percentages', 0.10),
    ],
    'hard': [
        ('integers',    0.25),
        ('decimals',    0.30),
        ('fractions',   0.25),
        ('algebra',     0.10),
        ('percentages', 0.10),
    ],
}

CATEGORY_LABELS = {
    'integers':    'Integers',
    'decimals':    'Decimals',
    'fractions':   'Fractions',
    'algebra':     'Algebra',
    'percentages': 'Percentages',
}
