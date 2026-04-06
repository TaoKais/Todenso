# Todenso

Todenso is a local Flask web app for creating user accounts and saving each user's private historical ENSO drawings on the same machine.

## Features

- Create local users with password-protected drawing saves
- Draw ENSO sketches directly in the browser
- Store the drawing history in a local SQLite database
- Run directly with Python or inside Docker

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\app.py
```

Open `http://localhost:8000`.

## Run with Docker

```powershell
docker build -t todenso .
docker run --rm -p 8000:8000 -v "${PWD}\data:/app/data" todenso
```

## Data storage

- SQLite database: `data/todenso.sqlite3`
- User passwords are stored as hashes
- Drawings are stored as JSON path data per user
