"""
Constants: difficulty params, timing, scoring.
"""

# Categories available at every difficulty (Easy/Medium/Normal/Hard)
BASE_CATEGORIES = ['integers', 'decimals', 'fractions', 'algebra', 'percentages']

# Categories added on top of BASE_CATEGORIES, Normal/Hard only — deliberately
# absent from Easy/Medium (see CLAUDE.md Question Categories section)
ADVANCED_CATEGORIES = ['exponents_roots', 'ratios_proportions']

# Full category list — used for by_category dict init and results-screen
# breakdown rows across all difficulties (Easy/Medium rows for the two
# advanced categories will always show 0 questions / "—", by design)
CATEGORIES = BASE_CATEGORIES + ADVANCED_CATEGORIES

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
        ('integers',            0.24),
        ('decimals',            0.20),
        ('fractions',           0.20),
        ('algebra',             0.08),
        ('percentages',         0.08),
        ('exponents_roots',     0.10),
        ('ratios_proportions',  0.10),
    ],
    'hard': [
        ('integers',            0.20),
        ('decimals',            0.24),
        ('fractions',           0.20),
        ('algebra',             0.08),
        ('percentages',         0.08),
        ('exponents_roots',     0.10),
        ('ratios_proportions',  0.10),
    ],
}

CATEGORY_LABELS = {
    'integers':            'Integers',
    'decimals':            'Decimals',
    'fractions':           'Fractions',
    'algebra':             'Algebra',
    'percentages':         'Percentages',
    'exponents_roots':     'Exponents & Roots',
    'ratios_proportions':  'Ratios & Proportions',
}
