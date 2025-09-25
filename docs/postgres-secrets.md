# Configuracao de Segredos do Postgres

Use as credenciais do banco (as mesmas do docker-compose.yml) para popular o gerenciador de segredos e variaveis de ambiente do backend.

## Valores-padrao

| Variavel          | Valor sugerido     |
|------------------|--------------------|
| POSTGRES_HOST     | localhost          |
| POSTGRES_PORT     | 5433               |
| POSTGRES_DB       | licitai            |
| POSTGRES_USER     | licitai_user       |
| POSTGRES_PASSWORD | licitai_password   |

Ajuste os valores conforme o ambiente real.

## GitHub Actions

1. Abra Settings > Secrets and variables > Actions.
2. Crie os secrets:
   - POSTGRES_HOST
   - POSTGRES_PORT
   - POSTGRES_DB
   - POSTGRES_USER
   - POSTGRES_PASSWORD
3. Exporte-os no workflow via bloco env:.

## Execucao local (PowerShell)

`
Set-Item -Path Env:POSTGRES_HOST localhost
Set-Item -Path Env:POSTGRES_PORT 5433
Set-Item -Path Env:POSTGRES_DB licitai
Set-Item -Path Env:POSTGRES_USER licitai_user
Set-Item -Path Env:POSTGRES_PASSWORD licitai_password
`

## Execucao local (bash/zsh)

`
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5433
export POSTGRES_DB=licitai
export POSTGRES_USER=licitai_user
export POSTGRES_PASSWORD=licitai_password
`

Reinicie o backend (uvicorn main:app --reload --port 8000) apos definir as variaveis.

## Check automatico

O script python scripts/check_secrets.py agora valida as variaveis de Postgres. Execute-o em pipelines ou antes de iniciar a API.
