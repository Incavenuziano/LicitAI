from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from backend.main import app, get_db
from backend.models import Base, Licitacao

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def populate_db(db_session):
    licitacao_1 = Licitacao(
        id=1,
        numero_controle_pncp="11111",
        objeto_compra="Aquisicao de 100 unidades de cadeira de escritorio ergonomica",
        valor_total_estimado=50000.00,
    )
    licitacao_2 = Licitacao(
        id=2,
        numero_controle_pncp="22222",
        objeto_compra="Contratacao de servico de limpeza e conservacao predial",
        valor_total_estimado=120000.00,
    )
    licitacao_3 = Licitacao(
        id=3,
        numero_controle_pncp="33333",
        objeto_compra="Compra de material de escritorio (canetas e papel)",
        valor_total_estimado=15000.00,
    )

    db_session.add_all([licitacao_1, licitacao_2, licitacao_3])
    db_session.commit()
    return db_session


def test_search_finds_licitacao(populate_db):
    from backend import crud

    db = populate_db
    resultados = crud.search_licitacoes_by_objeto(db, query="cadeira")
    assert len(resultados) == 1
    assert resultados[0].id == 1
    assert "cadeira de escritorio" in resultados[0].objeto_compra

    resultados_limpeza = crud.search_licitacoes_by_objeto(db, query="limpeza")
    assert len(resultados_limpeza) == 1
    assert resultados_limpeza[0].id == 2

    resultados_escritorio = crud.search_licitacoes_by_objeto(db, query="escritorio")
    assert len(resultados_escritorio) == 2


def test_pesquisa_precos_por_item_endpoint(populate_db, mocker):
    mocker.patch(
        "backend.src.agents.agente_preco_vencedor._compras_list_contratos_por_objeto",
        new=AsyncMock(return_value=[123, 456]),
    )
    mocker.patch(
        "backend.src.agents.agente_preco_vencedor._compras_precos_itens_do_contrato",
        new=AsyncMock(return_value=[100.0, 150.0]),
    )
    mocker.patch(
        "backend.src.agents.agente_preco_vencedor._buscar_precos_praticados",
        new=AsyncMock(
            return_value=[
                {"fonte": "precos_praticados", "preco": 200.0, "catmat": 99901},
                {"fonte": "precos_praticados", "preco": 250.0, "catmat": 99902},
            ]
        ),
    )
    mocker.patch(
        "src.agents.agente_preco_vencedor._compras_list_contratos_por_objeto",
        new=AsyncMock(return_value=[123, 456]),
    )
    mocker.patch(
        "src.agents.agente_preco_vencedor._compras_precos_itens_do_contrato",
        new=AsyncMock(return_value=[100.0, 150.0]),
    )
    mocker.patch(
        "src.agents.agente_preco_vencedor._buscar_precos_praticados",
        new=AsyncMock(
            return_value=[
                {"fonte": "precos_praticados", "preco": 200.0, "catmat": 99901},
                {"fonte": "precos_praticados", "preco": 250.0, "catmat": 99902},
            ]
        ),
    )

    response = client.get("/pesquisa/precos_por_item?descricao=cadeira&fonte=todas")

    assert response.status_code == 200
    data = response.json()

    assert data["licitacoes_locais_consideradas"] == 1
    assert data["precos_encontrados"] == 6

    stats = data["stats"]
    assert stats["count"] == 6
    assert stats["min"] == 100.0
    assert stats["max"] == 250.0
    expected_mean = (100 + 150 + 100 + 150 + 200 + 250) / 6
    assert stats["mean"] == pytest.approx(expected_mean, rel=1e-6)
    assert stats["median"] == pytest.approx(150.0)
