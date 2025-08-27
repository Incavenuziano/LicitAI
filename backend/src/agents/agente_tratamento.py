import json
from sqlalchemy.orm import Session

from .. import crud, schemas, database

def salvar_licitacoes(licitacoes_json: str) -> str:
    """
    Recebe uma string JSON contendo uma lista de licitações, valida cada uma,
    e as salva no banco de dados. Evita a criação de duplicatas.

    Args:
        licitacoes_json (str): A string JSON com a lista de licitações a serem salvas.

    Returns:
        str: Um resumo da operação, indicando quantas licitações foram processadas.
    """
    print("--- Executando função: salvar_licitacoes ---")
    try:
        licitacoes = json.loads(licitacoes_json)
        if not isinstance(licitacoes, list):
            return json.dumps({"erro": "O JSON de entrada não é uma lista."})
    except json.JSONDecodeError:
        return json.dumps({"erro": "A string de entrada não é um JSON válido."})

    db: Session = next(database.get_db())
    
    for licitacao_data in licitacoes:
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
        
        dados_validos = {k: v for k, v in dados_adaptados.items() if v is not None}

        try:
            licitacao_schema = schemas.LicitacaoCreate(**dados_validos)
            crud.create_licitacao(db=db, licitacao=licitacao_schema)
        except Exception as e:
            print(f"Erro ao processar licitação {dados_adaptados.get('numero_controle_pncp')}: {e}")
            continue

    total_processado = len(licitacoes)
    db.close()
    
    resultado = f"{total_processado} licitações foram processadas e salvas no banco de dados."
    print(f"--- {resultado} ---")
    return json.dumps({"status": "sucesso", "mensagem": resultado})

if __name__ == "__main__":
    exemplo_json_str = '''
    [
      {
        "numeroControlePNCP": "123456789-1-00001/2024",
        "anoCompra": 2024,
        "sequencialCompra": 1,
        "modalidadeNome": "Pregão - Eletrônico",
        "objetoCompra": "Aquisição de material de escritório para teste.",
        "valorTotalEstimado": 50000.00,
        "orgaoEntidade": { "razaoSocial": "Ministério da Educação" },
        "unidadeOrgao": { "nomeUnidade": "Campus Teste", "ufSigla": "DF", "municipioNome": "Brasília" },
        "dataPublicacaoPncp": "2024-08-20T10:00:00",
        "dataEncerramentoProposta": "2024-09-01T10:00:00",
        "linkSistemaOrigem": "http://comprasnet.gov.br"
      }
    ]
    '''
    
    print("Iniciando teste de salvamento de licitações...")
    print("--------------------------------------------------")
    resultado_salvamento = salvar_licitacoes(exemplo_json_str)
    print("\n--- Resultado do Salvamento ---")
    print(resultado_salvamento)
