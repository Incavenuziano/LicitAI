import pandas as pd

# Importações do nosso projeto
from ..database import engine

def analisar_licitacoes_com_pandas():
    """
    Usa a biblioteca Pandas para carregar as licitações do banco de dados e fazer uma análise.
    Esta função se conecta ao banco de dados, conta o número total de licitações,
    e agrupa as licitações por modalidade.
    Retorna uma string contendo um relatório formatado da análise.
    """
    print("--- Iniciando análise com Pandas ---")
    try:
        query = "SELECT * FROM licitacoes;"
        df = pd.read_sql(query, engine)

        if df.empty:
            return "Nenhuma licitação encontrada no banco de dados para analisar."

        total_licitacoes = len(df)
        contagem_por_modalidade = df['modalidade_nome'].value_counts().to_string()

        resultado_analise = f"""
        --- Relatório de Análise de Licitações ---
        
        Total de Licitações no Banco de Dados: {total_licitacoes}

        Distribuição por Modalidade:
        {contagem_por_modalidade}
        
        -------------------------------------------
        """
        print("--- Análise concluída ---")
        return resultado_analise

    except Exception as e:
        error_message = f"Ocorreu um erro durante a análise com Pandas: {e}"
        print(error_message)
        return error_message

# Exemplo de como chamar a função
if __name__ == '__main__':
    print("Executando a função de análise de dados em modo de teste...")
    resultado = analisar_licitacoes_com_pandas()
    print("\n--- Resultado da Análise ---")
    print(resultado)
