# CLAUDE.md — MindMath Trainer Architecture Reference

Read this file at the start of every session before making any changes. It provides enough context to understand the full project without reading every source file from scratch.

---

## Project Overview

MindMath Trainer is a Flask-based multi-game PWA designed to run on an iPhone (Safari → Add to Home Screen). It is served locally from a Windows machine on the home network (host `0.0.0.0`, port 5000) and is also deployable to cloud platforms (Render, Railway) via a Procfile.

The app currently has three games, accessible from a game-launcher home screen at `/`:
- **Mental Arithmetic** — Optiver-style arithmetic training with Open Practice (adaptive, untimed) and Test Mode (80 questions, 8 min, MC). Five question categories across 4 difficulty levels.
- **Sequences** — Number and letter pattern sequences across four difficulty levels. Practice Mode (adaptive) and Test Mode (8 min, MC, +1/−1 scoring). Supports Multiple Choice and Open Answer (numpad for numbers, A–Z keyboard for letters).
- **Word Associations** — Verbal analogy questions ("Crown : Tree → Head : ___?"). Practice Mode only, Multiple Choice (4 options). Questions sourced from a hardcoded curated JSON bank. Supports English, German, and French (language selected on settings page via 3-button selector). 10 analogy categories, 150+ questions per language.

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
├── question_engine.py      Arithmetic question generation: 5 categories × 4 difficulties, MC attachment
├── sequence_engine.py      Sequence generation: 4 difficulties, number + letter types, MC distractor attachment
├── association_engine.py   Bank loader, question server, answer checker, module-level language cache
├── scoring.py              Post-session stats computation for arithmetic modes
├── requirements.txt        Flask, gunicorn
├── Procfile                web: gunicorn app:app
├── CLAUDE.md               This file — architecture reference
├── flagged_questions.json  Append-only list of user-flagged questions (excluded from git)
├── .gitignore              Excludes venv, __pycache__, .env, flagged_questions.json
├── data/
│   ├── associations_en.json    EN question bank (150 verbal analogy questions, 10 categories)
│   ├── associations_de.json    DE question bank (same structure, 150 German questions)
│   ├── associations_fr.json    FR question bank (156 French questions, 10 categories)
│   └── validate_associations.py  Quality-check script: flags too-similar pairs, duplicates, hypernym confusion
├── static/
│   ├── app.js              Minimal shared JS (prevents double-tap zoom on iOS; syncPendingFlags on load/online)
│   ├── style.css           Complete styling; CSS variables; responsive dark theme
│   ├── manifest.json       PWA manifest (name, icons, standalone display, theme colour)
│   ├── icon-192.png        PWA icon 192×192
│   ├── icon-512.png        PWA icon 512×512
│   ├── sw.js               Service worker: cache key `mindmath-v2`, cache-first /static/, network-only Flask routes
│   ├── offline.html        Self-contained offline game page; all 3 games MC-only; reads sessionStorage `offline_start`
│   ├── js/
│   │   ├── rng.js              Seeded PRNG (Mulberry32) + math helpers: floorDiv, pyMod, gcd, trunc, r2, isRepeating
│   │   ├── question_engine.js  Offline arithmetic question generation (MC only) — port of question_engine.py
│   │   ├── sequence_engine.js  Offline sequence question generation (MC only) — port of updated sequence_engine.py
│   │   └── association_engine.js  Async bank loader + question server — fetches /static/data/ JSON banks
│   └── data/
│       ├── associations_en.json   Copy of data/associations_en.json (served to SW and offline page)
│       ├── associations_de.json   Copy of data/associations_de.json
│       └── associations_fr.json   Copy of data/associations_fr.json
└── templates/
    ├── base.html               Base template: PWA meta tags, manifest link, stylesheet, deferred app.js
    ├── home.html               Game launcher — tile selector for all games (/)
    ├── arithmetic.html         Arithmetic game settings page (/arithmetic) — mode, difficulty, timer, format
    ├── practice.html           Open Practice screen: timer, question card, open/MC answer area, feedback overlay
    ├── test.html               Test Mode screen: global timer, MC options, progress bar, quit button
    ├── results.html            Arithmetic results: score, per-category breakdown (shared for both arithmetic modes)
    ├── sequence_home.html      Sequences game settings page (/sequences) — mode, difficulty, answer format
    ├── sequence.html           Sequences practice game screen (/sequences/play) — term boxes, numpad or A-Z keyboard
    ├── sequence_test.html      Sequences test mode screen (/sequences/test) — MC, global timer, +1/−1 scoring
    ├── sequence_results.html   Sequences results: practice stats / test score + performance band, question log with rule
    ├── association_home.html   Word Associations settings page (/associations) — language selector (EN/DE)
    ├── association.html        Word Associations game screen (/associations/play) — analogy display + MC options
    ├── association_results.html Word Associations results: stats, category breakdown, question log with relationship
    └── flags.html              Flagged questions viewer (/flags) — with per-card delete (fade-out, no reload)
```

---

## Architecture Decisions

These decisions are intentional and must not be undone without explicit instruction:

- **No database** — session stats are in-memory only (lost on session end). Flagged questions write to `flagged_questions.json` (append-only, one JSON array).
- **Flask server-side sessions** hold all game state: current question, streaks, level modifier, stats, test questions array. No client-side persistence.
- **Question transitions via AJAX** — no full page reloads during a session (`/next-question`, `/submit-answer`, `/end-session`, `/end-test` are all JSON endpoints). Same pattern applies to sequences (`/sequences/next`, `/sequences/submit`, `/sequences/end`).
- **`viewport-fit=cover`** is set in the viewport meta tag to enable `env(safe-area-inset-top/bottom)` for iPhone safe area insets (Dynamic Island, notch, home indicator).
- **Body-level safe-area padding**: `.screen` class (non-game screens: home, arithmetic, sequence_home, results, flags) applies `padding-top: calc(16px + env(safe-area-inset-top, 0px))`. Game screens (`.practice-screen`, `.test-screen`, `.seq-screen`) handle their own env() padding internally, so there is no double-padding.
- **`session['question_log']`** is initialised as `[]` at session start for both modes. In Practice Mode, every `/submit-answer` call appends one entry. In Test Mode, the full log is built in `/end-test` from `test_questions` + `chosen_answers`. The log is passed to `results.html` as the `question_log` template variable.
- **Question pre-validation**: all questions served through `get_validated_question()` in `question_engine.py` which applies a 7-point check (finite answer, display parses close to answer, no duplicate MC options, text non-empty with operator, etc.). Retries up to 50 times; falls back to Easy with a `stderr` warning if max attempts exceeded.
- **`host="0.0.0.0"`** — app binds to all interfaces so it is reachable over local WiFi from iPhone.
- **PWA manifest + Apple meta tags** in `base.html` for full-screen iPhone install via Add to Home Screen.
- **European division notation** — Normal and Hard use `:` (e.g., `120 : 8`); Easy and Medium use `/`.
- **Test questions are pre-generated deterministically** from a random seed at session start and stored in `session['test_questions']` — prevents cheating by regenerating and ensures consistent replay.
- **Adaptive difficulty** applies only to Open Practice, not Test Mode — `level_modifier` shifts question complexity within the selected difficulty tier.
- **Open Answer input uses a custom on-screen numpad** — digits, `.`, `/` keys arranged in a 4×3 grid. Native iPhone keyboard is never triggered in Open Answer mode. Fraction entry (e.g. `3/4`) is supported natively.
- **Rounding tolerance is repeating-decimal-only** — `is_repeating()` uses `Fraction.limit_denominator(10000)` to detect mathematically repeating decimals. Only those get the 0.005 absolute tolerance; terminating decimals (0.375, 0.25, etc.) require exact entry.
- **Home screen is a game launcher at `/`**. Each game lives under its own URL namespace (`/arithmetic`, `/sequences`). Future games add tiles to home.html and new route namespaces.
- **Sequences game uses session keys prefixed with `seq_`** — `seq_difficulty`, `seq_answer_mode`, `seq_stats`, `seq_current`, `seq_question_log`, `seq_results` — to avoid collision with arithmetic session keys.
- **Word Associations uses session keys prefixed with `assoc_`** — `assoc_language`, `assoc_used_ids`, `assoc_stats`, `assoc_current`, `assoc_question_log`, `assoc_results` — to avoid collision with other games.
- **Association JSON banks live in `static/data/`** — `association_engine.py` reads from `static/data/associations_{lang}.json` (updated from `data/` in session 13 to unify server and offline paths). The `data/` directory still exists as the canonical edit location; `static/data/` holds identical copies for SW caching and the offline page. Update both whenever editing a bank. The bank is cached module-level; never modified at runtime.
- **Word Associations question bank is hardcoded JSON** — loaded from `static/data/associations_en.json`, `static/data/associations_de.json`, or `static/data/associations_fr.json` depending on the selected language. The bank is cached in a module-level dict in `association_engine.py` so files are read only once per process. The bank is never modified at runtime.
- **Bank exhaustion behaviour**: `get_association_question()` receives `exclude_ids` (session's used ID list). When all 150 IDs are exhausted, `available` falls back to the full bank and the session restarts seamlessly.
- **Word Associations is Practice-only** — no Test Mode, no timer, no difficulty setting. Language (EN/DE/FR) is the only setting, selected on the settings page via a 3-button selector.
- **Offline mode uses `navigator.onLine` + service worker** — each settings page Start button checks `navigator.onLine`; if offline, it writes `sessionStorage.setItem('offline_start', params)` and redirects to `/static/offline.html`. The offline page reads this key on boot: if found, it sets game/difficulty/language and calls `startGame()` immediately; if absent, it shows the game selector (game-select-screen). The service worker (`static/sw.js`, cache key `mindmath-v2`) handles `request.mode === 'navigate'` first (try network, fall back to cached `/static/offline.html`), then cache-first for all `/static/` URLs. All five game templates (`practice.html`, `test.html`, `sequence.html`, `sequence_test.html`, `association.html`) have JS engine fallbacks gated by `_offlineActive`: when any fetch fails, `_goOffline()` is called (sets flag, shows toast), subsequent calls use local JS engines. `showOfflineResults()` in `app.js` shows end-of-game stats overlay. Play Again reloads the page (reconnects online or re-enters offline flow). Flags submitted while offline are queued in `localStorage.pending_flags` and synced via `syncPendingFlags()` on next page load or `online` event.
- **JS engine files mirror Python exactly** — `static/js/question_engine.js` and `static/js/sequence_engine.js` are line-by-line ports of their Python counterparts. When editing Python generators, update the corresponding JS generators too. `rng.js` exports `RNG` (Mulberry32 seeded PRNG) + shared helpers (`floorDiv`, `pyMod`, `gcd`, `trunc`, `r2`, `isRepeating`). All JS engine files use UMD wrappers so they work in both Node.js (for self-tests) and browser `<script>` tags.
- **Letter keyboard is a custom A–Z grid** (4 rows × 7 columns) in `sequence.html`. Native keyboard is never triggered for letter sequences.
- **Sequence answers are always exact** — `_check_sequence_answer()` uses string equality (case-insensitive) or numeric tolerance of 0.001. No repeating-decimal tolerance is applied.

---

## Game Modes

### Open Practice
- Infinite questions until user taps "End".
- Per-question countdown timer: 10s / 15s / 20s / Unlimited (user-selected on home screen). Unlimited means no countdown, no auto-skip.
- Answer format: Open Answer (custom numpad, no native keyboard) or Multiple Choice (4 options stacked vertically, same distractor logic as Test Mode) — user-selected on home screen.
- Adaptive difficulty: 5 correct in a row → `level_modifier` +1 (max +5); 3 wrong in a row → `level_modifier` -1 (min -3). Modifier passed to question generator.
- Immediate feedback overlay after each answer (correct / wrong / skipped), with special "Accepted" message for rounded-decimal matches on repeating decimals only.
- **Pause mode** (all answer modes): ⏸ button in top bar (left of 🚩) available in all 5 game screens. Tapping freezes all timers, shows a full-screen overlay with: "⏸ Paused — Question Log (N answered)" header, scrollable list of ALL answered questions in reverse chronological order (most recent first), and a "▶ Resume" button at bottom. Each log entry shows: question number, question text, user's answer, correct answer, result icon, and a 🚩 Flag button. Resume restores timers from exact frozen values. Purely client-side; no new Flask endpoints. State kept in `sessionLog` JS array (all entries, newest prepended). For test modes: `pauseElapsedOffset` / `totalPausedSeconds` track accumulated pause time so the global countdown adjusts correctly.
- **Three flagging entry points** (all game screens):
  1. 🚩 button in top bar during a question → flags the current unanswered question.
  2. 🚩 button per entry in the pause overlay log → flags a historical answered question.
  3. 🚩 button per card in the end-of-round question log on results screens.
  All three use the same `POST /flag` endpoint. After flagging, the button becomes "✓ Flagged" and is disabled.
- Skip button always visible in bottom zone (calls same handler as timer expiry).
- Session ends at "End" button → `/end-session` POST → redirects to `/results`.
- Stats tracked: total, correct, wrong, skipped, total_time, by_category.

### Results Screens
All three results screens (`results.html`, `sequence_results.html`, `association_results.html`) share a standardised bottom button pair:

  **[ 🏠 Home ]**  **[ 🔄 Play Again ]**

- Both buttons on the same row, equal width (`flex: 1`), 12px gap, `min-height: 52px`.
- **Home**: navigates to `/`. Secondary style (dark background, accent border).
- **Play Again**: POSTs to `/restart`, `/sequences/restart`, or `/associations/restart` respectively. Server reads the stored session settings (difficulty, mode, answer_mode, timer) and re-initialises the session with the same parameters — effectively skipping the settings screen. Primary style (accent purple fill).
- **End-of-round Question Log**: each card has a 🚩 Flag button that opens a flag modal pre-filled with that question's data. Flag modal HTML and `flagFromLog()` / `submitFlagModal()` JS added to all three results templates.

After any session, `results.html` shows:
1. Badge + big score / question count.
2. Summary stats card (correct / wrong / skipped, percentages, avg time).
3. Category breakdown table.
4. **Question Log** (collapsible, default collapsed): header "Question Log (N questions)". One card per question: number, category pill, question text, result (✓/✗/—), your answer vs correct answer, 🚩 Flag button. Left border colour: green (correct), red (wrong), grey (skipped). Server-rendered via Jinja2. Practice: `time_taken` shown per card. Test Mode: time shown as `None` (omitted).

### UX / Layout (game screens)
- Game screens (`.practice-screen`, `.test-screen`): `height: 100dvh; overflow: hidden; flex column`.
- **Safe area**: `.practice-screen` and `.test-screen` use `padding: calc(12px + env(safe-area-inset-top, 0px)) 16px calc(8px + env(safe-area-inset-bottom, 0px))`. This clears the Dynamic Island / notch on all iPhone models automatically. Requires `viewport-fit=cover` in the meta tag.
- **Touch latency**: `touch-action: manipulation`, `-webkit-tap-highlight-color: transparent`, and `-webkit-touch-callout: none` applied globally via the `*` reset. A broad explicit selector (`a, button, [role="button"], input[type="submit"], input[type="button"], .mode-btn, .diff-btn, .game-tile, .modal-backdrop, .flag-delete-btn, …`) also applies `cursor: pointer; touch-action: manipulation; user-select: none` to every tappable element. Three event tiers:
  - **touchstart** — digit/dot/slash/minus/backspace numpad keys and MC option buttons. Fires at finger-DOWN (fastest). `e.preventDefault()` suppresses the subsequent click. Safe because these actions are non-destructive.
  - **touchend** — Start button (home), numpad ✓ submit, pause/flag/end buttons (practice top bar), quit/flag buttons (test top bar), home tile links, modal/confirm buttons (`_tap()` helper). Fires at finger-LIFT. `e.preventDefault()` suppresses synthesized click. A timestamp guard (`Date.now() - lastTouch < 600ms`) in the companion click listener prevents double-fire.
  - **`_tap(e, fn)` helper** — used for modal/confirm buttons that need both `ontouchend=` and `onclick=` attributes in HTML (Jinja2-rendered contexts where `addEventListener` is impractical). Pattern: if `touchend`, sets `e.currentTarget._lt = Date.now()` and calls `fn()`; if `click`, bails if `_lt` < 600ms ago.
- **Zero `onclick=` policy**: No template uses bare `onclick=` on tappable elements. Every tappable element uses either `bindBtn()` (JS-bound `touchend`), `ontouchstart=`, or paired `ontouchend=` + `onclick=` via `_tap()`. `onclick=` alone is never used because it has 300ms latency on iOS Safari.
- **PWA icon cache-busting**: `apple-touch-icon` and `manifest.json` links in `base.html` use hardcoded `/static/…?v=N` paths (not `url_for`) so query-string version params are preserved. Bump `?v=N` when regenerating icons to force iOS Safari to re-fetch.
- **`apple-touch-icon` vs manifest icons**: `apple-touch-icon` is used by iOS Safari "Add to Home Screen". The `manifest.json` icons are used by Android/Chrome. Both must be updated when regenerating icons. `manifest.json` must have `"scope": "/"` for correct PWA install scope.
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

## Sequences Game

### Route Map

| Method | URL | Description |
|---|---|---|
| GET | `/sequences` | Settings page (`sequence_home.html`) — mode, difficulty, answer format |
| POST | `/sequences/start` | Init session; redirects to `/sequences/test` (test) or `/sequences/play` (practice) |
| GET | `/sequences/play` | Practice game screen (`sequence.html`) |
| POST | `/sequences/next` | AJAX — generate next practice question, returns JSON |
| POST | `/sequences/submit` | AJAX — validate answer, update stats, returns `{result, correct_answer}` |
| POST | `/sequences/end` | Finalise practice stats, redirect to `/sequences/results` |
| GET | `/sequences/test` | Test mode screen (`sequence_test.html`) |
| POST | `/sequences/test/next` | AJAX — generate next test question (always MC), returns JSON |
| POST | `/sequences/test/submit` | AJAX — update score (+1/−1/0), append to log, returns `{score, total, correct, wrong}` |
| POST | `/sequences/test/end` | Finalise test, compute performance band, redirect to `/sequences/results` |
| GET | `/sequences/results` | Results screen (`sequence_results.html`) — handles both practice and test modes |

### Sequence Types by Difficulty

| Difficulty | Number types (count) | Letter types (count) |
|---|---|---|
| Easy (5 num, 5 let) | `arithmetic` (d ±1–5), `geometric_x2/div2`, `count_by_10` (10,20,30…), `even_numbers`, `odd_numbers` | `alphabet_step` (+1), `alphabet_step` (+2), `alphabet_rev` (−1), `vowels` (A,E,I,O,U), `alphabet_rev_skip` (skip-2 from Z) |
| Medium (11 num, 6 let) | `arithmetic` (d ±5–20), `geometric_x3/x4/div3`, `squares`, `triangular`, `primes`, `alternating_sign`, `powers_of_2`, `powers_of_3`, `multiples_N`, `collatz`, `digit_sum` *(moved back from Hard)* | `alternating_step` (+2+3), `alphabet_rev2` (−2), `skip_wrap`, `alternating_ends` (A,Z,B,Y…), `consonants`, `prime_positions` |
| Normal (14 num, 5 let) | `fibonacci`, `alternating_interleaved`, `increasing_differences`, `arithmetic_neg` (crosses zero), `geometric_alt_sign` (×−r), `square_offset` (n²+c), `alternating_two_step` (+d1+d2), `cubes`, `second_order_recurrence`, `lucas_numbers`, `catalan_numbers`, `cumulative_sum` *(moved from Medium)*, `factorial` *(moved from Hard)*, `digital_root` *(moved from Hard)* | `positional` (increasing gaps), `two_letter` (AB,CD,EF), `keyboard_row` (QWERTY), `diagonal_grid`, `two_seq_merge` |
| Hard (14 num, 6 let) | `alternating_op` (×m +a), `power_offset` (2^n+c), `recursive_double` (×2+c), `interleaved_geometric`, `recaman`, `sylvester`, `look_and_say`, `padovan`, `tribonacci`, `generalized_recurrence` (a×T(n-1)+b×T(n-2)+c), `interleaved_two_rules` (arith+geom), `second_diff_geometric` (diffs ×r), `weighted_fibonacci` (a×T(n-1)+b×T(n-2)), `alternating_recurrence` | `alphabet_wrap` (+3/4/5 mod 26), `complex_positional` (irregular gaps), `caesar_shift` (+1,+2,+3…), `fibonacci_positions`, `modular_arithmetic` (×2+1 mod 26), `interleaved_letters` (two step-sizes) |

### rule_description Field

Every question dict carries `rule_description` — a user-facing plain-language explanation (max 2 lines) of the sequence rule. It is stored in the question log (`seq_question_log` entries) and displayed as a "Rule:" row in the question log on `sequence_results.html`. Examples:
- Arithmetic: `"Each term increases by 4."`
- Geometric ×3: `"Each term is multiplied by 3."`
- Fibonacci: `"Each term is the sum of the two preceding terms (starts 2, 3)."`
- Alternating step: `"Alternating steps: +2 then +3, repeating."`
- Keyboard row: `"Consecutive letters from the top row of a QWERTY keyboard."`
- Caesar shift: `"Each letter is shifted by an increasing amount: +1, +2, +3, +4... (Caesar cipher)."`

### Test Mode (Sequences)

- Duration: 8 minutes (`SEQ_TEST_DURATION = 480` in `app.py`).
- Always MC (4 options). Open answer setting is hidden in test mode.
- Scoring: +1 correct, −1 wrong, 0 skipped.
- Questions generated on demand (not pre-generated), via `_next_seq_test_question()`.
- No feedback between questions — answer tapped → submit → next question loaded immediately.
- Global countdown timer; auto-POSTs to `/sequences/test/end` at 0:00.
- Quit button with inline confirmation (same pattern as arithmetic test).

**Performance bands** (shown on results screen):

| Score | Band |
|---|---|
| ≥ 40 | Excellent |
| 30–39 | Great |
| 20–29 | Good |
| 10–19 | Getting there |
| < 10 | Keep practising |

### Sequence MC Distractor Rules

`_num_distractors()` in `sequence_engine.py` generates 3 numeric distractors via offset strategies (±percentage, ±scaled magnitude, ±multiplier). Key constraint added in session 11:

- **Integer sequence rule**: if `_is_integer_sequence(q)` is True (no decimal point in any non-blank term), all distractor candidates are rounded to the nearest integer before deduplication. This prevents decimal distractors (e.g. 8.0, 9.5) from appearing when the correct answer is an integer. `_is_integer_sequence()` checks whether all visible terms contain no `.` character.

### Blank Position Rules

| Difficulty | Blank positions |
|---|---|
| Easy | Always last |
| Medium | Last or second-to-last |
| Normal | Any position except first |
| Hard | Any position including first |

### Session Keys

| Key | Type | Description |
|---|---|---|
| `seq_difficulty` | str | `easy` \| `medium` \| `normal` \| `hard` |
| `seq_mode` | str | `practice` \| `test` |
| `seq_answer_mode` | str | `mc` \| `open` (practice only) |
| `seq_stats` | dict | `{total, correct, wrong, skipped, total_time, by_type}` (practice only) |
| `seq_current` | dict | Current question dict from `get_sequence_question()` |
| `seq_question_log` | list | Log entries (appended per answer, both modes). Each entry includes `rule_description`. |
| `seq_results` | dict | Computed at `/sequences/end` or `/sequences/test/end`; includes `mode` key |
| `seq_test_score` | int | Running +1/−1/0 score (test mode only) |
| `seq_test_total` | int | Total questions answered (test mode only) |
| `seq_test_correct` | int | Correct count (test mode only) |
| `seq_test_wrong` | int | Wrong count (test mode only) |
| `seq_test_skipped` | int | Skipped count (test mode only) |
| `seq_test_start` | float | `time.time()` at test start (for elapsed calculation) |

### Letter Keyboard Layout

```
A  B  C  D  E  F  G
H  I  J  K  L  M  N
O  P  Q  R  S  T  U
V  W  X  Y  Z  ⌫  ✓
```
7 columns × 4 rows. For `two_letter` sequence types, allows 2-char input. All other letter types allow max 1 char. `⌫` clears the entire field; `✓` submits.

---

## Word Associations Game

### Route Map

| Method | URL | Description |
|---|---|---|
| GET | `/associations` | Settings page (`association_home.html`) — language selector (EN/DE) |
| POST | `/associations/start` | Init session; generates first question; redirects to `/associations/play` |
| GET | `/associations/play` | Game screen (`association.html`) |
| POST | `/associations/next` | AJAX — generate next question, returns JSON |
| POST | `/associations/submit` | AJAX — validate answer, update stats, returns `{correct, correct_answer, result}` |
| POST | `/associations/end` | Finalise stats, redirect to `/associations/results` |
| GET | `/associations/results` | Results screen (`association_results.html`) — stats, category breakdown, question log |

### Session Keys

| Key | Type | Description |
|---|---|---|
| `assoc_language` | str | `'en'` \| `'de'` \| `'fr'` — set at `/associations/start`, used throughout the session |
| `assoc_used_ids` | list | IDs of questions already served in this session (deduplication) |
| `assoc_stats` | dict | `{total, correct, wrong, skipped}` |
| `assoc_current` | dict | Current question dict (includes `options` and `correct_index`) |
| `assoc_question_log` | list | Log entries appended on each `/associations/submit` call |
| `assoc_results` | dict | Computed at `/associations/end`; includes `language`, `total`, `correct`, `wrong`, `skipped` |

### Question Schema

Each question in the JSON banks has this structure:

```json
{
  "id": "en_pw_001",
  "prompt_a1": "Crown",
  "prompt_a2": "Tree",
  "prompt_b1": "Head",
  "answer": "Body",
  "distractors": ["Neck", "Torso", "Skull"],
  "relationship": "The crown is the topmost part of a tree; the head is the topmost part of a body.",
  "category": "part_to_whole"
}
```

When served by `get_association_question()`, the dict is augmented with:
- `options`: list of 4 strings (answer + 3 distractors, shuffled)
- `correct_index`: int, position of the correct answer in `options`

The question is displayed as: **Crown : Tree → Head : ___?**

### 10 Analogy Categories

| Category | Description |
|---|---|
| `part_to_whole` | A1 is a component of A2; B1 is a component of the answer |
| `function_purpose` | A1 is used to perform A2; B1 is used to perform the answer |
| `cause_effect` | A1 causes or leads to A2; B1 causes or leads to the answer |
| `degree_intensity` | A1 and A2 differ only in intensity; same for B1 and answer |
| `antonyms` | A1 is the opposite of A2; B1 is the opposite of the answer |
| `category_member` | A1 belongs to category A2; B1 belongs to the answer category |
| `location` | A1 lives or exists in A2; B1 lives or exists in the answer |
| `creator_creation` | A1 creates A2; B1 creates the answer |
| `tool_user` | A1 is a tool; A2 is the person who uses it (same for B1/answer) |
| `sequence_order` | A1 comes before A2 in a natural sequence; same for B1/answer |

### Language Support

Three languages are available, selected on the settings page with a 3-button selector (`🇬🇧 English / 🇩🇪 Deutsch / 🇫🇷 Français`). Language stays fixed for the entire session and is stored in `assoc_language`.

| Code | Language | Bank file | Questions | Notes |
|---|---|---|---|---|
| `'en'` | English | `data/associations_en.json` | 150 | Original bank |
| `'de'` | German | `data/associations_de.json` | 150 | Culturally adapted, not word-for-word translated |
| `'fr'` | French | `data/associations_fr.json` | 156 | IDs: `fr_XX_NNN` format |

French bank breakdown: `part_to_whole`×15, `function_purpose`×18, `cause_effect`×15, `degree_intensity`×15, `antonyms`×15, `category_member`×18, `location`×15, `creator_creation`×15, `tool_user`×15, `sequence_order`×15.

`load_bank()` in `association_engine.py` accepts `'en'`, `'de'`, or `'fr'`. `associations_start` and `associations_restart` routes validate against this set.

### Category Reveal Behaviour

The question category is **hidden during the question** and only revealed after the user answers. In `association.html`:

- The `<div class="question-category" id="category-label">` is initialised `style="display:none"`.
- `renderQuestion()` explicitly hides it again on each new question.
- `showFeedback()` injects the category as a styled accent pill (`<span class="feedback-cat">`) at the top of the feedback answer display, so the user sees the category label only in the feedback overlay after answering.

### Question Quality Rules

Five rules enforced when authoring distractor entries in the JSON banks (validated by `data/validate_associations.py`):

1. **No too-similar pairs**: distractors must not be synonyms or near-synonyms of the correct answer (e.g. "Torso" and "Body" are too similar).
2. **No duplicate distractors**: all 3 distractors must be distinct from each other and from the correct answer.
3. **No hypernym confusion**: distractors must not be the category name itself or a direct supertype (e.g. `category_member` questions must not use "Animal" as a distractor when the answer is "Dog").
4. **Plausible but wrong**: each distractor should be a word a guesser might plausibly pick — related to the domain but clearly incorrect in the analogy.
5. **Language consistency**: German and French questions must use grammatically natural phrasings; distractors must be in the same language as the answer.

`data/validate_associations.py` runs checks 1–3 programmatically. Run it after editing any bank: `python data/validate_associations.py`. Output: flag count per bank and total. Target: 0 flags.

### Answer Validation

`check_association_answer(user_answer, correct_answer)` — case-insensitive exact string match after stripping whitespace. Always returns bool. Since it is MC-only, the user answer is always one of the 4 presented options.

### relationship Field

Each question has a `relationship` field: 1–2 sentences in plain language explaining the analogy connection. Displayed in the question log on results screen as "Relationship: …". In German questions, the relationship is also in German.

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
- **Integers**: 2-digit × 2-digit, 3-digit addition/subtraction, 2-digit division, chain multiply-then-add (`a×b+c`), three-term addition; 30% chance of negative subtraction result
- **Decimals**: 2 decimal places, division by 0.1/0.2/0.25/0.4/0.5/0.8, mixed decimal ×/+/−, add-then-subtract chains, 2dp-divisor division
- **Fractions**: fraction-to-decimal conversion, fraction addition, fraction × integer, fraction subtraction (mixed denominators; result may be negative), mixed-number-minus-fraction, three-fraction addition
- **Algebra**: two-step equations (ax+b=c), fraction coefficients, multiply-then-divide (`ax:b=c`), negative-coefficient form (`-ax+b=c`); 30% chance x is negative
- **Percentages**: decimal percentages, reverse percentages, % increase/decrease, find-the-base (`pct% of ? = result`), % of a sum (`pct% of (a+b)`)
- **Exponents & Roots** *(Normal/Hard only — see below)*
- **Ratios & Proportions** *(Normal/Hard only — see below)*

### Hard
- **Integers**: 3-digit × 2-digit, multi-step chains, bracket expressions, bracket-then-multiply (`(a-b)×c`), grouped exact division (`(a×b):c`)
- **Decimals**: division by small divisors (0.03–0.15), 2dp×2dp multiplication, add-plus-division chains
- **Fractions**: mixed number addition, fraction ÷ fraction, chain operations, mixed number subtraction, three-term fraction multiplication chain
- **Algebra**: bracket expansion, decimal coefficients, two-variable elimination, double-bracket-minus-constant, fractional equation (`(x+a)/b=c`); 30% chance x is negative
- **Percentages**: compound %, nested %, reverse hard % problems, triple successive % change, % of a difference (`pct% of (a-b)`)
- **Exponents & Roots** *(Normal/Hard only — see below)*
- **Ratios & Proportions** *(Normal/Hard only — see below)*

---

## Question Categories

Seven categories total, generated in `question_engine.py`. Five are available at every difficulty; two — `exponents_roots` and `ratios_proportions` — are **deliberately Normal/Hard-only** (no Easy/Medium variant exists; this is an intentional scope decision, not an oversight). `config.py` exposes `BASE_CATEGORIES` (the original 5, used at all difficulties) and `ADVANCED_CATEGORIES` (the 2 new ones, Normal/Hard only); `CATEGORIES` is the full union used for results-screen breakdown rows and session `by_category` dict init at every difficulty (so Easy/Medium results always show a `—` / 0-question row for the two advanced categories — expected, not a bug).

| Category | Generation summary | Difficulties |
|---|---|---|
| `integers` | Arithmetic with whole numbers; difficulty scales operand size and operation complexity | All |
| `decimals` | Decimal arithmetic; difficulty scales decimal places and divisor complexity | All |
| `fractions` | Fraction operations; difficulty scales from unit fractions to mixed number chains | All |
| `algebra` | Equation solving for x; difficulty scales from one-step to bracket/multi-variable | All |
| `percentages` | % calculations; difficulty scales from round % to compound/nested/reverse | All |
| `exponents_roots` | Squares/cubes/roots/exponent notation; Hard adds cube roots, mixed exponent expressions, non-perfect-square roots | Normal, Hard only |
| `ratios_proportions` | Simplifying ratios, solving proportions; Hard adds multi-term ratios and inverse proportion word problems | Normal, Hard only |

**Percentages — exact decimal answers**: `correct_answer` stores the mathematically exact result with no integer rounding. Examples: `53 × 1.1 = 58.3` (not 58), `446 × 0.9 = 401.4` (not 401), `80 × 1.15 = 92` (integer result, int stored), `70 × 0.95 = 66.5`. The `_trunc(val, 2)` helper is used instead of `round()` or `int()` so whole-number results are stored as `int` and non-integer results as `float`.

**Test Mode Normal distribution** (from `TEST_DISTRIBUTION` in `config.py`): Easy/Medium unchanged (~30–40% integers, ~20–25% decimals/fractions, ~10% algebra, ~10% percentages, across the 5 base categories only). Normal/Hard now split across all 7 categories: integers 24%/20%, decimals 20%/24%, fractions 20%/20%, algebra 8%/8%, percentages 8%/8%, exponents_roots 10%/10%, ratios_proportions 10%/10% (Normal/Hard respectively) — the original 5-category Normal/Hard weights were scaled by 0.8 to make room for the two new categories at 10% each.

**Practice Mode**: equal random distribution across all 5 base categories at Easy/Medium; equal random distribution across all 7 categories (base + advanced) at Normal/Hard. Selection is difficulty-aware via `_next_practice_question()` in `app.py`.

### Exponents & Roots — category detail
- **Normal**: squares of 2-digit numbers (`a^2`), cubes of 2–10 (`a^3`), square roots of perfect squares up to 400 (`√n`), simple exponent notation (`base^exp`, base/exp 2–5).
- **Hard**: cube roots of perfect cubes (`∛n`), mixed exponent expressions (`a^2 + b^2`), larger exponents (base 2–6, exp 3–6), and non-perfect-square roots requiring a decimal answer (`√n = ? (3 d.p.)`, answer pre-rounded to 3dp). The irrational-root answer is accepted via the existing generic 0.2%-relative-tolerance exact-match check in `_check_answer()` (`app.py`) — because the stored answer is already rounded to 3dp, this tolerance alone comfortably accepts reasonable nearby entries without needing the repeating-decimal (`is_repeating()`) rounding path at all. All question text includes a trailing `= ?` so it satisfies `_validate_question()`'s Check 5 (text must contain a math symbol) even for root/exponent notation that has no `+/-/x/// /:/×/%` of its own.

### Ratios & Proportions — category detail
- **Normal**: simplifying a ratio to lowest terms (`Simplify the ratio a : b`); solving a simple proportion `a : b = c : x`.
- **Hard**: multi-term ratio division (`Divide N in the ratio a:b:c, find the ___ share`); inverse proportion word problems (`a workers → b days, c workers → ? days`).
- **Answer-format decision**: "Simplify the ratio" answers are expressed as a **simplified fraction** (e.g. ratio `30 : 18` → answer `1 2/3`, reusing `_frac_str`/`_clean_frac_ans`), which reuses `_check_answer()`'s existing fraction-string parsing and `_fraction_distractors()` unmodified — no new "a:b" answer format was added. All other ratio sub-patterns (proportion-solving, multi-term share, inverse proportion) resolve to a single plain number and reuse the existing numeric-answer path and `_numeric_distractors()` unmodified.

### Offline parity gap (known, deliberate)
`static/js/question_engine.js` (the offline JS port) has **not** been updated for this session's changes — it does not yet generate `exponents_roots` or `ratios_proportions` questions, nor the new Normal/Hard sub-patterns added to the 5 base categories. Offline mode will keep serving the pre-session question set until offline-JS parity work resumes. This is a known gap, not a bug.

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
- **Delete endpoint**: `POST /flags/delete` — receives JSON `{ "index": N }` where N is the 0-based index in the reverse-chronological display order (index 0 = newest). Loads the file, converts to reverse order, removes entry at N, converts back, writes. Returns `{ "success": true, "remaining": M }` or `{ "error": "..." }` with status 400/500. Handles missing file (returns success, 0), index out of range (400).
- **Frontend deletion**: each flag card has a "✕ Delete" button. Click shows inline confirmation `"Delete this flag? [Yes] [Cancel]"`. Confirmed → `fetch` to `/flags/delete` → card fades out (opacity→0, 200ms) → removed from DOM → count header updated. If all deleted, empty-state message shown. No page reload. After each deletion, remaining cards are re-indexed in JS (`reindexCards()`).
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

**Standing rule — never touch `.env` as a side effect**: `.env` is a local-only, git-ignored file. It must never be deleted, overwritten, or modified as a side effect of any other task — including cleanup of temporary test files, scratch fixtures, or other artifacts created during a session. This applies to every future session, not just a one-off caution. If `.env` genuinely needs to be regenerated for any reason, that must be flagged explicitly to the user *before* proceeding, never done silently as part of unrelated cleanup.

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

Full session-by-session history has moved to `CHANGELOG.md`. This file documents current architecture only.

