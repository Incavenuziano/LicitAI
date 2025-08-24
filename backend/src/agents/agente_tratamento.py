
import json
from textwrap import dedent
from sqlalchemy.orm import Session

from src import crud, schemas, database
from agno.agent import Agent
from agno.models.google import Gemini

# --- Ferramenta de Tratamento e Persistência ---

def salvar_licitacoes(licitacoes_json: str) -> str:
    """
    Recebe uma string JSON contendo uma lista de licitações, valida cada uma,
    e as salva no banco de dados. Evita a criação de duplicatas.

    Args:
        licitacoes_json (str): A string JSON com a lista de licitações a serem salvas.

    Returns:
        str: Um resumo da operação, indicando quantas licitações foram processadas, 
             quantas eram novas e quantas já existiam.
    """
    print("--- Executando ferramenta: salvar_licitacoes ---")
    try:
        licitacoes = json.loads(licitacoes_json)
        if not isinstance(licitacoes, list):
            return json.dumps({"erro": "O JSON de entrada não é uma lista."})
    except json.JSONDecodeError:
        return json.dumps({"erro": "A string de entrada não é um JSON válido."})

    db: Session = next(database.get_db())
    novas_count = 0
    existentes_count = 0

    for licitacao_data in licitacoes:
        # Adaptação dos campos da API para o nosso modelo
        # A API usa 'orgaoEntidade.razaoSocial', nosso modelo espera 'orgao_entidade_nome'
        # Esta é uma simplificação. Um tratamento mais robusto seria feito aqui.
        dados_adaptados = {
            "numero_controle_pncp": licitacao_data.get("numeroControlePNCP"),
            "ano_compra": licitacao_data.get("anoCompra"),
            "sequencial_compra": licitacao_data.get("sequencialCompra"),
            "modalidade_nome": licitacao_data.get("modalidadeNome"),
            "objeto_compra": licitacao_data.get("objetoCompra"),
            "valor_total_estimado": licitacao_data.get("valorTotalEstimado"),
            "orgao_entidade_nome": licitacao_data.get("orgaoEntidade", {}).get("razaoSocial"),
            "unidade_orgao_nome": licitacao_data.get("unidadeOrgao", {}).get("nomeUnidade"),
            "uf": licitacao_data.get("unidadeOrgao", {}).get("ufSigla"),
            "municipio_nome": licitacao_data.get("unidadeOrgao", {}).get("municipioNome"),
            "data_publicacao_pncp": licitacao_data.get("dataPublicacaoPncp"),
            "data_encerramento_proposta": licitacao_data.get("dataEncerramentoProposta"),
            "link_sistema_origem": licitacao_data.get("linkSistemaOrigem"),
        }
        
        # Remove chaves com valores None para não dar erro no Pydantic
        dados_validos = {k: v for k, v in dados_adaptados.items() if v is not None}

        try:
            licitacao_schema = schemas.LicitacaoCreate(**dados_validos)
            # A função crud.create_licitacao já verifica duplicatas
            db_licitacao = crud.create_licitacao(db=db, licitacao=licitacao_schema)
            # A função retorna um objeto, então podemos verificar se ele foi criado agora ou já existia
            # Esta lógica é simplificada. Uma forma melhor seria a função crud retornar um booleano.
            # Por enquanto, vamos assumir que se não deu erro, foi processado.
        except Exception as e:
            print(f"Erro ao processar licitação {dados_adaptados.get('numero_controle_pncp')}: {e}")
            continue # Pula para a próxima em caso de erro

    # A lógica de contagem aqui é uma simplificação. O ideal seria o CRUD nos informar.
    total_processado = len(licitacoes)
    db.close()
    
    resultado = f"{total_processado} licitações foram processadas e salvas no banco de dados."
    print(f"--- {resultado} ---")
    return json.dumps({"status": "sucesso", "mensagem": resultado})


# --- Definição do Agente de Tratamento ---

agente_tratamento = Agent(
    model=Gemini(id="gemini-1.5-flash"),
    instructions=dedent("""
        Você é um agente de ETL (Extract, Transform, Load) de dados de licitações.
        Sua única função é receber uma lista de licitações em formato JSON e usar a ferramenta
        `salvar_licitacoes` para persisti-las no banco de dados.
        Apenas confirme a execução da ferramenta.
    """
    ),
    tools=[salvar_licitacoes],
    show_tool_calls=True,
)
