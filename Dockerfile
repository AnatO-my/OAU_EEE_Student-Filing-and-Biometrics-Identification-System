# syntax=docker/dockerfile:1
# Record the resolved image digests with each release; rebuild for security updates.
ARG NODE_IMAGE=node:24-bookworm-slim
ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG CADDY_IMAGE=caddy:2.11.7-alpine

FROM ${NODE_IMAGE} AS portal-build
WORKDIR /build/portal
COPY frontend/portal/package.json frontend/portal/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/portal/ ./
COPY frontend/guardian-results/src/ /build/guardian-results/src/
RUN npm run build

FROM ${PYTHON_IMAGE} AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/eee/app:/srv/eee \
    DJANGO_SETTINGS_MODULE=config.production_settings \
    PSYCOPG_IMPL=python
WORKDIR /srv/eee
# Use the maintained system libpq rather than the binary wheel's bundled libpq.
# PostgreSQL server and client major versions need not match for connections.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
COPY deployment/requirements.txt deployment/requirements.txt
RUN pip install --no-cache-dir -r deployment/requirements.txt
COPY app/ app/
COPY manage.py ./
COPY deployment/ deployment/
COPY deployment/caddy-routes /srv/eee-caddy-routes
# Build public Django/admin static assets with a dummy DB and no real secrets.
RUN DJANGO_SECRET_KEY=build-only-not-a-runtime-secret DJANGO_DEBUG=false \
    python manage.py collectstatic --noinput --settings=deployment.build_settings
RUN groupadd --gid 10001 eee && useradd --uid 10001 --gid 10001 --no-create-home eee
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--config", "deployment/gunicorn.conf.py", "config.wsgi:application"]

# An independent TLS/static edge for a Linux VM running compose.production.yml.
FROM ${CADDY_IMAGE} AS edge
COPY --from=portal-build /build/portal/dist /srv/portal
COPY --from=backend /srv/static /srv/static
COPY deployment/Caddyfile /etc/caddy/Caddyfile
COPY deployment/caddy-routes /srv/eee-caddy-routes

# Two-service PaaS layout: this web container plus the backend image as a worker.
# The PaaS must terminate HTTPS and route ONLY its public HTTPS endpoint here.
FROM backend AS hosted-web
USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends supervisor \
    && rm -rf /var/lib/apt/lists/*
COPY --from=edge /usr/bin/caddy /usr/local/bin/caddy
COPY --from=portal-build /build/portal/dist /srv/portal
ENV GUNICORN_BIND=127.0.0.1:8000 XDG_DATA_HOME=/tmp/caddy/data XDG_CONFIG_HOME=/tmp/caddy/config
USER 10001:10001
EXPOSE 8080
CMD ["supervisord", "--nodaemon", "--configuration", "/srv/eee/deployment/supervisord.conf"]
