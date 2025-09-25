# Plano de Rotação de Segredos

## Escopo

- `GOOGLE_API_KEY` / `GEMINI_API_KEY` (Google Gemini / Agno)
- `TRANSPARENCIA_API_KEY` (Portal da Transparência)
- `NEXTAUTH_SECRET` (Frontend / NextAuth)

## Etapas Gerais

1. **Inventário**
   - Identificar onde as chaves foram utilizadas: repositório local, pipelines, instâncias em execução, documentação compartilhada.
   - Remover versões antigas de backups ou serviços (ex.: notebooks, scripts ad hoc) antes da rotação.

2. **Gerar credenciais novas**
   - Gemini: console Google AI Studio ? reemitir chave ou criar projeto/API key dedicados.
   - Transparência: portal oficial (https://api.portaldatransparencia.gov.br) ? revogar chave anterior e solicitar nova.
   - NextAuth: gerar `openssl rand -hex 32` ou `python -c "import secrets;print(secrets.token_hex(32))"`.

3. **Propagar em um gerenciador de segredos** (recomendado)
   - Azure Key Vault, AWS Secrets Manager, Google Secret Manager ou HashiCorp Vault.
   - Crie entradas com nomes claros (ex.: `licitai-google-gemini`, `licitai-transparencia`, `licitai-nextauth-secret`).
   - Defina políticas de acesso (apps/API backend/CI) com princípio de menor privilégio.

4. **Atualizar pipelines/deploy**
   - GitHub Actions: usar `Settings ? Secrets and variables ? Actions` e criar `GOOGLE_API_KEY`, `TRANSPARENCIA_API_KEY`, `NEXTAUTH_SECRET`.
   - GitLab CI / Azure DevOps / outros: inserir como variáveis protegidas e mascaradas.
   - Docker Compose / Kubernetes:
     - Compose: criar arquivo `.env` **local** a partir de `backend/.env.example` e `frontend/.env.local.example` apenas em ambientes seguros.
     - Kubernetes: montar `Secret` e injetar como env vars nos deployments (`envFrom: secretRef`).

5. **Atualizar aplicações**
   - Backend: garantir que `uvicorn` leia as novas variáveis no ambiente antes do start (`GOOGLE_API_KEY`, `TRANSPARENCIA_API_KEY`).
   - Frontend: configurar `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL` via ambiente ou plataforma (Vercel, etc.).
   - Reiniciar serviços após confirmar que as novas chaves estão presentes (`echo $ENV_VAR` em pods/containers).

6. **Revogar credenciais antigas**
   - Depois de validar o funcionamento com as chaves novas, revogar a chave anterior em cada provedor.
   - Registrar data/hora e responsável pela rotação.

7. **Monitorar**
   - Habilitar alertas de uso indevido/anômalo nas plataformas (quando disponível).
   - Revisar logs do backend após a troca para garantir que não há erros de autenticação.

## Checklist por Ambiente

### Desenvolvimento Local
- Copiar `.env.example` ? `.env` (backend) e `.env.local.example` ? `.env.local` (frontend).
- Popular com as novas credenciais via gerenciador de segredos (nunca commitar).
- Adicionar passos de `pre-commit` ou `git-secrets` para prevenir vazamentos futuros.

### CI/CD
- Atualizar os secrets do pipeline antes do próximo deploy.
- Registar no README ou runbook a localização das variáveis.
- Usar máscaras no output dos jobs (`::add-mask::` no GitHub Actions, `mask:` no GitLab).

### Produção
- Se usar orquestração em nuvem, preferir `Secret Manager` nativo e montar como env vars ou volumes.
- Automatizar a rotação periódica (ex.: script mensal que reemite chaves Gemini).
- Documentar fallback: como restaurar chave antiga caso precise reverter rápido (desde que ainda válida).

## Automação Sugerida

Criar workflow `scripts/rotate_secrets.md` (ou Playbook interno) com comandos:

```bash
# Exemplo: gerar novo NEXTAUTH_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# Validar presença antes do deploy
python - <<'PY'
import os, sys
required = ["GOOGLE_API_KEY", "TRANSPARENCIA_API_KEY", "NEXTAUTH_SECRET"]
missing = [k for k in required if not os.getenv(k)]
if missing:
    sys.exit(f"Missing secrets: {', '.join(missing)}")
PY
```

Adicionar este script aos pipelines (stage de `pre-deploy`) para evitar releases sem segredos novos.

## Governança

- Manter histórico de rotações (data, motivo, quem executou) no runbook interno ou wiki.
- Definir SLA de rotação (ex.: a cada 90 dias) e alertar responsáveis.
- Revisar permissões de quem pode criar/apagar secrets no repositório ou na nuvem.

