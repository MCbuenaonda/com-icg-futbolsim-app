gcloud builds submit --tag gcr.io/soy-radius-332400/com-icg-futbolsim:20261029-0954-420ad9b
gcloud run deploy com-icg-futbolsim --image gcr.io/soy-radius-332400/com-icg-futbolsim:20261029-0954-420ad9b --platform managed --region us-central1 --project soy-radius-332400 --allow-unauthenticated

# CLAVE=$(openssl rand -hex 32); echo "$CLAVE"
# gcloud run services update com-icg-futbolsim --region us-central1 --project soy-radius-332400 --update-env-vars PULSO_CLAVE=$CLAVE
# gcloud scheduler jobs create http pulso-futbolsim --project soy-radius-332400 --location us-central1 --schedule "* * * * *" --time-zone "America/Mexico_City" --uri "https://com-icg-futbolsim-vs5mrijyjq-uc.a.run.app/tareas/pulso" --http-method POST --headers "X-Pulso-Clave=$CLAVE" --attempt-deadline 180s --max-retry-attempts 0