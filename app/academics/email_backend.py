"""Django SMTP using native OS certificate validation, scoped to this backend."""
import ssl
import smtplib

import truststore
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend
from django.utils.functional import cached_property


SMTP_BACKENDS = ("django.core.mail.backends.smtp.EmailBackend",
                 "academics.email_backend.EmailBackend")


class LoginAuthentication:
    def login(self, user, password, *, initial_response_ok=True):
        self.ehlo_or_helo_if_needed()
        if "LOGIN" not in self.esmtp_features.get("auth", "").upper().split():
            raise smtplib.SMTPNotSupportedError("Configured SMTP LOGIN is not advertised.")
        self.user, self.password = user, password
        # Use exactly the challenge-response exchange validated by the CLI.
        return self.auth("LOGIN", self.auth_login, initial_response_ok=False)


class LoginSMTP(LoginAuthentication, smtplib.SMTP):
    pass


class LoginSMTPSSL(LoginAuthentication, smtplib.SMTP_SSL):
    pass


class EmailBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        method = getattr(settings, "EMAIL_SMTP_AUTH_METHOD", "auto")
        if method == "auto":
            return super().connection_class
        if method != "LOGIN":
            raise ImproperlyConfigured("EMAIL_SMTP_AUTH_METHOD must be auto or LOGIN.")
        return LoginSMTPSSL if self.use_ssl else LoginSMTP

    @cached_property
    def ssl_context(self):
        # Windows uses CryptoAPI for chain building/validation. Do not globally
        # monkey-patch ssl, disable verification, or remove OpenSSL verify flags.
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if self.ssl_certfile or self.ssl_keyfile:
            context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
        return context
