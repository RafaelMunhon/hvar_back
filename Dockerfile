# Use uma imagem base do Python
FROM python:3.9-slim

# Instala o ffmpeg com suporte completo
RUN apt-get update && \
    apt-get install -y ffmpeg libavcodec-extra && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask==2.0.1 werkzeug==2.0.3

# Copia o resto do código
COPY . .

# Copia o arquivo de credenciais
COPY conteudo-autenticare-d2aaae9aeffe.json .
#COPY conteudo-autenticare-d2aaae9aeffe.json /app/
#ENV GOOGLE_APPLICATION_CREDENTIALS=/conteudo-autenticare-d2aaae9aeffe.json

# Cria diretórios necessários
RUN mkdir -p app/arquivosTemporarios \
    app/videosFinalizados \
    app/videosEstudio \
    app/downloadHeygen \
    app/output_jsons \
    app/videoPexel/logo

# Define variáveis de ambiente
ENV HOST=0.0.0.0
ENV PORT=8080
# Timeouts alinhados com TimeoutConfig
ENV TIMEOUT=600
ENV GRACEFUL_TIMEOUT=300
ENV KEEPALIVE=120
ENV WORKERS=1
ENV THREADS=8
ENV MAX_REQUESTS=0
ENV WORKER_CLASS=gthread

# Expõe a porta que a aplicação vai usar
EXPOSE 8080

# Comando para rodar a aplicação com configurações otimizadas
CMD exec gunicorn \
    --bind :$PORT \
    --workers $WORKERS \
    --threads $THREADS \
    --timeout $TIMEOUT \
    --worker-class $WORKER_CLASS \
    --max-requests $MAX_REQUESTS \
    --graceful-timeout $GRACEFUL_TIMEOUT \
    --keep-alive $KEEPALIVE \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app.main:app