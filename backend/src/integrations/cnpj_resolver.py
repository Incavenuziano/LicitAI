from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None


def _norm(s: str) -> str:
    try:
        import unicodedata
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    except Exception:
        pass
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _similar(a: str, b: str) -> float:
    """Token-based Jaccard similarity for org name matching."""
    ta = set(_norm(a).split())
    tb = set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    uni = len(ta | tb)
    return inter / uni


def resolve_cnpj_by_name_via_pncp(
    nome_orgao: str,
    *,
    uf: Optional[str] = None,
    total_days: int = 365,
    step_days: int = 30,
    page_limit: int = 5,
    timeout: float = 30.0,
) -> Optional[str]:
    """Heurística: varre publicações no PNCP para mapear nome do órgão → CNPJ.

    - Usa /api/consulta/v1/contratacoes/publicacao em blocos de datas.
    - Coleta pairs (orgaoEntidade.nome, orgaoEntidade.cnpj) e retorna o CNPJ com maior similaridade.
    """
    if httpx is None:
        return None
    base_dt = datetime.utcnow()
    start_dt = base_dt - timedelta(days=total_days)
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    best_cnpj = None
    best_score = 0.0

    cur = start_dt
    while cur <= base_dt:
        nxt = min(cur + timedelta(days=step_days), base_dt)
        params_base: Dict[str, Any] = {
            "dataInicial": cur.strftime("%Y%m%d"),
            "dataFinal": nxt.strftime("%Y%m%d"),
            # sem filtrar modalidade para ampliar cobertura
            "pagina": 1,
            "tamanhoPagina": 50,
        }
        if uf:
            params_base["uf"] = uf
        for page in range(1, page_limit + 1):
            params = dict(params_base)
            params["pagina"] = page
            try:
                r = httpx.get(url, params=params, timeout=timeout)
                r.raise_for_status()
                payload: Any = r.json()
            except Exception:
                break
            data = payload.get("data") if isinstance(payload, dict) else None
            if not data:
                break
            for row in data:
                if not isinstance(row, dict):
                    continue
                ent = row.get("orgaoEntidade") or {}
                nome = ent.get("nome") or ent.get("descricao") or ""
                cnpj = ent.get("cnpj") or ""
                if not nome or not cnpj:
                    continue
                score = _similar(nome_orgao, nome)
                if score > best_score:
                    best_score = score
                    best_cnpj = cnpj
        cur = nxt + timedelta(days=1)
    return best_cnpj


def resolve_cnpj_by_name_via_google(
    nome_orgao: str,
    *,
    api_key_env: str = "GOOGLE_API_KEY",
    cse_id_env: str = "GOOGLE_CSE_ID",
    timeout: float = 20.0,
) -> Optional[str]:
    """Opcional: usa Google Custom Search (requer chave e cx) para extrair CNPJ por regex.

    Observação: Evite raspar Google diretamente; use a API oficial (CSE) e respeite ToS.
    """
    if httpx is None:
        return None
    import os
    key = os.getenv(api_key_env)
    cx = os.getenv(cse_id_env)
    if not key or not cx:
        return None
    q = f"CNPJ {nome_orgao}"
    try:
        r = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"q": q, "key": key, "cx": cx, "num": 5},
            timeout=timeout,
        )
        r.raise_for_status()
        js = r.json()
    except Exception:
        return None
    cnpj_rx = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b")
    items = js.get("items") or []
    for it in items:
        for field in (it.get("title"), it.get("snippet"), (it.get("link") or "")):
            if not field:
                continue
            m = cnpj_rx.search(field)
            if m:
                raw = m.group(0)
                return re.sub(r"\D+", "", raw)
    return None

