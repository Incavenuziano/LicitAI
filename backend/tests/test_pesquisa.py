from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from backend.main import app, get_db
from backend.models import Base, Licitacao

# Configuração do banco de dados de teste em memória
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cria as tabelas no banco de dados de teste
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Sobrescreve a dependência get_db para usar o banco de teste
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    """Fixture para criar um banco de dados limpo para cada teste."""
    Base.metadata.drop_all(bind=engine) # Limpa dados antigos
    Base.metadata.create_all(bind=engine) # Cria tabelas novas
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def populate_db(db_session):
    """Adiciona dados de licitação ao banco de dados para os testes."""
    licitacao_1 = Licitacao(
        id=1,
        numero_controle_pncp="11111",
        objeto_compra="Aquisição de 100 unidades de cadeira de escritório ergonômica",
        valor_total_estimado=50000.00
    )
    licitacao_2 = Licitacao(
        id=2,
        numero_controle_pncp="22222",
        objeto_compra="Contratação de serviço de limpeza e conservação predial",
        valor_total_estimado=120000.00
    )
    licitacao_3 = Licitacao(
        id=3,
        numero_controle_pncp="33333",
        objeto_compra="Compra de material de escritório (canetas e papel)",
        valor_total_estimado=15000.00
    )

    db_session.add_all([licitacao_1, licitacao_2, licitacao_3])
    db_session.commit()
    return db_session

def test_search_finds_licitacao(populate_db):
    """Testa se a busca no banco de dados encontra a licitação correta."""
    from backend import crud
    db = populate_db
    resultados = crud.search_licitacoes_by_objeto(db, query="cadeira")
    assert len(resultados) == 1
    assert resultados[0].id == 1
    assert "cadeira de escritório" in resultados[0].objeto_compra

    resultados_limpeza = crud.search_licitacoes_by_objeto(db, query="limpeza")
    assert len(resultados_limpeza) == 1
    assert resultados_limpeza[0].id == 2

    resultados_escritorio = crud.search_licitacoes_by_objeto(db, query="escritório")
    assert len(resultados_escritorio) == 2 # Encontra a 1 e a 3


def test_pesquisa_precos_por_item_endpoint(populate_db, mocker):
    """Testa o endpoint de pesquisa de preços, mockando as chamadas externas."""
    # 1. Configura os mocks para as funções que fazem chamadas HTTP
    mocker.patch(
        "backend.src.agents.agente_preco_vencedor._compras_list_contratos_por_objeto",
        return_value=[123, 456]  # Retorna 2 IDs de contrato falsos
    )
    mocker.patch(
        "backend.src.agents.agente_preco_vencedor._compras_precos_itens_do_contrato",
        return_value=[100.0, 150.0]  # Para cada contrato, retorna 2 preços falsos
    )

    # 2. Chama o endpoint da API
    response = client.get("/pesquisa/precos_por_item?descricao=cadeira")

    # 3. Verifica os resultados
    assert response.status_code == 200
    data = response.json()

    # A busca por "cadeira" encontra 1 licitação local
    assert data["licitacoes_locais_consideradas"] == 1
    # Mockamos 2 contratos, cada um com 2 preços, então esperamos 4 preços no total
    assert data["precos_encontrados"] == 4
    
    # Verifica as estatísticas calculadas com base nos preços mockados [100, 150, 100, 150]
    stats = data["stats"]
    assert stats["count"] == 4
    assert stats["min"] == 100.0
    assert stats["max"] == 150.0
    assert stats["mean"] == 125.0
    assert stats["median"] == 125.0
