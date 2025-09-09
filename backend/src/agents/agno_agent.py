import os
import json
from typing import Optional

try:
    from agno.agent import Agent  # type: ignore
    from agno.models.google import Gemini  # type: ignore
    from agno.tools.decorator import tool  # type: ignore
    from agno.storage.sqlite import SqliteStorage  # type: ignore
    from agno.memory.v2.memory import Memory  # type: ignore
    from agno.memory.v2.db.sqlite import SqliteMemoryDb  # type: ignore
except Exception:
    Agent = None  # type: ignore
    Gemini = None  # type: ignore
    tool = None  # type: ignore
    SqliteStorage = None  # type: ignore
    Memory = None  # type: ignore
    SqliteMemoryDb = None  # type: ignore

from ..agents.agente_busca import consultar_licitacoes_publicadas
from ..agents.agente_tratamento import salvar_licitacoes
from ..integrations.anexos import pncp_extrair_anexos_de_pagina, comprasnet_contrato_arquivos
from .. import crud
from ..database import SessionLocal
from .. import analysis_service


if tool is not None:
    @tool
    def buscar_licitacoes(
        uf: Optional[str] = None,
        data_inicial: Optional[str] = None,
        data_final: Optional[str] = None,
        codigo_modalidade: Optional[int] = 6,
        tamanho_pagina: Optional[int] = 10,
    ) -> str:
        """Busca licitacoes no PNCP com filtros opcionais e retorna JSON (string)."""
        return consultar_licitacoes_publicadas(
            codigo_modalidade=codigo_modalidade,
            data_inicial=data_inicial,
            data_final=data_final,
            uf=uf,
            tamanho_pagina=tamanho_pagina or 10,
        )


    @tool
    def salvar_licitacoes_json(licitacoes_json: str) -> str:
        """Salva licitacoes (JSON string) no banco de dados e retorna um resumo (string)."""
        return salvar_licitacoes(licitacoes_json)


    @tool
    def anexos_pncp(link_pagina: str) -> str:
        """Extrai links de PDF a partir de uma pagina do PNCP (ou sistema de origem)."""
        pdfs = pncp_extrair_anexos_de_pagina(link_pagina)
        return json.dumps({"link": link_pagina, "pdfs": pdfs, "count": len(pdfs)}, ensure_ascii=False)


    @tool
    def anexos_comprasnet(contrato_id: int, base_url: Optional[str] = None) -> str:
        """Lista URLs de arquivos (anexos) de um contrato no ComprasNet."""
        arquivos = comprasnet_contrato_arquivos(
            contrato_id=contrato_id,
            base_url=base_url or "https://contratos.comprasnet.gov.br",
        )
        return json.dumps({"contrato_id": contrato_id, "arquivos": arquivos, "count": len(arquivos)}, ensure_ascii=False)


    @tool
    def criar_e_rodar_analise(licitacao_id: int) -> str:
        """Cria (ou reseta) uma analise para a licitacao informada e executa imediatamente."""
        db = SessionLocal()
        try:
            analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
            analysis_service.run_analysis(analise.id)
            return json.dumps({"analise_id": analise.id, "status": "concluida"}, ensure_ascii=False)
        finally:
            db.close()


def make_agent() -> Agent:
    """Cria um agente Agno com Gemini-flash, storage e memoria persistente.

    Requer:
      - pip install agno google-generativeai
      - variavel de ambiente GEMINI_API_KEY (ou GOOGLE_API_KEY)
    """
    if (
        Agent is None
        or Gemini is None
        or tool is None
        or SqliteStorage is None
        or Memory is None
        or SqliteMemoryDb is None
    ):
        raise ImportError(
            "Dependencias do Agno nao encontradas. Instale: pip install agno google-generativeai"
        )

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    # Usa o modelo solicitado
    model = Gemini(id="gemini-2.5-flash", api_key=api_key)

    # Storage e memoria persistente do agente
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tmp_dir = os.path.join(base_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    storage = SqliteStorage(
        table_name="licitai_agent",
        db_file=os.path.join(tmp_dir, "agents.db"),
        auto_upgrade_schema=True,
    )
    memory_db = SqliteMemoryDb(
        table_name="memory",
        db_file=os.path.join(tmp_dir, "memory.db"),
    )
    memory = Memory(db=memory_db)

    return Agent(
        name="LicitAI Agent",
        agent_id="licitai-agent",
        model=model,
        storage=storage,
        memory=memory,
        tools=[
            buscar_licitacoes,
            salvar_licitacoes_json,
            anexos_pncp,
            anexos_comprasnet,
            criar_e_rodar_analise,
        ],
        show_tool_calls=True,
        enable_user_memories=True,
        add_history_to_messages=True,
        num_history_responses=5,
        add_datetime_to_instructions=True,
        markdown=False,
    )


def run_agent(message: str, context: Optional[dict] = None) -> str:
    agent = make_agent()
    if context:
        agent.context = context
    response = agent.run(message)
    try:
        return str(response)
    except Exception:
        return json.dumps({"result": response}, ensure_ascii=False)


# Prompt base adaptado para análise de editais (Lei 14.133/21, TCU, etc.)
BASE_PROMPT = (
    "Instruções para o LLM\n"
    "Você é um especialista em licitações públicas, com conhecimento aprofundado na Lei nº 14.133/2021,\n"
    "nas orientações do Tribunal de Contas da União (TCU), e nas melhores práticas de planejamento,\n"
    "instrução, julgamento e fiscalização de contratos administrativos.\n\n"
    "Contexto da Análise:\n"
    "Será analisada uma seção específica de um edital de licitação (ou o edital completo).\n"
    "A sua tarefa é examinar o conteúdo apresentado e emitir uma avaliação técnico-jurídica com base na\n"
    "conformidade legal, nos princípios constitucionais, nas boas práticas administrativas e nos\n"
    "entendimentos do TCU.\n\n"
    "Sua análise deve considerar os seguintes eixos normativos e operacionais:\n"
    "I. Conformidade Legal (Lei nº 14.133/2021) – prazos, procedimentos, publicações, contraditório, ampla defesa, isonomia, interesse público.\n"
    "II. Princípios Aplicáveis – legalidade, impessoalidade, moralidade, publicidade, eficiência, planejamento,\n"
    "vinculação ao instrumento convocatório, julgamento objetivo, desenvolvimento nacional sustentável.\n"
    "III. Check de Elementos Essenciais do Edital – objeto, fundamentos legais, critério de julgamento, habilitação,\n"
    "cláusulas contratuais, condições de participação, cronograma, sanções, impugnação/recursos, PNCP.\n"
    "IV. Riscos Jurídicos e Omissões – dispositivos omissos/ilegais, desproporcionalidade, hipóteses de impugnação.\n"
    "V. Jurisprudência e Boas Práticas do TCU – entendimentos relevantes e recomendações.\n"
    "VI. Recomendações Técnicas – melhorias para legalidade, economicidade, eficiência, transparência e segurança jurídica.\n\n"
    "Formato de Resposta Esperado:\n"
    "## [TÍTULO DA SEÇÃO ANALISADA]\n\n"
    "### 1. Conformidade Legal\n[✔️ ou ⚠️] Análise com citação de artigos pertinentes da Lei nº 14.133/21.\n\n"
    "### 2. Princípios da Administração Pública\n[✔️ ou ⚠️] Indicação dos princípios envolvidos e eventuais violações.\n\n"
    "### 3. Checklist Técnico\n| Item | Avaliação | Observação técnica |\n|---|---|---|\n"
    "| Objeto definido | ✔️/⚠️/❌ | … |\n| Fundamentação legal | ✔️/⚠️/❌ | … |\n| Critério de julgamento | ✔️/⚠️/❌ | … |\n| Requisitos de habilitação | ✔️/⚠️/❌ | … |\n| Cláusulas contratuais | ✔️/⚠️/❌ | … |\n| Condições de participação | ✔️/⚠️/❌ | … |\n| Cronograma | ✔️/⚠️/❌ | … |\n| Sanções administrativas | ✔️/⚠️/❌ | … |\n| Impugnação/recursos | ✔️/⚠️/❌ | … |\n| PNCP | ✔️/⚠️/❌ | … |\n\n"
    "### 4. Riscos Jurídicos Identificados\n- …\n\n"
    "### 5. Jurisprudência Aplicável\n> Cite entendimentos do TCU pertinentes.\n\n"
    "### 6. Recomendações Técnicas\n- …\n\n"
    "Observações Finais:\n"
    "Seja técnico, claro e objetivo; cite artigos da Lei 14.133/21 quando aplicável; não faça suposições;\n"
    "use marcadores (✔️, ⚠️, ❌) para indicar conformidade.\n"
)


def run_edital_analysis(texto: str, titulo_secao: Optional[str] = None, context: Optional[dict] = None) -> str:
    """Executa a análise de um texto de edital usando o agente Agno (Gemini 2.5 Flash)."""
    agent = make_agent()
    if context:
        agent.context = context
    titulo = titulo_secao or "Seção do Edital"
    prompt = f"{BASE_PROMPT}\n\n## {titulo}\n\n[TEXTO]\n{texto}\n\nProduza a análise conforme o formato esperado."
    resp = agent.run(prompt)
    try:
        return str(resp)
    except Exception:
        return json.dumps({"result": resp}, ensure_ascii=False)
