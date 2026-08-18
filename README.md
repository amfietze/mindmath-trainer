# MindMath Trainer

A personal iPhone PWA for practicing IQ-test-style mental skills — mental arithmetic, number/letter sequences, and verbal analogies — built to run as a home-screen app via Safari's "Add to Home Screen."

## Features

- **Three games**: Mental Arithmetic (fast-paced, timed arithmetic training, 7 question categories, 4 difficulty levels), Sequences (number and letter pattern puzzles), and Word Associations (verbal analogies in English, German, and French).
- **Two modes per game**: an untimed adaptive Practice mode and a timed, scored Test mode.
- **Offline support**: installable as a PWA with a service worker, so all three games remain playable without a network connection.
- **Adaptive difficulty**: Practice mode adjusts question difficulty based on recent performance.
- **Question flagging**: any question can be flagged for later review if it seems wrong or unclear.

## Tech Stack

- Python 3.11, Flask
- Gunicorn (production WSGI server)
- Vanilla JavaScript, Jinja2 templates
- No database — session state is in-memory; flags persist to a local JSON file
- Service worker + offline JS ports for full offline play

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# then edit .env and set FLASK_ENV=development and a SECRET_KEY value

# 4. Run the app
python app.py
# binds 0.0.0.0:5000 — open http://localhost:5000,
# or http://<your-local-ip>:5000 from another device on the same network
```

## Project Status

This is a personal/hobby project built for my own use, and it isn't actively seeking outside contributions. Feel free to fork it or open an issue if something's broken.

## License

Released under the MIT License — see [LICENSE](LICENSE) for details.
