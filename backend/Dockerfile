# Derleme bağlamı depo köküdür (docker-compose.yml: context: ., dockerfile: backend/Dockerfile)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# CPU sürümü torch (GPU sürümünden çok daha küçük), ardından diğer bağımlılıklar
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r backend/requirements.txt

COPY backend backend
COPY data/__init__.py data/__init__.py
COPY data/pipeline data/pipeline
COPY data/seed data/seed

EXPOSE 8000
CMD ["sh", "backend/start.sh"]
