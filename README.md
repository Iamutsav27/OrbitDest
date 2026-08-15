# Minimal Flask API

This project contains a small Flask API with three endpoints and tests.

Quick start

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the app:

```bash
python app.py
```

3. Run tests:

```bash
pytest -q
```

Docker
------

Build and run with Docker:

```bash
docker build -t omnichannel:latest .
docker run -p 5000:5000 omnichannel:latest
```

Or with docker-compose:

```bash
docker-compose up --build
```

CI
--

The repository includes a GitHub Actions workflow at `.github/workflows/ci.yml` which runs `pytest` on push and pull requests.

Files

- `app.py`: Flask application
- `tests/test_app.py`: pytest tests
- `requirements.txt`: dependencies
