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
- **`viewport-fit=cover`** is set in the viewport meta tag to enable `env(safe-area-inset-top/bottom)` for iPhone safe area insets (Dynamic Island, notch, home indicator).
- **`session['question_log']`** is initialised as `[]` at session start for both modes. In Practice Mode, every `/submit-answer` call appends one entry. In Test Mode, the full log is built in `/end-test` from `test_questions` + `chosen_answers`. The log is passed to `results.html` as the `question_log` template variable.
- **Question pre-validation**: all questions served through `get_validated_question()` in `question_engine.py` which applies a 7-point check (finite answer, display parses close to answer, no duplicate MC options, text non-empty with operator, etc.). Retries up to 50 times; falls back to Easy with a `stderr` warning if max attempts exceeded.
- **`host="0.0.0.0"`** — app binds to all interfaces so it is reachable over local WiFi from iPhone.
- **PWA manifest + Apple meta tags** in `base.html` for full-screen iPhone install via Add to Home Screen.
- **European division notation** — Normal and Hard use `:` (e.g., `120 : 8`); Easy and Medium use `/`.
- **Test questions are pre-generated deterministically** from a random seed at session start and stored in `session['test_questions']` — prevents cheating by regenerating and ensures consistent replay.
- **Adaptive difficulty** applies only to Open Practice, not Test Mode — `level_modifier` shifts question complexity within the selected difficulty tier.
- **Open Answer input uses a custom on-screen numpad** — digits, `.`, `/` keys arranged in a 4×3 grid. Native iPhone keyboard is never triggered in Open Answer mode. Fraction entry (e.g. `3/4`) is supported natively.
- **Rounding tolerance is repeating-decimal-only** — `is_repeating()` uses `Fraction.limit_denominator(10000)` to detect mathematically repeating decimals. Only those get the 0.005 absolute tolerance; terminating decimals (0.375, 0.25, etc.) require exact entry.

---

## Game Modes

### Open Practice
- Infinite questions until user taps "End".
- Per-question countdown timer: 10s / 15s / 20s / Unlimited (user-selected on home screen). Unlimited means no countdown, no auto-skip.
- Answer format: Open Answer (custom numpad, no native keyboard) or Multiple Choice (4 options stacked vertically, same distractor logic as Test Mode) — user-selected on home screen.
- Adaptive difficulty: 5 correct in a row → `level_modifier` +1 (max +5); 3 wrong in a row → `level_modifier` -1 (min -3). Modifier passed to question generator.
- Immediate feedback overlay after each answer (correct / wrong / skipped), with special "Accepted" message for rounded-decimal matches on repeating decimals only.
- **Pause mode** (Open Answer only): ⏸ button in top bar freezes timer; shows a review panel with the current question and last 3 answered questions. Each history entry shows result, question text, user's answer vs correct answer, and a 🚩 flag button. Resume resumes countdown from exact frozen position. Timer at 0 when paused → auto-skip on resume. Purely client-side; no new Flask endpoints. State kept in `recentQuestions` JS array (max 3 entries, newest first).
- Skip button always visible in bottom zone (calls same handler as timer expiry).
- Session ends at "End" button → `/end-session` POST → redirects to `/results`.
- Stats tracked: total, correct, wrong, skipped, total_time, by_category.

### Results Screen
After any session, `results.html` shows:
1. Badge + big score / question count.
2. Summary stats card (correct / wrong / skipped, percentages, avg time).
3. Category breakdown table.
4. **Question Log** (collapsible, default collapsed): header "Question Log (N questions)". Toggle via single tap/click on header. Body has `max-height: 60vh; overflow-y: auto`. One card per question: number, category pill, question text, result (✓/✗/—), your answer vs correct answer. Left border colour: green (correct), red (wrong), grey (skipped). Wrong-answer cards show the correct answer in larger/bolder style. Server-rendered via Jinja2 — no JS rendering loop. Practice: `time_taken` shown per card. Test Mode: time shown as `None` (omitted).

### UX / Layout (game screens)
- Game screens (`.practice-screen`, `.test-screen`): `height: 100dvh; overflow: hidden; flex column`.
- **Safe area**: `.practice-screen` and `.test-screen` use `padding: calc(12px + env(safe-area-inset-top, 0px)) 16px calc(8px + env(safe-area-inset-bottom, 0px))`. This clears the Dynamic Island / notch on all iPhone models automatically. Requires `viewport-fit=cover` in the meta tag.
- **Touch latency**: `touch-action: manipulation`, `-webkit-tap-highlight-color: transparent`, and `-webkit-touch-callout: none` applied globally via the `*` reset. Also explicitly set on `.top-bar`, `.top-bar button/a`, and `.btn-start`. Three event tiers:
  - **touchstart** — digit/dot/slash/minus/backspace numpad keys and MC option buttons. Fires at finger-DOWN (fastest). `e.preventDefault()` suppresses the subsequent click. Safe because these actions are non-destructive.
  - **touchend** — Start button (home), numpad ✓ submit, pause/flag/end buttons (practice top bar), quit/flag buttons (test top bar). Fires at finger-LIFT. `e.preventDefault()` suppresses synthesized click. A timestamp guard (`Date.now() - lastTouch < 600ms`) in the companion click listener prevents double-fire on any browser that still sends the synthesized click. Used for destructive or irreversible actions so the user can slide their finger away to cancel.
  - **click only** — confirmation dialog buttons (Cancel, Yes quit), flag-modal Submit/Cancel. These are already inside a deliberate modal flow so the 300ms latency is acceptable and changing them would add complexity for no UX gain.
  - Start button is `type="button"` (not `type="submit"`) so form.submit() is called exclusively by JS, eliminating any risk of double-form-submission.
- **Top bar** — `min-height: 52px; flex-shrink: 0`. Practice: `[stat-mini] [timer] [⏸] [🚩] [End]`. Test: `[✕Quit] [Q counter] [timer] [score] [🚩]`. Flag button uses `btn-pause` class in both.
- **Question zone** (`.middle-zone`) — `flex: 2` (40% of remaining height). Question text `clamp(1.6rem, 5vw, 2.2rem)`. Feedback overlay is `position: absolute; inset: 0` within this zone.
- **Answer zone** (`.bottom-zone`) — `flex: 3` (60% of remaining height). Contains MC options or numpad, plus Skip button (40px fixed height).
- MC buttons: vertical flex column (`options-grid`), each `flex: 1; min-height: 56px`. 4 buttons fill the zone proportionally.
- Custom numpad: 4×3 `numpad-grid` (flex:1 within `numpad-wrap`), 52px actions row (⌫ + − + ✓), 48px display. The `−` key inserts `-` only as the first character (negative answers). Display shows "Your answer" placeholder when empty; font auto-shrinks from 1.8rem down to 1.0rem for long inputs.
- Home and Results screens scroll freely (`min-height: 100dvh`, no `overflow: hidden`).

### Distractor Generation (MC mode)
`_numeric_distractors()` in `question_engine.py` uses a 5-strategy pool per distractor attempt (up to 300 attempts):
1. **Percentage offset**: `answer × (1 ± 5/10/15/20%)` — rounded to same decimal places as answer.
2. **Magnitude-scaled error**: `answer ± offset` where offset scales with `abs(answer)` (1–3 for <10, 2–10 for <100, 5–50 for <1000, 10–100 for ≥1000).
3. **Mental math mistake**: round to nearest 5/10, or apply a percentage error twice.
4. **Plausible neighbour**: random value in 70%–130% of answer range.
5. **Sign flip**: `-answer` (used at most once for positive correct answers; forced at least once for negative correct answers).

Constraints: all 4 options distinct within 0.001; no distractor >9× or <0.111× the correct answer; at most 1 negative distractor when correct answer is positive.

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
- **Integers**: 2-digit operands, products up to ~200 (e.g. 17×8), 2-digit division; 30% chance of negative subtraction result
- **Decimals**: 1 decimal place, includes division by simple decimals (0.5, 0.25, 2.0, 5.0); 30% chance of negative subtraction result
- **Fractions**: unit fractions, proper fraction × integer, or fraction subtraction (same denominator, denominators 3–6; result may be negative)
- **Algebra**: one-step isolation with whole number coefficients, wider operand range; 30% chance x is negative (e.g. x + 10 = 3)
- **Percentages**: round percentages (10%, 20%, 25%, 50%, 75%) of 2-digit numbers (10–99)

### Normal
- **Integers**: 2-digit × 2-digit, 3-digit addition/subtraction, 2-digit division; 30% chance of negative subtraction result
- **Decimals**: 2 decimal places, division by 0.1/0.2/0.25/0.4/0.5/0.8, mixed decimal ×/+/−
- **Fractions**: fraction-to-decimal conversion, fraction addition, fraction × integer, fraction subtraction (mixed denominators; result may be negative)
- **Algebra**: two-step equations (ax+b=c), fraction coefficients; 30% chance x is negative
- **Percentages**: decimal percentages, reverse percentages, % increase/decrease

### Hard
- **Integers**: 3-digit × 2-digit, multi-step chains, bracket expressions
- **Decimals**: division by small divisors (0.03–0.15)
- **Fractions**: mixed number addition, fraction ÷ fraction, chain operations
- **Algebra**: bracket expansion, decimal coefficients, two-variable elimination; 30% chance x is negative
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

**Percentages — exact decimal answers**: `correct_answer` stores the mathematically exact result with no integer rounding. Examples: `53 × 1.1 = 58.3` (not 58), `446 × 0.9 = 401.4` (not 401), `80 × 1.15 = 92` (integer result, int stored), `70 × 0.95 = 66.5`. The `_trunc(val, 2)` helper is used instead of `round()` or `int()` so whole-number results are stored as `int` and non-integer results as `float`.

**Test Mode Normal distribution** (from `TEST_DISTRIBUTION` in `config.py`):
~30% integers, 25% decimals, 25% fractions, 10% algebra, 10% percentages.

**Practice Mode**: equal random distribution across all 5 categories.

---

## Answer Validation

Applies to all free-text answer endpoints (`/submit-answer` in Practice Mode). Open Practice now uses a custom on-screen numpad — the native iPhone keyboard is never shown in this mode.

### Rules (implemented in `_check_answer()` in `app.py`)
1. **Fraction string handling**: user input like `3/4` or `-3/4` is parsed as `float(3)/float(4)` (or `float(-3)/float(4)`) before comparison. Exclusion check for operators no longer includes `-` so leading minus in fractions is accepted.
2. **Exact match**: `abs(user - correct) / max(abs(correct), 1e-9) < 0.002` (0.2% relative tolerance). Returns `{'correct': True, 'rounded': False}`.
3. **Rounded match (repeating decimals only)**: if not exact but `abs(user - correct) <= 0.005` AND `is_repeating(correct)` is True. Returns `{'correct': True, 'rounded': True}`. Example: 1/3 ≈ 0.333, 1/6 ≈ 0.167.
4. **Wrong**: everything else — including rounded versions of terminating decimals (e.g. 0.38 for 0.375). Returns `{'correct': False, 'rounded': False}`.
5. **Fallback**: if float conversion fails, string comparison is used (`rounded` always False).

### `is_repeating(correct_value)` — `app.py`
Two-stage check to avoid float-noise false positives (e.g. `0.1 + 0.2 = 0.30000000000000004`):

**Stage 1** — `_is_terminating_by_decimal_check(v)`: if `v × 10^n` is an integer for n = 0..4 (within 1e-6), the value is terminating → `is_repeating` returns False immediately.

**Stage 2** — Fraction analysis on noise-reduced float: round to 9 significant figures, then use `Fraction.limit_denominator(100000)`. Strip all factors of 2 and 5 from denominator; if denom ≠ 1, it's repeating.

Examples: `0.375 = 3/8` → stage 1 catches it (0.375 × 10³ = 375) → **terminating**. `0.333... ≈ 1/3` → stage 1 fails → stage 2: denom 3 → **repeating** (rounded answer accepted).

### Feedback for rounded match
The `/submit-answer` response includes `"rounded": true` and `"exact_answer": "0.333333"` (6dp, trailing zeros stripped). The practice feedback overlay shows: **"Accepted"** with sub-line **"Exact answer: 0.333333"** instead of the normal "Correct! / Answer: X".

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

- **[2026-04-09]** — Session 6: touch latency follow-up — converted remaining onclick buttons to touchend:
  - `home.html` Start button: `type="submit"` → `type="button"` (id `start-btn`); touchend + timestamp-guarded click fallback calls `form.submit()`.
  - `practice.html` pause/flag/end top-bar buttons: removed `onclick=`, bound via `bindBtn()` in script.
  - `practice.html` numpad ✓ submit: removed `onclick=`, bound via `bindBtn()` (touchend fires at finger-lift, preventing accidental submit).
  - `test.html` quit/flag top-bar buttons: removed `onclick=`, bound via `bindBtn()`.
  - `style.css`: added explicit `touch-action: manipulation` to `.top-bar`, `.top-bar button`, `.top-bar a`, `.btn-start`.
  - `CLAUDE.md`: documented three-tier event strategy (touchstart / touchend / click-only).

- **[2026-04-09]** — Session 5: five fixes + one new feature from iPhone device testing:
  1. **Touch delay fix** — Added `-webkit-tap-highlight-color: transparent`, `-webkit-touch-callout: none`, `touch-action: manipulation` to global `*` reset. Added `user-select: none; -webkit-user-select: none` to all interactive element classes. Numpad digit/dot/slash/minus/backspace keys now fire on `touchstart` (via `ontouchstart` HTML attribute + `e.preventDefault()` to suppress click double-fire). MC option buttons and Skip button also get touchstart listeners. Submit (✓) keeps click-only. `touch-action: manipulation` already eliminates 300ms tap delay; touchstart additionally fires at finger-down not finger-lift.
  2. **MC distractors** — Replaced `_distractor_candidate()` + simple loop in `_numeric_distractors()` with a 5-strategy pool approach: percentage offsets, magnitude-scaled errors, mental math mistakes, plausible neighbours (70–130% range), sign flips. Constraints: ≤1 sign-flip for positive answers, ≥1 positive for negative answers, no 10× differences, 300-attempt loop with scaled fallback.
  3. **iPhone safe area** — `.practice-screen` and `.test-screen` now use `padding: calc(12px + env(safe-area-inset-top, 0px)) 16px calc(8px + env(safe-area-inset-bottom, 0px))`. This clears Dynamic Island / notch / home indicator on all iPhone models. `viewport-fit=cover` was already set.
  4. **Percentage answers** — Removed `round()` from `pct_increase` and `pct_decrease` generators in `_gen_percentages()`. Now uses `_trunc(..., 2)` which stores exact decimal results (e.g. 53×1.1=58.3, 446×0.9=401.4) without truncating to integer.
  5. **Question log** — `session['question_log']` initialised at session start for both modes. Practice: appended per answer in `/submit-answer`. Test: built in `/end-test` from questions + chosen answers. Passed to `results.html` as `question_log`. Results screen shows collapsible "Question Log (N questions)" section: per-card layout with colour-coded left border, question text, result, your answer vs correct, time (Practice only). Server-rendered Jinja2, `max-height: 60vh; overflow-y: auto`.
  6. **CLAUDE.md** updated: Architecture Decisions, UX/Layout, Question Categories, Distractor Generation, Results Screen sections all updated.

- **[2026-04-09]** — Session 4: four targeted fixes from real-device testing:
  1. **Negative answers enabled** — `_gen_integers` (Medium/Normal subtraction: 30% chance b > a → negative result), `_gen_decimals` (Medium sub1: 30% chance negative), `_gen_fractions` (Medium + Normal: added `frac_sub` type; result may be negative), `_gen_algebra` (Medium/Normal/Hard: 30% chance x is negative). `_distractor_candidate` gains strategy 5: sign flip (`-ans_f`). `-` key added to numpad action row (allowed only as first char). `submitAnswer()` guards against lone `-`. `_check_answer()` fraction parser now accepts `-3/4` format (removed `-` from operator exclusion list).
  2. **Answer display field** — removed "0" default; placeholder "Your answer" shown in `var(--text-dim)` when empty; background changed to `var(--bg)`; font auto-shrinks 1.8→1.6→1.4→1.2→1.0rem via JS based on input length.
  3. **`is_repeating()` two-stage fix** — added `_is_terminating_by_decimal_check(v)` (checks `v × 10^n` is integer for n=0..4); `is_repeating()` uses this first to avoid float-noise false positives (e.g. `0.30000000000000004`); stage 2 uses `float(f"{v:.9g}")` + `limit_denominator(100000)`.
  4. **Flag button moved to top bar** — removed fixed-position `🚩` button from both `practice.html` and `test.html`; added inline `btn-pause`-styled flag button to each top bar. Removed dead `.flag-btn` CSS.
  5. **CLAUDE.md** updated: Difficulty Levels (negative answers), Answer Validation (two-stage check, fraction format fix), UX/Layout (numpad action row, top bar layout).

- **[2026-04-09]** — Session 3: six targeted improvements from real-device testing:
  1. **Rounding tolerance restricted to repeating decimals** — `is_repeating()` added to `app.py` using `Fraction.limit_denominator(10000)`. `_check_answer()` now only accepts rounded answers (within 0.005) when `is_repeating(correct)` is True. Terminating decimals (0.375, 0.25, etc.) require exact entry.
  2. **Question pre-validation** — `get_validated_question()` added to `question_engine.py` with a 7-point validation check: finite answer, display parses correctly, no duplicate MC options, all options distinct, non-empty question text with operator, 6dp round stays finite. Retries up to 50× per difficulty; falls back to Easy with stderr warning. All call sites in `app.py` and `question_engine.py` updated.
  3. **Pause mode** (Open Answer practice) — ⏸ button in top bar freezes timer at exact remaining value. Review panel shows current question + last 3 answered questions with result icons, entered vs correct answer, and per-entry 🚩 flag buttons. Resume adjusts `questionStartTime` so timer continues from freeze point. Entirely client-side.
  4. **Custom numeric keypad replaces text input** — 4×3 grid (7–9 / 4–6 / 1–3 / . 0 /) plus ⌫ and ✓ keys. Native iPhone keyboard never appears in Open Answer mode. Fraction entry via `/` key. Input validation: no double `.`, no `.` after `/`, no `/` at start or after `.`. Removed the orphaned blue submit button that appeared beside the old text input.
  5. **40/60 proportional layout** — `middle-zone` changed to `flex: 2` (40%), `bottom-zone` to `flex: 3` (60%). MC option buttons changed from 2×2 CSS grid to 4×1 vertical flex column (`flex: 1; min-height: 56px`). Skip button fixed at 40px height. Question text `clamp(1.6rem, 5vw, 2.2rem)`. Top bar `min-height: 52px`.
  6. **CLAUDE.md** updated: Answer Validation, Architecture Decisions, Open Practice, new UX/Layout section.

- **[2026-04-09]** — Mobile UX fixes (iPhone first-device-test findings):
  - **iOS keyboard submission**: Open Practice answer input wrapped in `<form onsubmit="handleSubmit(event)">` so the native iOS "Go"/"Done"/tick key submits the answer. `input[type="text"]` + `inputmode="decimal"` preserved (never `type="number"`). `blur()` called on submit to dismiss keyboard before feedback overlay appears. Keydown Enter listener removed (form submit covers all cases).
  - **Skip button**: Added explicit Skip button to Practice mode bottom zone (was previously only via timer expiry).
  - **300ms touch delay eliminated**: `touch-action: manipulation` added to `html`, `body`, and all interactive elements globally in `style.css`. Viewport meta updated to `maximum-scale=1.0, user-scalable=no` to disable double-tap zoom detection in iOS Safari.
  - **Single-screen layout**: Practice and Test screens now use `height: 100dvh; overflow: hidden` via `.practice-screen` / `.test-screen`. Layout split into three zones: top-bar (flex-shrink: 0), middle-zone (flex: 1, position: relative), bottom-zone (flex-shrink: 0). Feedback overlay now `position: absolute; inset: 0` within middle-zone rather than in flow. Option buttons reduced from 64px to 52px min-height. Question text uses `clamp(1.4rem, 5vw, 2rem)`.

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
