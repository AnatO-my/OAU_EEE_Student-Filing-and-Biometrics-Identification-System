"""Read-only PostgreSQL connectivity check without logging credentials or provider errors."""

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections


def diagnostic(error):
    """Classify failures using fixed messages; never return provider text."""
    cause = error.__cause__ or error
    sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    by_sqlstate = {
        "28P01": "Authentication rejected; verify the database user and password.",
        "28000": "Connection authorization rejected; check the database role and service access rules.",
        "3D000": "Database not found; verify the database name from Aiven.",
        "42501": "The database role lacks permission for this operation.",
        "53300": "Connection limit reached; stop unused application or database-client connections.",
        "57P03": "PostgreSQL is not ready; wait until the service is Running.",
    }
    if sqlstate in by_sqlstate:
        return by_sqlstate[sqlstate]

    # libpq connection errors often have no SQLSTATE. Inspect their text locally
    # but emit only these fixed explanations, never a hostname, URI or password.
    message = str(error).casefold()
    categories = (
        (("certificate contains ip address with invalid length",),
         "The PostgreSQL client rejected an IP-address entry in the server certificate. "
         "Use the documented compatible Windows client libraries; keep SSL mode verify-full."),
        (("no password supplied", "password is required"),
         "No database password was supplied; run the private setup prompt in this same terminal."),
        (("password authentication failed", "authentication failed"),
         "Authentication rejected; verify the database user and password."),
        (("could not translate host name", "failed to resolve host", "getaddrinfo", "name or service not known"),
         "DNS lookup failed; check the hostname and network DNS access."),
        (("root certificate file", "certificate verify failed", "certificate verification failed", "does not match host name"),
         "TLS certificate verification failed; check the service CA file and hostname. Keep verification enabled."),
        (("timeout expired", "timed out"),
         "Connection timed out; check service status and outbound access to the configured port."),
        (("connection refused", "actively refused"),
         "The TCP connection was refused; check the service status, host and port."),
        (("server closed the connection", "connection reset", "forcibly closed", "eof detected"),
         "The remote connection was closed during setup; check service status and retry the read-only check."),
    )
    for patterns, explanation in categories:
        if any(pattern in message for pattern in patterns):
            return explanation
    return "Check service status, hostname, port, password, CA certificate and network access."


class Command(BaseCommand):
    help = "Check PostgreSQL connectivity, TLS, capacity and schema presence without changing data."
    requires_system_checks = []
    requires_migrations_checks = False

    def handle(self, *args, **options):
        connection = connections["default"]
        if connection.vendor != "postgresql":
            raise CommandError(
                "Select config.postgres_settings and configure POSTGRES_* first. "
                "The default SQLite database is not a hosted connection test."
            )

        stage = "connection, TLS and authentication"
        try:
            self.stdout.write(f"Checking: {stage}")
            self.stdout.flush()
            connection.ensure_connection()
            self.stdout.write(f"Passed: {stage}")
            stage = "read-only database diagnostics"
            self.stdout.write(f"Checking: {stage}")
            self.stdout.flush()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('server_version'), "
                    "current_setting('max_connections')::integer, "
                    "pg_database_size(current_database()), "
                    "(SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()), "
                    "to_regclass('django_migrations') IS NOT NULL"
                )
                version, max_connections, size_bytes, tls, has_migrations = cursor.fetchone()
            sslmode = connection.settings_dict.get("OPTIONS", {}).get("sslmode")
            if sslmode in {"require", "verify-ca", "verify-full"} and not tls:
                raise CommandError("The connection did not report TLS. No database changes were made.")
            self.stdout.write(f"PostgreSQL version: {version}")
            self.stdout.write(f"TLS active: {'yes' if tls else 'no'}; configured SSL mode: {sslmode or 'libpq default'}")
            self.stdout.write(f"Server connection limit: {max_connections} (provider connections also count)")
            self.stdout.write(f"Database size: {size_bytes / (1024 * 1024):.2f} MiB")
            self.stdout.write(f"Django migration table present: {'yes' if has_migrations else 'no'}")
            self.stdout.write(self.style.SUCCESS("Read-only connection check passed. No tables or records changed."))
        except DatabaseError as error:
            raise CommandError(
                f"PostgreSQL connection check failed at {stage}. {diagnostic(error)} "
                "Raw provider errors and credentials were suppressed."
            ) from None
        finally:
            connection.close()
