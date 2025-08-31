# Backend (FastAPI)

- Python API with SQLAlchemy and PostgreSQL.
- Defaults match `docker-compose.yml` (Postgres on `localhost:5433`).

## Prerequisites

- Python 3.10+
- Docker (for the DB) and Docker Compose

## Setup

1) Start the database

```bash
# from repo root
docker compose up -d db
# or: docker-compose up -d db
```

2) Create a virtualenv and install deps

```bash
cd backend
python -m venv .venv
. .venv/Scripts/Activate.ps1   # PowerShell on Windows
# source .venv/bin/activate    # bash/zsh on macOS/Linux
pip install -U pip
pip install -r requirements.txt
```

3) Run the API (hot-reload)

```bash
# from backend directory
uvicorn main:app --reload --port 8000
# or from repo root
# uvicorn backend.main:app --reload --port 8000
```

## Endpoints (quick test)

- GET `/` – health message
- POST `/users/` – create user `{ email, password, nickname? }`
- POST `/login` – OAuth2 form `{ username: email, password }`
- GET `/licitacoes` – list with analyses
- POST `/analises/` – `{ licitacao_ids: number[] }` creates background analyses

Notes
- CORS allows `http://localhost:3000` for the frontend.
- DB connection is hardcoded in `src/database.py` to match compose defaults.
