import asyncio
import os

import pytest

from backend.src.services.precos_praticados import (
    ComprasGovPrecoClient,
    consultar_material_precos,
)

CATMAT_EXAMPLE = 99830  # item amplamente utilizado (arma de fogo de pequeno porte)
RUN_ONLINE_TESTS = os.getenv("RUN_ONLINE_TESTS", "0").strip().lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    not RUN_ONLINE_TESTS,
    reason="Teste de integracao externo. Defina RUN_ONLINE_TESTS=1 para habilitar.",
)


def test_consultar_material_por_catmat_retorna_precos():
    async def runner() -> None:
        async with ComprasGovPrecoClient() as client:
            data = await client.consultar_material(CATMAT_EXAMPLE, tamanho_pagina=20)
        assert data.get("resultado"), "Esperava ao menos um registro de preco"
        for row in data["resultado"]:
            assert int(row.get("codigoItemCatalogo")) == CATMAT_EXAMPLE

    asyncio.run(runner())


def test_fluxo_busca_por_descricao_e_precos():
    async def runner() -> None:
        termo_busca = "arma de fogo"
        async with ComprasGovPrecoClient() as client:
            itens = await client.buscar_itens_por_descricao(termo_busca, tamanho_pagina=200, limit=5)
            assert itens, "Esperava encontrar itens no catalogo para o termo informado"
            codigo = itens[0].codigo_item
            precos = await consultar_material_precos(codigo, client=client, tamanho_pagina=20)
        assert precos, "Fluxo completo deveria retornar precos para o item filtrado"
        assert all(preco.codigo_item_catalogo == codigo for preco in precos)

    asyncio.run(runner())
