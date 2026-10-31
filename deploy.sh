#!/usr/bin/env bash
# Construye la imagen y la publica en Cloud Run. Uso: ./deploy.sh
# Para versionar los cambios en git: hacer commit y push aparte, con un mensaje que los describa.
set -euo pipefail

PROYECTO=soy-radius-332400
SERVICIO=com-icg-futbolsim
IMAGEN="gcr.io/$PROYECTO/$SERVICIO"
TAG="$(date +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)"

gcloud builds submit --project "$PROYECTO" --tag "$IMAGEN:$TAG"
gcloud run deploy "$SERVICIO" --image "$IMAGEN:$TAG" --platform managed --region us-central1 --project "$PROYECTO" --allow-unauthenticated

echo "Publicado $IMAGEN:$TAG"

# --- Una sola vez: clave del pulso y job del Cloud Scheduler (ya creados en producción) ---
# CLAVE=$(openssl rand -hex 32); echo "$CLAVE"
# gcloud run services update com-icg-futbolsim --region us-central1 --project soy-radius-332400 --update-env-vars PULSO_CLAVE=$CLAVE
# gcloud scheduler jobs create http pulso-futbolsim --project soy-radius-332400 --location us-central1 --schedule "* * * * *" --time-zone "America/Mexico_City" --uri "https://com-icg-futbolsim-vs5mrijyjq-uc.a.run.app/tareas/pulso" --http-method POST --headers "X-Pulso-Clave=$CLAVE" --attempt-deadline 180s --max-retry-attempts 0
