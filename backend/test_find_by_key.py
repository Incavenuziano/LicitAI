# -*- coding: utf-8 -*-
import json
import re
import sys
import os

# Adiciona o diretório raiz ao path para encontrar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.integrations.pncp import pncp_compra_por_chave

# Dados do caso de teste fornecido pelo usuário
cnpj_raw = "09.572.680/0002-73"
ano = 2025
sequencial = 90016

# Limpa o CNPJ para enviar apenas os números, como a API pode esperar
cnpj = re.sub(r'[.\/-]', '', cnpj_raw)

print(f"Buscando no PNCP com a chave: CNPJ={cnpj}, Ano={ano}, Sequencial={sequencial}")

# Chama a função
result = pncp_compra_por_chave(cnpj=cnpj, ano=ano, sequencial=sequencial)

if result:
    print("\n--- SUCESSO! Dados encontrados no PNCP: ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print("\n--- FALHA: Nenhum resultado encontrado para esta chave. ---")
