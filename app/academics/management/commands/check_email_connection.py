"""Check SMTP setup, TLS and authentication without issuing MAIL/RCPT/DATA."""
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError

from academics.sharing_transport import validate_email_configuration
from academics.email_backend import SMTP_BACKENDS


def diagnostic(error):
    # Never echo raw provider errors: they may contain account or secret values.
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP authentication rejected. Verify the sender account and its Google App Password, not its normal password."
    if isinstance(error, ssl.SSLCertVerificationError):
        return "TLS certificate verification failed. Check the computer clock and Python's trusted certificates; do not disable certificate verification."
    if isinstance(error, ssl.SSLError):
        return "TLS negotiation failed. Check port/TLS settings and any antivirus or network interception."
    if isinstance(error, socket.gaierror):
        return "DNS lookup failed for the SMTP host. Check internet access and DNS settings."
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "SMTP connection or login timed out. Check internet access and whether the network/firewall permits outbound SMTP on the configured port."
    if isinstance(error, ConnectionRefusedError):
        return "SMTP connection refused. Check the SMTP host/port and network/firewall rules."
    if isinstance(error, smtplib.SMTPNotSupportedError):
        return "The server did not offer the required TLS/authentication method. Check the SMTP host and port."
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return "SMTP server disconnected during connection or login. Check network restrictions and TLS interception."
    if isinstance(error, OSError):
        return "Network/socket error while opening SMTP. Check internet access, firewall and proxy restrictions."
    return f"SMTP setup/login failed ({type(error).__name__}). No raw provider or credential values were logged."


def staged_check(connection, output, auth_method="auto"):
    """Walk the SMTP handshake explicitly; never use SMTP debug logging."""
    server = None
    stage = "TCP connection and SMTP greeting"

    def begin(name):
        nonlocal stage
        stage = name
        output.write(f"Checking: {stage}")
        output.flush()

    def ehlo(name):
        begin(name)
        code, _ = server.ehlo()
        if code != 250:
            raise CommandError(f"SMTP greeting rejected at {stage} (code {code}). No email sent.")
        output.write(f"Passed: {stage}")

    try:
        begin(stage)
        kwargs = {"timeout": connection.timeout}
        if connection.use_ssl:
            kwargs["context"] = connection.ssl_context
            server = smtplib.SMTP_SSL(connection.host, connection.port, **kwargs)
        else:
            server = smtplib.SMTP(connection.host, connection.port, **kwargs)
        output.write(f"Passed: {stage}")
        ehlo("EHLO before authentication" if connection.use_ssl else "EHLO before TLS")
        if connection.use_tls:
            begin("TLS handshake and certificate verification")
            server.starttls(context=connection.ssl_context)
            output.write(f"Passed: {stage}")
            ehlo("EHLO after TLS")
        if connection.username and connection.password:
            begin("SMTP authentication")
            if not server.has_extn("auth"):
                raise CommandError("SMTP authentication was not advertised after TLS. No email sent.")
            if auth_method == "LOGIN":
                if "LOGIN" not in server.esmtp_features.get("auth", "").upper().split():
                    raise CommandError("SMTP LOGIN was not advertised by this server. No email sent.")
                output.write("Using LOGIN challenge-response; credentials remain hidden.")
                server.user = connection.username
                server.password = connection.password
                server.auth("LOGIN", server.auth_login, initial_response_ok=False)
            else:
                server.login(connection.username, connection.password)
            output.write(f"Passed: {stage}")
        else:
            output.write("Authentication skipped: no SMTP credentials configured.")
    except CommandError:
        raise
    except Exception as error:
        raise CommandError(f"Failed at {stage}. {diagnostic(error)} No email sent.") from None
    finally:
        if server is not None:
            server.close()


class Command(BaseCommand):
    help = "Check SMTP connection, TLS and login without sending mail or processing the queue."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--stages", action="store_true",
                            help="Show the SMTP handshake stage without printing credentials or sending mail.")
        parser.add_argument("--auth-method", choices=("auto", "LOGIN"), default="auto",
                            help="Test LOGIN challenge-response instead of automatic SMTP authentication; implies --stages.")

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND not in SMTP_BACKENDS:
            raise CommandError("Configure the SMTP backend in this same terminal first. No email sent.")
        try:
            validate_email_configuration()
        except ValidationError as error:
            raise CommandError(" ".join(error.messages) + " No email sent.") from None
        self.stdout.write("Checking SMTP connection, TLS and login; no email will be sent.")
        if options["stages"] or options["auth_method"] != "auto":
            staged_check(get_connection(fail_silently=False), self.stdout, options["auth_method"])
            self.stdout.write("Staged check completed. No email sent; the queue was not accessed.")
            return
        connection = None
        try:
            connection = get_connection(fail_silently=False)
            if not connection.open():
                raise CommandError("SMTP connection could not be opened. No email sent.")
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(diagnostic(error) + " No email sent.") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    self.stderr.write("SMTP connection cleanup did not complete; no email was sent.")
        self.stdout.write("SMTP connection, TLS and login succeeded. No email sent; the delivery queue was not accessed.")
