from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from .. import models, crud


def _clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()


def _extract_keywords(texto: str, min_len: int = 4) -> List[str]:
    texto = _clean_text(texto)
    # remove pontuação simples
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
        "aquisição",
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
    """Retorna licitações semelhantes no banco usando Jaccard de palavras do objeto."""
    base_kw = _extract_keywords(base.objeto_compra or "")
    if not base_kw:
        return []
    # busca um conjunto razoável de registros (ajuste conforme volume)
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
    """Tenta localizar valores adjudicados/contratados via endpoints públicos do PNCP.

    Heurística: usa o número de controle PNCP se disponível para consultar possíveis
    endpoints de contratos/itens. O PNCP publica endpoints sob /api/consulta/v1/ ...
    Como a estrutura pode variar, aqui tentamos alguns caminhos e coletamos valores numéricos
    que aparentem ser preço vencedor.
    """
    if not numero_controle_pncp:
        return []

    bases = [
        # hipotético endpoint de contratos filtrando por número de controle
        ("https://pncp.gov.br/api/consulta/v1/contratos", {"numeroControlePNCP": numero_controle_pncp}),
        # hipotético endpoint de resultados/itens (quando existir)
        ("https://pncp.gov.br/api/consulta/v1/contratacoes/itens", {"numeroControlePNCP": numero_controle_pncp}),
    ]
    precos: List[float] = []
    for url, params in bases:
        data = await _http_get_json(url, params=params)
        if not data:
            continue
        # Varre estrutura tentando encontrar campos de valor
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    kl = str(k).lower()
                    if isinstance(v, (int, float)) and any(x in kl for x in ["valor", "preco", "price"]):
                        try:
                            precos.append(float(v))
                        except Exception:
                            pass
                    elif isinstance(v, str):
                        # tenta parsear '12345,67' ou '12345.67'
                        if any(x in kl for x in ["valor", "preco", "price"]):
                            m = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})", v)
                            for s in m:
                                try:
                                    s2 = s.replace(".", "").replace(",", ".")
                                    precos.append(float(s2))
                                except Exception:
                                    pass
                    elif isinstance(v, (list, dict)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
    return precos


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
    """Lista preços unitários/total dos itens do contrato (quando disponíveis)."""
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


async def pesquisar_precos_vencedores_similares(
    db: Session, licitacao_id: int, top_k_similares: int = 20, fonte: str = "comprasgov"
) -> Dict[str, Any]:
    """Para uma licitação selecionada, pesquisa licitações semelhantes no banco e
    tenta obter preços vencedores via PNCP (com heurísticas) para consolidar estatísticas.
    """
    base = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not base:
        return {"error": "Licitação não encontrada"}

    similares = find_similares_no_banco(db, base, top_k=top_k_similares)
    all_prices: List[Tuple[int, float]] = []  # (licitacao_id, price)

    for li in similares:
        prices_li: List[float] = []
        # Fonte ComprasGov (preferencial)
        if fonte in ("comprasgov", "ambas"):
            # Monta uma query de objeto simples com palavras-chave da licitação similar
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


async def pesquisar_precos_por_item(
    db: Session,
    descricao: str,
    limit_ids: int = 30,
    fonte: str = "comprasgov",
) -> Dict[str, Any]:
    """Pesquisa preços por descrição de item, consultando fontes públicas (ComprasGov e/ou PNCP).

    - comprasgov: busca contratos pelo campo objeto e extrai preços de itens.
    - pncp: como heurística, busca licitações no banco cujo objeto contenha palavras da descrição e tenta extrair
      preços via APIs públicas do PNCP a partir do número de controle.
    """
    kws = _extract_keywords(descricao)
    query = " ".join(kws) if kws else (descricao or "").strip()

    all_prices: List[Tuple[str, float]] = []  # (fonte_tag, preco)
    considerados: Dict[str, int] = {}

    # Fonte ComprasGov
    if fonte in ("comprasgov", "ambas") and query:
        contrato_ids = await _compras_list_contratos_por_objeto(query, limit_ids=limit_ids)
        considerados["comprasgov_contratos"] = len(contrato_ids)
        for cid in contrato_ids:
            try:
                prices = await _compras_precos_itens_do_contrato(cid)
                for p in prices:
                    all_prices.append(("comprasgov", float(p)))
            except Exception:
                continue

    # Fonte PNCP (heurística baseada em licitações do DB)
    if fonte in ("pncp", "ambas") and kws:
        # Busca até 100 licitações locais cujo objeto contenha ao menos uma palavra-chave
        like_filters = [models.Licitacao.objeto_compra.ilike(f"%{kw}%") for kw in kws]
        q = db.query(models.Licitacao)
        # SQLAlchemy não tem OR direto sobre lista sem reduce, mas podemos encadear OR via string fallback
        from sqlalchemy import or_  # type: ignore
        q = q.filter(or_(*like_filters)).limit(100)
        lics = q.all()
        considerados["pncp_licitacoes"] = len(lics)
        for li in lics:
            try:
                prices = await _tenta_precos_pncp_por_numero_controle(li.numero_controle_pncp)
                for p in prices:
                    all_prices.append(("pncp", float(p)))
            except Exception:
                continue

    stats = _stats([p for _, p in all_prices])
    detalhes = [{"fonte": f, "preco": p} for f, p in all_prices[:1000]]
    return {
        "query": descricao,
        "fonte": fonte,
        "considerados": considerados,
        "precos_encontrados": len(all_prices),
        "stats": stats,
        "detalhes": detalhes,
    }
