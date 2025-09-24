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

- GET `/` — health message
- POST `/users/` — create user `{ email, password, nickname? }`
- POST `/login` — OAuth2 form `{ username: email, password }`
- GET `/licitacoes` — list with analyses
- POST `/analises/` — `{ licitacao_ids: number[] }` creates background analyses

Notes
- CORS allows `http://localhost:3000` for the frontend.
- DB connection is hardcoded in `src/database.py` to match compose defaults.

## Novos Endpoints

- POST `/buscar_licitacoes`
  - Body: `{ data_inicio?: 'YYYY-MM-DD', data_fim?: 'YYYY-MM-DD', uf?: 'SP' | 'DF' | ..., codigo_modalidade?: number=6, tamanho_pagina?: number=10 }`
  - Consulta o PNCP e salva as licitações retornadas no banco; retorna um resumo do salvamento.

- POST `/rag/indexar/{licitacao_id}`
  - Extrai texto do edital principal (anexo local) e cria embeddings (chunking) no banco.
  - Requisitos: pacote `google-generativeai` instalado e variável de ambiente `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`).
  - Resposta: `{ "indexed_chunks": number }`.

- POST `/rag/perguntar/{licitacao_id}`
  - Body: `{ "question": string, "top_k"?: number=4 }`
  - Retorna os trechos mais relevantes: `{ "results": [{ "score": number, "chunk": string }, ...] }`.

- GET `/pesquisa/precos_por_item?descricao=CADEIRA&limit_ids=30&fonte=ambas`
  - Pesquisa preços via ComprasGov (contratos/itens) e/ou PNCP e consolida estatísticas.
  - Resposta inclui: `precos_encontrados`, `stats` (min/max/mean/median), `detalhes`, e `licitacoes_locais_consideradas` (compatível com testes).

- POST `/oportunidades/ativas`
  - Consulta propostas em aberto (PNCP). Aceita dois modos:
    - Modo simples (default): filtros diretos (`uf`, `data_inicio`, `data_fim`, `codigo_modalidade`, `pagina`, `tamanho_pagina`).
    - Modo amplo (`amplo=true`): varredura por blocos de data/UF/modalidades com paginação segura (`total_days`, `step_days`, `ufs[]`, `modal_codes[]`, `page_limit`, `tamanho_pagina`, `data_fim_ref`).
  - Retorno: lista JSON consolidada (sem duplicatas por `numeroControlePNCP` sempre que possível).

### Exemplos (curl)

Simples (filtra DF nos últimos dias):
```bash
curl -X POST http://localhost:8000/oportunidades/ativas \
  -H 'Content-Type: application/json' \
  -d '{
        "uf": "DF",
        "data_inicio": "2025-01-01",
        "data_fim": "2025-01-15",
        "codigo_modalidade": 6,
        "pagina": 1,
        "tamanho_pagina": 50
      }'
```

Varredura ampla (14 dias, blocos de 7 dias, SP/RJ):
```bash
curl -X POST http://localhost:8000/oportunidades/ativas \
  -H 'Content-Type: application/json' \
  -d '{
        "amplo": true,
        "total_days": 14,
        "step_days": 7,
        "ufs": ["SP", "RJ"],
        "modal_codes": [6, 1],
        "page_limit": 25,
        "tamanho_pagina": 50
      }'
```

## RAG (Embeddings)

- Dependências: `pip install google-generativeai`.
- Ambiente: defina `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`).
- Modelo padrão: `text-embedding-004` (Gemini).
- Fluxo típico:
  - `POST /rag/indexar/{licitacao_id}`: extrai texto do PDF (pdfplumber; fallback OCR) e indexa.
  - `POST /rag/perguntar/{licitacao_id}`: calcula similaridade por cosseno e retorna top_k.

## OCR e Extração (robustez e cache)

O serviço de análise usa extração nativa de PDF/HTML e faz fallback para OCR (Tesseract) quando necessário. Resultados são cacheados por URL para evitar reprocessamento pesado.

Variáveis de ambiente opcionais:

- TESSERACT_CMD: caminho do binário `tesseract` (Windows ex.: `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`)
- TESSERACT_LANG: idioma do OCR (default `por`)
- OCR_MAX_PAGES: páginas máximas no OCR de PDF (default `10`)
- OCR_DPI: resolução para conversão PDF→imagem (default `200`)
- OCR_MIN_CHARS: early-stop do OCR quando acumular este mínimo de caracteres (default `1500`)
- OCR_CACHE_DIR: diretório do cache (default `backend/tmp/ocr_cache`)
- OCR_CACHE_TTL: TTL do cache em segundos (default `259200`, 3 dias)

Endpoints úteis:
- GET `/health/ocr` — diagnóstico de bibliotecas e binários (pytesseract, poppler/pdftoppm, etc.).
