from __future__ import annotations

import asyncio
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

BASE_URL = "https://dadosabertos.compras.gov.br"
CATALOGO_PATH = "/modulo-material/4_consultarItemMaterial"
MATERIAL_PRECO_PATH = "/modulo-pesquisa-preco/1_consultarMaterial"
MATERIAL_DETALHE_PATH = "/modulo-pesquisa-preco/2_consultarMaterialDetalhe"
SERVICO_PRECO_PATH = "/modulo-pesquisa-preco/3_consultarServico"
SERVICO_DETALHE_PATH = "/modulo-pesquisa-preco/4_consultarServicoDetalhe"


class PrecosPraticadosError(RuntimeError):
    """Erro padrão para falhas ao consultar os endpoints de preços praticados."""


@dataclass
class CatalogoItem:
    codigo_item: int
    descricao_item: str
    codigo_classe: Optional[int] = None
    nome_classe: Optional[str] = None
    raw: Dict[str, Any] | None = None


@dataclass
class MaterialPreco:
    codigo_item_catalogo: int
    id_compra: str
    preco_unitario: float
    quantidade: float
    uf: Optional[str]
    municipio: Optional[str]
    nome_orgao: Optional[str]
    raw: Dict[str, Any]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def _validate_page_size(value: int) -> int:
    if value < 10:
        return 10
    if value > 500:
        return 500
    return value


class ComprasGovPrecoClient:
    """Cliente assíncrono para a API de Preços Praticados do Compras.gov.br."""

    def __init__(self, *, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ComprasGovPrecoClient":
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:  # type: ignore[override]
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        try:
            response = await self._client.request(method, path, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrecosPraticadosError(f"Falha ao consultar {path}: {exc}") from exc
        data = response.json()
        if not isinstance(data, dict):
            raise PrecosPraticadosError(f"Resposta inesperada em {path}")
        return data

    async def consultar_material(self, codigo_item_catalogo: int, *, pagina: int = 1, tamanho_pagina: int = 50, **filtros: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pagina": pagina,
            "tamanhoPagina": _validate_page_size(tamanho_pagina),
            "codigoItemCatalogo": int(codigo_item_catalogo),
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return await self._request("GET", MATERIAL_PRECO_PATH, params=params)

    async def consultar_material_detalhe(self, id_compra: str, *, pagina: int = 1, tamanho_pagina: int = 50, **filtros: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pagina": pagina,
            "tamanhoPagina": _validate_page_size(tamanho_pagina),
            "idCompra": id_compra,
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return await self._request("GET", MATERIAL_DETALHE_PATH, params=params)

    async def consultar_servico(self, codigo_item_catalogo: int, *, pagina: int = 1, tamanho_pagina: int = 50, **filtros: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pagina": pagina,
            "tamanhoPagina": _validate_page_size(tamanho_pagina),
            "codigoItemCatalogo": int(codigo_item_catalogo),
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return await self._request("GET", SERVICO_PRECO_PATH, params=params)

    async def consultar_servico_detalhe(self, id_compra: str, *, pagina: int = 1, tamanho_pagina: int = 50, **filtros: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pagina": pagina,
            "tamanhoPagina": _validate_page_size(tamanho_pagina),
            "idCompra": id_compra,
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return await self._request("GET", SERVICO_DETALHE_PATH, params=params)

    async def listar_catalogo(self, *, pagina: int = 1, tamanho_pagina: int = 100, **filtros: Any) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "pagina": pagina,
            "tamanhoPagina": _validate_page_size(tamanho_pagina),
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return await self._request("GET", CATALOGO_PATH, params=params)

    async def buscar_itens_por_descricao(
        self,
        termo: str,
        *,
        pagina: int = 1,
        tamanho_pagina: int = 200,
        limit: Optional[int] = None,
        filtros_catalogo: Optional[Dict[str, Any]] = None,
    ) -> List[CatalogoItem]:
        if not termo:
            return []
        filtros = dict(filtros_catalogo or {})
        data = await self.listar_catalogo(pagina=pagina, tamanho_pagina=tamanho_pagina, **filtros)
        resultado = data.get("resultado") or []
        termo_norm = _normalize_text(termo)
        itens: List[CatalogoItem] = []
        for row in resultado:
            descricao = str(row.get("descricaoItem") or "")
            if termo_norm in _normalize_text(descricao):
                item = CatalogoItem(
                    codigo_item=int(row.get("codigoItem")),
                    descricao_item=descricao,
                    codigo_classe=row.get("codigoClasse"),
                    nome_classe=row.get("nomeClasse"),
                    raw=row,
                )
                itens.append(item)
                if limit is not None and len(itens) >= limit:
                    break
        return itens

    @staticmethod
    def extrair_precos(data: Dict[str, Any]) -> List[MaterialPreco]:
        resultado = data.get("resultado") or []
        precos: List[MaterialPreco] = []
        for row in resultado:
            try:
                preco = MaterialPreco(
                    codigo_item_catalogo=int(row.get("codigoItemCatalogo")),
                    id_compra=str(row.get("idCompra")),
                    preco_unitario=float(row.get("precoUnitario")),
                    quantidade=float(row.get("quantidade")),
                    uf=row.get("estado"),
                    municipio=row.get("municipio"),
                    nome_orgao=row.get("nomeOrgao"),
                    raw=row,
                )
                precos.append(preco)
            except (TypeError, ValueError):
                continue
        return precos


async def consultar_material_precos(
    codigo_item_catalogo: int,
    *,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    client: Optional[ComprasGovPrecoClient] = None,
    **filtros: Any,
) -> List[MaterialPreco]:
    own_client = client is None
    if own_client:
        client = ComprasGovPrecoClient()
    assert client is not None
    try:
        data = await client.consultar_material(
            codigo_item_catalogo,
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
            **filtros,
        )
        return client.extrair_precos(data)
    finally:
        if own_client:
            await client.aclose()

