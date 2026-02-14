import logging
import traceback
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from . import crud, models
from .database import SessionLocal

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
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None

try:
    from .agents.agno_agent import run_edital_analysis  # type: ignore
except Exception:
    run_edital_analysis = None  # type: ignore


def _extract_text_from_pdf(data: bytes) -> Optional[str]:
    """Extract text directly from a PDF using pdfplumber or pypdf."""
    if pdfplumber is not None:
        try:
            texts: List[str] = []
            with pdfplumber.open(BytesIO(data)) as pdf:
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text() or ""
                    except Exception:
                        page_text = ""
                    if page_text:
                        texts.append(page_text)
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


def _ocr_pdf(data: bytes, *, lang: str = "por", dpi: int = 200, max_pages: int = 10) -> Optional[str]:
    """Fallback OCR extraction for image only PDFs."""
    if convert_from_bytes is None or pytesseract is None:
        return None
    try:
        images = convert_from_bytes(data, dpi=dpi)
        texts: List[str] = []
        for idx, image in enumerate(images):
            if max_pages and idx >= max_pages:
                break
            try:
                extracted = pytesseract.image_to_string(image, lang=lang)
            except Exception:
                extracted = ""
            if extracted:
                texts.append(extracted)
        combined = "\n".join(texts).strip()
        return combined or None
    except Exception:
        return None


def extract_text_from_link(link: str) -> Tuple[str, Dict[str, Any]]:
    """Download a remote resource and attempt to extract text."""
    texto: Optional[str] = None
    meta: Dict[str, Any] = {"from_cache": False}
    if not requests:
        return "", meta
    try:
        resp = requests.get(link, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        data = resp.content
        meta["ctype"] = content_type
        if "pdf" in content_type or link.lower().endswith(".pdf"):
            texto = _extract_text_from_pdf(data)
            if not texto or len(texto) < 200:
                texto = _ocr_pdf(data)
                meta["method"] = "ocr" if texto else "pdf-sem-texto"
            else:
                meta["method"] = "pdf-texto"
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
            meta["method"] = "html"
    except Exception:
        texto = ""
        meta["method"] = "erro"
    return texto or "", meta


def _parse_date_br(value: str) -> Optional[datetime]:
    """Parse brazilian formatted dates (best effort)."""
    value = (value or "").strip()
    formats = ["%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y %H:%M", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _normalize_field_key(label: str) -> str:
    import re
    import unicodedata

    label = unicodedata.normalize("NFKD", label or "")
    label = "".join(ch for ch in label if not unicodedata.combining(ch))
    label = label.lower()
    label = re.sub(r"[^a-z0-9]+", " ", label)
    return label.strip()


FIELD_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "orgao_entidade_nome": (
        "orgao responsavel",
        "orgao",
        "orgao entidade",
        "entidade contratante",
        "entidade"
    ),
    "objeto_compra": (
        "objeto",
        "descricao do objeto",
        "objeto principal"
    ),
    "valor_total_estimado": (
        "valor estimado",
        "valor total estimado",
        "valor global",
        "valor maximo"
    ),
    "data_encerramento_proposta": (
        "data de encerramento",
        "data encerramento",
        "prazo final",
        "data limite"
    ),
    "modalidade_nome": ("modalidade",),
    "uf": ("uf", "estado"),
    "municipio_nome": ("municipio", "cidade"),
}


def _extract_structured_data_from_analysis(markdown: str) -> Dict[str, Any]:
    if not markdown:
        return {}

    lines = markdown.splitlines()
    section: List[str] = []
    capture = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        normalized = _normalize_field_key(stripped)
        if not capture:
            if "informacoes gerais do edital" in normalized or normalized.startswith("### 1 informacoes gerais"):
                capture = True
            continue
        if stripped.startswith("### "):
            break
        section.append(stripped)

    if not section:
        return {}

    results: Dict[str, Any] = {}
    for line in section:
        clean = line.lstrip('-*•').strip()
        if not clean:
            continue
        if set(clean) <= {"|", "-"}:
            continue
        if ':' in clean:
            key, value = clean.split(':', 1)
        elif '–' in clean:
            key, value = clean.split('–', 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue

        normalized_key = _normalize_field_key(key)
        target_field = None
        for field, keywords in FIELD_KEYWORDS.items():
            if any(keyword in normalized_key for keyword in keywords):
                target_field = field
                break
        if not target_field:
            continue

        if target_field == "valor_total_estimado":
            amount = _parse_money_br(value)
            if amount is not None:
                results[target_field] = Decimal(f"{amount:.2f}")
        elif target_field == "data_encerramento_proposta":
            parsed = _parse_date_br(value)
            if parsed:
                results[target_field] = parsed
        elif target_field == "uf":
            results[target_field] = value[:2].upper()
        else:
            results[target_field] = value

    return results


def _extract_basic_metadata(text: str) -> Dict[str, Any]:
    import re

    meta: Dict[str, Any] = {}
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    for idx, line in enumerate(lines):
        match = re.match(r"(?i)^(objeto(\s+da\s+licitac[a-z]+)?|finalidade)\s*[:\-]\s*(.+)$", line)
        if match:
            valor = match.group(3).strip()
            if len(valor) < 20 and idx + 1 < len(lines):
                valor = (valor + " " + lines[idx + 1].strip()).strip()
            meta["objeto_compra"] = valor
            break

    for line in lines[:40]:
        match = re.match(r"(?i)^(orgao|\u00f3rg\u00e3o|entidade)\s*[:\-]\s*(.+)$", line)
        if match:
            meta["orgao_entidade_nome"] = match.group(2).strip()
            break

    for line in lines:
        match = re.search(r"(?i)(encerramento|prazo\s*final).*?([0-3]?\d[\/-][01]?\d[\/-]\d{2,4}(?:\s+\d{1,2}:\d{2})?)", line)
        if match:
            parsed = _parse_date_br(match.group(2))
            if parsed:
                meta["data_encerramento_proposta"] = parsed
                break
    return meta


def _build_edital_summary_md(licitacao: models.Licitacao, meta: Dict[str, Any], items: Optional[List[Dict[str, Any]]] = None, limit_items: int = 5) -> str:
    orgao = (meta.get("orgao_entidade_nome") or licitacao.orgao_entidade_nome or "N/A").strip()
    objeto = (meta.get("objeto_compra") or licitacao.objeto_compra or "N/A").strip()
    encerramento = meta.get("data_encerramento_proposta") or licitacao.data_encerramento_proposta
    if isinstance(encerramento, datetime):
        encerramento_txt = encerramento.strftime("%d/%m/%Y %H:%M")
    else:
        encerramento_txt = "N/A"

    lines: List[str] = []
    lines.append("## Resumo da Licitacao\n")
    lines.append(f"- **Orgao/Entidade:** {orgao if orgao else 'N/A'}")
    lines.append(f"- **Objeto:** {objeto if objeto else 'N/A'}")
    lines.append(f"- **Encerramento de Propostas:** {encerramento_txt}\n")

    sample = (items or [])[: max(0, limit_items)]
    if sample:
        lines.append("**Itens (amostra):**")
        lines.append("| Item | Descricao | Qtd | Unid | Vlr Unit. | Vlr Total | Marca | Modelo |")
        lines.append("|---:|---|---:|:---:|---:|---:|---|---|")

        def _fmt_text(value: Any, default: str = "N/A") -> str:
            if value is None:
                return default
            if isinstance(value, str):
                cleaned = value.strip()
                return cleaned if cleaned else default
            return str(value)

        def _fmt_num(value: Any) -> str:
            if value is None:
                return "N/A"
            try:
                return f"{float(value):.2f}"
            except Exception:
                return _fmt_text(value)

        def _fmt_money(value: Any) -> str:
            if value is None:
                return "N/A"
            try:
                return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return _fmt_text(value)

        for item in sample:
            lines.append(
                "| {item} | {desc} | {qtd} | {unid} | {vu} | {vt} | {marca} | {modelo} |".format(
                    item=_fmt_text(item.get("item")),
                    desc=_fmt_text(item.get("descricao")).replace("|", " ")[:120],
                    qtd=_fmt_num(item.get("quantidade")),
                    unid=_fmt_text(item.get("unidade")),
                    vu=_fmt_money(item.get("valor_unitario")),
                    vt=_fmt_money(item.get("valor_total")),
                    marca=_fmt_text(item.get("marca")),
                    modelo=_fmt_text(item.get("modelo")),
                )
            )
        lines.append("")

    lines.append("> Nota: dados acima foram extraidos automaticamente e podem conter pequenas imprecisoes.\n")
    return "\n".join(lines)


def _parse_money_br(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    text = str(value)
    text = text.replace("R$", "").replace(" ", "").replace("\xa0", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def _extract_items_from_table_rows(rows: List[List[str]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    header = [str(col or "").strip().lower() for col in rows[0]]

    def idx(keyword: str) -> Optional[int]:
        for i, col in enumerate(header):
            if keyword in col:
                return i
        return None

    i_item = idx("item")
    i_desc = idx("descr")
    i_qtd = idx("quant")
    i_un = idx("unid")
    i_vu = idx("valor unit")
    i_vt = idx("valor total")
    i_marca = idx("marca")
    i_modelo = idx("modelo")

    extracted: List[Dict[str, Any]] = []
    for row in rows[1:]:
        def safe(pos: Optional[int]) -> Optional[str]:
            if pos is None or pos >= len(row):
                return None
            return row[pos]

        try:
            item_num = int(str(safe(i_item)).strip()) if safe(i_item) is not None else None
        except Exception:
            item_num = None

        try:
            quantidade = float(str(safe(i_qtd)).replace(",", ".")) if safe(i_qtd) is not None else None
        except Exception:
            quantidade = None

        extracted.append(
            {
                "item": item_num,
                "descricao": safe(i_desc),
                "quantidade": quantidade,
                "unidade": safe(i_un),
                "valor_unitario": _parse_money_br(safe(i_vu)),
                "valor_total": _parse_money_br(safe(i_vt)),
                "marca": safe(i_marca),
                "modelo": safe(i_modelo),
            }
        )
    return extracted


def _extract_items_from_text(text: str) -> List[Dict[str, Any]]:
    import re

    lines = [ln.strip() for ln in (text or "").splitlines()]
    items: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def push():
        nonlocal current
        if current and current.get("item") is not None:
            items.append(current)
        current = None

    for line in lines:
        if not line:
            continue
        match = re.match(r"item\s*(\d+)\s*[-:]?\s*(.*)$", line, flags=re.I)
        if match:
            push()
            try:
                number = int(match.group(1))
            except Exception:
                number = None
            current = {
                "item": number,
                "descricao": match.group(2).strip() if match.group(2) else None,
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "marca": None,
                "modelo": None,
            }
            continue
        if current is None:
            continue
        lower = line.lower()
        if lower.startswith("quantidade:"):
            try:
                current["quantidade"] = float(line.split(":", 1)[1].strip().replace(",", "."))
            except Exception:
                pass
        elif lower.startswith("unidade:"):
            current["unidade"] = line.split(":", 1)[1].strip()
        elif lower.startswith("valor unit"):
            current["valor_unitario"] = _parse_money_br(line.split(":", 1)[1])
        elif lower.startswith("valor total"):
            current["valor_total"] = _parse_money_br(line.split(":", 1)[1])
        elif lower.startswith("marca:"):
            current["marca"] = line.split(":", 1)[1].strip()
        elif lower.startswith("modelo:"):
            current["modelo"] = line.split(":", 1)[1].strip()
    push()
    return items


def _markdown_to_html(text: str) -> str:
    try:
        import markdown  # type: ignore
        return markdown.markdown(text)
    except Exception:
        pass

    import html

    chunks = [chunk.strip() for chunk in (text or "").split("\n\n") if chunk.strip()]
    html_blocks: List[str] = []
    for chunk in chunks:
        lines = chunk.splitlines()
        if all(line.strip().startswith(('-', '*')) for line in lines):
            items = []
            for line in lines:
                stripped = line.strip()[1:].strip()
                items.append(f"<li>{html.escape(stripped)}</li>")
            html_blocks.append("<ul>" + "".join(items) + "</ul>")
        else:
            html_blocks.append(f"<p>{html.escape(chunk)}</p>")
    return "".join(html_blocks)


def _format_analysis_html(html: str) -> str:
    try:
        import re as _re

        body = html or ""
        if "<" not in body:
            body = "\n".join(f"<p>{line.strip()}</p>" for line in body.splitlines() if line.strip())
        else:
            body = body.replace("<ul>", "").replace("</ul>", "")
            body = _re.sub(r"<li>\s*", "<p>&bull; ", body)
            body = _re.sub(r"\s*</li>", "</p>", body)

        return (
            '<div class="analysis-result" style="text-align: justify; line-height: 1.6;">'
            + body
            + "</div>"
        )
    except Exception:
        return html


def _compose_final_html(summary_md: str, analysis_md: str) -> str:
    parts: List[str] = []
    if summary_md:
        parts.append(_format_analysis_html(_markdown_to_html(summary_md)))
    if analysis_md:
        parts.append(_format_analysis_html(_markdown_to_html(analysis_md)))
    return "".join(parts)




# Compat helper kept for backwards compatibility with legacy tests
def _analisar_texto_edital_enriquecida(texto: str) -> tuple[str, dict[str, list[str]]]:
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

def _prepare_text_from_pdf(anexo_path: Path) -> Optional[str]:
    if not anexo_path.exists():
        return None
    try:
        data = anexo_path.read_bytes()
    except Exception:
        return None
    texto = _extract_text_from_pdf(data) or ""
    if len(texto) < 200:
        texto = _ocr_pdf(data) or ""
    return texto or None


def _generate_complete_analysis(licitacao: models.Licitacao, texto: str) -> Tuple[str, Dict[str, Any]]:
    if not texto:
        raise ValueError("Nenhum texto extraido para a analise.")
    titulo = f"Analise do Edital: { (licitacao.objeto_compra or '').strip() or 'Sem objeto definido' }"
    resultado_md: str
    if run_edital_analysis is None:
        resumo_simples, _ = _analisar_texto_edital_enriquecida(texto)
        resultado_md = (
            "### Analise automatica (modo degradado)\n\n"
            "A integracao com Agno/Gemini nao esta disponivel neste ambiente.\n\n"
            f"{resumo_simples}\n"
        )
    else:
        try:
            resultado_md = run_edital_analysis(texto=texto, titulo_secao=titulo)  # type: ignore[arg-type]
            if not isinstance(resultado_md, str):
                resultado_md = str(resultado_md)
        except Exception:
            logger.warning("[analysis] Agno/Gemini indisponivel em runtime; aplicando fallback", exc_info=True)
            resumo_simples, _ = _analisar_texto_edital_enriquecida(texto)
            resultado_md = (
                "### Analise automatica (modo degradado)\n\n"
                "Nao foi possivel executar o modelo principal nesta rodada.\n\n"
                f"{resumo_simples}\n"
            )

    analysis_fields = _extract_structured_data_from_analysis(resultado_md)


    meta = _extract_basic_metadata(texto)
    if meta.get("objeto_compra") and "objeto_compra" not in analysis_fields:
        analysis_fields["objeto_compra"] = meta["objeto_compra"]
    if meta.get("orgao_entidade_nome") and "orgao_entidade_nome" not in analysis_fields:
        analysis_fields["orgao_entidade_nome"] = meta["orgao_entidade_nome"]
    if meta.get("data_encerramento_proposta") and "data_encerramento_proposta" not in analysis_fields:
        analysis_fields["data_encerramento_proposta"] = meta["data_encerramento_proposta"]

    try:
        itens = _extract_items_from_text(texto)
    except Exception:
        itens = []

    summary_md = _build_edital_summary_md(licitacao, meta, itens)
    final_html = _compose_final_html(summary_md, resultado_md)
    logger.info("[analysis] structured fields: %s", analysis_fields)
    return final_html, analysis_fields


def run_analysis(analise_id: int) -> None:
    """Executa a analise completa para uma licitacao existente."""
    db: Session = SessionLocal()
    analise = None
    try:
        analise = crud.get_analise(db, analise_id)
        if not analise:
            logger.warning(f"[run_analysis] analise_id={analise_id} nao encontrada")
            return

        crud.update_analise_status(db, analise_id, "Processando")
        lic = crud.get_licitacao(db, analise.licitacao_id)
        if lic is None:
            crud.update_analise(db, analise_id, status="Erro", resultado="Licitacao nao encontrada para a analise.")
            return

        anexo = crud.get_principal_anexo(db, analise.licitacao_id)
        if not anexo or not anexo.local_path:
            crud.update_analise(db, analise_id, status="Erro", resultado="Nenhum edital principal encontrado para a licitacao.")
            return

        texto = _prepare_text_from_pdf(Path(anexo.local_path))
        if not texto:
            crud.update_analise(db, analise_id, status="Erro", resultado="Nao foi possivel extrair texto do edital associado.")
            return

        resultado_html, analysis_fields = _generate_complete_analysis(lic, texto)
        crud.set_analise_resultado(db, analise_id, resultado_html, status="Concluido")
        if analysis_fields:
            logger.info("[run_analysis] updating licitacao %s with %s", lic.id, analysis_fields)
            try:
                crud.update_licitacao_fields_if_empty(db, lic.id, **analysis_fields)
            except Exception:
                logger.warning("[run_analysis] nao foi possivel atualizar campos extraidos", exc_info=True)
        logger.info(f"[run_analysis] concluido analise_id={analise_id}")
    except Exception:
        logger.error(f"[run_analysis] falha analise_id={analise_id}", exc_info=True)
        if analise:
            try:
                crud.update_analise(db, analise_id, status="Erro")
            except Exception:
                pass
    finally:
        db.close()


def run_analysis_from_file(analise_id: int, file_path: str) -> None:
    """Executa a analise utilizando um arquivo PDF fornecido manualmente."""
    db: Session = SessionLocal()
    analise = None
    try:
        analise = crud.get_analise(db, analise_id)
        if not analise:
            logger.warning(f"[run_analysis_from_file] analise_id={analise_id} nao encontrada")
            return

        crud.update_analise_status(db, analise_id, "Processando")
        lic = crud.get_licitacao(db, analise.licitacao_id)
        if lic is None:
            crud.update_analise(db, analise_id, status="Erro", resultado="Licitacao relacionada nao foi encontrada.")
            return

        texto = _prepare_text_from_pdf(Path(file_path))
        if not texto:
            crud.update_analise(db, analise_id, status="Erro", resultado="Nao foi possivel extrair texto do arquivo enviado.")
            return

        resultado_html, analysis_fields = _generate_complete_analysis(lic, texto)
        crud.set_analise_resultado(db, analise_id, resultado_html, status="Concluido")
        if analysis_fields:
            logger.info("[run_analysis_from_file] updating licitacao %s com %s", lic.id, analysis_fields)
            try:
                crud.update_licitacao_fields_if_empty(db, lic.id, **analysis_fields)
            except Exception:
                logger.warning("[run_analysis_from_file] nao foi possivel atualizar campos extraidos", exc_info=True)
        logger.info(f"[run_analysis_from_file] concluido analise_id={analise_id}")
    except Exception:
        logger.error(f"[run_analysis_from_file] falha analise_id={analise_id}", exc_info=True)
        if analise:
            try:
                crud.update_analise(db, analise_id, status="Erro")
            except Exception:
                pass
    finally:
        db.close()


# Placeholders for legacy helpers used by scripts and agents -------------------

async def baixar_edital_com_playwright(link_pagina: str, licitacao_id: int) -> Optional[str]:
    logger.warning("baixar_edital_com_playwright nao esta implementado neste ambiente.")
    return None


def baixar_edital_via_api(licitacao: models.Licitacao) -> Optional[str]:
    logger.warning("baixar_edital_via_api nao esta implementado neste ambiente.")
    return None


async def baixar_edital_com_playwright_storage(link_pagina: str, identificador: str | int) -> Optional[str]:
    logger.warning("baixar_edital_com_playwright_storage nao esta implementado neste ambiente.")
    return None


async def baixar_edital_com_playwright_storage_v2(link_pagina: str, identificador: str | int) -> Optional[str]:
    logger.warning("baixar_edital_com_playwright_storage_v2 nao esta implementado neste ambiente.")
    return None


def resolve_edital_pdf_with_playwright(*args, **kwargs) -> Optional[str]:
    logger.warning("resolve_edital_pdf_with_playwright nao esta implementado neste ambiente.")
    return None
