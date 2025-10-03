from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..helpers import parse_numero_controle
from ..integrations import pncp as pncp_api

INTERESTING_KEYWORDS = [
    "preco",
    "precos",
    "pesquisa",
    "cotacao",
    "orcamento",
    "mapa",
    "planilha",
]
MAX_PDF_PAGES = 6


@dataclass
class PrecoDocumento:
    valor: float
    documento_path: str
    documento_info: Dict[str, Any]


def _br_to_float(text: Any) -> Optional[float]:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        try:
            value = float(text)
        except Exception:
            return None
        return value if value > 0 else None
    s = str(text).strip()
    if not s:
        return None
    s = s.replace("R$", "", 1)
    s = s.replace(" ", "")
    if s.count(",") == 1:
        s = s.replace(".", "").replace(",", ".")
    try:
        value = float(s)
    except Exception:
        return None
    return value if value > 0 else None


def _extract_prices_from_text(text: str) -> List[float]:
    values: List[float] = []
    if not text:
        return values
    pattern = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+\.\d{2})(?!\d)")
    for match in pattern.findall(text):
        price = _br_to_float(match)
        if price is not None:
            values.append(price)
    return values


def _extract_prices_from_pdf(path: Path) -> List[float]:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return []
    values: List[float] = []
    try:
        with pdfplumber.open(path) as pdf:
            for idx, page in enumerate(pdf.pages):
                if idx >= MAX_PDF_PAGES:
                    break
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                if text:
                    values.extend(_extract_prices_from_text(text))
    except Exception:
        return []
    return values


def _dataframe_price_candidates(df) -> List[float]:
    values: List[float] = []
    try:
        columns = list(df.columns)
    except Exception:
        return values
    cues = ("valor", "preco", "price", "unit", "total", "vlr")
    lower_map = {c: (str(c).lower() if isinstance(c, str) else "") for c in columns}
    target_cols = [c for c in columns if any(k in lower_map[c] for k in cues)]
    if not target_cols:
        target_cols = columns
    for col in target_cols:
        series = df[col]
        for item in series:
            price = _br_to_float(item)
            if price is not None:
                values.append(price)
    return values


def _extract_prices_from_excel(path: Path) -> List[float]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return []
    try:
        frames = pd.read_excel(path, sheet_name=None)
    except Exception:
        return []
    values: List[float] = []
    for frame in frames.values():
        try:
            values.extend(_dataframe_price_candidates(frame))
        except Exception:
            continue
    return values


def _extract_prices_from_csv(path: Path) -> List[float]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return []
    values: List[float] = []
    encodings = [None, "latin-1", "utf-8", "utf-16"]
    for enc in encodings:
        try:
            frame = pd.read_csv(path, encoding=enc) if enc else pd.read_csv(path)
            values.extend(_dataframe_price_candidates(frame))
            break
        except Exception:
            continue
    return values


def _extract_prices_from_file(path: str) -> List[float]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_prices_from_pdf(p)
    if suffix in {".xlsx", ".xls"}:
        return _extract_prices_from_excel(p)
    if suffix == ".csv":
        return _extract_prices_from_csv(p)
    return []


def _is_interesting_document(doc: Dict[str, Any]) -> bool:
    fields = [
        doc.get("titulo"),
        doc.get("tipo_nome"),
        doc.get("tipoNome"),
        doc.get("tipoDocumentoNome"),
    ]
    text = " ".join([str(f).lower() for f in fields if f])
    if not text:
        return False
    return any(k in text for k in INTERESTING_KEYWORDS)


def _dedupe_prices(values: List[float]) -> List[float]:
    seen = set()
    result: List[float] = []
    for value in values:
        key = round(value, 2)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _collect_precos_sync(numero_controle_pncp: str) -> List[PrecoDocumento]:
    parsed = parse_numero_controle(numero_controle_pncp)
    if not parsed:
        return []
    ano = int(parsed["ano"])
    try:
        sequencial = int(parsed["sequencial"])
    except Exception:
        try:
            sequencial = int(parsed["sequencial"].lstrip("0") or "0")
        except Exception:
            return []
    numero_compra = f"{sequencial}/{ano}"

    row = pncp_api.pncp_buscar_por_numero_compra_expanded(
        numero_compra,
        total_days=365,
        step_days=30,
        page_limit=8,
    )
    if not row:
        return []

    orgao = row.get("orgaoEntidade") or {}
    cnpj = orgao.get("cnpj") or orgao.get("cnpjOrgao") or orgao.get("cnpjEntidade") or row.get("cnpj")
    if not cnpj:
        return []

    docs = pncp_api.listar_documentos_compra(str(cnpj), ano, sequencial)
    if not docs:
        return []

    interesting = [doc for doc in docs if _is_interesting_document(doc)]
    if not interesting:
        interesting = docs[:5]

    resultados: List[PrecoDocumento] = []
    for doc in interesting:
        seq_doc = doc.get("sequencial") or doc.get("id")
        if seq_doc is None:
            continue
        try:
            seq_doc_int = int(str(seq_doc))
        except Exception:
            continue
        path = pncp_api.baixar_documento_por_sequencial(
            str(cnpj),
            ano,
            sequencial,
            seq_doc_int,
        )
        if not path:
            continue
        prices = _extract_prices_from_file(path)
        if not prices:
            continue
        for value in _dedupe_prices(prices):
            resultados.append(
                PrecoDocumento(
                    valor=value,
                    documento_path=path,
                    documento_info=doc,
                )
            )
    return resultados


async def coletar_precos_normalizados(numero_controle_pncp: str) -> List[PrecoDocumento]:
    if not numero_controle_pncp:
        return []
    return await asyncio.to_thread(_collect_precos_sync, numero_controle_pncp)
