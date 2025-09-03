import pytest

from backend.src.analysis_service import (
    _extract_items_from_table_rows,
    _extract_items_from_text,
)


def test_extract_items_from_table_rows_basic():
    # Header + two rows as a typical PDF table extraction
    rows = [
        [
            "Item",
            "Descrição",
            "Quantidade",
            "Unidade",
            "Valor Unitário",
            "Valor Total",
            "Marca",
            "Modelo",
        ],
        [
            "1",
            "Cadeira giratória",
            "10",
            "UN",
            "R$ 150,00",
            "R$ 1.500,00",
            "MarcaX",
            "ModeloY",
        ],
        [
            "2",
            "Mesa retangular",
            "5",
            "UN",
            "R$ 300,00",
            "R$ 1.500,00",
            "MarcaZ",
            "ModeloK",
        ],
    ]

    items = _extract_items_from_table_rows(rows)
    assert len(items) == 2

    i1 = items[0]
    assert i1["item"] == 1
    assert "cadeira" in (i1["descricao"] or "").lower()
    assert i1["quantidade"] == 10.0
    assert (i1["unidade"] or "").upper() == "UN"
    assert i1["valor_unitario"] == 150.0
    assert i1["valor_total"] == 1500.0
    assert i1["marca"] == "MarcaX"
    assert i1["modelo"] == "ModeloY"

    i2 = items[1]
    assert i2["item"] == 2
    assert i2["quantidade"] == 5.0
    assert i2["valor_unitario"] == 300.0
    assert i2["valor_total"] == 1500.0


def test_extract_items_from_text_fallback():
    texto = "\n".join(
        [
            "Item 1 - Cadeira giratória com braço",
            "Quantidade: 10",
            "Unidade: UN",
            "Valor Unitário: R$ 150,00",
            "Valor Total: R$ 1.500,00",
            "Marca: MarcaX",
            "Modelo: ModeloY",
            "",
            "Item 2: Mesa retangular 120x60",
            "Quantidade: 5",
            "Unidade: UN",
            "Valor Unitario: R$ 300,00",
            "Valor Total: R$ 1.500,00",
        ]
    )

    items = _extract_items_from_text(texto)
    assert len(items) >= 2

    j1 = items[0]
    assert j1["item"] == 1
    assert "cadeira" in (j1["descricao"] or "").lower()
    assert j1["quantidade"] == 10.0
    assert (j1["unidade"] or "").upper() == "UN"
    assert j1["valor_unitario"] == 150.0
    assert j1["valor_total"] == 1500.0
    assert j1["marca"] == "MarcaX"
    assert j1["modelo"] == "ModeloY"

    j2 = items[1]
    assert j2["item"] == 2
    assert j2["quantidade"] == 5.0
    assert j2["valor_unitario"] == 300.0
    assert j2["valor_total"] == 1500.0

