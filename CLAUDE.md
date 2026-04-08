# CLAUDE.md — MindMath Trainer Architecture Reference

Read this file at the start of every session before making any changes. It provides enough context to understand the full project without reading every source file from scratch.

---

## Project Overview

MindMath Trainer is a Flask-based mental arithmetic web app designed to run as a Progressive Web App (PWA) on an iPhone (Safari → Add to Home Screen). It is served locally from a Windows machine on the home network (host `0.0.0.0`, port 5000), accessible from the iPhone via the machine's local IP address, and also deployable to cloud platforms (Render, Railway) via a Procfile. The app trains users for Optiver-style mental arithmetic tests with two game modes: an adaptive open practice mode and a timed multiple-choice test mode.

---

## Tech Stack

- Python 3.11.9 (pinned in runtime.txt)
- Flask >= 3.0.0 (server-side sessions, Jinja2 templates, routing)
- Gunicorn >= 21.2.0 (production WSGI server via Procfile)
- python-dotenv >= 1.0.0 (loads .env in development; no-op in production)
- Vanilla JavaScript (no frameworks; all logic inline in templates)
- Jinja2 templates (server-rendered HTML; no client-side rendering framework)
- CSS custom properties (variables) for theming — dark mode, accent colour `#6c63ff`
- Flask server-side sessions (cookie-based, signed with `SECRET_KEY`)
- `flagged_questions.json` for bug reporting (append-only, no database)
- No database — all game state is in-memory within the session

---

## File Map

```
mental-math-trainer/
├── app.py                  Main Flask app: all routes, session logic, answer validation helpers
├── config.py               Constants: difficulty params, timing, scoring thresholds, TEST_DISTRIBUTION
├── question_engine.py      All question generation: 5 categories × 4 difficulties, multiple-choice attachment
├── scoring.py              Post-session stats computation for both modes
├── requirements.txt        Flask, gunicorn
├── Procfile                web: gunicorn app:app
├── CLAUDE.md               This file — architecture reference
├── flagged_questions.json  Append-only list of user-flagged questions (excluded from git)
├── .gitignore              Excludes venv, __pycache__, .env, flagged_questions.json
├── static/
│   ├── app.js              Minimal shared JS (prevents double-tap zoom on iOS)
│   ├── style.css           Complete styling; CSS variables; responsive dark theme
│   ├── manifest.json       PWA manifest (name, icons, standalone display, theme colour)
│   ├── icon-192.png        PWA icon 192×192
│   └── icon-512.png        PWA icon 512×512
└── templates/
    ├── base.html           Base template: PWA meta tags, manifest link, stylesheet, deferred app.js
    ├── home.html           Home screen: mode selector, difficulty grid, settings card, start form
    ├── practice.html       Open Practice screen: timer, question card, open/MC answer area, feedback overlay
    ├── test.html           Test Mode screen: global timer, MC options, progress bar, quit button
    ├── results.html        Results screen: score, per-category breakdown (shared for both modes)
    └── flags.html          Flagged questions viewer (/flags)
```

---

## Architecture Decisions

These decisions are intentional and must not be undone without explicit instruction:

- **No database** — session stats are in-memory only (lost on session end). Flagged questions write to `flagged_questions.json` (append-only, one JSON array).
- **Flask server-side sessions** hold all game state: current question, streaks, level modifier, stats, test questions array. No client-side persistence.
- **Question transitions via AJAX** — no full page reloads during a session (`/next-question`, `/submit-answer`, `/end-session`, `/end-test` are all JSON endpoints).
- **All question generation is programmatic and validated** — each generated question passes `_valid()` before use; up to 20 retries with fallback to easy difficulty.
- **`host="0.0.0.0"`** — app binds to all interfaces so it is reachable over local WiFi from iPhone.
- **PWA manifest + Apple meta tags** in `base.html` for full-screen iPhone install via Add to Home Screen.
- **European division notation** — Normal and Hard use `:` (e.g., `120 : 8`); Easy and Medium use `/`.
- **Test questions are pre-generated deterministically** from a random seed at session start and stored in `session['test_questions']` — prevents cheating by regenerating and ensures consistent replay.
- **Adaptive difficulty** applies only to Open Practice, not Test Mode — `level_modifier` shifts question complexity within the selected difficulty tier.

---

## Game Modes

### Open Practice
- Infinite questions until user taps "End".
- Per-question countdown timer: 10s / 15s / 20s / Unlimited (user-selected on home screen). Unlimited means no countdown, no auto-skip.
- Answer format: Open Answer (free-text numeric input) or Multiple Choice (4 options, same distractor logic as Test Mode) — user-selected on home screen.
- Adaptive difficulty: 5 correct in a row → `level_modifier` +1 (max +5); 3 wrong in a row → `level_modifier` -1 (min -3). Modifier passed to question generator.
- Immediate feedback overlay after each answer (correct / wrong / skipped), with special "Accepted" message for rounded-decimal matches.
- Session ends at "End" button → `/end-session` POST → redirects to `/results`.
- Stats tracked: total, correct, wrong, skipped, total_time, by_category.

### Test Mode
- Exactly 80 questions, fixed 8-minute global timer.
- Always multiple choice (4 options per question). Answer format setting from home screen has no effect.
- Timer duration setting from home screen has no effect.
- Optiver scoring: +1 correct, -1 wrong, 0 skipped.
- No mid-test feedback — answer chosen immediately advances to next question.
- Test ends when all questions answered or timer expires → `/end-test` POST → redirects to `/results`.
- Quit button always visible; shows inline confirmation before clearing session.

---

## Settings (Home Screen)

All settings submitted via the `/start` POST form. Stored in `flask.session` for the duration of the session.

| Setting | Name | Default | Applies to |
|---|---|---|---|
| `timer_duration` | Time per question | `10` (seconds) | Practice only. Values: `10`, `15`, `20`, `unlimited`. `unlimited` → `question_time=0` sentinel in session. |
| `difficulty` | Difficulty | `normal` | Both modes. Values: `easy`, `medium`, `normal`, `hard`. |
| `answer_mode` | Answer format | `open` | Practice only. Values: `open` (free-text), `mc` (multiple choice). Test Mode ignores this. |

When Test Mode is selected on the home screen, the timer_duration and answer_mode settings are visually disabled (greyed out) and their inputs are set to `disabled`, so they are not submitted.

---

## Difficulty Levels

Defined in `question_engine.py` generators. `config.py` defines `TEST_DISTRIBUTION` for test-mode category weighting per difficulty.

### Easy
- **Integers**: operands 2–20, operations +/−/×/÷ with simple whole results
- **Decimals**: 1 decimal place, basic +/−/×/÷ with simple divisors (2, 4, 5)
- **Fractions**: unit fractions `(1/n) × integer`, denominator 2–10
- **Algebra**: single-step isolation (x+a=b, ax=b, x/a=b), small whole numbers
- **Percentages**: round percentages (10%, 20%, 25%, 50%, 75%) of round bases

### Medium *(new level between Easy and Normal)*
- **Integers**: 2-digit operands, products up to ~200 (e.g. 17×8), 2-digit division
- **Decimals**: 1 decimal place, includes division by simple decimals (0.5, 0.25, 2.0, 5.0)
- **Fractions**: unit fractions + simple proper fraction × small integer (denominators 2–5)
- **Algebra**: one-step isolation with whole number coefficients, wider operand range (x+30=55, 12x=144)
- **Percentages**: round percentages (10%, 20%, 25%, 50%, 75%) of 2-digit numbers (10–99)

### Normal
- **Integers**: 2-digit × 2-digit, 3-digit addition/subtraction, 2-digit division
- **Decimals**: 2 decimal places, division by 0.1/0.2/0.25/0.4/0.5/0.8, mixed decimal ×/+/−
- **Fractions**: fraction-to-decimal conversion, fraction addition, fraction × integer
- **Algebra**: two-step equations (ax+b=c), fraction coefficients
- **Percentages**: decimal percentages, reverse percentages, % increase/decrease

### Hard
- **Integers**: 3-digit × 2-digit, multi-step chains, bracket expressions
- **Decimals**: division by small divisors (0.03–0.15)
- **Fractions**: mixed number addition, fraction ÷ fraction, chain operations
- **Algebra**: bracket expansion, decimal coefficients, two-variable elimination
- **Percentages**: compound %, nested %, reverse hard % problems

---

## Question Categories

Five categories, generated in `question_engine.py`:

| Category | Generation summary |
|---|---|
| `integers` | Arithmetic with whole numbers; difficulty scales operand size and operation complexity |
| `decimals` | Decimal arithmetic; difficulty scales decimal places and divisor complexity |
| `fractions` | Fraction operations; difficulty scales from unit fractions to mixed number chains |
| `algebra` | Equation solving for x; difficulty scales from one-step to bracket/multi-variable |
| `percentages` | % calculations; difficulty scales from round % to compound/nested/reverse |

**Test Mode Normal distribution** (from `TEST_DISTRIBUTION` in `config.py`):
~30% integers, 25% decimals, 25% fractions, 10% algebra, 10% percentages.

**Practice Mode**: equal random distribution across all 5 categories.

---

## Answer Validation

Applies to all free-text answer endpoints (`/submit-answer` in Practice Mode).

### Rules (implemented in `_check_answer()` in `app.py`)
1. **Fraction string handling**: user input like `3/4` is parsed as `float(3)/float(4)` before comparison.
2. **Exact match**: `abs(user - correct) / max(abs(correct), 1e-9) < 0.002` (0.2% relative tolerance). Returns `{'correct': True, 'rounded': False}`.
3. **Rounded match**: if not exact but `abs(user - correct) <= 0.005`. Returns `{'correct': True, 'rounded': True}`.
4. **Wrong**: everything else. Returns `{'correct': False, 'rounded': False}`.
5. **Fallback**: if float conversion fails, string comparison is used (`rounded` always False).

### Feedback for rounded match
The `/submit-answer` response includes `"rounded": true` and `"exact_answer": "0.333333"` (6 significant decimal places, trailing zeros stripped). The practice feedback overlay shows: **"Accepted"** with sub-line **"Exact answer: 0.333333"** instead of the normal "Correct! / Answer: X".

### Multiple Choice submissions (Practice MC mode)
Client sends `mc_selected_index` and `mc_correct_index`. Server compares these integers directly, bypassing string matching. `rounded` is always `False` for MC.

---

## Flagging System

Users can flag a question using the 🚩 button during any mode.

- **Endpoint**: `POST /flag` — accepts JSON, writes to `flagged_questions.json`.
- **Schema** (each record):
  ```json
  {
    "timestamp": "2026-04-07T14:30:00Z",
    "game_mode": "practice" | "test",
    "difficulty": "easy" | "medium" | "normal" | "hard",
    "question_text": "17 x 8",
    "correct_answer": "136",
    "category": "integers",
    "user_comment": "optional free text"
  }
  ```
- **Review page**: `GET /flags` — renders `flags.html` with all flags in reverse-chronological order.
- `flagged_questions.json` is excluded from git (`.gitignore`).

---

## Deployment

### Local (development)
```bash
# 1. Copy the environment template and fill in values:
#    cp .env.example .env   (set FLASK_ENV=development and a SECRET_KEY)
# 2. Install dependencies:
#    pip install -r requirements.txt
# 3. Run the app:
python app.py
# binds 0.0.0.0:5000
# Find machine IP: ipconfig (Windows) or ifconfig (Mac)
# Access from iPhone: http://<local-ip>:5000
```

A `.env` file (copied from `.env.example`) is required for local runs. It must set at least `FLASK_ENV=development` and a `SECRET_KEY` value. Without `FLASK_ENV=development`, the app will raise a `RuntimeError` on startup if `SECRET_KEY` is not set.

### Cloud (Render / Railway)
- `Procfile` contains: `web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`
  (`$PORT` is injected dynamically by Render; `--workers 2` suits the free-tier instance.)
- `runtime.txt` pins the Python version to **3.11.9** — Render reads this at build time.
- Set `SECRET_KEY` environment variable on the host. The app will raise a `RuntimeError` on startup if it is missing in production.
- Push repo root; Render and Railway auto-detect `Procfile`.
- No build steps or database provisioning required.

---

## Known Issues / Flagged Bugs

No known issues. Check `flagged_questions.json` for user-reported bugs.

---

## Changelog

- **[2026-04-08]** — Pre-deployment hardening:
  - `runtime.txt` added, pinning Python to 3.11.9 for Render.
  - `SECRET_KEY` validation: raises `RuntimeError` on startup in production if unset; dev fallback preserved when `FLASK_ENV=development`.
  - `.env.example` added as local developer setup template.
  - `python-dotenv >= 1.0.0` added to `requirements.txt`; loaded at top of `app.py` (no-op in production).
  - Procfile updated to `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT` for correct Render port binding.
  - `debug=True` replaced with `debug=os.environ.get('FLASK_ENV') == 'development'` in `app.run()`.

- **[2026-04-07]** — Initial build: full app generated by Claude Code — Flask PWA with two game modes (Open Practice, Test Mode), 5 question categories, 3 difficulty levels (Easy/Normal/Hard), adaptive difficulty in Practice, Optiver scoring in Test Mode, flag/review system, PWA manifest.
- **[2026-04-07]** — Session 2 additions by Claude Code:
  - **Settings panel** on home screen: timer duration (10s/15s/20s/Unlimited, Practice only), difficulty expanded to 4 levels (Easy/Medium/Normal/Hard), answer format (Open Answer/Multiple Choice, Practice only). Settings passed to backend via `/start` POST, stored in `flask.session`.
  - **Quit button** in Test Mode: always-visible small button in top bar; shows inline confirmation before clearing session and navigating home via `/quit` endpoint.
  - **Rounded decimal tolerance**: `_check_answer()` accepts answers within 0.005 absolute tolerance as correct with "Accepted — exact answer: X" feedback. Applies to all free-text submissions in Practice Mode.
