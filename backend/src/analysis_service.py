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
    from .agents.agno_agent import run_edital_analysis  # type: ignore
except Exception:
    run_edital_analysis = None  # type: ignore
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
from .embeddings_service import index_licitacao

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


def _extract_items_from_pdf_bytes(data: bytes) -> list[Dict[str, Any]]:
    return []


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


def _ocr_image(data: bytes, lang_default: str = "por") -> Optional[str]:
    if pytesseract is None or Image is None:
        return None
    try:
        img = Image.open(BytesIO(data))
        return pytesseract.image_to_string(img, lang=lang_default)
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
    lower = texto.lower()
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

# --- FIM helpers adicionados ---




