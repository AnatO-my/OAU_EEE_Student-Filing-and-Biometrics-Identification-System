# Prepared hosting runbook

**Hosting is deferred. These instructions are for a later reviewed deployment.**
For the active laptop setup, follow the local launcher and frontend documentation.
Do not run these commands against the verified Aiven database merely to validate
the templates. The database already contains its migrations, groups and privately
created administrator.

## Prepared artifacts

| Artifact | Purpose |
| --- | --- |
| `Dockerfile`, target `backend` | Non-root Django/Gunicorn image; same image can run the email worker. |
| `Dockerfile`, target `hosted-web` | React + Django admin static + Caddy/Gunicorn under Supervisor for a two-service PaaS layout. |
| `Dockerfile`, target `edge` | Automatic HTTPS/static edge for a separately approved Linux VM. |
| `compose.production.yml` | Portable VM layout; API port private; email worker requires the `email` profile. |
| `deployment/production.env.example` | Runtime configuration template. Real values belong only in private runtime secret storage. |
| `deployment/compose.env.example` | Nonsecret VM routing inputs. |
| `deployment/gunicorn.conf.py` | One process, two request threads, no raw access logs containing guardian tokens. |

The portal builds from `frontend/portal` with `npm ci --ignore-scripts --no-audit
--no-fund` and `npm run build`. It uses relative `/api` URLs. Caddy serves its
bundle at `/`, Django admin assets at `/static/`, and proxies `/api/`, `/admin/`
and health endpoints to Django. Unknown API routes remain Django errors instead
of returning the SPA. The integrated guardian page is
`/portal/hod/guardian-results`; the standalone legacy bundle is not deployed.

The build collects Django static files with `deployment.build_settings`, a dummy
database and a public build-only secret. `.dockerignore` allows only source needed
by the image and excludes local credentials, private data, certificates and
databases. Runtime secrets must never be build arguments. Python/Node image tags
track their maintained release families; record resolved image digests and the
source revision before any actual release. Gunicorn and Caddy are version pinned.

## Gates before any hosted rollout

1. Confirm a no-card account can access the selected ongoing free plan, private
   source and required runtime resources. Recheck current quotas and keep the
   resource estimate at $0; do not upgrade or attach a payment method.
2. Build and test both images against a disposable synthetic PostgreSQL database
   and fake email provider. Prove admin CSS, direct SPA navigation, CSRF/login,
   role restrictions, queue processing and restart recovery. Never substitute a
   real guardian address for a smoke-test destination.
3. Verify actual Aiven connectivity from Linux with `verify-full` and the service
   CA, then run `check_database_connection` and `migrate --check` read-only. The
   image uses `PSYCOPG_IMPL=python` with Debian's maintained system libpq, not the
   wheel's bundled libpq. Its compatibility with this Aiven certificate has not
   yet been tested. Never lower TLS verification to pass a check.
4. Verify backup restoration into a separate database. Preserve a release record
   and rollback target. Do not reset the integration database or replay its queue.
5. Review the exact target URL and source revision before exposure. Enable real
   email delivery only after a controlled-recipient test and explicit worker start.

`config.production_settings` requires a stable random Django secret of at least
50 characters, explicit allowed hosts, explicit HTTPS CSRF origins and
`POSTGRES_SSLMODE=verify-full`. Supply the reset URL as
`https://HOST/reset-password`. `DJANGO_TRUST_PROXY_HEADERS=true` is safe only
because the backend is unreachable directly and the supplied edge overwrites
`X-Forwarded-Proto`. Do not publish container port 8000. Start with one-hour HSTS
while validating the hostname, then deliberately extend it after HTTPS is proven.

## Candidate two-service PaaS layout

Northflank remains an unverified candidate described in `hosting-options.md`.
Use the root `Dockerfile` with repository-root build context and the following
reviewed settings if work resumes:

| Setting | Web | Email worker |
| --- | --- | --- |
| Docker target | `hosted-web` | `backend` |
| Replicas | 1 | 1 |
| Public port | HTTP 8080 only, behind provider HTTPS | None |
| Startup command | Image default | `python manage.py process_result_shares --channel email --watch --interval 5 --limit 25` |
| Liveness | HTTP `/health/live/`, port 8080 | Process restart policy; inspect queue progress |
| Readiness | HTTP `/health/ready/`, port 8080 | Read-only DB preflight before starting |
| Shutdown grace | At least 100 seconds | At least 100 seconds |

Create no extra managed database. Put CA content at runtime path
`/run/secrets/aiven_ca`, readable by UID 10001, and set `POSTGRES_SSLROOTCERT` to
that path. Put actual environment values in runtime secret storage, not build
variables. Include the generated HTTPS hostname plus `localhost,127.0.0.1` in
allowed hosts; health checks use localhost. The API and worker use the same
database and Django secret. Keep SMTP credentials restricted to required
processes. Production rejects dummy/console email backends; keep
`RESULT_SHARING_ENABLED=false` and the worker stopped until delivery is reviewed.

Northflank documents
[Docker build targets](https://northflank.com/docs/v1/application/build/build-with-a-dockerfile),
[runtime secret files](https://northflank.com/docs/v1/application/secure/upload-secret-files)
and [HTTPS ingress](https://northflank.com/docs/v1/application/network/networking-on-northflank).
Check runtime file permissions without printing file content. The combined web
container trusts its provider's HTTPS boundary; do not expose it directly over
public plain HTTP. Provider HTTP ingress must redirect to HTTPS.

The ordinary database budget is two simultaneous API request connections and one
email worker connection, with `CONN_MAX_AGE=0`. Leave room within Aiven's total
20 connections for provider sessions, administrative checks and deploy overlap.
Do not increase Gunicorn processes or replicas without revisiting connections
and replacing the process-local authentication throttle cache with a shared cache.

## Portable VM commands, only on an approved existing host

This option does not authorize creating a VM, buying a domain or supplying a
card. Install maintained Docker/Compose on a separately approved Linux host.
The Compose file needs version 2.30 or newer for raw environment-file support.
Create private runtime files with restrictive host permissions. The example
paths are `private-data/deployment/production.env` and
`private-data/aiven/ca.pem`; those directories stay outside Git/build context.
Use literal `KEY=value` lines in the runtime environment file: no shell expansion
or quotation wrapping, because Compose reads it in raw mode.

```sh
docker compose --env-file deployment/compose.env.example -f compose.production.yml config --quiet
docker compose --env-file deployment/compose.env.example -f compose.production.yml build --pull
docker compose --env-file deployment/compose.env.example -f compose.production.yml run --rm --no-deps api python manage.py check --deploy
docker compose --env-file deployment/compose.env.example -f compose.production.yml run --rm --no-deps api python manage.py check_database_connection
docker compose --env-file deployment/compose.env.example -f compose.production.yml run --rm --no-deps api python manage.py migrate --check
docker compose --env-file deployment/compose.env.example -f compose.production.yml up -d api edge
```

Replace the nonsecret routing template with reviewed hostname/contact values
before running. Open only 80/443 publicly; restrict SSH and keep application and
database ports private. Preserve Caddy's data volume for certificate state.
Migrations are a deliberate separate action after a backup and review; container
startup never runs them. Enable the `email` profile only after the delivery gate:

```sh
docker compose --env-file deployment/compose.env.example -f compose.production.yml --profile email up -d email-worker
```

On rollback, stop the worker first and restore the prior application images.
Do not automatically roll back schema or retry ambiguous deliveries: a provider
may have accepted mail before the worker lost its connection. Review uncertain
attempts using the existing reconciliation workflow. Logs and public health
responses must not reveal database credentials, guardian tokens or message bodies.

## Verification status

Static-file collection was checked locally using an isolated dummy database.
Docker/Compose and Linux runtime validation remain pending because Docker is
unavailable here. Caddy binary download failed before checksum validation; no
downloaded binary was executed. No claim is made of successful image builds,
hosted health checks, hosted Aiven TLS, SMTP egress or cloud backup restoration.
