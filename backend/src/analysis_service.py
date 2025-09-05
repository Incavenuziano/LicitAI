import time
import traceback
import re
import os
import shutil
import subprocess
import hashlib
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple, Dict, Any
import json
import unicodedata
from urllib.parse import urljoin

from sqlalchemy.orm import Session
from .database import SessionLocal
from . import crud
from .agents.agente_analise import analisar_licitacoes_com_pandas
from .integrations.pncp import (
    pncp_buscar_por_link,
    pncp_buscar_por_link_expanded,
    pncp_buscar_por_numero_compra_expanded,
    listar_documentos_compra,
    baixar_documento_por_sequencial,
)
from .integrations.cnpj_resolver import resolve_cnpj_by_name_via_pncp, resolve_cnpj_by_name_via_google
from . import crud as crud_mod
from .integrations.anexos import pncp_extrair_anexos_de_pagina

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # Fallback se nÃ£o instalado

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # Fallback se nÃ£o instalado

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
except Exception:  # pragma: no cover
    pdfminer_extract_text = None
try:
    import pypdf  # type: ignore
except Exception:  # pragma: no cover
    pypdf = None
try:
    from pdf2image import convert_from_bytes  # type: ignore
except Exception:  # pragma: no cover
    convert_from_bytes = None
try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None
try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None

try:
    from charset_normalizer import from_bytes as cn_from_bytes  # type: ignore
except Exception:  # pragma: no cover
    cn_from_bytes = None

# Playwright (opcional)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # type: ignore
except Exception:  # pragma: no cover
    sync_playwright = None  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

# --- ConfiguraÃ§Ãµes e utilitÃ¡rios de cache/paths ---
_BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
_CACHE_DIR = Path(os.getenv("OCR_CACHE_DIR", _BASE_DIR / "tmp" / "ocr_cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL = int(os.getenv("OCR_CACHE_TTL", "259200"))  # 3 dias por padrÃ£o


def _cache_key(url: str) -> str:
    m = hashlib.sha256()
    m.update(url.encode("utf-8", errors="ignore"))
    return m.hexdigest()


def _cache_path(url: str) -> Path:
    return _CACHE_DIR / f"{_cache_key(url)}.json"


def _cache_get(url: str) -> Optional[Dict[str, Any]]:
    try:
        p = _cache_path(url)
        if not p.exists():
            return None
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        ts = float(data.get("ts", 0))
        if time.time() - ts > _CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _cache_put(url: str, payload: Dict[str, Any]) -> None:
    try:
        payload = dict(payload)
        payload["ts"] = time.time()
        p = _cache_path(url)
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _fetch_url(url: str, timeout: int = 25) -> Tuple[Optional[bytes], str]:
    """Baixa conteÃºdo do URL. Retorna (bytes, content_type)."""
    if not requests:
        return None, ""
    try:
        headers = {"User-Agent": "LicitAI/1.0 (+https://example.local)"}
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        return resp.content, ctype
    except Exception:
        return None, ""

def _robust_decode(data: bytes) -> str:
    """Decodes byte string using charset-normalizer or falls back to utf-8."""
    if not data:
        return ""
    if cn_from_bytes:
        try:
            results = cn_from_bytes(data)
            best_match = results.best()
            if best_match:
                return str(best_match)
        except Exception:
            pass  # Fallback to default
    # Fallback if library is missing or fails
    return data.decode("utf-8", errors="replace")


def _extract_text_from_pdf(data: bytes) -> Optional[str]:
    """Extrai texto de PDF priorizando pdfplumber; fallback para pypdf.

    HeurÃ­sticas: tenta senha vazia em PDFs protegidos antes da extraÃ§Ã£o.
    """
    # 1) Tenta com pdfplumber (mais robusto para layout)
    if pdfplumber is not None:
        try:
            texts: list[str] = []
            # Tenta abrir com password vazio primeiro
            try:
                pdf = pdfplumber.open(BytesIO(data), password="")
            except Exception:
                pdf = pdfplumber.open(BytesIO(data))
            with pdf:
                for page in pdf.pages:
                    try:
                        txt = page.extract_text() or ""
                        if txt:
                            texts.append(txt)
                    except Exception:
                        continue
            combined = "\n".join(texts).strip()
            if combined:
                return combined
        except Exception:
            pass

    # 2) Fallback pypdf
    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(BytesIO(data))
            try:
                if getattr(reader, "is_encrypted", False):
                    try:
                        reader.decrypt("")  # tenta senha vazia
                    except Exception:
                        pass
            except Exception:
                pass
            texts = []
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or "")
                except Exception:
                    continue
            combined = "\n".join(texts).strip()
            if combined:
                return combined
        except Exception:
            pass

    return None

    # 3) Fallback pdfminer.six (quando disponível)
    if pdfminer_extract_text is not None:
        try:
            from io import BytesIO as _BIO
            txt = pdfminer_extract_text(_BIO(data))
            txt = (txt or "").strip()
            if txt:
                return txt
        except Exception:
            pass

    return None


def _extract_text_from_html(data: bytes) -> Optional[str]:
    html = _robust_decode(data)
    if BeautifulSoup is None:
        try:
            return re.sub(r"<[^>]+>", " ", html)
        except Exception:
            return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return None


def _analisar_texto_edital(texto: str) -> str:
    """Extrai alguns itens Ãºteis do texto do edital e monta um resumo."""
    lower = texto.lower()
    def norm(s: str) -> str:
        return s

    # Valores monetÃ¡rios (R$ 1.234,56)
    valores = re.findall(r"R\$\s?[\d\.]{1,12},\d{2}", texto)
    valores_unicos = sorted(set(valores))[:10]

    # Datas dd/mm/yyyy
    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto)
    datas_unicas = sorted(set(datas))[:10]

    # Palavrasâ€‘chave
    chaves = {
        "modalidade": any(k in lower for k in ["pregÃ£o", "pregao", "tomada de preÃ§os", "concorrÃªncia", "dispensa"]),
        "habilitacao": ("habilita" in lower),
        "objeto": ("objeto" in lower or "do objeto" in lower),
        "vigencia": ("vigÃªncia" in lower or "vigencia" in lower),
        "proposta": ("proposta" in lower),
    }

    # ClassificaÃ§Ã£o simples (ServiÃ§o vs AquisiÃ§Ã£o)
    servico_kw = ["serviÃ§", "servic", "execuÃ§", "execuc", "manuten", "consultor"]
    aquis_kw = ["aquisiÃ§", "aquisic", "compra", "fornecimento", "material", "equipamento"]
    tipo = "ServiÃ§o" if any(k in lower for k in servico_kw) else ("AquisiÃ§Ã£o" if any(k in lower for k in aquis_kw) else "Outros")

    partes = [
        "--- Resumo automÃ¡tico do edital ---",
        f"Tamanho do texto: ~{len(texto):,} caracteres",
        f"ClassificaÃ§Ã£o sugerida: {tipo}",
        f"Valores monetÃ¡rios (amostra): {', '.join(valores_unicos) if valores_unicos else 'nÃ£o encontrados'}",
        f"Datas encontradas (amostra): {', '.join(datas_unicas) if datas_unicas else 'nÃ£o encontradas'}",
        "Indicadores de conteÃºdo:",
        f" - Modalidade mencionada: {'sim' if chaves['modalidade'] else 'nÃ£o'}",
        f" - HabilitaÃ§Ã£o: {'sim' if chaves['habilitacao'] else 'nÃ£o'}",
        f" - Objeto: {'sim' if chaves['objeto'] else 'nÃ£o'}",
        f" - VigÃªncia: {'sim' if chaves['vigencia'] else 'nÃ£o'}",
        f" - Proposta: {'sim' if chaves['proposta'] else 'nÃ£o'}",
    ]
    return "\n".join(partes)


def _find_pdf_links_from_html(data: bytes, base_url: str) -> list[str]:
    """Procura links de PDF em uma pÃ¡gina HTML e retorna URLs absolutas."""
    links: list[str] = []
    html = _robust_decode(data)
    if not html:
        return links

    hrefs: list[str] = []
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                text = (a.get_text() or "").lower()
                hrefs.append(href)
                # Preferir Ã¢ncoras com palavras-chave
                if href.lower().endswith(".pdf") or \
                   ("pdf" in href.lower()) or \
                   ("edital" in text) or ("anexo" in text) or ("download" in text):
                    links.append(urljoin(base_url, href))
        except Exception:
            pass

    # Fallback rÃ¡pido via regex
    try:
        regex_links = re.findall(r"href=\"([^\"]+)\"|href='([^']+)'", html, flags=re.I)
        for a, b in regex_links:
            href = a or b
            if not href:
                continue
            if href not in hrefs and (href.lower().endswith(".pdf") or "pdf" in href.lower()):
                links.append(urljoin(base_url, href))
    except Exception:
        pass

    # Remover duplicatas preservando ordem
    seen = set()
    unique = []
    for u in links:
        if u not in seen:
            unique.append(u)
            seen.add(u)
    return unique[:5]


# --- Playwright: captura de download (PDF/ZIP) e resolucao do melhor PDF ---
def _score_pdf_name(name: str) -> int:
    """Pontua o arquivo por relevancia do nome.

    Peso (exemplo):
      edital > instrumento > termo de referencia > anexo.
    """
    try:
        base = _strip_accents(name.lower())
    except Exception:
        base = name.lower()
    score = 0
    # Pesos principais
    if "edital" in base:
        score += 100
    if "instrumento" in base or "instrumento convocatorio" in base:
        score += 70
    if ("termo" in base and "refer" in base) or "tr_" in base or "_tr" in base:
        score += 60
    if "anexo" in base:
        score += 15
    # Ajustes menores
    if "retificacao" in base or "retifica" in base:
        score += 5
    if "minuta" in base and "contrat" in base:
        score += 20
    if base.endswith(".pdf"):
        score += 5
    return score


def _extract_zip_best_pdf(zip_path: Path, out_dir: Path) -> Optional[Path]:
    import zipfile
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(out_dir)
        pdfs: list[Path] = []
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f.lower().endswith('.pdf'):
                    pdfs.append(Path(root) / f)
        if not pdfs:
            return None
        best = max(pdfs, key=lambda p: _score_pdf_name(p.name))
        return best
    except Exception:
        return None


def resolve_edital_pdf_with_playwright(url: str, download_base: Optional[Path] = None, timeout_ms: int = 30000) -> Optional[Path]:
    """Abre a pagina com Playwright, tenta links/botoes de download e captura PDF/ZIP.

    - Se ZIP, extrai e pontua PDFs por relevancia.
    - Retorna caminho do PDF mais provavel ou None.

    Requer:
      pip install playwright
      playwright install chromium
    """
    if sync_playwright is None:
        return None
    try:
        base = download_base or (Path(__file__).resolve().parent.parent / 'tmp' / 'playwright_downloads')
        base.mkdir(parents=True, exist_ok=True)
        workdir = base / (str(int(time.time())) + '_' + _cache_key(url)[:8])
        workdir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            headful_env = os.getenv("USE_PLAYWRIGHT_HEADFUL", "0").strip().lower() in {"1", "true", "yes"}
            storage_state_path = os.getenv("PLAYWRIGHT_STORAGE", "").strip() or None
            launch_kwargs = {}
            if headful_env:
                launch_kwargs["headless"] = False
            else:
                launch_kwargs["headless"] = True
            # Try to look less like automation
            browser = p.chromium.launch(**launch_kwargs)
            context_kwargs = {
                "accept_downloads": True,
                "locale": "pt-BR",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            }
            if storage_state_path and Path(storage_state_path).exists():
                context_kwargs["storage_state"] = str(storage_state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url)
            try:
                page.wait_for_load_state('networkidle', timeout=timeout_ms)
            except PlaywrightTimeoutError:
                pass

            # Heuristicas de selecao de links/botoes
            candidates = []
            # Texto
            texts = [
                r"edital", r"instrumento", r"termo de referencia|TR", r"anexo",
                r"baixar|download", r"abrir", r"visualizar",
            ]
            for t in texts:
                try:
                    candidates.append(page.locator(f"a:has-text(/{t}/i)"))
                except Exception:
                    pass
            # Atributos
            selectors = [
                "a[download]", "a[href$=.pdf]", "a[href*=edital]", "a[href*=.zip]",
                "button:has-text('Download')", "button:has-text('Baixar')",
            ]
            for sel in selectors:
                try:
                    candidates.append(page.locator(sel))
                except Exception:
                    pass

            best_pdf: Optional[Path] = None

            def handle_download(click_fn) -> Optional[Path]:
                try:
                    with page.expect_download(timeout=timeout_ms) as dl_info:
                        click_fn()
                    dl = dl_info.value
                    suggested = dl.suggested_filename or 'download'
                    target = workdir / suggested
                    dl.save_as(str(target))
                    if target.suffix.lower() == '.pdf':
                        return target
                    if target.suffix.lower() == '.zip':
                        extracted_dir = workdir / (target.stem + "_unzipped")
                        return _extract_zip_best_pdf(target, extracted_dir)
                except PlaywrightTimeoutError:
                    return None
                except Exception:
                    return None
                return None

            # 1) Tenta clicar em candidatos
            for loc in candidates:
                try:
                    count = loc.count()
                except Exception:
                    continue
                for i in range(min(count, 8)):
                    el = loc.nth(i)
                    try:
                        if not el.is_visible():
                            continue
                    except Exception:
                        pass
                    res = handle_download(lambda e=el: e.click(force=False))
                    if res and res.exists():
                        best_pdf = res
                        break
                if best_pdf:
                    break

            # 2) Como fallback, tenta interceptar navegacoes/downloads genericos
            if not best_pdf:
                try:
                    with page.expect_download(timeout=timeout_ms) as dl_info:
                        page.keyboard.press('End')
                        page.wait_for_timeout(400)
                        page.keyboard.press('Home')
                    dl = dl_info.value
                    suggested = dl.suggested_filename or 'arquivo'
                    target = workdir / suggested
                    dl.save_as(str(target))
                    if target.suffix.lower() == '.pdf':
                        best_pdf = target
                    elif target.suffix.lower() == '.zip':
                        best_pdf = _extract_zip_best_pdf(target, workdir / (target.stem + '_unzipped'))
                except Exception:
                    pass

            # 3) Se nao houve download, procura links diretos e baixa via requests
            if not best_pdf:
                try:
                    hrefs = page.eval_on_selector_all('a', 'els => els.map(e => e.href)')
                    if isinstance(hrefs, list):
                        pdf_like = [h for h in hrefs if isinstance(h, str) and (h.lower().endswith('.pdf') or '.pdf' in h.lower())]
                        pdf_like.sort(key=lambda u: _score_pdf_name(u.split('/')[-1]), reverse=True)
                        for h in pdf_like[:5]:
                            data, _ctype = _fetch_url(h)
                            if data:
                                fn = h.split('/')[-1] or 'arquivo.pdf'
                                dest = workdir / fn
                                dest.write_bytes(data)
                                best_pdf = dest
                                break
                except Exception:
                    pass

            # 4) Caso ainda nao ache, escolhe melhor PDF no workdir
            if not best_pdf:
                try:
                    all_pdfs = list(workdir.rglob('*.pdf'))
                    if all_pdfs:
                        best_pdf = max(all_pdfs, key=lambda p: _score_pdf_name(p.name))
                except Exception:
                    pass

            context.close()
            browser.close()
            return best_pdf
    except Exception:
        return None


def _map_modalidade_to_pncp_code(nome: Optional[str]) -> Optional[int]:
    """Mapeia nome de modalidade para código PNCP (parcial, extensível)."""
    if not nome:
        return None
    nm = _strip_accents(str(nome).lower())
    # Principais
    if "pregao" in nm:
        return 6  # Pregão Eletrônico
    # Outros podem ser adicionados conforme necessidade/documentação
    return None


def _strip_accents(s: str) -> str:
    try:
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    except Exception:
        return s


def _extrair_objeto(texto: str) -> Optional[str]:
    linhas = texto.splitlines()
    for i, ln in enumerate(linhas):
        ln_low = _strip_accents(ln.lower())
        if "objeto" in ln_low:
            trecho = [ln.strip()]
            for j in range(1, 3):
                if i + j < len(linhas):
                    trecho.append(linhas[i + j].strip())
            joined = " ".join(trecho)
            return (joined[:800] + "...") if len(joined) > 800 else joined
    clean = re.sub(r"\s+", " ", texto).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")


def _analisar_texto_edital_enriquecida(texto: str) -> Tuple[str, Dict[str, Any]]:
    lower = texto.lower()
    norm = _strip_accents(lower)

    valores = re.findall(r"R\$\s?[\d\.]{1,12},\d{2}", texto)
    valores_unicos = sorted(set(valores))[:10]
    maior_valor = None
    try:
        def to_num(v: str) -> float:
            v = v.replace('R$', '').strip().replace('.', '').replace(',', '.')
            return float(v)
        if valores_unicos:
            maior_valor = max(valores_unicos, key=lambda v: to_num(v))
    except Exception:
        pass

    datas = set()
    for rx in [r"\b\d{2}/\d{2}/\d{4}\b", r"\b\d{2}-\d{2}-\d{4}\b", r"\b\d{4}-\d{2}-\d{2}\b"]:
        datas.update(re.findall(rx, texto))
    datas_unicas = sorted(list(datas))[:12]

    cnpjs = re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b", texto)
    emails = re.findall(r"[\w.-]+@[\w.-]+\.[A-Za-z]{2,}", texto)
    urls = re.findall(r"https?://\S+", texto)

    servico_kw = ["servico", "execucao", "manutenc", "consultor", "obra", "projeto"]
    aquis_kw = ["aquisic", "compra", "fornecimento", "material", "equipamento"]
    tipo = "ServiÃ§o" if any(k in norm for k in servico_kw) else ("AquisiÃ§Ã£o" if any(k in norm for k in aquis_kw) else "Outros")

    flags = {
        "exige_visita_tecnica": ("visita tecnica" in norm or "vistoria tecnica" in norm),
        "exige_atestado_capacidade": ("atestado de capacidade" in norm or "capacidade tecnica" in norm),
        "exclusivo_me_epp": ("exclusivo para me e epp" in norm or "me/epp" in norm or "microempresa" in norm),
        "criterio_menor_preco": ("menor preco" in norm),
        "criterio_tecnica_preco": ("tecnica e preco" in norm),
    }

    modalidade = None
    if "pregao" in norm:
        modalidade = "PregÃ£o"
    elif "concorrencia" in norm:
        modalidade = "ConcorrÃªncia"
    elif "tomada de preco" in norm:
        modalidade = "Tomada de PreÃ§os"
    elif "dispensa" in norm:
        modalidade = "Dispensa"

    objeto = _extrair_objeto(texto)

    resumo_partes = [
        "--- Resumo automÃ¡tico do edital ---",
        f"Tamanho do texto: ~{len(texto):,} caracteres",
        f"ClassificaÃ§Ã£o sugerida: {tipo}",
        f"Modalidade (heurÃ­stica): {modalidade or 'indefinida'}",
        f"Maior valor (amostra): {maior_valor or 'nÃ£o identificado'}",
        f"Datas encontradas (amostra): {', '.join(datas_unicas) if datas_unicas else 'nÃ£o encontradas'}",
        "Indicadores:",
        f" - Visita tÃ©cnica: {'sim' if flags['exige_visita_tecnica'] else 'nÃ£o'}",
        f" - Atestado de capacidade: {'sim' if flags['exige_atestado_capacidade'] else 'nÃ£o'}",
        f" - Exclusivo ME/EPP: {'sim' if flags['exclusivo_me_epp'] else 'nÃ£o'}",
        f" - CritÃ©rio: {'Menor PreÃ§o' if flags['criterio_menor_preco'] else ('TÃ©cnica e PreÃ§o' if flags['criterio_tecnica_preco'] else 'indefinido')}",
        f"Objeto (aprox.): {objeto or 'nÃ£o identificado'}",
    ]

    dados = {
        "classificacao": tipo,
        "modalidade": modalidade,
        "valores_amostra": valores_unicos,
        "maior_valor": maior_valor,
        "datas_amostra": datas_unicas,
        "cnpjs": cnpjs[:5],
        "emails": emails[:5],
        "urls": urls[:5],
        "flags": flags,
        "objeto": objeto,
    }
    # --- Enriquecimentos adicionais ---
    try:
        # Telefones
        telefones = re.findall(r"\b(?:\(?\d{2}\)?\s*)?\d{4,5}-\d{4}\b", texto)
        if telefones:
            dados["telefones"] = telefones[:5]
    except Exception:
        pass

    # Retorno principal: resumo em texto e dados estruturados
    return "\n".join(resumo_partes), dados


def _to_float(num_str: Optional[str]) -> Optional[float]:
    try:
        if num_str is None:
            return None
        s = str(num_str)
        s = s.replace("\u00A0", " ").strip()  # NBSP
        s = re.sub(r"(?i)r\$\s?", "", s)  # remove R$
        s = s.replace(".", "").replace(",", ".")
        s = re.sub(r"[^0-9\.-]", "", s)
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _extract_items_from_table_rows(rows: list[list]) -> list[Dict[str, Any]]:
    items: list[Dict[str, Any]] = []
    if not rows:
        return items

    def norm(s: Any) -> str:
        try:
            return _strip_accents(str(s or "").strip().lower())
        except Exception:
            return ""

    header_idx = None
    header_map: Dict[int, str] = {}
    key_map = {
        "item": "item",
        "n": "item",
        "no": "item",
        "nº": "item",
        "descricao": "descricao",
        "descri": "descricao",
        "produto": "descricao",
        "objeto": "descricao",
        "quantidade": "quantidade",
        "qtd": "quantidade",
        "qtde": "quantidade",
        "unidade": "unidade",
        "und": "unidade",
        "uni": "unidade",
        "un": "unidade",
        "valor unitario": "valor_unitario",
        "preco unitario": "valor_unitario",
        "vl unitario": "valor_unitario",
        "valor total": "valor_total",
        "vl total": "valor_total",
        "preco total": "valor_total",
        "marca": "marca",
        "modelo": "modelo",
    }

    for i, row in enumerate(rows[:6]):
        texts = [norm(c) for c in row]
        score = 0
        local_map: Dict[int, str] = {}
        for j, txt in enumerate(texts):
            for k, dst in key_map.items():
                if k in txt and dst not in local_map.values():
                    local_map[j] = dst
                    score += 1
                    break
        if score >= 2:
            header_idx = i
            header_map = local_map
            break

    start_row = 0 if header_idx is None else header_idx + 1
    for r in rows[start_row:]:
        if not any(c for c in r):
            continue
        obj: Dict[str, Any] = {
            "item": None,
            "descricao": None,
            "quantidade": None,
            "unidade": None,
            "valor_unitario": None,
            "valor_total": None,
            "marca": None,
            "modelo": None,
        }
        for j, cell in enumerate(r):
            key = header_map.get(j)
            val = cell if cell is not None else ""
            if key == "item":
                m = re.search(r"\d+", str(val))
                obj["item"] = int(m.group()) if m else None
            elif key == "descricao":
                obj["descricao"] = str(val).strip() or None
            elif key == "quantidade":
                obj["quantidade"] = _to_float(str(val))
            elif key == "unidade":
                obj["unidade"] = str(val).strip() or None
            elif key == "valor_unitario":
                obj["valor_unitario"] = _to_float(str(val))
            elif key == "valor_total":
                obj["valor_total"] = _to_float(str(val))
            elif key == "marca":
                obj["marca"] = str(val).strip() or None
            elif key == "modelo":
                obj["modelo"] = str(val).strip() or None

        if obj.get("descricao") or any(obj.get(k) is not None for k in ("quantidade", "valor_unitario", "valor_total")):
            items.append(obj)
    return items


def _extract_items_from_pdf_bytes(data: bytes) -> list[Dict[str, Any]]:
    if pdfplumber is None:
        return []
    try:
        items: list[Dict[str, Any]] = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                for t in tables:
                    try:
                        items.extend(_extract_items_from_table_rows(t))
                    except Exception:
                        continue
        dedup = []
        seen = set()
        for it in items:
            key = (
                (it.get("descricao") or "").strip()[:60].lower(),
                it.get("quantidade"),
                (it.get("unidade") or "").lower(),
            )
            if key not in seen:
                seen.add(key)
                dedup.append(it)
        return dedup
    except Exception:
        return []


def _extract_items_from_text(texto: str) -> list[Dict[str, Any]]:
    items: list[Dict[str, Any]] = []
    lines = [ln.strip() for ln in texto.splitlines()]
    i = 0
    while i < len(lines):
        ln_norm = _strip_accents(lines[i].lower())
        m = re.match(r"\bitem\s+(\d+)\b[:\-\]?\s*(.*)", ln_norm)
        if m:
            try:
                idx = int(m.group(1))
            except Exception:
                idx = None  # pragma: no cover
            desc_parts = []
            raw_after = lines[i][len(lines[i]) - len(lines[i].lstrip()):].strip()
            if raw_after:
                desc_parts.append(lines[i])
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                nxt_norm = _strip_accents(nxt.lower())
                if re.match(r"\bitem\s+\d+\b", nxt_norm):
                    break
                if any(k in nxt_norm for k in ["quantidade", "qtde", "unidade", "valor unit", "valor total", "marca", "modelo"]):
                    break
                if nxt:
                    desc_parts.append(nxt)
                j += 1

            bloco = " ".join([p for p in desc_parts if p]).strip()
            lookahead = " ".join(lines[i:j+8])
            la_norm = _strip_accents(lookahead.lower())
            qtd = None
            m_qtd = re.search(r"\b(qtde|quantidade)\s*[:\-]?\s*([\d\.,]+)", la_norm)
            if m_qtd:
                qtd = _to_float(m_qtd.group(2))
            und = None
            m_und = re.search(r"\b(unidade|un|und|uni)\s*[:\-]?\s*([a-zA-Z]{1,6})\b", la_norm)
            if m_und:
                und = m_und.group(2).upper()
            vu = None
            m_vu = re.search(r"valor\s*unit[a-z]*\s*[:\-]?\s*(r\$\s*)?([\d\.,]+)", la_norm)
            if m_vu:
                vu = _to_float(m_vu.group(2))
            vt = None
            m_vt = re.search(r"valor\s*total\s*[:\-]?\s*(r\$\s*)?([\d\.,]+)", la_norm)
            if m_vt:
                vt = _to_float(m_vt.group(2))
            marca = None
            modelo = None
            window_lines = lines[i:j+8]
            try:
                brand_line = next((ln for ln in window_lines if re.search(r"\bmarca\b", _strip_accents(ln.lower()))), None)
                if brand_line:
                    m_b = re.search(r"marca\s*[:\-]?\s*(.+)$", brand_line, re.I)
                    if m_b:
                        marca = m_b.group(1).strip()
            except Exception:
                pass
            try:
                model_line = next((ln for ln in window_lines if re.search(r"\bmodelo\b", _strip_accents(ln.lower()))), None)
                if model_line:
                    m_m = re.search(r"modelo\s*[:\-]?\s*(.+)$", model_line, re.I)
                    if m_m:
                        modelo = m_m.group(1).strip()
            except Exception:
                pass

            items.append({
                "item": idx,
                "descricao": bloco or None,
                "quantidade": qtd,
                "unidade": und,
                "valor_unitario": vu,
                "valor_total": vt,
                "marca": marca,
                "modelo": modelo,
            })
            i = j
        else:
            i += 1
    return items
    try:
        # Datas por contexto (nomeadas)
        nomeadas: Dict[str, Optional[str]] = {}
        ctx_patterns = {
            "data_abertura_propostas": r"abertura[^\n]{0,50}?\b(\d{2}[/-]\d{2}[/-]\d{4})",
            "data_sessao_publica": r"sess[aÃ£oÃ£oÃ£][^\n]{0,50}?\b(\d{2}[/-]\d{2}[/-]\d{4})",
            "data_limite_impugnacao": r"impugna[cÃ§]ao?[^\n]{0,50}?\b(\d{2}[/-]\d{2}[/-]\d{4})",
            "data_visita_tecnica": r"visita t[eÃ©]cnica[^\n]{0,50}?\b(\d{2}[/-]\d{2}[/-]\d{4})",
        }
        for key, rx in ctx_patterns.items():
            m = re.search(rx, lower)
            nomeadas[key] = m.group(1) if m else None
        dados["datas_nomeadas"] = nomeadas
    except Exception:
        pass

    try:
        # Itens / Lotes (heurÃ­stica leve)
        norm = _strip_accents(lower)
        itens_count = len(re.findall(r"\bitem\s+\d+\b", norm))
        lotes_count = len(re.findall(r"\blote\s+\d+\b", norm))
        dados["itens_detectados"] = {"itens": itens_count, "lotes": lotes_count}
        resumo_partes.append(f"Itens/Lotes (heuristica): itens={itens_count}, lotes={lotes_count}")
    except Exception:
        pass

    # Flags extras no resumo
    try:
        resumo_partes.append(f" - Consorcio: {'permitido' if dados['flags'].get('permite_consorcio') else 'nao mencionado'}")
        resumo_partes.append(f" - Garantia: {'exige' if dados['flags'].get('exige_garantia') else 'nao identificado'}")
    except Exception:
        pass

    return "\n".join(resumo_partes), dados


def _ocr_pdf2(data: bytes, lang_default: str = "por") -> Optional[str]:
    """OCR de PDF com limites e early-stop.

    VariÃ¡veis de ambiente:
    - OCR_MAX_PAGES (default 10)
    - OCR_DPI (default 200)
    - OCR_MIN_CHARS (default 1500)
    """
    if convert_from_bytes is None or pytesseract is None:
        return None
    try:
        tcmd = os.getenv("TESSERACT_CMD")
        if tcmd:
            pytesseract.pytesseract.tesseract_cmd = tcmd
        lang = os.getenv("TESSERACT_LANG", lang_default)
        max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))
        dpi = int(os.getenv("OCR_DPI", "200"))
        min_chars = int(os.getenv("OCR_MIN_CHARS", "1500"))

        images = convert_from_bytes(data, dpi=dpi, first_page=1, last_page=max_pages)
        texts: list[str] = []
        total = 0
        for img in images:
            try:
                txt = pytesseract.image_to_string(img, lang=lang)
                if txt:
                    texts.append(txt)
                    total += len(txt)
                    if total >= min_chars:
                        break
            except Exception:
                continue
        combined = "\n".join(texts).strip()
        return combined or None
    except Exception:
        return None
def _ocr_pdf(data: bytes, lang_default: str = "por") -> Optional[str]:
    """Realiza OCR em um PDF (convertendo pÃ¡ginas para imagens)."""
    if convert_from_bytes is None or pytesseract is None:
        return None
    try:
        tcmd = os.getenv("TESSERACT_CMD")
        if tcmd:
            pytesseract.pytesseract.tesseract_cmd = tcmd
        lang = os.getenv("TESSERACT_LANG", lang_default)
        images = convert_from_bytes(data, dpi=300)
        texts: list[str] = []
        # Limita para evitar processamento excessivo em PDFs muito longos
        for img in images[:15]:
            try:
                txt = pytesseract.image_to_string(img, lang=lang)
                if txt:
                    texts.append(txt)
            except Exception:
                continue
        combined = "\n".join(texts).strip()
        return combined or None
    except Exception:
        return None


def _ocr_image(data: bytes, lang_default: str = "por") -> Optional[str]:
    if pytesseract is None or Image is None:
        return None
    try:
        tcmd = os.getenv("TESSERACT_CMD")
        if tcmd:
            pytesseract.pytesseract.tesseract_cmd = tcmd
        lang = os.getenv("TESSERACT_LANG", lang_default)
        img = Image.open(BytesIO(data))
        txt = pytesseract.image_to_string(img, lang=lang)
        return (txt or "").strip() or None
    except Exception:
        return None


def get_ocr_health() -> Dict[str, Any]:
    """Retorna diagnÃ³stico do OCR/PDF/HTML: mÃ³dulos Python e binÃ¡rios externos."""
    modules = {
        "requests": requests is not None,
        "beautifulsoup4": BeautifulSoup is not None,
        "pdfplumber": pdfplumber is not None,
        "pypdf": pypdf is not None,
        "pdf2image": convert_from_bytes is not None,
        "pytesseract": pytesseract is not None,
        "Pillow": Image is not None,
    }

    # Tesseract binary check
    tesseract_cmd = None
    tesseract_ok = False
    tesseract_version = None
    try:
        if pytesseract is not None:
            tesseract_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
        tesseract_path = tesseract_cmd or shutil.which("tesseract")
        if tesseract_path:
            tesseract_ok = True
            try:
                out = subprocess.run([tesseract_path, "-v"], capture_output=True, text=True, timeout=5)
                tesseract_version = (out.stdout or out.stderr or "").splitlines()[0].strip()
            except Exception:
                pass
    except Exception:
        pass

    # Poppler (pdftoppm) check for pdf2image on Windows
    poppler_path = shutil.which("pdftoppm")
    poppler_ok = poppler_path is not None
    poppler_version = None
    if poppler_ok:
        try:
            out = subprocess.run([poppler_path, "-v"], capture_output=True, text=True, timeout=5)
            poppler_version = (out.stdout or out.stderr or "").splitlines()[0].strip()
        except Exception:
            pass

    ok = all(modules[m] for m in ["pdfplumber", "pypdf"]) and (tesseract_ok or modules["pdfplumber"])  # OCR opcional

    return {
        "ok": ok,
        "modules": modules,
        "tesseract": {
            "available": tesseract_ok,
            "cmd": tesseract_cmd or shutil.which("tesseract"),
            "version": tesseract_version,
            "lang_env": os.getenv("TESSERACT_LANG"),
        },
        "poppler": {
            "available": poppler_ok,
            "pdftoppm": poppler_path,
            "version": poppler_version,
        },
        "notes": "OCR Ã© usado somente como fallback quando extraÃ§Ã£o nativa falha ou Ã© insuficiente.",
    }


def extract_text_from_link(link_edital: str) -> Tuple[str, Dict[str, Any]]:
    """Extrai texto de um link de edital com cache e fallback robusto.

    Retorna (texto, meta) onde meta inclui: method, ctype, pdf_resolvido, from_cache.
    """
    # Cache por URL
    cached = _cache_get(link_edital)
    if cached and isinstance(cached.get("text"), str):
        return cached["text"], {
            "method": cached.get("method", "cache"),
            "ctype": cached.get("ctype", ""),
            "pdf_resolvido": cached.get("pdf_resolvido"),
            "from_cache": True,
        }

    method = ""
    pdf_resolvido = None
    ctype = ""
    texto_edital: Optional[str] = None

    # Opcional: tentar Playwright primeiro para capturar downloads (controlado por env)
    try:
        use_pw = os.getenv("USE_PLAYWRIGHT_EDITAL", "0").strip().lower() in {"1", "true", "yes"}
    except Exception:
        use_pw = False
    if use_pw:
        try:
            best_pdf = resolve_edital_pdf_with_playwright(link_edital)
        except Exception:
            best_pdf = None
        if best_pdf and best_pdf.exists():
            try:
                data = best_pdf.read_bytes()
                ctype = "application/pdf"
                texto_edital = _extract_text_from_pdf(data)
                try:
                    itens = _extract_items_from_pdf_bytes(data)
                except Exception:
                    itens = []
                if not texto_edital or len(texto_edital) < 200:
                    ocr_txt = _ocr_pdf2(data)
                    if ocr_txt:
                        texto_edital = ocr_txt
                        method = "OCR"
                    else:
                        method = "PDF-sem-texto"
                else:
                    method = "Extracao de texto"
                pdf_resolvido = str(best_pdf)
            except Exception:
                # Continua com fluxo normal se falhar
                texto_edital = None

    # Download
    data, ctype = _fetch_url(link_edital)
    itens: list[Dict[str, Any]] = []
    if data:
        is_pdf = ("pdf" in (ctype or "").lower()) or link_edital.lower().endswith(".pdf")
        if is_pdf:
            texto_edital = _extract_text_from_pdf(data)
            try:
                itens = _extract_items_from_pdf_bytes(data)
            except Exception:
                itens = []
            if not texto_edital or len(texto_edital) < 200:
                ocr_txt = _ocr_pdf2(data)
                if ocr_txt:
                    texto_edital = ocr_txt
                    method = "OCR"
                else:
                    method = "PDF-sem-texto"
            else:
                method = "Extracao de texto"
        else:
            # Imagem direto
            if (ctype or "").lower().startswith("image/") or re.search(r"\.(png|jpe?g|tiff?)$", link_edital, re.I):
                ocr_txt = _ocr_image(data)
                if ocr_txt:
                    texto_edital = ocr_txt
                    method = "OCR"
            # HTML + tentativa de links PDF
            if not texto_edital:
                html_text = _extract_text_from_html(data)
                if html_text:
                    texto_edital = html_text
                    method = method or "HTML"
                try:
                    pdf_links = _find_pdf_links_from_html(data, link_edital)
                    for pdf_url in pdf_links:
                        pdata, pctype = _fetch_url(pdf_url)
                        if not pdata:
                            continue
                        if (pctype and "pdf" in pctype.lower()) or pdf_url.lower().endswith(".pdf"):
                            pdf_text = _extract_text_from_pdf(pdata)
                            try:
                                itens = _extract_items_from_pdf_bytes(pdata)
                            except Exception:
                                itens = []
                            if not pdf_text or len(pdf_text) < 200:
                                ocr_txt2 = _ocr_pdf2(pdata)
                                if ocr_txt2:
                                    pdf_text = ocr_txt2
                                    method = "OCR"
                            if pdf_text and len(pdf_text) >= 50:
                                texto_edital = pdf_text
                                pdf_resolvido = pdf_url
                                method = method or "PDF-link"
                                break
                except Exception:
                    pass

    if not texto_edital:
        texto_edital = (
            "Nao foi possivel extrair texto do edital automaticamente. "
            "O PDF pode estar protegido ou ser um documento escaneado (imagem). "
            "Para OCR, instale Tesseract e pytesseract, ou forneca um link alternativo."
        )
        method = method or "Falha"

    # Se nao encontrou itens via tabela, tenta fallback no texto
    if not itens and texto_edital:
        try:
            itens = _extract_items_from_text(texto_edital)
        except Exception:
            itens = []

    # grava cache
    _cache_put(
        link_edital,
        {
            "text": texto_edital,
            "method": method or "Extracao de texto",
            "ctype": ctype or "",
            "pdf_resolvido": pdf_resolvido,
        },
    )

    return texto_edital, {
        "method": method or "Extracao de texto",
        "ctype": ctype or "",
        "pdf_resolvido": pdf_resolvido,
        "from_cache": False,
        "itens": itens,
        "itens_count": len(itens),
    }

def run_analysis(analise_id: int):
    """
    Rotina principal de analise (executa em segundo plano).
    Abre sua propria sessao de banco, independente da requisicao web.
    """
    db: Session = SessionLocal()
    print(f"[Analise ID: {analise_id}] - Iniciando analise...")

    status_final = "Erro"
    resultado_final = (
        "Ocorreu um erro inesperado que impediu a finalizacao da analise."
    )

    try:
        # 1) Marca como processando para o frontend mostrar em amarelo
        crud.update_analise(
            db, analise_id=analise_id, status="Processando", resultado="Iniciando..."
        )

        # 2) Busca a analise e a licitacao associada
        analise = crud.get_analise(db, analise_id=analise_id)
        if not analise:
            print(
                f"[Analise ID: {analise_id}] - ERRO: Analise nao encontrada apos ser criada."
            )
            return

        link_edital = analise.licitacao.link_sistema_origem
        print(f"[Analise ID: {analise_id}] - Link do edital: {link_edital}")

        # 3) Valida o link do edital
        if not link_edital:
            raise ValueError("Link do edital nao encontrado para a analise.")

        # 4) Extrai o conteÃºdo (com cache e heurÃ­sticas robustas)
        print(f"[Analise ID: {analise_id}] - Tentando PNCP antes de baixar pelo site...")
        texto_edital: Optional[str] = None
        meta: Dict[str, Any] = {}
        pdf_resolvido: Optional[str] = None
        ocr_usado = False

        # 4.a) Tenta via PNCP (publicacoes) encontrar o link do processo e anexos
        try:
            use_pncp = os.getenv("USE_PNCP_API", "1").strip().lower() in {"1", "true", "yes"}
        except Exception:
            use_pncp = True
        if use_pncp:
            try:
                lic = analise.licitacao
                cod_mod = _map_modalidade_to_pncp_code(getattr(lic, "modalidade_nome", None))
                row = None
                if cod_mod and getattr(lic, "data_publicacao_pncp", None):
                    row = pncp_buscar_por_link(
                        link_sistema_origem=link_edital,
                        data_ref=lic.data_publicacao_pncp,
                        codigo_modalidade=cod_mod,
                        uf=getattr(lic, "uf", None),
                    )
                    # Se não achou, tenta busca expandida (múltiplas modalidades e janelas)
                    if not row:
                        row = pncp_buscar_por_link_expanded(
                            link_sistema_origem=link_edital,
                            data_hint=getattr(lic, "data_publicacao_pncp", None),
                            uf=getattr(lic, "uf", None),
                            cnpj=None,
                            total_days=365,
                            step_days=30,
                            page_limit=10,
                        )
                # Se ainda não achou, tenta por númeroCompra (sequencial/ano), para descobrir CNPJ e detalhes
                if not row:
                    seq = getattr(lic, "sequencial_compra", None)
                    ano = getattr(lic, "ano_compra", None)
                    if seq and ano:
                        try:
                            row = pncp_buscar_por_numero_compra_expanded(
                                (int(seq), int(ano)),
                                data_hint=getattr(lic, "data_publicacao_pncp", None),
                                uf=getattr(lic, "uf", None),
                                total_days=365,
                                step_days=30,
                                page_limit=10,
                            )
                        except Exception:
                            row = None
                # Se ainda não achou, tenta resolver CNPJ por nome do órgão e consultar por chave
                if not row:
                    org_name = getattr(lic, "orgao_entidade_nome", None)
                    if org_name and getattr(lic, "sequencial_compra", None) and getattr(lic, "ano_compra", None):
                        cnpj_guess = resolve_cnpj_by_name_via_pncp(org_name, uf=getattr(lic, "uf", None))
                        if not cnpj_guess:
                            cnpj_guess = resolve_cnpj_by_name_via_google(org_name)
                        if cnpj_guess:
                            try:
                                det = pncp_compra_por_chave(str(cnpj_guess), int(getattr(lic, "ano_compra")), int(getattr(lic, "sequencial_compra")))
                                if isinstance(det, dict):
                                    row = det
                            except Exception:
                                pass
                if row:
                    # 1) Tenta API de Documentos do PNCP (se configurado)
                    try:
                        use_docs = os.getenv("USE_PNCP_DOCS", "1").strip().lower() in {"1", "true", "yes"}
                    except Exception:
                        use_docs = True
                    cnpj = None
                    ano_c = None
                    seq_c = None
                    try:
                        ent = row.get("orgaoEntidade") or {}
                        cnpj = ent.get("cnpj")
                        ano_c = row.get("anoCompra")
                        seq_c = row.get("sequencialCompra")
                    except Exception:
                        pass
                    if use_docs and cnpj and ano_c and seq_c:
                        docs = listar_documentos_compra(str(cnpj), int(ano_c), int(seq_c))
                        # Seleciona melhor documento (por título/tipo/nome do arquivo se existir url)
                        def _doc_score(d: dict) -> int:
                            name = (d.get("titulo") or d.get("tipo_nome") or "").lower()
                            return _score_pdf_name(name)
                        if docs:
                            best = max(docs, key=_doc_score)
                            saved_path: Optional[str] = None
                            # Se houver URL direta, tenta baixar por URL; senão baixa por sequencial
                            url_direct = best.get("url")
                            if url_direct:
                                data, ctype_hint = _fetch_url(url_direct)
                                if data:
                                    # Salva em tmp
                                    outdir = Path(__file__).resolve().parent.parent / 'tmp' / 'pncp_docs'
                                    outdir.mkdir(parents=True, exist_ok=True)
                                    fn = url_direct.split('/')[-1] or 'documento.pdf'
                                    outp = outdir / fn
                                    outp.write_bytes(data)
                                    saved_path = str(outp)
                                    ctype_used = ctype_hint or "application/octet-stream"
                                else:
                                    saved_path = None
                                    ctype_used = ""
                            if not saved_path:
                                try:
                                    saved_path = baixar_documento_por_sequencial(str(cnpj), int(ano_c), int(seq_c), int(best.get("sequencial")))
                                    ctype_used = "application/octet-stream"
                                except Exception:
                                    saved_path = None
                                    ctype_used = ""
                            if saved_path and Path(saved_path).exists():
                                sp = Path(saved_path)
                                # registra anexo
                                try:
                                    sha = hashlib.sha256(sp.read_bytes()).hexdigest()
                                    crud_mod.create_anexo(
                                        db,
                                        licitacao_id=getattr(lic, 'id', None),
                                        source='pncp_docs',
                                        url=url_direct,
                                        filename=sp.name,
                                        local_path=str(sp),
                                        content_type=ctype_used,
                                        size_bytes=sp.stat().st_size,
                                        sha256=sha,
                                        score=None,
                                        status='saved',
                                        error=None,
                                    )
                                except Exception:
                                    pass
                                if sp.suffix.lower() == '.zip':
                                    extracted = _extract_zip_best_pdf(sp, sp.parent / (sp.stem + '_unzipped'))
                                    if extracted and extracted.exists():
                                        data = extracted.read_bytes()
                                        pdf_resolvido = str(extracted)
                                    else:
                                        data = sp.read_bytes()
                                        pdf_resolvido = str(sp)
                                else:
                                    data = sp.read_bytes()
                                    pdf_resolvido = str(sp)
                                texto_edital = _extract_text_from_pdf(data)
                                try:
                                    itens = _extract_items_from_pdf_bytes(data)
                                except Exception:
                                    itens = []
                                if not texto_edital or len(texto_edital) < 200:
                                    ocr_txt = _ocr_pdf2(data)
                                    if ocr_txt:
                                        texto_edital = ocr_txt
                                        ocr_usado = True
                                meta = {
                                    "method": "PNCP-Docs" if not ocr_usado else "PNCP-Docs+OCR",
                                    "ctype": ctype_used,
                                    "pdf_resolvido": pdf_resolvido,
                                    "from_cache": False,
                                    "itens": itens,
                                    "itens_count": len(itens),
                                }
                            else:
                                # fallback para página pública
                                page_link = (row.get("linkProcessoEletronico") or row.get("linkSistemaOrigem") or link_edital)
                                pdfs = pncp_extrair_anexos_de_pagina(page_link)
                                if pdfs:
                                    best_url = max(pdfs, key=lambda u: _score_pdf_name(u.split('/')[-1]))
                                    data, ctype_hint = _fetch_url(best_url)
                                    if data:
                                        texto_edital = _extract_text_from_pdf(data)
                                        try:
                                            itens = _extract_items_from_pdf_bytes(data)
                                        except Exception:
                                            itens = []
                                        if not texto_edital or len(texto_edital) < 200:
                                            ocr_txt = _ocr_pdf2(data)
                                            if ocr_txt:
                                                texto_edital = ocr_txt
                                                ocr_usado = True
                                        meta = {
                                            "method": "PNCP-API+HTML" if not ocr_usado else "PNCP-API+OCR",
                                            "ctype": ctype_hint or "application/pdf",
                                            "pdf_resolvido": best_url,
                                            "from_cache": False,
                                            "itens": itens,
                                            "itens_count": len(itens),
                                        }
                                        pdf_resolvido = best_url
                                        # registra anexo remoto (sem arquivo local)
                                        try:
                                            crud_mod.create_anexo(
                                                db,
                                                licitacao_id=getattr(lic, 'id', None),
                                                source='pncp_html',
                                                url=best_url,
                                                filename=best_url.split('/')[-1],
                                                local_path=None,
                                                content_type=ctype_hint or '',
                                                size_bytes=None,
                                                sha256=None,
                                                score=None,
                                                status='saved',
                                                error=None,
                                            )
                                        except Exception:
                                            pass
                    else:
                        # Sem cnpj/ano/seq: tenta página pública
                        page_link = (row.get("linkProcessoEletronico") or row.get("linkSistemaOrigem") or link_edital)
                        pdfs = pncp_extrair_anexos_de_pagina(page_link)
                        if pdfs:
                            best_url = max(pdfs, key=lambda u: _score_pdf_name(u.split('/')[-1]))
                            data, ctype_hint = _fetch_url(best_url)
                            if data:
                                texto_edital = _extract_text_from_pdf(data)
                                try:
                                    itens = _extract_items_from_pdf_bytes(data)
                                except Exception:
                                    itens = []
                                if not texto_edital or len(texto_edital) < 200:
                                    ocr_txt = _ocr_pdf2(data)
                                    if ocr_txt:
                                        texto_edital = ocr_txt
                                        ocr_usado = True
                                meta = {
                                    "method": "PNCP-API+HTML" if not ocr_usado else "PNCP-API+OCR",
                                    "ctype": ctype_hint or "application/pdf",
                                    "pdf_resolvido": best_url,
                                    "from_cache": False,
                                    "itens": itens,
                                    "itens_count": len(itens),
                                }
                                pdf_resolvido = best_url
                                # registra anexo remoto
                                try:
                                    crud_mod.create_anexo(
                                        db,
                                        licitacao_id=getattr(lic, 'id', None),
                                        source='pncp_html',
                                        url=best_url,
                                        filename=best_url.split('/')[-1],
                                        local_path=None,
                                        content_type=ctype_hint or '',
                                        size_bytes=None,
                                        sha256=None,
                                        score=None,
                                        status='saved',
                                        error=None,
                                    )
                                except Exception:
                                    pass
            except Exception:
                pass

        # 4.b) Fallback para fluxo atual (requests/HTML/PDF/OCR ou Playwright, se habilitado)
        if not texto_edital:
            print(f"[Analise ID: {analise_id}] - Extraindo conteudo do edital (cache/heuristicas)...")
            extracted_text, meta2 = extract_text_from_link(link_edital)
            texto_edital = extracted_text
            meta = meta2 if isinstance(meta2, dict) else {}
            ocr_usado = (meta.get("method") == "OCR") if isinstance(meta, dict) else False
            pdf_resolvido = meta.get("pdf_resolvido") if isinstance(meta, dict) else None

        # 5) Se nao conseguiu extrair texto, gera orientacao
        if not texto_edital:
            texto_edital = (
                "Nao foi possivel extrair texto do edital automaticamente. "
                "O PDF pode estar protegido ou ser um documento escaneado (imagem). "
                "Para OCR, instale Tesseract e pytesseract, ou forneca um link alternativo."
            )
            method = method or "Falha"

        # 6) Normaliza e gera um resumo + dados estruturados
        try:
            texto_edital = unicodedata.normalize("NFC", texto_edital)
        except Exception:
            pass
        resumo, dados = _analisar_texto_edital_enriquecida(texto_edital)

        # 7) Complementa com um breve panorama do banco (Pandas)
        print(f"[Analise ID: {analise_id}] - Gerando panorama de dados...")
        panorama = analisar_licitacoes_com_pandas()

        metodo = meta.get("method", "Extracao de texto") if isinstance(meta, dict) else ("OCR" if ocr_usado else "Extracao de texto")
        # Formata saida melhor estruturada
        bullets = []
        bullets.append(f"- Link: {link_edital}")
        bullets.append(f"- Método: {metodo}")
        bullets.append(f"- PDF resolvido: {pdf_resolvido or 'N/A'}")
        if isinstance(meta, dict):
            if meta.get('ctype'):
                bullets.append(f"- Content-Type: {meta.get('ctype')}")
            if meta.get('itens_count'):
                bullets.append(f"- Itens extraídos: {meta.get('itens_count')}")

        # Campos chave do 'dados'
        chave_lines = []
        try:
            chave_lines.append(f"Modalidade: {dados.get('modalidade') or 'indefinida'}")
            if dados.get('classificacao'):
                chave_lines.append(f"Classificação: {dados.get('classificacao')}")
            if dados.get('maior_valor'):
                chave_lines.append(f"Maior valor (amostra): {dados.get('maior_valor')}")
            if dados.get('datas_amostra'):
                chave_lines.append(f"Datas (amostra): {', '.join(dados.get('datas_amostra') or [])}")
            if dados.get('objeto'):
                chave_lines.append(f"Objeto (aprox.): {dados.get('objeto')}")
        except Exception:
            pass

        resultado_final = (
            "Análise do Edital\n"
            + "\n".join(bullets)
            + "\n\nResumo\n"
            + resumo
            + ("\n\nChaves\n" + "\n".join(f"- {l}" for l in chave_lines) if chave_lines else "")
            + "\n\nDetalhes (JSON)\n"
            + json.dumps(dados, ensure_ascii=False, indent=2)
            + "\n\nPanorama (Banco / Pandas)\n"
            + str(panorama)
        )
        status_final = "Concluido"
        print(f"[Analise ID: {analise_id}] - Analise concluida.")

    except Exception as e:
        print(f"[Analise ID: {analise_id}] - ERRO DURANTE A ANALISE: {e}")
        full_traceback = traceback.format_exc()
        resultado_final = (
            "Ocorreu um erro inesperado durante a analise.\n\n"
            f"Detalhes do Erro:\n{full_traceback}"
        )
        status_final = "Erro"

    finally:
        # 4) Atualiza o registro no banco com o resultado final (sucesso ou erro)
        crud.update_analise(
            db, analise_id=analise_id, status=status_final, resultado=resultado_final
        )
        db.close()
        print(
            f"[Analise ID: {analise_id}] - Analise finalizada e salva no banco com status: {status_final}."
        )
