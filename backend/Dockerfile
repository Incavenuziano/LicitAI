# 1. Imagem Base: Começamos com uma imagem oficial do Python.
# A tag 'slim' é uma versão mais leve, ótima para produção.
FROM python:3.11-slim

# 2. Variáveis de Ambiente: Boas práticas para Python em Docker.
#    - PYTHONDONTWRITEBYTECODE: Impede o Python de criar arquivos .pyc.
#    - PYTHONUNBUFFERED: Garante que os logs (prints) apareçam em tempo real.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Diretório de Trabalho: Define o diretório principal dentro do contêiner.
WORKDIR /app

# 4. Instalar Dependências:
#    - Primeiro, copiamos apenas o 'requirements.txt' para aproveitar o cache do Docker.
#    - Se este arquivo não mudar, o Docker não reinstala tudo de novo, acelerando o build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar o Código-Fonte:
#    - Copia todo o resto do código do backend para dentro do contêiner.
COPY . .

# 6. Comando de Execução:
#    - Diz ao contêiner qual comando executar quando ele iniciar.
#    - Usamos 0.0.0.0 para que a API seja acessível de fora do contêiner.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
