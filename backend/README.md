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

- GET `/` â€“ health message
- POST `/users/` â€“ create user `{ email, password, nickname? }`
- POST `/login` â€“ OAuth2 form `{ username: email, password }`
- GET `/licitacoes` â€“ list with analyses
- POST `/analises/` â€“ `{ licitacao_ids: number[] }` creates background analyses

Notes
- CORS allows `http://localhost:3000` for the frontend.
- DB connection is hardcoded in `src/database.py` to match compose defaults.

## OCR e ExtraÃ§Ã£o (robustez e cache)

O serviÃ§o de anÃ¡lise usa extraÃ§Ã£o nativa de PDF/HTML e faz fallback para OCR (Tesseract) quando necessÃ¡rio. Resultados sÃ£o cacheados por URL para evitar reprocessamento pesado.

VariÃ¡veis de ambiente opcionais:

- TESSERACT_CMD: caminho do binÃ¡rio `tesseract` (Windows ex.: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- TESSERACT_LANG: idioma do OCR (default `por`)
- OCR_MAX_PAGES: pÃ¡ginas mÃ¡ximas no OCR de PDF (default `10`)
- OCR_DPI: resoluÃ§Ã£o para conversÃ£o PDFâ†’imagem (default `200`)
- OCR_MIN_CHARS: earlyâ€‘stop do OCR quando acumular este mÃ­nimo de caracteres (default `1500`)
- OCR_CACHE_DIR: diretÃ³rio do cache (default `backend/tmp/ocr_cache`)
- OCR_CACHE_TTL: TTL do cache em segundos (default `259200`, 3 dias)

Endpoints Ãºteis:
- GET `/health/ocr` â€” diagnÃ³stico de bibliotecas e binÃ¡rios (pytesseract, poppler/pdftoppm, etc.).
