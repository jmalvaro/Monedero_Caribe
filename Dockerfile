FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY carga ./carga
COPY scripts ./scripts
EXPOSE 8050
# Las variables de conexión se pasan al ejecutar: docker run --env-file .env -p 8050:8050 monedero-caribe
CMD ["sh", "-c", "gunicorn app.main:server --bind 0.0.0.0:${PORT:-8050} --workers 1 --threads 4 --timeout 120"]
