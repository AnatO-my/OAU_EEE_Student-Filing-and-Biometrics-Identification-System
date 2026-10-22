"""Provider adapters. Acceptance is not delivery/read confirmation."""
import json
import re
import smtplib
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.mail import EmailMessage

from .email_backend import SMTP_BACKENDS


# Mark a provider response that definitively refused a delivery submission.
class RejectedSubmission(Exception):
    pass


# Mark a transport outcome where provider acceptance cannot safely be determined.
class UncertainSubmission(Exception):
    pass


def validate_email_configuration():
    """Validate SMTP setup without connecting or exposing account secrets."""
    if settings.EMAIL_BACKEND not in SMTP_BACKENDS:
        return
    host = settings.EMAIL_HOST.strip().lower()
    if not host or host in ("localhost", "127.0.0.1"):
        raise ValidationError("Configure the sending email provider's SMTP host.")
    sender = settings.DEFAULT_FROM_EMAIL
    if "\r" in sender or "\n" in sender:
        raise ValidationError("Invalid sender address.")
    address = parseaddr(sender)[1]
    validate_email(address)
    if address.rsplit("@", 1)[-1].lower().endswith(".invalid"):
        raise ValidationError("Configure the actual sending email address.")
    if host == "smtp.gmail.com":
        validate_email(settings.EMAIL_HOST_USER)
        if not settings.EMAIL_HOST_PASSWORD:
            raise ValidationError("Configure the Gmail App Password privately on the server.")
        if address.casefold() != settings.EMAIL_HOST_USER.casefold():
            raise ValidationError("Use the configured Gmail account as the sender address.")
        tls = settings.EMAIL_USE_TLS
        ssl = settings.EMAIL_USE_SSL
        if not ((tls and not ssl and settings.EMAIL_PORT == 587) or
                (ssl and not tls and settings.EMAIL_PORT == 465)):
            raise ValidationError("Gmail requires TLS on port 587 or SSL on port 465.")


# Ensure the selected delivery channel has a usable real provider configuration.
def validate_transport(channel):
    if not settings.RESULT_SHARING_ENABLED:
        raise ValidationError("Enable configured result delivery before queuing reports.")
    if channel == "email":
        if settings.EMAIL_BACKEND in ("django.core.mail.backends.console.EmailBackend",
                "django.core.mail.backends.dummy.EmailBackend", "django.core.mail.backends.filebased.EmailBackend"):
            raise ValidationError("Configure a real email provider before queuing result emails.")
        validate_email_configuration()
    else:
        values = (settings.WHATSAPP_ACCESS_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID,
                  settings.WHATSAPP_API_VERSION, settings.WHATSAPP_RESULT_TEMPLATE,
                  settings.WHATSAPP_TEMPLATE_LANGUAGE)
        if not all(values):
            raise ValidationError("Configure the WhatsApp Cloud API and approved result template.")
        if not re.fullmatch(r"v[0-9]+\.[0-9]+", settings.WHATSAPP_API_VERSION) or not re.fullmatch(
                r"[0-9]+", settings.WHATSAPP_PHONE_NUMBER_ID):
            raise ValidationError("Invalid WhatsApp API version or phone-number ID.")


# Send one email and distinguish explicit rejection from an ambiguous transport failure.
def submit_email(delivery):
    try:
        count = EmailMessage(delivery.subject, delivery.body, settings.DEFAULT_FROM_EMAIL,
            [delivery.destination], headers={"Message-ID": f"<result-share-{delivery.pk}@student-records.invalid>"}).send()
        if count != 1:
            raise RejectedSubmission()
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
            smtplib.SMTPAuthenticationError, smtplib.SMTPDataError):
        raise RejectedSubmission() from None
    except RejectedSubmission:
        raise
    except Exception:
        # Transport exceptions can occur after server acceptance: do not auto-retry.
        raise UncertainSubmission() from None
    return ""


# Submit one approved WhatsApp template and return its provider message identifier.
def submit_whatsapp(delivery):
    payload = {"messaging_product": "whatsapp", "to": delivery.destination[1:],
        "type": "template", "template": {"name": settings.WHATSAPP_RESULT_TEMPLATE,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE}, "components": [
                {"type": "body", "parameters": [{"type": "text", "text": delivery.body}]}]}}
    request = Request(f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read(65536))
        provider_id = data["messages"][0]["id"]
        if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
            raise ValueError()
        return provider_id
    except HTTPError as error:
        if 400 <= error.code < 500 and error.code != 408:
            raise RejectedSubmission() from None
        raise UncertainSubmission() from None
    except (URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError, OSError):
        raise UncertainSubmission() from None
