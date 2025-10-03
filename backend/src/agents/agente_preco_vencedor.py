from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from .. import models, crud
from ..services.pncp_pipeline import PrecoDocumento, coletar_precos_normalizados
from ..services.precos_praticados import ComprasGovPrecoClient, consultar_material_precos


def _clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()


def _extract_keywords(texto: str, min_len: int = 4) -> List[str]:
    texto = _clean_text(texto)
    # remove pontuaÃ§Ã£o simples
    texto = re.sub(r"[.,;:/\\()[\]{}\"']+", " ", texto)
    toks = [t for t in texto.split() if len(t) >= min_len]
    # remove termos muito comuns
    stop = {
        "de",
        "da",
        "do",
        "para",
        "com",
        "em",
        "e",
        "ou",
        "declaracao",
        "servico",
        "servicos",
        "material",
        "aquisiÃ§Ã£o",
        "aquisicao",
        "compra",
        "objeto",
        "fornecimento",
    }
    return [t for t in toks if t not in stop]


def _similarity(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    uni = len(sa | sb)
    return inter / uni


def find_similares_no_banco(
    db: Session, base: models.Licitacao, top_k: int = 20
) -> List[models.Licitacao]:
    """Retorna licitaÃ§Ãµes semelhantes no banco usando Jaccard de palavras do objeto."""
    base_kw = _extract_keywords(base.objeto_compra or "")
    if not base_kw:
        return []
    # busca um conjunto razoÃ¡vel de registros (ajuste conforme volume)
    candidatos = (
        db.query(models.Licitacao)
        .filter(models.Licitacao.id != base.id)
        .limit(500)
        .all()
    )
    scored: List[Tuple[float, models.Licitacao]] = []
    for c in candidatos:
        sim = _similarity(base_kw, _extract_keywords(c.objeto_compra or ""))
        if sim > 0:
            scored.append((sim, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


async def _http_get_json(url: str, params: Dict[str, Any] | None = None, timeout: float = 15.0) -> Optional[Dict[str, Any] | List[Any]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def _tenta_precos_pncp_por_numero_controle(
    numero_controle_pncp: Optional[str],
) -> List[float]:
    """Busca valores no PNCP combinando pipeline de anexos e heuristicas JSON legadas."""
    if not numero_controle_pncp:
        return []

    def _dedupe(values: List[float]) -> List[float]:
        vistos = set()
        resultado: List[float] = []
        for valor in values:
            try:
                num = float(valor)
            except Exception:
                continue
            chave = round(num, 2)
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(num)
        return resultado

    coletados: List[float] = []

    bases = [
        ("https://pncp.gov.br/api/consulta/v1/contratos", {"numeroControlePNCP": numero_controle_pncp}),
        ("https://pncp.gov.br/api/consulta/v1/contratacoes/itens", {"numeroControlePNCP": numero_controle_pncp}),
    ]
    for url, params in bases:
        data = await _http_get_json(url, params=params)
        if not data:
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    kl = str(k).lower()
                    if isinstance(v, (int, float)) and any(x in kl for x in ["valor", "preco", "price"]):
                        try:
                            coletados.append(float(v))
                        except Exception:
                            pass
                    elif isinstance(v, str):
                        if any(x in kl for x in ["valor", "preco", "price"]):
                            m = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})", v)
                            for s in m:
                                try:
                                    s2 = s.replace(".", "").replace(",", ".")
                                    coletados.append(float(s2))
                                except Exception:
                                    pass
                    elif isinstance(v, (list, dict)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

    try:
        pipeline_docs: List[PrecoDocumento] = await coletar_precos_normalizados(numero_controle_pncp)
    except Exception:
        pipeline_docs = []
    else:
        for doc in pipeline_docs:
            if isinstance(doc.valor, (int, float)):
                coletados.append(float(doc.valor))

    return _dedupe(coletados)
def _stats(nums: List[float]) -> Dict[str, Any]:
    if not nums:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    nums2 = sorted(nums)
    n = len(nums2)
    total = sum(nums2)
    if n % 2 == 1:
        med = nums2[n // 2]
    else:
        med = (nums2[n // 2 - 1] + nums2[n // 2]) / 2.0
    return {
        "count": n,
        "min": nums2[0],
        "max": nums2[-1],
        "mean": total / n,
        "median": med,
    }
async def _compras_list_contratos_por_objeto(objeto_query: str, limit_ids: int = 40) -> List[int]:
    """Consulta contratos na API ComprasGov filtrando por 'objeto'. Retorna IDs de contratos.

    Doc base: https://api.compras.dados.gov.br/openapi.yaml
    Path: /comprasContratos/v1/contratos?objeto=...
    """
    ids: List[int] = []
    try:
        params = {"objeto": objeto_query, "offset": 0}
        data = await _http_get_json("https://compras.dados.gov.br/comprasContratos/v1/contratos", params=params)
        # A API normalmente retorna uma lista de dicts ou um objeto com 'data'.
        rows: List[Dict[str, Any]] = []
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            # tenta chave 'data' ou similar
            maybe = data.get("data")
            if isinstance(maybe, list):
                rows = [r for r in maybe if isinstance(r, dict)]
        for r in rows:
            cid = r.get("id")
            if isinstance(cid, int):
                ids.append(cid)
            if len(ids) >= limit_ids:
                break
    except Exception:
        pass
    return ids


async def _compras_precos_itens_do_contrato(contrato_id: int) -> List[float]:
    """Lista preÃ§os unitÃ¡rios/total dos itens do contrato (quando disponÃ­veis)."""
    url = f"https://compras.dados.gov.br/comprasContratos/doc/contrato/{contrato_id}/itens_compras_contratos"
    prices: List[float] = []
    data = await _http_get_json(url)
    rows: List[Dict[str, Any]] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        maybe = data.get("data")
        if isinstance(maybe, list):
            rows = [r for r in maybe if isinstance(r, dict)]
    for it in rows:
        vu = it.get("valor_unitario")
        vt = it.get("valor_total")
        try:
            if isinstance(vu, (int, float)) and vu > 0:
                prices.append(float(vu))
        except Exception:
            pass
        try:
            if isinstance(vt, (int, float)) and vt > 0 and isinstance(it.get("quantidade"), (int, float)) and it.get("quantidade"):
                q = float(it.get("quantidade"))
                if q > 0:
                    prices.append(float(vt) / q)
        except Exception:
            pass
    return prices


async def _compras_obter_contrato_info(contrato_id: int) -> Optional[Dict[str, Any]]:
    """ObtÃ©m metadados de um contrato: datas (assinatura, vigÃªncia), Ã³rgÃ£o, etc.

    Endpoint esperado: https://compras.dados.gov.br/comprasContratos/doc/contrato/{id}
    """
    url = f"https://compras.dados.gov.br/comprasContratos/doc/contrato/{contrato_id}"
    data = await _http_get_json(url)
    if isinstance(data, dict):
        return data
    return None


async def serie_comprasgov_por_descricao(descricao: str, limit_ids: int = 30) -> List[Dict[str, Any]]:
    """Gera sÃ©rie (date,value,fonte,contrato_id) a partir de contratos do ComprasGov por termo do objeto.

    - Data usada: data de assinatura do contrato (aproximaÃ§Ã£o)
    - Valor: preÃ§os unitÃ¡rios derivados dos itens do contrato
    """
    ids = await _compras_list_contratos_por_objeto(descricao, limit_ids=limit_ids)
    out: List[Dict[str, Any]] = []
    for cid in ids:
        try:
            meta = await _compras_obter_contrato_info(cid)
            # heurÃ­stica: procurar campo de data (assinatura/vigÃªncia)
            date_str = None
            if isinstance(meta, dict):
                for k, v in meta.items():
                    kl = str(k).lower()
                    if isinstance(v, str) and any(t in kl for t in ["assin", "vigenc", "data"]):
                        date_str = v
                        break
            # normalizar data para YYYY-MM-DD quando possÃ­vel
            norm_date = None
            if date_str:
                try:
                    from datetime import datetime as _dt
                    # tentar iso, yyyy-mm-dd, dd/mm/yyyy
                    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
                        try:
                            norm_date = _dt.strptime(date_str[:19], fmt).strftime("%Y-%m-%d")
                            break
                        except Exception:
                            continue
                except Exception:
                    norm_date = None
            prices = await _compras_precos_itens_do_contrato(cid)
            for p in prices:
                out.append({
                    "date": norm_date or None,
                    "value": float(p),
                    "fonte": "comprasgov",
                    "contrato_id": cid,
                })
        except Exception:
            continue
    # filtra entradas sem valor
    return [x for x in out if isinstance(x.get("value"), (int, float))]


async def _pncp_busca_publicacoes(
    *,
    data_inicial: str,
    data_final: str,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    uf: Optional[str] = None,
    codigo_modalidade: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Consulta PNCP publicaÃ§oes no intervalo informado.

    Endpoint: https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
    Requer dataInicial/dataFinal (yyyyMMdd)
    """
    params: Dict[str, Any] = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if uf:
        params["uf"] = uf
    if codigo_modalidade is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade
    try:
        r = httpx.get("https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao", params=params, timeout=45.0)
        r.raise_for_status()
        return r.json()  # type: ignore[return-value]
    except Exception:
        return None


async def serie_pncp_por_descricao(
    descricao: str,
    *,
    total_days: int = 180,
    step_days: int = 30,
    uf: Optional[str] = None,
    codigo_modalidade: Optional[int] = None,
    page_limit: int = 10,
    tamanho_pagina: int = 50,
) -> List[Dict[str, Any]]:
    """Gera sÃ©rie (date,value,fonte,numeroControlePNCP) a partir de publicaÃ§Ãµes do PNCP por termo do objeto.

    - Data usada: dataEncerramentoProposta (preferida) ou dataPublicacaoPncp
    - Valor: valorTotalEstimado (aproximaÃ§Ã£o do ticket da compra)
    """
    from datetime import datetime, timedelta

    base = datetime.utcnow()
    start = base - timedelta(days=total_days)

    # blocos yyyyMMdd
    blocks: List[tuple[str, str]] = []
    cur = start
    while cur <= base:
        nxt = min(cur + timedelta(days=step_days), base)
        blocks.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + timedelta(days=1)

    want = descricao.lower()
    out: List[Dict[str, Any]] = []

    for d_ini, d_fim in blocks:
        for page in range(1, page_limit + 1):
            payload = await _pncp_busca_publicacoes(
                data_inicial=d_ini,
                data_final=d_fim,
                pagina=page,
                tamanho_pagina=tamanho_pagina,
                uf=uf,
                codigo_modalidade=codigo_modalidade,
            )
            data_rows = payload.get("data") if isinstance(payload, dict) else None  # type: ignore[union-attr]
            if not data_rows:
                break
            for row in data_rows:
                if not isinstance(row, dict):
                    continue
                try:
                    obj = str(row.get("objetoCompra") or "").lower()
                except Exception:
                    obj = ""
                if want and (want not in obj):
                    continue

                # Data preferencial de encerramento de propostas; fallback dataPublicacaoPncp
                date_raw = row.get("dataEncerramentoProposta") or row.get("dataPublicacaoPncp")
                date_norm = None
                if isinstance(date_raw, str) and date_raw:
                    try:
                        # data vem no formato ISO yyyy-MM-ddTHH:MM:SS
                        date_norm = date_raw[:10]
                    except Exception:
                        date_norm = None

                # Valor estimado
                val = row.get("valorTotalEstimado")
                try:
                    val_f = float(val) if isinstance(val, (int, float)) else None
                except Exception:
                    val_f = None
                if val_f is None:
                    continue

                out.append({
                    "date": date_norm,
                    "value": float(val_f),
                    "fonte": "pncp",
                    "numeroControlePNCP": row.get("numeroControlePNCP"),
                })
    # ordenar e filtrar
    out = [p for p in out if p.get("date") and isinstance(p.get("value"), (int, float))]
    out.sort(key=lambda x: x.get("date"))
    return out


async def pesquisar_precos_vencedores_similares(
    db: Session, licitacao_id: int, top_k_similares: int = 20, fonte: str = "comprasgov"
) -> Dict[str, Any]:
    """Para uma licitaÃ§Ã£o selecionada, pesquisa licitaÃ§Ãµes semelhantes no banco e
    tenta obter preÃ§os vencedores via PNCP (com heurÃ­sticas) para consolidar estatÃ­sticas.
    """
    base = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not base:
        return {"error": "LicitaÃ§Ã£o nÃ£o encontrada"}

    similares = find_similares_no_banco(db, base, top_k=top_k_similares)
    all_prices: List[Tuple[int, float]] = []  # (licitacao_id, price)

    for li in similares:
        prices_li: List[float] = []
        # Fonte ComprasGov (preferencial)
        if fonte in ("comprasgov", "ambas"):
            # Monta uma query de objeto simples com palavras-chave da licitaÃ§Ã£o similar
            kws = _extract_keywords(li.objeto_compra or "")[:5]
            if kws:
                query = " ".join(kws)
                contrato_ids = await _compras_list_contratos_por_objeto(query, limit_ids=15)
                for cid in contrato_ids:
                    prices_li.extend(await _compras_precos_itens_do_contrato(cid))
        # Fonte PNCP (complementar)
        if (not prices_li) and fonte in ("pncp", "ambas"):
            prices_li.extend(await _tenta_precos_pncp_por_numero_controle(li.numero_controle_pncp))

        for p in prices_li:
            all_prices.append((li.id, p))

    stats = _stats([p for _, p in all_prices])
    detalhes = [
        {"licitacao_id": lid, "preco": p}
        for (lid, p) in all_prices
    ]
    return {
        "base": {
            "id": base.id,
            "numero_controle_pncp": base.numero_controle_pncp,
            "objeto_compra": base.objeto_compra,
        },
        "similares_considerados": len(similares),
        "precos_encontrados": len(all_prices),
        "stats": stats,
        "detalhes": detalhes,
    }




async def _buscar_precos_praticados(
    descricao: str,
    *,
    limit_itens: int = 5,
    limit_precos: int = 50,
) -> List[Dict[str, Any]]:
    termo = (descricao or "").strip()
    if not termo:
        return []

    try:
        catmat_candidates = {int(match) for match in re.findall(r"\d{5,}", termo)}
    except ValueError:
        catmat_candidates = set()

    resultados: List[Dict[str, Any]] = []
    processados: set[int] = set()

    try:
        async with ComprasGovPrecoClient() as client:
            for codigo in catmat_candidates:
                processados.add(codigo)
                registros = await consultar_material_precos(codigo, client=client, tamanho_pagina=limit_precos)
                for registro in registros:
                    resultados.append({
                        "fonte": "precos_praticados",
                        "preco": float(registro.preco_unitario),
                        "catmat": codigo,
                        "descricao_item": registro.raw.get("descricaoItem") if registro.raw else None,
                        "uf": registro.uf,
                        "municipio": registro.municipio,
                        "orgao": registro.nome_orgao,
                        "quantidade": registro.quantidade,
                        "id_compra": registro.id_compra,
                    })

            itens = await client.buscar_itens_por_descricao(
                termo, tamanho_pagina=200, limit=limit_itens
            )
            for item in itens:
                codigo = item.codigo_item
                if codigo in processados:
                    continue
                processados.add(codigo)
                registros = await consultar_material_precos(codigo, client=client, tamanho_pagina=limit_precos)
                for registro in registros:
                    resultados.append({
                        "fonte": "precos_praticados",
                        "preco": float(registro.preco_unitario),
                        "catmat": codigo,
                        "descricao_item": item.descricao_item,
                        "uf": registro.uf,
                        "municipio": registro.municipio,
                        "orgao": registro.nome_orgao,
                        "quantidade": registro.quantidade,
                        "id_compra": registro.id_compra,
                    })
    except Exception:
        return resultados

    return resultados


async def pesquisar_precos_por_item(
    db: Session,
    descricao: str,
    limit_ids: int = 30,
    fonte: str = "comprasgov",
) -> Dict[str, Any]:
    """Pesquisa preÃ§os por descriÃ§Ã£o de item em vÃ¡rias fontes pÃºblicas."""
    kws = _extract_keywords(descricao)
    query = " ".join(kws) if kws else (descricao or "").strip()

    valores: List[float] = []
    detalhes: List[Dict[str, Any]] = []
    considerados: Dict[str, int] = {}

    def adicionar_preco(fonte_tag: str, valor: Any, extra: Optional[Dict[str, Any]] = None) -> None:
        try:
            num = float(valor)
        except (TypeError, ValueError):
            return
        valores.append(num)
        registro = {"fonte": fonte_tag, "preco": num}
        if extra:
            registro.update(extra)
        detalhes.append(registro)

    if fonte in ("comprasgov", "ambas", "todas") and query:
        contrato_ids = await _compras_list_contratos_por_objeto(query, limit_ids=limit_ids)
        considerados["comprasgov_contratos"] = len(contrato_ids)
        for cid in contrato_ids:
            try:
                prices = await _compras_precos_itens_do_contrato(cid)
                for p in prices:
                    adicionar_preco("comprasgov", p, {"contrato_id": cid})
            except Exception:
                continue

    if fonte in ("pncp", "ambas", "todas") and kws:
        from sqlalchemy import or_  # type: ignore

        like_filters = [models.Licitacao.objeto_compra.ilike(f"%{kw}%") for kw in kws]
        q = db.query(models.Licitacao).filter(or_(*like_filters)).limit(100)
        lics = q.all()
        considerados["pncp_licitacoes"] = len(lics)
        for li in lics:
            try:
                prices = await _tenta_precos_pncp_por_numero_controle(li.numero_controle_pncp)
                for p in prices:
                    adicionar_preco("pncp", p, {"licitacao_id": li.id})
            except Exception:
                continue

    if fonte in ("precos_praticados", "todas"):
        praticados = await _buscar_precos_praticados(descricao)
        considerados["precos_praticados_itens"] = len({item.get("catmat") for item in praticados if item.get("catmat")})
        considerados["precos_praticados_precos"] = len(praticados)
        for item in praticados:
            extra = {k: v for k, v in item.items() if k not in {"fonte", "preco"}}
            adicionar_preco("precos_praticados", item.get("preco"), extra)

    stats = _stats(valores)
    return {
        "query": descricao,
        "fonte": fonte,
        "considerados": considerados,
        "precos_encontrados": len(valores),
        "stats": stats,
        "detalhes": detalhes[:1000],
    }

