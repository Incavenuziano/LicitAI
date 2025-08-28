import time
from sqlalchemy.orm import Session
from . import crud

def run_analysis(db: Session, analise_id: int):
    """
    Esta é a função principal do nosso agente de análise.
    Ela será executada em segundo plano.
    """
    print(f"[Análise ID: {analise_id}] - Iniciando análise...")

    # 1. Atualiza o status para 'Em Andamento'
    crud.update_analise(db, analise_id=analise_id, status="Em Andamento", resultado="")

    # 2. Pega o objeto da análise e a licitação associada
    analise = crud.get_analise(db, analise_id=analise_id)
    if not analise:
        print(f"[Análise ID: {analise_id}] - ERRO: Análise não encontrada.")
        return

    link_edital = analise.licitacao.link_sistema_origem
    print(f"[Análise ID: {analise_id}] - Link do edital: {link_edital}")

    # 3. Simula o trabalho pesado (download, leitura de PDF, IA)
    #    No futuro, a lógica real entrará aqui.
    try:
        print(f"[Análise ID: {analise_id}] - Simulando download e processamento do PDF...")
        time.sleep(15) # Simula uma tarefa de 15 segundos
        resultado_final = "Análise de teste concluída com sucesso. Itens encontrados: 5. Valor total: R$ 50.000,00."
        status_final = "Concluído"
        print(f"[Análise ID: {analise_id}] - Simulação concluída.")

    except Exception as e:
        print(f"[Análise ID: {analise_id}] - ERRO durante a análise: {e}")
        resultado_final = f"Ocorreu um erro: {e}"
        status_final = "Erro"

    # 4. Atualiza o registro no banco com o resultado final
    crud.update_analise(db, analise_id=analise_id, status=status_final, resultado=resultado_final)
    print(f"[Análise ID: {analise_id}] - Análise finalizada e salva no banco.")
