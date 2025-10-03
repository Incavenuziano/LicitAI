from __future__ import annotations

"""
Cliente leve para a API do Portal da Transparência (dados do Executivo Federal).

Observações importantes:
- A API exige uma chave no header HTTP:  'chave-api-dados: <TOKEN>'
- Configure a variável de ambiente TRANSPARENCIA_API_KEY com o seu token.
- A base pública mais comum é: https://api.portaldatransparencia.gov.br/api-de-dados
- Recursos populares incluem 'contratos' e 'despesas' (pagamentos/empenhos).

Este módulo fornece:
- TransparenciaClient: get/paginação genéricos com header de autenticação.
- Helpers convenientes para contratos por CNPJ, e despesas/pagamentos por CNPJ.

Nota: Alguns nomes de parâmetros podem variar conforme documentação da API. Os helpers tentam usar
nomes comuns; ajuste se necessário nos argumentos extras (**kwargs).
"""

from typing import Any, Dict, List, Optional, Tuple
import os

try:  # opcional até instalado
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


DEFAULT_BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"


class TransparenciaError(RuntimeError):
    pass


class TransparenciaClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL):
        if httpx is None:
            raise TransparenciaError("httpx não instalado. pip install httpx")
        self.api_key = api_key or os.getenv("TRANSPARENCIA_API_KEY")
        if not self.api_key:
            raise TransparenciaError(
                "Defina TRANSPARENCIA_API_KEY no ambiente com sua chave do Portal da Transparência"
            )
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "chave-api-dados": self.api_key or "",
        }

    def get(self, resource: str, params: Dict[str, Any]) -> Tuple[List[Any], Dict[str, Any]]:
        """GET genérico: retorna (lista_json, meta_headers_simplificados).

        Meta inclui: total (X-Total-Count), link (Link), status_code.
        """
        url = f"{self.base_url}/{resource.lstrip('/')}"
        with httpx.Client(timeout=45.0, headers=self._headers()) as client:
            r = client.get(url, params=params)
            try:
                r.raise_for_status()
            except Exception as e:  # inclui o payload de erro
                raise TransparenciaError(f"{e}: {r.text}")
            try:
                data = r.json()
            except Exception:
                data = []
            meta = {
                "total": r.headers.get("X-Total-Count"),
                "link": r.headers.get("Link"),
                "status_code": r.status_code,
            }
            return (data if isinstance(data, list) else [data], meta)

    def get_paged(
        self, resource: str, *, pagina_inicial: int = 1, max_paginas: int = 5, **params: Any
    ) -> List[Any]:
        """Itera páginas (param 'pagina') acumulando resultados.

        Alguns recursos usam apenas 'pagina' (sem 'tamanhoPagina').
        """
        out: List[Any] = []
        pagina = pagina_inicial
        for _ in range(max_paginas):
            p = dict(params)
            p["pagina"] = pagina
            rows, meta = self.get(resource, p)
            if not rows:
                break
            out.extend([r for r in rows if isinstance(r, (dict, list))])
            # Heurística simples: se veio menos que 1 página típica, interrompe
            # A API não garante tamanho fixo; usar X-Total-Count pode ajudar em client caller.
            if len(rows) < 1:
                break
            pagina += 1
        return out


# ----------------- Helpers de alto nível -----------------

def contratos_por_cnpj(
    cnpj: str,
    *,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    pagina_inicial: int = 1,
    max_paginas: int = 5,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Lista contratos por CNPJ do contratado.

    Parâmetros comuns (sujeitos à documentação oficial):
      - cnpjContratado, dataInicial, dataFinal, pagina
    """
    client = TransparenciaClient()
    params: Dict[str, Any] = {}
    # nomes conforme documentação típica
    params["cnpjContratado"] = cnpj
    if data_inicio:
        params["dataInicial"] = data_inicio
    if data_fim:
        params["dataFinal"] = data_fim
    params.update(kwargs)
    rows = client.get_paged("contratos", pagina_inicial=pagina_inicial, max_paginas=max_paginas, **params)
    return [r for r in rows if isinstance(r, dict)]


def pagamentos_por_cnpj(
    cnpj: str,
    *,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    pagina_inicial: int = 1,
    max_paginas: int = 5,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Lista despesas/pagamentos por CNPJ favorecido.

    Observação: no Portal, pagamentos podem estar sob recursos como 'despesas'.
    Parâmetros comuns: cnpjFavorecido (ou cnpjFornecedor), dataInicial, dataFinal, pagina.
    """
    client = TransparenciaClient()
    params: Dict[str, Any] = {}
    # parâmetros comuns encontrados na documentação
    # ajuste 'cnpjFornecedor' -> 'cnpjFavorecido' conforme o recurso real desejado
    params["cnpjFavorecido"] = cnpj
    if data_inicio:
        params["dataInicial"] = data_inicio
    if data_fim:
        params["dataFinal"] = data_fim
    params.update(kwargs)
    rows = client.get_paged("despesas", pagina_inicial=pagina_inicial, max_paginas=max_paginas, **params)
    return [r for r in rows if isinstance(r, dict)]

