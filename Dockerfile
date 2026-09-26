# Imagen de FutbolSim (FastAPI + Jinja2) lista para Cloud Run / cualquier runtime de contenedores en GCP.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias primero: esta capa se cachea mientras requirements.txt no cambie.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Sin root dentro del contenedor.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run inyecta PORT (8080 por defecto); en local se puede sobreescribir con -e PORT=...
ENV PORT=8080
EXPOSE 8080

# --proxy-headers/--forwarded-allow-ips: detrás del balanceador de Cloud Run el tráfico llega por
# HTTP interno; sin esto, request.url_for(...) (usado en los redirects de login/logout) generaría
# URLs http:// en vez de https://.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
