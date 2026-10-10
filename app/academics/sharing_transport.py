"""Provider adapters. Acceptance is not delivery/read confirmation."""
import json
import re
import smtplib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage


class RejectedSubmission(Exception):
    pass


class UncertainSubmission(Exception):
    pass


def validate_transport(channel):
    if not settings.RESULT_SHARING_ENABLED:
        raise ValidationError("Enable configured result delivery before queuing reports.")
    if channel == "email":
        if settings.EMAIL_BACKEND in ("django.core.mail.backends.console.EmailBackend",
                "django.core.mail.backends.dummy.EmailBackend", "django.core.mail.backends.filebased.EmailBackend"):
            raise ValidationError("Configure a real email provider before queuing result emails.")
    else:
        values = (settings.WHATSAPP_ACCESS_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID,
                  settings.WHATSAPP_API_VERSION, settings.WHATSAPP_RESULT_TEMPLATE,
                  settings.WHATSAPP_TEMPLATE_LANGUAGE)
        if not all(values):
            raise ValidationError("Configure the WhatsApp Cloud API and approved result template.")
        if not re.fullmatch(r"v[0-9]+\.[0-9]+", settings.WHATSAPP_API_VERSION) or not re.fullmatch(
                r"[0-9]+", settings.WHATSAPP_PHONE_NUMBER_ID):
            raise ValidationError("Invalid WhatsApp API version or phone-number ID.")


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
