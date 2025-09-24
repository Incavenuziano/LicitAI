import json
from typing import Optional, List, Dict, Any
import httpx
from charset_normalizer import from_bytes as cn_from_bytes
from datetime import datetime, timedelta

def _to_yyyymmdd(value):
    """Normaliza datas para o formato exigido pela API (yyyyMMdd)."""
    if not value:
        return None
    txt = str(value).strip()
    if len(txt) == 8 and txt.isdigit():
        return txt
    try:
        from datetime import datetime as _dt
        return _dt.strptime(txt, "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        return txt


def consultar_licitacoes_publicadas(
    codigo_modalidade: Optional[int] = 6,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    uf: Optional[str] = None,
    pagina: int = 1,
    tamanho_pagina: int = 10,
) -> str:
    """Consulta licitacoes publicadas no PNCP com filtros opcionais."""
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    params: dict[str, object] = {
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if codigo_modalidade is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade
    di = _to_yyyymmdd(data_inicial)
    df = _to_yyyymmdd(data_final)
    if di:
        params["dataInicial"] = di
    if df:
        params["dataFinal"] = df
    if uf:
        params["uf"] = uf

    try:
        print(f"--- Executando busca PNCP com parametros: {params} ---")
        response = httpx.get(base_url, params=params, timeout=45.0)
        response.raise_for_status()

        raw_content = response.content
        decoded_str = str(cn_from_bytes(raw_content).best())
        payload = json.loads(decoded_str)

        print("--- Consulta ao PNCP bem-sucedida ---")
        if isinstance(payload, dict) and payload.get("data"):
            return json.dumps(payload["data"], indent=2, ensure_ascii=False)
        return json.dumps({"mensagem": "Nenhuma licitacao encontrada para os criterios fornecidos."}, indent=2, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_details = e.response.content.decode("utf-8", errors="replace")
        snippet = error_details[:500]
        if len(error_details) > 500:
            snippet += '... [truncado]'
        print(f"--- Erro na API PNCP: {e.response.status_code} - {snippet} ---")
        return json.dumps({
            "erro": "Falha ao consultar a API do PNCP.",
            "status_code": e.response.status_code,
            "detalhes": error_details,
        }, ensure_ascii=False)

    except Exception as e:
        raw_snippet = ''
        if 'response' in locals():
            try:
                raw_text = response.text
                if raw_text:
                    raw_snippet = raw_text[:500]
                    if len(raw_text) > 500:
                        raw_snippet += '... [truncado]'
            except Exception:
                raw_snippet = ''
        if raw_snippet:
            print(f"--- Corpo bruto retornado (parcial): {raw_snippet} ---")
        print(f"--- Erro inesperado: {e} ---")
        return json.dumps({"erro": "Um erro inesperado ocorreu.", "detalhes": str(e)}, ensure_ascii=False)



if __name__ == "__main__":
    print("Iniciando teste de busca de licitações...")
    print("-----------------------------------------")
    resultado_json = consultar_licitacoes_publicadas(codigo_modalidade=6, tamanho_pagina=5)
    print("\n--- Resultado da Consulta ---")
    try:
        resultado_formatado = json.loads(resultado_json)
        print(json.dumps(resultado_formatado, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(resultado_json)


# ---------------- OPORTUNIDADES ATIVAS (Propostas em Aberto) -----------------

def consultar_oportunidades_ativas(
    codigo_modalidade: Optional[int] = None,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    uf: Optional[str] = None,
    pagina: int = 1,
    tamanho_pagina: int = 50,
) -> str:
    """Consulta oportunidades ativas (propostas em aberto) no PNCP."""
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"

    params: Dict[str, object] = {
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if codigo_modalidade is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade
    di = _to_yyyymmdd(data_inicial)
    df = _to_yyyymmdd(data_final)
    if di:
        params["dataInicial"] = di
    if df:
        params["dataFinal"] = df
    if uf:
        params["uf"] = uf

    try:
        print(f"--- Executando busca PNCP (propostas em aberto) com parametros: {params} ---")
        response = httpx.get(base_url, params=params, timeout=45.0)
        response.raise_for_status()
        raw_content = response.content
        decoded_str = str(cn_from_bytes(raw_content).best())
        payload = json.loads(decoded_str)
        if isinstance(payload, dict) and payload.get("data") is not None:
            return json.dumps(payload["data"], indent=2, ensure_ascii=False)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_details = e.response.content.decode("utf-8", errors="replace")
        snippet = error_details[:500]
        if len(error_details) > 500:
            snippet += '... [truncado]'
        print(f"--- Erro na API PNCP (propostas): {e.response.status_code} - {snippet} ---")
        return json.dumps({
            "erro": "Falha ao consultar propostas em aberto (PNCP).",
            "status_code": e.response.status_code,
            "detalhes": error_details,
        }, ensure_ascii=False)

    except Exception as e:
        raw_snippet = ''
        if 'response' in locals():
            try:
                raw_text = response.text
                if raw_text:
                    raw_snippet = raw_text[:500]
                    if len(raw_text) > 500:
                        raw_snippet += '... [truncado]'
            except Exception:
                raw_snippet = ''
        if raw_snippet:
            print(f"--- Corpo bruto retornado (parcial) (propostas): {raw_snippet} ---")
        print(f"--- Erro inesperado (propostas): {e} ---")
        return json.dumps({"erro": "Um erro inesperado ocorreu.", "detalhes": str(e)}, ensure_ascii=False)



def buscar_oportunidades_ativas_amplo(
    *,
    total_days: int = 14,
    step_days: int = 7,
    ufs: Optional[List[str]] = None,
    modal_codes: Optional[List[int]] = None,
    page_limit: int = 10,
    tamanho_pagina: int = 30,
    data_fim_ref: Optional[str] = None,
) -> str:
    """
    Varredura ampla de oportunidades ativas (propostas em aberto), paginando por blocos de data e UF.

    - total_days: janela total (em dias) a cobrir. Se data_fim_ref não informado, usa hoje.
    - step_days: salto por bloco (em dias) para segmentar a busca e respeitar limites da API.
    - ufs: lista de UFs a considerar. Se None, usa UFs brasileiras padrão.
    - modal_codes: lista de códigos de modalidade a tentar. Se None, usa [1..20].
    - page_limit: limite de páginas a consultar por combinação (bloco/UF/modalidade).
    - tamanho_pagina: tamanho de página na API (máximo conforme documentação PNCP).
    - data_fim_ref: data final base no formato YYYY-MM-DD; se None, hoje.

    Retorna string JSON (lista consolidada, sem duplicatas por `numeroControlePNCP`).
    """
    import datetime as _dt

    if ufs is None:
        ufs = [
            "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
        ]
    # Se não informado, não filtra por modalidade (evita 422 para códigos inválidos)
    codes_iter: List[Optional[int]] = modal_codes if modal_codes else [None]

    # Base temporal
    if data_fim_ref:
        try:
            # aceita YYYY-MM-DD ou YYYYMMDD
            fmt = "%Y-%m-%d" if "-" in str(data_fim_ref) else "%Y%m%d"
            base_dt = _dt.datetime.strptime(str(data_fim_ref), fmt)
        except Exception:
            base_dt = _dt.datetime.utcnow()
    else:
        base_dt = _dt.datetime.utcnow()

    start_dt = base_dt - _dt.timedelta(days=total_days)

    # Gera blocos de datas [cur, cur+step] no formato yyyyMMdd
    blocks: List[tuple[str, str]] = []
    cur = start_dt
    while cur < base_dt:
        nxt = min(cur + _dt.timedelta(days=step_days), base_dt)
        blocks.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + _dt.timedelta(days=1)

    seen: set[str] = set()
    results: List[Dict[str, Any]] = []
    blocks_ok = 0
    blocks_timeout = 0
    pages_ok = 0
    pages_timeout = 0

    for d_ini, d_fim in blocks:
        for uf in ufs:
            for cod in codes_iter:
                for page in range(1, page_limit + 1):
                    payload_str = consultar_oportunidades_ativas(
                        codigo_modalidade=cod,
                        data_inicial=d_ini,
                        data_final=d_fim,
                        uf=uf,
                        pagina=page,
                        tamanho_pagina=tamanho_pagina,
                    )
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        pages_timeout += 1
                        continue
                    rows = payload
                    if isinstance(payload, dict) and payload.get("data") is not None:
                        rows = payload.get("data")
                    # Ignora respostas de erro conhecidas (ex.: 422 por modalidade inválida)
                    if isinstance(payload, dict) and str(payload.get("status_code")) == "422":
                        break
                    if isinstance(payload, dict) and payload.get("erro") == "timeout":
                        pages_timeout += 1
                        continue
                    if not isinstance(rows, list) or not rows:
                        break
                    pages_ok += 1

                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        key = str(row.get("numeroControlePNCP") or row.get("id") or row.get("linkSistemaOrigem") or "")
                        if not key:
                            # inclui mesmo sem chave quando necessário
                            results.append(row)
                            continue
                        if key in seen:
                            continue
                        seen.add(key)
                        results.append(row)

    return json.dumps({"data": results, "meta": {"pages_ok": pages_ok, "pages_timeout": pages_timeout}}, indent=2, ensure_ascii=False)


# ---------------- Descoberta de Modalidades (heurística) -----------------

def descobrir_modalidades_publicacao(
    *,
    data_fim: Optional[str] = None,
    janela_dias: int = 30,
    ufs_amostra: Optional[List[str]] = None,
    codigos_tentar: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Descobre (id,nome) de modalidades válidas consultando publicações recentes.

    Estratégia: para uma janela recente e um conjunto pequeno de UFs, tenta códigos
    de 1..30 e coleta (modalidadeId, modalidadeNome) quando houver resposta com dados.
    """
    if httpx is None:
        return []
    if ufs_amostra is None:
        ufs_amostra = ["DF", "SP", "RJ", "MG", "BA", "RS"]
    if codigos_tentar is None:
        codigos_tentar = list(range(1, 31))

    # datas yyyyMMdd
    try:
        if data_fim:
            base = datetime.strptime(data_fim.replace("-", ""), "%Y%m%d")
        else:
            base = datetime.utcnow()
    except Exception:
        base = datetime.utcnow()
    d_ini = (base - timedelta(days=janela_dias)).strftime("%Y%m%d")
    d_fim = base.strftime("%Y%m%d")

    found: Dict[int, str] = {}
    for uf in ufs_amostra:
        for cod in codigos_tentar:
            url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
            params = {
                "pagina": 1,
                "tamanhoPagina": 10,
                "dataInicial": d_ini,
                "dataFinal": d_fim,
                "codigoModalidadeContratacao": cod,
                "uf": uf,
            }
            try:
                r = httpx.get(url, params=params, timeout=20.0)
                if r.status_code != 200:
                    continue
                payload = r.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                if not data or not isinstance(data, list):
                    continue
                for row in data:
                    try:
                        mid = int(row.get("modalidadeId"))
                        mname = str(row.get("modalidadeNome") or "").strip()
                        if mid and mname and mid not in found:
                            found[mid] = mname
                    except Exception:
                        continue
            except Exception:
                continue
    return [{"code": k, "label": v} for k, v in sorted(found.items(), key=lambda x: x[0])]
