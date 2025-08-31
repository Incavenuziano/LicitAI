from __future__ import annotations

import json
import re
from typing import Any, List, Optional
from urllib.parse import urljoin

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None


def comprasnet_contrato_arquivos(
    contrato_id: int,
    base_url: str = "https://contratos.comprasnet.gov.br",
    timeout: float = 45.0,
) -> List[str]:
    """
    Consulta os arquivos (anexos) de um contrato no ComprasNet, via endpoint:
    GET {base_url}/api/contrato/{contrato_id}/arquivos

    Retorna lista de URLs (absolutas quando possível).
    """
    if httpx is None:
        return []
    url = f"{base_url.rstrip('/')}/api/contrato/{contrato_id}/arquivos"
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        data: Any = resp.json()
    except Exception:
        return []

    arquivos: List[str] = []
    # Formatos previstos: {'arquivos': [{ 'path_arquivo': '/storage/...' }, ...]}
    # ou lista simples de strings.
    if isinstance(data, dict):
        items = data.get("arquivos") or data.get("data") or []
    else:
        items = data

    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                path = it.get("path_arquivo") or it.get("arquivo") or None
                if path:
                    arquivos.append(urljoin(base_url, str(path)))
                else:
                    # Pode vir como { 'arquivo_1': 'http...' }
                    for v in it.values():
                        if isinstance(v, str):
                            arquivos.append(urljoin(base_url, v))
            elif isinstance(it, str):
                arquivos.append(urljoin(base_url, it))

    # Remover duplicatas mantendo ordem
    seen = set()
    unique: List[str] = []
    for u in arquivos:
        if u not in seen:
            unique.append(u)
            seen.add(u)
    return unique


def comprasnet_arquivos_periodo(
    base_url: str = "https://contratos.comprasnet.gov.br",
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    timeout: float = 45.0,
) -> Any:
    """Consulta arquivos alterados em período: GET /api/v1/contrato/arquivos
    Parâmetros de datas dependem da API; aqui aceitamos strings (ex.: '2024-01-01').
    """
    if httpx is None:
        return []
    url = f"{base_url.rstrip('/')}/api/v1/contrato/arquivos"
    params = {"pagina": pagina, "tamanhoPagina": tamanho_pagina}
    if data_inicio:
        params["dataInicio"] = data_inicio
    if data_fim:
        params["dataFim"] = data_fim
    try:
        resp = httpx.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _find_pdf_links_from_html(html: str, base_url: str) -> List[str]:
    links: List[str] = []
    parsed = False
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                text = (a.get_text() or "").lower()
                if not href:
                    continue
                if href.lower().endswith(".pdf") or ("pdf" in href.lower()) or ("edital" in text) or ("anexo" in text):
                    links.append(urljoin(base_url, href))
            parsed = True
        except Exception:
            parsed = False
    if not parsed:
        for m in re.findall(r"href=\"([^\"]+)\"|href='([^']+)'", html, flags=re.I):
            href = m[0] or m[1]
            if href and (href.lower().endswith(".pdf") or "pdf" in href.lower()):
                links.append(urljoin(base_url, href))
    seen = set()
    out: List[str] = []
    for u in links:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


def pncp_extrair_anexos_de_pagina(
    pagina_url: str,
    timeout: float = 30.0,
) -> List[str]:
    """Baixa uma página do PNCP (ou sistema de origem) e tenta identificar links de PDF (anexos)."""
    if httpx is None:
        return []
    try:
        resp = httpx.get(pagina_url, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
        return _find_pdf_links_from_html(html, pagina_url)[:10]
    except Exception:
        return []

