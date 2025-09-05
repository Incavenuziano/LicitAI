from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None


def _normalize_date_str(d: str | datetime) -> str:
    """Aceita 'YYYY-MM-DD', 'YYYYMMDD' ou datetime e retorna 'YYYYMMDD'."""
    if isinstance(d, datetime):
        return d.strftime("%Y%m%d")
    s = str(d).strip()
    # tenta YYYY-MM-DD
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y%m%d")
    except Exception:
        pass
    # tenta YYYYMMDD
    try:
        datetime.strptime(s, "%Y%m%d")
        return s
    except Exception:
        pass
    # fallback: hoje
    return datetime.utcnow().strftime("%Y%m%d")


def pncp_buscar_por_link(
    link_sistema_origem: str,
    data_ref: str | datetime,
    codigo_modalidade: int,
    *,
    uf: Optional[str] = None,
    cnpj: Optional[str] = None,
    janela_dias: int = 3,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    timeout: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """Busca no PNCP a contratação cuja publicação contenha o link do sistema de origem.

    - Endpoint: GET https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
    - Requisitos: dataInicial, dataFinal, codigoModalidadeContratacao, pagina

    Retorna o objeto (dict) da contratação quando encontrado; caso contrário, None.
    """
    if httpx is None:
        return None

    # janela de datas [data_ref - N, data_ref + N]
    try:
        # normaliza e reconstrói datetime para subtrair/adicionar
        dstr = _normalize_date_str(data_ref)
        base_dt = datetime.strptime(dstr, "%Y%m%d")
    except Exception:
        base_dt = datetime.utcnow()
    d_ini = (base_dt - timedelta(days=janela_dias)).strftime("%Y%m%d")
    d_fim = (base_dt + timedelta(days=janela_dias)).strftime("%Y%m%d")

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params: Dict[str, Any] = {
        "dataInicial": d_ini,
        "dataFinal": d_fim,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if uf:
        params["uf"] = uf
    if cnpj:
        params["cnpj"] = cnpj

    try:
        r = httpx.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        payload: Any = r.json()
    except Exception:
        return None

    data = None
    if isinstance(payload, dict):
        data = payload.get("data")
    if not isinstance(data, list):
        return None

    target = (link_sistema_origem or "").strip().lower()
    for row in data:
        if not isinstance(row, dict):
            continue
        lso = str(row.get("linkSistemaOrigem") or "").strip().lower()
        if not lso:
            continue
        if lso == target:
            return row
        # aproximação: compara hostname/caminho inicial
        if target and target.split("?")[0].rstrip("/") == lso.split("?")[0].rstrip("/"):
            return row
    return None


def pncp_compra_por_chave(
    cnpj: str,
    ano: int,
    sequencial: int,
    *,
    timeout: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """Consulta detalhamento da compra por chave (CNPJ, ano, sequencial).

    Endpoint:
      GET https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
    """
    if httpx is None:
        return None
    base = "https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"
    url = base.format(cnpj=str(cnpj).strip(), ano=int(ano), sequencial=int(sequencial))
    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _normalize_link(u: str) -> str:
    try:
        s = (u or "").strip()
        s = s.split('#')[0]
        s = s.rstrip('/')
        return s
    except Exception:
        return u or ""


def _links_match(a: str, b: str) -> bool:
    a = _normalize_link(a).lower()
    b = _normalize_link(b).lower()
    if not a or not b:
        return False
    if a == b:
        return True
    # Compara base sem querystring
    if a.split('?')[0] == b.split('?')[0]:
        # tenta casar por parâmetro 'compra=...'
        try:
            from urllib.parse import parse_qs, urlparse
            qa = parse_qs(urlparse(a).query)
            qb = parse_qs(urlparse(b).query)
            ca = (qa.get('compra') or [None])[0]
            cb = (qb.get('compra') or [None])[0]
            if ca and cb and ca == cb:
                return True
        except Exception:
            pass
    return False


def pncp_buscar_por_link_expanded(
    link_sistema_origem: str,
    *,
    data_hint: Optional[str | datetime] = None,
    uf: Optional[str] = None,
    cnpj: Optional[str] = None,
    modal_codes: Optional[list[int]] = None,
    total_days: int = 365,
    step_days: int = 30,
    page_limit: int = 10,
    timeout: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """Busca a publicação PNCP por link, varrendo múltiplas modalidades e janelas de datas.

    - Requerido pela API: dataInicial, dataFinal e codigoModalidadeContratacao.
    - Estratégia: define uma janela de busca por blocos (step_days) cobrindo total_days ao redor de data_hint (ou hoje),
      e tenta uma lista de códigos de modalidade. Para cada consulta, pagina até page_limit ou fim dos dados.
    """
    if httpx is None:
        return None
    if not modal_codes:
        # Lista abrangente; ajuste conforme documentação oficial se desejar ser mais restrito
        modal_codes = list(range(1, 21))  # 1..20

    # Base temporal
    base_dt = None
    if data_hint is not None:
        try:
            dstr = _normalize_date_str(data_hint)
            base_dt = datetime.strptime(dstr, "%Y%m%d")
        except Exception:
            base_dt = None
    if base_dt is None:
        base_dt = datetime.utcnow()

    half = total_days // 2
    start_dt = base_dt - timedelta(days=half)
    end_dt = base_dt + timedelta(days=half)

    # Gera blocos de datas [cur, cur+step]
    cur = start_dt
    blocks: list[tuple[str, str]] = []
    while cur <= end_dt:
        nxt = min(cur + timedelta(days=step_days), end_dt)
        blocks.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + timedelta(days=1)

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    target = _normalize_link(link_sistema_origem)

    for d_ini, d_fim in blocks:
        for cod in modal_codes:
            params: Dict[str, Any] = {
                "dataInicial": d_ini,
                "dataFinal": d_fim,
                "codigoModalidadeContratacao": cod,
                "pagina": 1,
                "tamanhoPagina": 50,
            }
            if uf:
                params["uf"] = uf
            if cnpj:
                params["cnpj"] = cnpj

            for page in range(1, page_limit + 1):
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
                    lso = row.get("linkSistemaOrigem") or ""
                    if _links_match(lso, target):
                        return row
    return None


def _parse_numero_compra(s: str | tuple[int, int] | None) -> Optional[tuple[int, int]]:
    """Extrai (sequencial, ano) de representações como '90016/2025'.

    Aceita também tupla já normalizada (sequencial, ano).
    """
    if s is None:
        return None
    if isinstance(s, tuple) and len(s) == 2:
        try:
            return int(s[0]), int(s[1])
        except Exception:
            return None
    try:
        txt = str(s)
        # procura padrão NN..N/YYYY
        import re
        m = re.search(r"(\d{1,10})\s*[/|-]\s*(\d{4})", txt)
        if m:
            seq = int(m.group(1))
            ano = int(m.group(2))
            return (seq, ano)
    except Exception:
        return None
    return None


def _numero_compra_match(a: str, b: str | tuple[int, int]) -> bool:
    pa = _parse_numero_compra(a)
    pb = _parse_numero_compra(b)
    if not pa or not pb:
        return False
    return pa == pb


def pncp_buscar_por_numero_compra_expanded(
    numero_compra: str | tuple[int, int],
    *,
    data_hint: Optional[str | datetime] = None,
    uf: Optional[str] = None,
    cnpj: Optional[str] = None,
    modal_codes: Optional[list[int]] = None,
    total_days: int = 365,
    step_days: int = 30,
    page_limit: int = 10,
    timeout: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """Busca publicação PNCP por númeroCompra ('sequencial/ano') com varredura ampla.

    Retorna o registro da publicação (contendo orgaoEntidade.cnpj, numeroCompra, etc.) se encontrado.
    """
    if httpx is None:
        return None
    key = _parse_numero_compra(numero_compra)
    if not key:
        return None

    if not modal_codes:
        modal_codes = list(range(1, 21))

    # Base temporal
    base_dt = None
    if data_hint is not None:
        try:
            dstr = _normalize_date_str(data_hint)
            base_dt = datetime.strptime(dstr, "%Y%m%d")
        except Exception:
            base_dt = None
    if base_dt is None:
        base_dt = datetime.utcnow()

    half = total_days // 2
    start_dt = base_dt - timedelta(days=half)
    end_dt = base_dt + timedelta(days=half)

    # Gera blocos de datas [cur, cur+step]
    cur = start_dt
    blocks: list[tuple[str, str]] = []
    while cur <= end_dt:
        nxt = min(cur + timedelta(days=step_days), end_dt)
        blocks.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + timedelta(days=1)

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    for d_ini, d_fim in blocks:
        for cod in modal_codes:
            params: Dict[str, Any] = {
                "dataInicial": d_ini,
                "dataFinal": d_fim,
                "codigoModalidadeContratacao": cod,
                "pagina": 1,
                "tamanhoPagina": 50,
            }
            if uf:
                params["uf"] = uf
            if cnpj:
                params["cnpj"] = cnpj

            for page in range(1, page_limit + 1):
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
                    if _numero_compra_match(str(row.get("numeroCompra") or ""), key):
                        return row
    return None


def pncp_compra_por_numero_compra_expanded(
    numero_compra: str | tuple[int, int],
    *,
    data_hint: Optional[str | datetime] = None,
    uf: Optional[str] = None,
    modal_codes: Optional[list[int]] = None,
    total_days: int = 365,
    step_days: int = 30,
    page_limit: int = 10,
    timeout: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """Convenience: encontra publicação por númeroCompra e consulta detalhes por chave (CNPJ/ano/sequencial)."""
    row = pncp_buscar_por_numero_compra_expanded(
        numero_compra,
        data_hint=data_hint,
        uf=uf,
        cnpj=None,
        modal_codes=modal_codes,
        total_days=total_days,
        step_days=step_days,
        page_limit=page_limit,
        timeout=timeout,
    )
    if not row:
        return None
    cnpj = None
    try:
        ent = row.get("orgaoEntidade") or {}
        cnpj = ent.get("cnpj")
    except Exception:
        cnpj = None
    key = _parse_numero_compra(numero_compra)
    if not (cnpj and key):
        return None
    seq, ano = key
    return pncp_compra_por_chave(cnpj=str(cnpj), ano=int(ano), sequencial=int(seq), timeout=timeout)


def pncp_find_publicacoes(
    *,
    codigo_modalidade: Optional[int] = None,
    data_inicial: str,
    data_final: str,
    codigo_unidade: Optional[str] = None,
    uf: Optional[str] = None,
    codigo_municipio_ibge: Optional[str] = None,
    cnpj: Optional[str] = None,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    timeout: float = 45.0,
) -> list[Dict[str, Any]]:
    """Consulta PNCP /v1/contratacoes/publicacao com filtros comuns.

    - Aceita tanto `codigo_unidade` mapeado para `codigoUnidadeAdministrativa` quanto `codigoUnidadeOrgao` (alguns docs variam nomenclatura).
    """
    if httpx is None:
        return []
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params: Dict[str, Any] = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if codigo_modalidade is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade
    if uf:
        params["uf"] = uf
    if codigo_municipio_ibge:
        params["codigoMunicipioIbge"] = codigo_municipio_ibge
    if codigo_unidade:
        # tenta ambas as chaves
        params["codigoUnidadeAdministrativa"] = codigo_unidade
        params["codigoUnidadeOrgao"] = codigo_unidade
    if cnpj:
        params["cnpj"] = str(cnpj)
    try:
        r = httpx.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        js: Any = r.json()
        data = js.get("data") if isinstance(js, dict) else None
        return data or []
    except Exception:
        return []


def pncp_find_numero_controle_by_filters(
    *,
    codigo_modalidade: Optional[int] = None,
    data_inicial: str,
    data_final: str,
    codigo_unidade: Optional[str] = None,
    uf: Optional[str] = None,
    codigo_municipio_ibge: Optional[str] = None,
    timeout: float = 45.0,
) -> Optional[tuple[str, Dict[str, Any]]]:
    """Retorna (numeroControlePNCP, row) do primeiro match pelos filtros.

    Nota: Ajuste os filtros (ex.: comparar `processo`, `objetoCompra`) para escolher o item correto quando houver muitos resultados.
    """
    rows = pncp_find_publicacoes(
        codigo_modalidade=codigo_modalidade,
        data_inicial=data_inicial,
        data_final=data_final,
        codigo_unidade=codigo_unidade,
        uf=uf,
        codigo_municipio_ibge=codigo_municipio_ibge,
        pagina=1,
        tamanho_pagina=50,
        timeout=timeout,
    )
    if not rows:
        return None
    row = rows[0]
    num = row.get("numeroControlePNCP")
    if isinstance(num, str):
        return num, row
    return None


# ------------------------------
# Documentos (listar e baixar)
# ------------------------------

def _pncp_base_api() -> str:
    """Base da API de integração do PNCP.

    - Produção: https://pncp.gov.br/api/pncp
    - Treinamento: https://treina.pncp.gov.br/api/pncp (se PNCP_API_ENV=treina)
    """
    import os
    env = (os.getenv("PNCP_API_ENV") or "").strip().lower()
    if env in {"treina", "training", "sandbox"}:
        return "https://treina.pncp.gov.br/api/pncp"
    return "https://pncp.gov.br/api/pncp"


def listar_documentos_compra(
    cnpj: str,
    ano: int,
    sequencial: int,
    *,
    timeout: float = 45.0,
) -> list[Dict[str, Any]]:
    """Lista documentos de uma contratação via API de integração do PNCP.

    Retorna uma lista normalizada: [{sequencial, url, tipo_id, tipo_nome, titulo, data_publicacao}].

    Observação: Pode exigir Authorization Bearer. Se PNCP_TOKEN estiver definido, inclui no header.
    """
    if httpx is None:
        return []
    base = _pncp_base_api().rstrip('/')
    url = f"{base}/v1/orgaos/{str(cnpj).strip()}/compras/{int(ano)}/{int(sequencial)}/arquivos"
    headers = {}
    try:
        import os
        tok = os.getenv("PNCP_TOKEN")
        if tok:
            headers["Authorization"] = f"Bearer {tok.strip()}"
    except Exception:
        pass
    try:
        r = httpx.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        data: Any = r.json()
    except Exception:
        return []
    docs: list[Dict[str, Any]] = []
    # Estruturas possíveis: { 'Documentos': [ {...} ] } ou lista simples
    items = None
    if isinstance(data, dict):
        items = data.get("Documentos") or data.get("documentos") or data.get("data")
    else:
        items = data
    if not isinstance(items, list):
        return []
    for it in items:
        if not isinstance(it, dict):
            continue
        docs.append({
            "sequencial": it.get("sequencialDocumento") or it.get("sequencial") or it.get("id"),
            "url": it.get("url") or it.get("link") or None,
            "tipo_id": it.get("tipoDocumentoId") or it.get("tipoId") or None,
            "tipo_nome": it.get("tipoDocumentoNome") or it.get("tipoNome") or None,
            "titulo": it.get("titulo") or it.get("title") or None,
            "data_publicacao": it.get("dataPublicacaoPncp") or it.get("dataPublicacao") or None,
        })
    return [d for d in docs if d.get("sequencial") is not None or d.get("url")]


def baixar_documento_por_sequencial(
    cnpj: str,
    ano: int,
    sequencial: int,
    seq_doc: int,
    *,
    dest_dir: Optional[str] = None,
    timeout: float = 60.0,
) -> Optional[str]:
    """Baixa um documento específico pelo sequencialDocumento.

    Retorna caminho do arquivo salvo (str) ou None.
    """
    if httpx is None:
        return None
    from pathlib import Path
    import os
    base = _pncp_base_api().rstrip('/')
    url = f"{base}/v1/orgaos/{str(cnpj).strip()}/compras/{int(ano)}/{int(sequencial)}/arquivos/{int(seq_doc)}"
    headers = {}
    tok = os.getenv("PNCP_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok.strip()}"
    try:
        with httpx.stream("GET", url, headers=headers, timeout=timeout) as resp:
            resp.raise_for_status()
            cd = resp.headers.get("content-disposition", "")
            fname = None
            # tenta extrair filename do header
            import re
            m = re.search(r'filename="?([^";]+)"?', cd)
            if m:
                fname = m.group(1)
            if not fname:
                # tenta por tipo
                ctype = (resp.headers.get("content-type") or "").lower()
                ext = ".pdf" if "pdf" in ctype else ".bin"
                fname = f"documento_{seq_doc}{ext}"
            base_dir = Path(dest_dir or (Path(__file__).resolve().parents[2] / 'tmp' / 'pncp_docs'))
            base_dir.mkdir(parents=True, exist_ok=True)
            out = base_dir / fname
            with open(out, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
            return str(out)
    except Exception:
        return None
