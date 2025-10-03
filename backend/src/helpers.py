import re
from typing import Optional, Dict


def parse_numero_controle(numero_controle: str) -> Optional[Dict[str, str]]:
    """
    Extrai o ano e o número sequencial de uma string de numeroControlePNCP.
    Exemplos: '012345678901234567890123456789012345-1-0001/2024'

    Retorna um dicionário com 'ano' e 'sequencial' (sem zeros à esquerda),
    ou None se o formato for inesperado.
    """
    if not numero_controle:
        return None
    try:
        s = str(numero_controle).strip()
    except Exception:
        return None

    m = re.search(r"-(\d+)/(\d{4})$", s)
    if not m:
        return None
    sequencial = m.group(1)
    ano = m.group(2)
    try:
        sequencial_norm = str(int(sequencial))
    except Exception:
        sequencial_norm = sequencial.lstrip("0") or sequencial
    return {"ano": ano, "sequencial": sequencial_norm}

