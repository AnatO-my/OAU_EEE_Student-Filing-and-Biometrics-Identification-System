from django.core.mail.backends.base import BaseEmailBackend


class DisabledEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if email_messages:
            raise OSError("Email delivery is disabled for this demonstration.")
        return 0
