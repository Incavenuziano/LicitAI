import json
from typing import Optional
import httpx
from charset_normalizer import from_bytes as cn_from_bytes

def consultar_licitacoes_publicadas(
    codigo_modalidade: Optional[int] = 6,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    uf: Optional[str] = None,
    pagina: int = 1,
    tamanho_pagina: int = 10,
) -> str:
    """
    Consulta licitações publicadas no PNCP com filtros opcionais.
    """
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    params: dict[str, object] = {
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if codigo_modalidade is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade
    if data_inicial:
        params["dataInicial"] = data_inicial
    if data_final:
        params["dataFinal"] = data_final
    if uf:
        params["uf"] = uf

    try:
        print(f"--- Executando busca PNCP com parâmetros: {params} ---")
        response = httpx.get(base_url, params=params, timeout=45.0)
        response.raise_for_status()
        
        # Decodificação robusta para evitar problemas de encoding
        raw_content = response.content
        decoded_str = str(cn_from_bytes(raw_content).best())
        payload = json.loads(decoded_str)

        print("--- Consulta ao PNCP bem-sucedida ---")
        if isinstance(payload, dict) and payload.get("data"):
            return json.dumps(payload["data"], indent=2, ensure_ascii=False)
        return json.dumps({"mensagem": "Nenhuma licitação encontrada para os critérios fornecidos."}, indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        error_details = e.response.content.decode("utf-8", errors="replace")
        print(f"--- Erro na API PNCP: {e.response.status_code} - {error_details} ---")
        return json.dumps({
            "erro": "Falha ao consultar a API do PNCP.",
            "status_code": e.response.status_code,
            "detalhes": error_details,
        }, ensure_ascii=False)
    except Exception as e:
        print(f"--- Erro inesperado: {e} ---")
        return json.dumps({"erro": "Um erro inesperado ocorreu.", "detalhes": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    print("Iniciando teste de busca de licitações...")
    print("-----------------------------------------")
    resultado_json = consultar_licitacoes_publicadas(codigo_modalidade=6, tamanho_pagina=5)
    print("\n--- Resultado da Consulta ---")
    try:
        resultado_formatado = json.loads(resultado_json)
        print(json.dumps(resultado_formatado, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(resultado_json)