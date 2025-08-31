import time
import traceback
import re
import os
import shutil
import subprocess
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
    requests = None  # Fallback se não instalado

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # Fallback se não instalado

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


def _fetch_url(url: str, timeout: int = 25) -> Tuple[Optional[bytes], str]:
    """Baixa conteúdo do URL. Retorna (bytes, content_type)."""
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
    """Extrai texto de PDF priorizando pdfplumber; fallback para pypdf."""
    # 1) Tenta com pdfplumber (mais robusto para layout)
    if pdfplumber is not None:
        try:
            texts: list[str] = []
            with pdfplumber.open(BytesIO(data)) as pdf:
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
            # Fallback básico: remove tags com regex simples (não perfeito)
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
    """Extrai alguns itens úteis do texto do edital e monta um resumo."""
    lower = texto.lower()
    def norm(s: str) -> str:
        return s

    # Valores monetários (R$ 1.234,56)
    valores = re.findall(r"R\$\s?[\d\.]{1,12},\d{2}", texto)
    valores_unicos = sorted(set(valores))[:10]

    # Datas dd/mm/yyyy
    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto)
    datas_unicas = sorted(set(datas))[:10]

    # Palavras‑chave
    chaves = {
        "modalidade": any(k in lower for k in ["pregão", "pregao", "tomada de preços", "concorrência", "dispensa"]),
        "habilitacao": ("habilita" in lower),
        "objeto": ("objeto" in lower or "do objeto" in lower),
        "vigencia": ("vigência" in lower or "vigencia" in lower),
        "proposta": ("proposta" in lower),
    }

    # Classificação simples (Serviço vs Aquisição)
    servico_kw = ["serviç", "servic", "execuç", "execuc", "manuten", "consultor"]
    aquis_kw = ["aquisiç", "aquisic", "compra", "fornecimento", "material", "equipamento"]
    tipo = "Serviço" if any(k in lower for k in servico_kw) else ("Aquisição" if any(k in lower for k in aquis_kw) else "Outros")

    partes = [
        "--- Resumo automático do edital ---",
        f"Tamanho do texto: ~{len(texto):,} caracteres",
        f"Classificação sugerida: {tipo}",
        f"Valores monetários (amostra): {', '.join(valores_unicos) if valores_unicos else 'não encontrados'}",
        f"Datas encontradas (amostra): {', '.join(datas_unicas) if datas_unicas else 'não encontradas'}",
        "Indicadores de conteúdo:",
        f" - Modalidade mencionada: {'sim' if chaves['modalidade'] else 'não'}",
        f" - Habilitação: {'sim' if chaves['habilitacao'] else 'não'}",
        f" - Objeto: {'sim' if chaves['objeto'] else 'não'}",
        f" - Vigência: {'sim' if chaves['vigencia'] else 'não'}",
        f" - Proposta: {'sim' if chaves['proposta'] else 'não'}",
    ]
    return "\n".join(partes)


def _find_pdf_links_from_html(data: bytes, base_url: str) -> list[str]:
    """Procura links de PDF em uma página HTML e retorna URLs absolutas."""
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
                # Preferir âncoras com palavras-chave
                if href.lower().endswith(".pdf") or \
                   ("pdf" in href.lower()) or \
                   ("edital" in text) or ("anexo" in text) or ("download" in text):
                    links.append(urljoin(base_url, href))
        except Exception:
            pass

    # Fallback rápido via regex
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
    tipo = "Serviço" if any(k in norm for k in servico_kw) else ("Aquisição" if any(k in norm for k in aquis_kw) else "Outros")

    flags = {
        "exige_visita_tecnica": ("visita tecnica" in norm or "vistoria tecnica" in norm),
        "exige_atestado_capacidade": ("atestado de capacidade" in norm or "capacidade tecnica" in norm),
        "exclusivo_me_epp": ("exclusivo para me e epp" in norm or "me/epp" in norm or "microempresa" in norm),
        "criterio_menor_preco": ("menor preco" in norm),
        "criterio_tecnica_preco": ("tecnica e preco" in norm),
    }

    modalidade = None
    if "pregao" in norm:
        modalidade = "Pregão"
    elif "concorrencia" in norm:
        modalidade = "Concorrência"
    elif "tomada de preco" in norm:
        modalidade = "Tomada de Preços"
    elif "dispensa" in norm:
        modalidade = "Dispensa"

    objeto = _extrair_objeto(texto)

    resumo_partes = [
        "--- Resumo automático do edital ---",
        f"Tamanho do texto: ~{len(texto):,} caracteres",
        f"Classificação sugerida: {tipo}",
        f"Modalidade (heurística): {modalidade or 'indefinida'}",
        f"Maior valor (amostra): {maior_valor or 'não identificado'}",
        f"Datas encontradas (amostra): {', '.join(datas_unicas) if datas_unicas else 'não encontradas'}",
        "Indicadores:",
        f" - Visita técnica: {'sim' if flags['exige_visita_tecnica'] else 'não'}",
        f" - Atestado de capacidade: {'sim' if flags['exige_atestado_capacidade'] else 'não'}",
        f" - Exclusivo ME/EPP: {'sim' if flags['exclusivo_me_epp'] else 'não'}",
        f" - Critério: {'Menor Preço' if flags['criterio_menor_preco'] else ('Técnica e Preço' if flags['criterio_tecnica_preco'] else 'indefinido')}",
        f"Objeto (aprox.): {objeto or 'não identificado'}",
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
def _ocr_pdf(data: bytes, lang_default: str = "por") -> Optional[str]:
    """Realiza OCR em um PDF (convertendo páginas para imagens)."""
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
    """Retorna diagnóstico do OCR/PDF/HTML: módulos Python e binários externos."""
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
        "notes": "OCR é usado somente como fallback quando extração nativa falha ou é insuficiente.",
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

        # 4) Baixa o conteudo do link (PDF/HTML)
        print(f"[Analise ID: {analise_id}] - Baixando conteudo do edital...")
        data, ctype = _fetch_url(link_edital)
        texto_edital: Optional[str] = None
        ocr_usado = False
        pdf_resolvido: Optional[str] = None
        if data:
            is_pdf = ("pdf" in ctype.lower()) or link_edital.lower().endswith(".pdf")
            if is_pdf:
                texto_edital = _extract_text_from_pdf(data)
                # Se falhou ou texto muito curto, tenta OCR
                if not texto_edital or len(texto_edital) < 200:
                    ocr_txt = _ocr_pdf(data)
                    if ocr_txt:
                        texto_edital = ocr_txt
                        ocr_usado = True
            else:
                # Se for imagem, tenta OCR direto
                if ctype.lower().startswith("image/") or re.search(r"\.(png|jpe?g|tiff?)$", link_edital, re.I):
                    ocr_txt = _ocr_image(data)
                    if ocr_txt:
                        texto_edital = ocr_txt
                        ocr_usado = True
                if not texto_edital:
                    # Tenta extrair do HTML e procurar links de PDF
                    texto_edital = _extract_text_from_html(data)
                    try:
                        pdf_links = _find_pdf_links_from_html(data, link_edital)
                        for pdf_url in pdf_links:
                            pdata, pctype = _fetch_url(pdf_url)
                            if not pdata:
                                continue
                            if (pctype and "pdf" in pctype.lower()) or pdf_url.lower().endswith(".pdf"):
                                pdf_text = _extract_text_from_pdf(pdata)
                                if not pdf_text or len(pdf_text) < 200:
                                    ocr_txt2 = _ocr_pdf(pdata)
                                    if ocr_txt2:
                                        pdf_text = ocr_txt2
                                        ocr_usado = True
                                if pdf_text and len(pdf_text) >= 50:
                                    texto_edital = pdf_text
                                    pdf_resolvido = pdf_url
                                    break
                    except Exception:
                        pass

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

        metodo = "OCR" if ocr_usado else "Extracao de texto"
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
