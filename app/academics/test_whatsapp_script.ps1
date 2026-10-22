$env:WHATSAPP_ACCESS_TOKEN = [System.Net.NetworkCredential]::new("", (Read-Host "WhatsApp access token" -AsSecureString)).Password
$env:WHATSAPP_PHONE_NUMBER_ID = "1387603647765468"
$env:WHATSAPP_BUSINESS_ACCOUNT_ID = "1079910328198118"
$env:WHATSAPP_API_VERSION = "YOUR_SUPPORTED_VERSION"
$env:WHATSAPP_RESULT_TEMPLATE = "EEE_RESULT_TEMPLATE"
$env:WHATSAPP_TEMPLATE_LANGUAGE = "en_US"

# Recipient who agreed to receive the test:
$env:MOCK_RESULT_PHONE = "+2348086877498"

@'
import os
from types import SimpleNamespace
from django.test import override_settings
from academics.sharing_transport import validate_transport, submit_whatsapp

report = (
    "TEST ONLY - fictional student results. "
    "Student: Example Student (MOCK-001). "
    "Session: 2026/2027; semester: harmattan. "
    "EEE301: score 70, units 3, grade point 5. "
    "EEE303: score 60, units 3, grade point 4. "
    "EEE305: score 40, units 3, grade point 1. "
    "Semester GPA: 3.333333333333333333333333333. "
    "CGPA: 3.333333333333333333333333333."
)

delivery = SimpleNamespace(
    destination=os.environ["MOCK_RESULT_PHONE"],
    body=report,
)

with override_settings(RESULT_SHARING_ENABLED=True):
    validate_transport("whatsapp")
    message_id = submit_whatsapp(delivery)
    print("WhatsApp accepted the test submission:", message_id)
'@ | .\.venv\Scripts\python.exe manage.py shell