import traceback
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from .database import SessionLocal
from . import crud
import logging

logger = logging.getLogger("analysis")

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None
try:
    import pypdf  # type: ignore
except Exception:
    pypdf = None
try:
    from pdf2image import convert_from_bytes  # type: ignore
except Exception:
    convert_from_bytes = None
try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None
try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None


def _extract_text_from_pdf(data: bytes) -> Optional[str]:
    if pdfplumber is not None:
        try:
            texts: list[str] = []
            with pdfplumber.open(BytesIO(data)) as pdf:
                for pg in pdf.pages:
                    try:
                        t = pg.extract_text() or ""
                    except Exception:
                        t = ""
                    if t:
                        texts.append(t)
            combined = "\n".join(texts).strip()
            if combined:
                return combined
        except Exception:
            pass
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


def _ocr_pdf2(data: bytes, lang_default: str = "por") -> Optional[str]:
    if convert_from_bytes is None or pytesseract is None:
        return None
    try:
        images = convert_from_bytes(data, dpi=200, first_page=1, last_page=5)
        texts: list[str] = []
        for img in images:
            try:
                txt = pytesseract.image_to_string(img, lang=lang_default)
                if txt:
                    texts.append(txt)
            except Exception:
                continue
        combined = "\n".join(texts).strip()
        return combined or None
    except Exception:
        return None


def extract_text_from_link(link: str) -> Tuple[str, Dict[str, Any]]:
    texto: Optional[str] = None
    meta: Dict[str, Any] = {"from_cache": False}
    if not requests:
        return "", meta
    try:
        resp = requests.get(link, timeout=30)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        data = resp.content
        meta["ctype"] = ctype
        if "pdf" in ctype or link.lower().endswith(".pdf"):
            texto = _extract_text_from_pdf(data)
            if not texto or len(texto) < 200:
                ocr = _ocr_pdf2(data)
                if ocr:
                    texto = ocr
                    meta["method"] = "OCR"
                else:
                    meta["method"] = "PDF-sem-texto"
            else:
                meta["method"] = "Extracao de texto"
            meta["pdf_resolvido"] = link
        else:
            if BeautifulSoup is not None:
                try:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "noscript"]):
                        tag.extract()
                    texto = soup.get_text(separator=" ")
                except Exception:
                    texto = resp.text
            else:
                texto = resp.text
            meta["method"] = "HTML"
    except Exception:
        texto = ""
        meta["method"] = "Falha"
    return texto or "", meta


def _analisar_texto_edital_enriquecida(texto: str) -> Tuple[str, Dict[str, Any]]:
    import re

    valores = re.findall(r"R\$\s?[\d\.]{1,12},\d{2}", texto)
    datas = re.findall(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", texto)
    resumo = [
        "--- Resumo do edital (simplificado) ---",
        f"Tamanho do texto: ~{len(texto):,} caracteres",
        f"Valores (amostra): {', '.join(sorted(set(valores))[:5]) if valores else 'nenhum'}",
        f"Datas (amostra): {', '.join(sorted(set(datas))[:5]) if datas else 'nenhuma'}",
    ]
    dados = {
        "valores_amostra": sorted(set(valores))[:10],
        "datas_amostra": sorted(set(datas))[:10],
    }
    return "\n".join(resumo), dados


def run_analysis(analise_id: int) -> None:
    """Processa uma análise de licitação (simplificado)."""
    db: Session = SessionLocal()
    try:
        logger.info(f"[run_analysis] start analise_id={analise_id}")
        analise = crud.get_analise(db, analise_id)
        if not analise:
            logger.warning(f"[run_analysis] analise_id={analise_id} não encontrada")
            return
        crud.update_analise_status(db, analise_id, "Processando")

        lic = crud.get_licitacao(db, analise.licitacao_id)
        if lic is None:
            resultado = "Não foi possível localizar a licitação relacionada."
        else:
            partes = [
                "Resumo automático da licitação:",
                f"Órgão: {lic.orgao_entidade_nome or 'N/D'}",
                f"Objeto: {lic.objeto_compra or 'N/D'}",
                f"UF/Município: {lic.uf or 'N/D'} / {lic.municipio_nome or 'N/D'}",
                f"Publicação: {lic.data_publicacao_pncp or 'N/D'}",
                f"Encerramento: {lic.data_encerramento_proposta or 'N/D'}",
                f"Valor estimado: {lic.valor_total_estimado or 'N/D'}",
            ]
            resumo_extra = ""
            if getattr(lic, "link_sistema_origem", None):
                txt, _ = extract_text_from_link(lic.link_sistema_origem)  # type: ignore[arg-type]
                if txt:
                    txt_preview = (txt[:800] + "...") if len(txt) > 800 else txt
                    resumo_extra = "\n\nAmostra do edital (texto extraído):\n" + txt_preview
            resultado = "\n".join(partes) + resumo_extra

        crud.set_analise_resultado(db, analise_id, resultado)
        logger.info(f"[run_analysis] done analise_id={analise_id} status=Concluído")
    except Exception:
        logger.exception(f"[run_analysis] failed analise_id={analise_id}")
        try:
            crud.update_analise_status(db, analise_id, "Erro")
        except Exception:
            pass
    finally:
        db.close()


def run_analysis_from_file(analise_id: int, file_path: str) -> None:
    """Processa análise usando um arquivo local (PDF/Imagem/HTML)."""
    db: Session = SessionLocal()
    try:
        logger.info(f"[run_analysis_from_file] start analise_id={analise_id} file_path={file_path}")
        analise = crud.get_analise(db, analise_id)
        if not analise:
            logger.warning(f"[run_analysis_from_file] analise_id={analise_id} não encontrada")
            return
        crud.update_analise_status(db, analise_id, "Processando")

        texto: str = ""
        try:
            p = Path(file_path)
            data = p.read_bytes()
            ctype = "application/pdf" if p.suffix.lower() == ".pdf" else "application/octet-stream"
            extracted = _extract_text_from_pdf(data) if ctype == "application/pdf" else None
            if not extracted:
                ocr = _ocr_pdf2(data)
                if ocr:
                    extracted = ocr
            texto = extracted or ""
        except Exception:
            texto = ""

        if not texto:
            resultado = "Não foi possível extrair texto do arquivo enviado."
        else:
            resumo, _ = _analisar_texto_edital_enriquecida(texto)
            resultado = resumo

        crud.set_analise_resultado(db, analise_id, resultado)
        logger.info(f"[run_analysis_from_file] done analise_id={analise_id} status=Concluído")
    except Exception:
        logger.exception(f"[run_analysis_from_file] failed analise_id={analise_id}")
        try:
            crud.update_analise_status(db, analise_id, "Erro")
        except Exception:
            pass
    finally:
        db.close()
