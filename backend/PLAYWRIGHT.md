Playwright para captura de editais

Visão geral
- Abre a página da compra, tenta localizar links/botões de download por texto e por atributos, captura o download (PDF/ZIP), extrai ZIPs e escolhe o PDF mais provável com base no nome do arquivo (edital > instrumento > termo de referencia > anexo).
- Salva os arquivos em `backend/tmp/playwright_downloads/<timestamp>_<hash>/`.

Requisitos
- pip install playwright
- python -m playwright install chromium

Como habilitar no backend
- Defina a variável de ambiente `USE_PLAYWRIGHT_EDITAL=1` antes de iniciar a API.
  - Windows PowerShell: `setx USE_PLAYWRIGHT_EDITAL 1`
  - Bash/Zsh: `export USE_PLAYWRIGHT_EDITAL=1`

Onde está a integração
- A função `resolve_edital_pdf_with_playwright(url)` foi adicionada em `backend/src/analysis_service.py`.
- Quando `USE_PLAYWRIGHT_EDITAL=1`, `extract_text_from_link` tenta usar Playwright primeiro para obter o PDF local e extrair texto.

Notas
- Se um ZIP for baixado, os PDFs internos são pontuados por heurística de nome. Você pode ajustar os pesos em `_score_pdf_name`.
- Caso Playwright não esteja disponível ou falhe, o backend usa o fluxo de extração anterior (requests + BeautifulSoup + pdfplumber/pypdf + OCR).

Captcha e bloqueios anti-bot
- A página pública do Compras pode exibir hCaptcha e bloquear navegação headless.
- Use modo headful e/ou reaproveite sessão gravada para contornar o captcha manualmente:
  - Modo headful: defina `USE_PLAYWRIGHT_HEADFUL=1` e rode uma chamada que abra o navegador; resolva o captcha manualmente.
  - Storage state: após resolver o captcha, salve o estado da sessão e reutilize:

Exemplo para salvar storage state:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/")
    input("Resolva o captcha e navegue até a página desejada; tecle ENTER para salvar...")
    ctx.storage_state(path="backend/tmp/pw_storage.json")
    browser.close()
```

Depois, defina `PLAYWRIGHT_STORAGE=backend/tmp/pw_storage.json` (e opcionalmente `USE_PLAYWRIGHT_HEADFUL=0`) para reutilizar a sessão.
