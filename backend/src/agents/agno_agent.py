import os
import json
import asyncio
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


    # Separamos a lógica da ferramenta para permitir testes diretos
    def _buscar_e_baixar_editais_logic(uf: str, data_inicial: str, data_final: str, tamanho_pagina: int = 5) -> str:
        """Lógica principal: busca licitações e, para cada uma, tenta baixar o edital."""
        print(f"--- Iniciando busca e download para {uf} de {data_inicial} a {data_final} ---")
        
        # 1. Buscar os metadados das licitações
        licitacoes_json_str = consultar_licitacoes_publicadas(
            uf=uf, data_inicial=data_inicial, data_final=data_final, tamanho_pagina=tamanho_pagina
        )
        try:
            licitacoes = json.loads(licitacoes_json_str)
        except json.JSONDecodeError:
            return f"Erro: A busca de licitações retornou um formato inválido."

        if not licitacoes:
            return "Nenhuma licitação encontrada para o período."

        # 2. Tentar baixar o edital para cada licitação
        sucessos = 0
        db = SessionLocal()
        try:
            for licitacao in licitacoes:
                link = licitacao.get("link_sistema_origem")
                licitacao_id = licitacao.get("id")
                if not link or not licitacao_id:
                    continue
                
                print(f"-- Tentando baixar edital para licitação ID: {licitacao_id} --")
                # Usamos asyncio.run para chamar nossa função assíncrona de forma síncrona no loop
                local_path = asyncio.run(analysis_service.baixar_edital_com_playwright(link, licitacao_id))
                
                if local_path:
                    sucessos += 1
                    # 3. Registrar o anexo no banco de dados
                    crud.create_anexo(
                        db=db,
                        licitacao_id=licitacao_id,
                        source="playwright_download",
                        local_path=local_path,
                        filename=os.path.basename(local_path),
                        content_type="application/pdf",
                        status="downloaded"
                    )
                    print(f"-- SUCESSO: Edital baixado e registrado para licitação ID: {licitacao_id} --")
        finally:
            db.close()

        resumo = f"Operação concluída. {len(licitacoes)} licitações encontradas. {sucessos} editais baixados com sucesso."
        print(resumo)
        return resumo

    # Criamos a ferramenta para o agente Agno usando a função de lógica
    buscar_e_baixar_editais = tool(_buscar_e_baixar_editais_logic)

    def _buscar_e_baixar_editais_logic_router(uf: str, data_inicial: str, data_final: str, tamanho_pagina: int = 10) -> str:  # type: ignore[func-redefined]
        print(f"--- Iniciando busca e download (router) para {uf} de {data_inicial} a {data_final} ---")

        licitacoes_json_str = consultar_licitacoes_publicadas(
            uf=uf, data_inicial=data_inicial, data_final=data_final, tamanho_pagina=tamanho_pagina
        )
        try:
            licitacoes = json.loads(licitacoes_json_str)
        except json.JSONDecodeError:
            return "Erro: A busca de licitações retornou um formato inválido."

        if isinstance(licitacoes, dict):
            data_list = licitacoes.get("data")
            if isinstance(data_list, list):
                licitacoes = data_list
            else:
                msg = licitacoes.get("mensagem") or licitacoes.get("erro") or "payload não é lista"
                return f"Nenhuma licitação processável: {msg}"

        if not licitacoes:
            return "Nenhuma licitação encontrada para o período."

        sucessos = 0
        db = SessionLocal()
        try:
            for row in licitacoes:
                numero_controle = row.get("numeroControlePNCP") or row.get("numero_controle_pncp")
                if not numero_controle:
                    continue

                licitacao_db = crud.get_licitacao_by_numero_controle(db, numero_controle)
                if not licitacao_db:
                    continue

                print(f"-- Processando licitação: {numero_controle} --")
                link = licitacao_db.link_sistema_origem or row.get("linkSistemaOrigem") or row.get("link_sistema_origem")

                local_path = None
                source_tag = None

                if link and ("compras.gov.br" in link or "pncp.gov.br" in link):
                    try:
                        local_path = analysis_service.baixar_edital_via_api(licitacao_db)
                        source_tag = "api_download" if local_path else None
                    except Exception:
                        local_path = None
                        source_tag = None

                if not local_path and link:
                    print("-- Método API falhou. Tentando Playwright como fallback... --")
                    ident = licitacao_db.id or numero_controle
                    local_path = asyncio.run(analysis_service.baixar_edital_com_playwright_storage_v2(link, ident))
                    source_tag = "playwright_download" if local_path else None

                if local_path:
                    sucessos += 1
                    crud.create_anexo(
                        db=db,
                        licitacao_id=licitacao_db.id,
                        source=source_tag or "download",
                        local_path=local_path,
                        filename=os.path.basename(local_path),
                        content_type="application/pdf",
                        status="downloaded",
                    )
                    print(f"-- SUCESSO: Edital baixado e registrado para licitação ID: {licitacao_db.id} --")
        finally:
            db.close()

        resumo = f"Operação concluída. {len(licitacoes)} licitações encontradas. {sucessos} editais baixados com sucesso."
        print(resumo)
        return resumo

    # Passa a ferramenta a usar o roteador por padrão
    buscar_e_baixar_editais = tool(_buscar_e_baixar_editais_logic_router)

    # Versao revisada: aceita numeroControlePNCP como identificador e prossegue sem ID (permite page.pause)
    def _buscar_e_baixar_editais_logic(uf: str, data_inicial: str, data_final: str, tamanho_pagina: int = 5) -> str:  # type: ignore[func-redefined]
        print(f"--- Iniciando busca e download para {uf} de {data_inicial} a {data_final} ---")

        licitacoes_json_str = consultar_licitacoes_publicadas(
            uf=uf, data_inicial=data_inicial, data_final=data_final, tamanho_pagina=tamanho_pagina
        )
        try:
            licitacoes = json.loads(licitacoes_json_str)
        except json.JSONDecodeError:
            return "Erro: A busca de licitações retornou um formato inválido."

        # Garantir que seja uma lista; se vier um dict com erro/mensagem, aborta com resumo
        if isinstance(licitacoes, dict):
            data_list = licitacoes.get("data")
            if isinstance(data_list, list):
                licitacoes = data_list
            else:
                msg = licitacoes.get("mensagem") or licitacoes.get("erro") or "payload não é lista"
                return f"Nenhuma licitação processável: {msg}"

        if not licitacoes:
            return "Nenhuma licitação encontrada para o período."

        sucessos = 0
        db = SessionLocal()
        try:
            for licitacao in licitacoes:
                link = licitacao.get("linkSistemaOrigem") or licitacao.get("link_sistema_origem")
                licitacao_id = licitacao.get("id")
                numero = licitacao.get("numeroControlePNCP") or licitacao.get("numero_controle_pncp")
                ident = licitacao_id or numero or "sem-ident"
                if not link:
                    continue

                print(f"-- Tentando baixar edital para identificador: {ident} --")
                # Usa versão com storage_state para facilitar passar pelo captcha invisível
                local_path = asyncio.run(analysis_service.baixar_edital_com_playwright_storage_v2(link, ident))

                if local_path:
                    sucessos += 1
                    if licitacao_id:
                        crud.create_anexo(
                            db=db,
                            licitacao_id=licitacao_id,
                            source="playwright_download",
                            local_path=local_path,
                            filename=os.path.basename(local_path),
                            content_type="application/pdf",
                            status="downloaded",
                        )
                        print(f"-- SUCESSO: Edital baixado e registrado para licitação ID: {licitacao_id} --")
                    else:
                        print(f"-- SUCESSO: Edital baixado (somente arquivo) para identificador: {ident} --")
        finally:
            db.close()

        resumo = f"Operação concluída. {len(licitacoes)} licitações encontradas. {sucessos} editais baixados com sucesso."
        print(resumo)
        return resumo

    # Atualiza a ferramenta para apontar para a versão revisada
    buscar_e_baixar_editais = tool(_buscar_e_baixar_editais_logic)


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
            buscar_e_baixar_editais, # <-- FERRAMENTA ADICIONADA
            anexos_pncp,
            anexos_comprasnet,
            criar_e_rodar_analise,
        ],
        show_tool_calls=True,
        enable_user_memories=True,
        add_history_to_messages=True,
        num_history_responses=5,
        add_datetime_to_instructions=True,
        markdown=True,
    )


def run_agent(message: str, context: Optional[dict] = None) -> str:
    agent = make_agent()
    if context:
        agent.context = context
    response = agent.run(message)
    try:
        return str(response)
    except Exception:
        return json.dumps({"result": resp}, ensure_ascii=False)


# Prompt base adaptado para análise de editais (Lei 14.133/21, TCU, etc.)
BASE_PROMPT = """Instruções para o LLM
Você é um especialista em licitações públicas, com conhecimento aprofundado na Lei nº 14.133/2021,
nas orientações do Tribunal de Contas da União (TCU), e nas melhores práticas de planejamento,
instrução, julgamento e fiscalização de contratos administrativos.

Contexto da Análise:
Será analisada uma seção específica de um edital de licitação (ou o edital completo).
A sua tarefa é examinar o conteúdo apresentado e emitir uma avaliação técnico-jurídica com base na
conformidade legal, nos princípios constitucionais, nas boas práticas administrativas e nos
entendimentos do TCU.

Sua análise deve considerar os seguintes eixos normativos e operacionais:
I. Conformidade Legal (Lei nº 14.133/2021) – prazos, procedimentos, publicações, contraditório, ampla defesa, isonomia, interesse público.
II. Princípios Aplicáveis – legalidade, impessoalidade, moralidade, publicidade, eficiência, planejamento,
vinculação ao instrumento convocatório, julgamento objetivo, desenvolvimento nacional sustentável.
III. Check de Elementos Essenciais do Edital – objeto, fundamentos legais, critério de julgamento, habilitação,
cláusulas contratuais, condições de participação, cronograma, sanções, impugnação/recursos, PNCP.
IV. Riscos Jurídicos e Omissões – dispositivos omissos/ilegais, desproporcionalidade, hipóteses de impugnação.
V. Jurisprudência e Boas Práticas do TCU – entendimentos relevantes e recomendações.
VI. Recomendações Técnicas – melhorias para legalidade, economicidade, eficiência, transparência e segurança jurídica.

Formato de Resposta Esperado:
## [TÍTULO DA SEÇÃO ANALISADA]

### 1. Conformidade Legal
[✔️ ou ⚠️] Análise com citação de artigos pertinentes da Lei nº 14.133/21.

### 2. Princípios da Administração Pública
[✔️ ou ⚠️] Indicação dos princípios envolvidos e eventuais violações.

### 3. Checklist Técnico
| Item | Avaliação | Observação técnica |
|---|---|---|
| Objeto definido | ✔️/⚠️/❌ | … |
| Fundamentação legal | ✔️/⚠️/❌ | … |
| Critério de julgamento | ✔️/⚠️/❌ | … |
| Requisitos de habilitação | ✔️/⚠️/❌ | … |
| Cláusulas contratuais | ✔️/⚠️/❌ | … |
| Condições de participação | ✔️/⚠️/❌ | … |
| Cronograma | ✔️/⚠️/❌ | … |
| Sanções administrativas | ✔️/⚠️/❌ | … |
| Impugnação/recursos | ✔️/⚠️/❌ | … |
| PNCP | ✔️/⚠️/❌ | … |

### 4. Riscos Jurídicos Identificados
- …

### 5. Jurisprudência Aplicável
> Cite entendimentos do TCU pertinentes.

### 6. Recomendações Técnicas
- …

Observações Finais:
Seja técnico, claro e objetivo; cite artigos da Lei 14.133/21 quando aplicável; não faça suposições;
use marcadores (✔️, ⚠️, ❌) para indicar conformidade.
"""


def run_edital_analysis(texto: str, titulo_secao: Optional[str] = None, context: Optional[dict] = None) -> str:
    """Executa a análise de um texto de edital usando o agente Agno (Gemini 2.5 Flash)."""
    agent = make_agent()
    if context:
        agent.context = context
    
    titulo = titulo_secao or "Seção do Edital"
    prompt = f"""{BASE_PROMPT}

## {titulo}

[TEXTO]
{texto}

Produza a análise conforme o formato esperado."""
    
    resp = agent.run(prompt)
    # Normalizar resposta para string de conteúdo (Markdown/Texto)
    try:
        # Objetos Agno geralmente expõem `.content`
        if hasattr(resp, "content") and isinstance(getattr(resp, "content"), str):
            return resp.content  # type: ignore[return-value]
        # Pode vir como dict
        if isinstance(resp, dict):
            if isinstance(resp.get("content"), str):
                return resp["content"]  # type: ignore[return-value]
            # Alguns modelos usam 'text' ou similar
            if isinstance(resp.get("text"), str):
                return resp["text"]  # type: ignore[return-value]
        # Fallback final: stringificar
        return str(resp)
    except Exception:
        try:
            return str(resp)
        except Exception:
            return json.dumps({"result": "<unserializable>"}, ensure_ascii=False)

