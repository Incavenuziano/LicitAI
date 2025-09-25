# Exemplo de Pipeline (GitHub Actions)

```yaml
name: Backend CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
      TRANSPARENCIA_API_KEY: ${{ secrets.TRANSPARENCIA_API_KEY }}
      NEXTAUTH_SECRET: ${{ secrets.NEXTAUTH_SECRET }}
      NEXT_PUBLIC_API_URL: ${{ vars.NEXT_PUBLIC_API_URL }}
      POSTGRES_HOST: ${{ secrets.POSTGRES_HOST }}
      POSTGRES_PORT: ${{ secrets.POSTGRES_PORT }}
      POSTGRES_DB: ${{ secrets.POSTGRES_DB }}
      POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
      POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Validate secrets
        run: python scripts/check_secrets.py
      - name: Install backend deps
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest
```

Ajustar o job para o frontend adicionando `npm install`/`npm test` e reutilizando o mesmo passo `Validate secrets`.
