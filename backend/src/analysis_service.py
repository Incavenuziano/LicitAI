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


def _extract_text_from_html(data: bytes) -> Optional[str]:
    if BeautifulSoup is None:
        try:
            # Fallback bÃ¡sico: remove tags com regex simples (nÃ£o perfeito)
            html = data.decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", html)
        except Exception:
            return None
    try:
        soup = BeautifulSoup(data, "html.parser")
        # Remove scripts/styles
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
    html = None
    try:
        html = data.decode("utf-8", errors="ignore")
    except Exception:
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

    # Download
    data, ctype = _fetch_url(link_edital)
    if data:
        is_pdf = ("pdf" in (ctype or "").lower()) or link_edital.lower().endswith(".pdf")
        if is_pdf:
            texto_edital = _extract_text_from_pdf(data)
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
            "Para OCR, instale Tesseract e Poppler (pdftoppm) e configure TESSERACT_CMD."
        )
        method = method or "Falha"

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
        print(f"[Analise ID: {analise_id}] - Extraindo conteudo do edital (cache/heuristicas)...")
        extracted_text, meta = extract_text_from_link(link_edital)
        texto_edital: Optional[str] = extracted_text
        ocr_usado = (meta.get("method") == "OCR") if isinstance(meta, dict) else False
        pdf_resolvido: Optional[str] = meta.get("pdf_resolvido") if isinstance(meta, dict) else None

        # 5) Se nao conseguiu extrair texto, gera orientacao
        if not texto_edital:
            texto_edital = (
                "Nao foi possivel extrair texto do edital automaticamente. "
                "O PDF pode estar protegido ou ser um documento escaneado (imagem). "
                "Para OCR, instale Tesseract e pytesseract, ou forneca um link alternativo."
            )

        # 6) Gera um resumo + dados estruturados
        resumo, dados = _analisar_texto_edital_enriquecida(texto_edital)

        # 7) Complementa com um breve panorama do banco (Pandas)
        print(f"[Analise ID: {analise_id}] - Gerando panorama de dados...")
        panorama = analisar_licitacoes_com_pandas()

        metodo = meta.get("method", "Extracao de texto") if isinstance(meta, dict) else ("OCR" if ocr_usado else "Extracao de texto")
        resultado_final = (
            "Resultado da analise do edital:\n"
            f"- Link: {link_edital}\n"
            f"- Metodo: {metodo}\\n\\n"
            f"- PDF resolvido: {pdf_resolvido or 'N/A'}\\n\\n"
            f"Resumo do edital:\n{resumo}\n\n"
            f"Detalhes extraidos (JSON):\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n\n"
            f"Panorama do banco (Pandas):\n{panorama}"
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
