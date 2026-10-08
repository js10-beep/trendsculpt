FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package*.json ./
RUN --mount=type=secret,id=environment_ca \
    if [ -f /run/secrets/environment_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/environment_ca; fi; \
    npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/requirements.lock.txt ./server/requirements.lock.txt
RUN --mount=type=secret,id=environment_ca \
    if [ -f /run/secrets/environment_ca ]; then export PIP_CERT=/run/secrets/environment_ca; fi; \
    pip install --no-cache-dir -r server/requirements.lock.txt
COPY server ./server
COPY scripts/prepare_models.py ./scripts/prepare_models.py
RUN --mount=type=secret,id=environment_ca \
    if [ -f /run/secrets/environment_ca ]; then export SSL_CERT_FILE=/run/secrets/environment_ca; fi; \
    python scripts/prepare_models.py --skip-metadata
COPY --from=frontend /build/dist ./dist
RUN useradd --system --uid 10001 --create-home sculpt && chown -R sculpt:sculpt /app
USER sculpt
VOLUME ["/app/.data"]
EXPOSE 8000
CMD ["python", "-m", "server.start"]
