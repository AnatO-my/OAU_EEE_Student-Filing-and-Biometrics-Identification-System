# Guardian result email: initial Gmail setup

17 October 2026. The initial version uses one server-configured sender selected
and authorized by the HOD. That may be the HOD's Gmail/Google Workspace mailbox.
The HOD configures access once; the application sends on that account's behalf.
The application login password and the Google account password stay separate.
Changing the sender is a deployment setting, not an ordinary guardian/profile edit.

## What the HOD does

1. Choose the sending account. A department-controlled mailbox makes handover to
   the next HOD easier, but the initial configuration also accepts a personal account.
2. Enable Google 2-Step Verification and create an App Password for this backend.
   Do not enter the normal Google password into this project or send secrets in chat.
3. Supply the sender address and App Password privately to the server configuration.
4. Sign in to the portal as HOD, choose students/session/semester, review each
   guardian's report and eligibility, then click Send.

Google documents App Password requirements and account restrictions at
https://support.google.com/mail/answer/185833?hl=en . Managed school/work accounts
may restrict availability; if it is unavailable, do not disable account security.
A future Google OAuth connection is a separate feature. There is currently no
per-HOD Connect Gmail screen or storage of Gmail credentials in User records.

The Gmail SMTP structure is smtp.gmail.com, port 587, STARTTLS, full account
address and App Password. The From address uses that same account. Google SMTP
reference: https://support.google.com/a/answer/176600?hl=en .

## What “interface and worker” means

The interface is the page where the HOD chooses students and reviews reports.
The existing backend already provides preview, queue, status and retry endpoints;
the React page still needs to connect those endpoints.

Clicking Send queues one separate email per eligible guardian. A background
worker takes emails from that queue, sends them and records the outcome. This
keeps the browser from waiting for hundreds of SMTP calls. The HOD does not run
the worker manually; deployment runs it under a scheduler/service.

The current command processes a bounded amount of queued work and then exits:

```powershell
.\.venv\Scripts\python.exe manage.py process_result_shares --limit 100
```

It processes both configured channels. Do not run it merely to test Gmail: it
may send already queued real reports. Use the isolated mock command below.
SMTP acceptance is not proof of inbox delivery. Uncertain submissions are not
automatically retried; the existing HOD workflow supports reviewed known failures.

## Prepare this Windows terminal

From the repository root:

```powershell
.\scripts\configure-gmail.ps1
```

It prompts for the sender and hidden App Password, then configures the current
PowerShell process and its child processes. It sends nothing, writes no credentials
to disk, and does not enable bulk sharing. Keep the same terminal for the test.
Closing this terminal ends this setup. For deployment, use private server secret
configuration and restart the API/worker with those settings.

These are the equivalent environment keys, with placeholders only:

```text
DJANGO_EMAIL_BACKEND=academics.email_backend.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=true
DJANGO_EMAIL_AUTH_METHOD=LOGIN
DJANGO_EMAIL_HOST_USER=the-chosen-account@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=GOOGLE_APP_PASSWORD
DJANGO_DEFAULT_FROM_EMAIL=EEE Department <the-chosen-account@gmail.com>
```

`.env.example` is documentation; manage.py does not automatically load a .env
file. Use the setup script for a local terminal, or inject variables from your
deployment's secret configuration. Never put the App Password in source control,
browser storage, application logs or a shared setup example.

Before sending, check connection/TLS/login without sending any mail:

```powershell
.\.venv\Scripts\python.exe manage.py check_email_connection
```

Run it in the same configured terminal. It distinguishes certificate, DNS,
authentication and network/timeout problems without logging passwords or raw
provider responses. It does not access students or the delivery queue. If a mock
send reported an uncertain outcome, inspect Inbox/Spam before trying again;
use this connection check for diagnosis instead of repeated sends.

If a disconnect remains ambiguous, use the staged check in the same terminal:

```powershell
.\.venv\Scripts\python.exe manage.py check_email_connection --stages
```

It prints progress for the SMTP greeting, EHLO, TLS and authentication. It does
not print credentials, AUTH payloads or raw server replies, and sends no mail.
An Avast certificate confirms inspection, but a persistent disconnect alone
does not prove Avast caused it; use the reported failure stage to investigate.

If every handshake stage passes but automatic authentication disconnects, test
LOGIN challenge-response without sending mail:

```powershell
.\.venv\Scripts\python.exe manage.py check_email_connection --auth-method LOGIN
```

This diagnostic keeps TLS verification enabled, requires LOGIN to be advertised
and does not fall back or retry automatically. The native SMTP backend now also
supports DJANGO_EMAIL_AUTH_METHOD=LOGIN to use this same exchange for actual mail;
the Gmail setup script sets it. The default outside that setup remains auto.
On the local probe, both initial AUTH PLAIN
and AUTH LOGIN commands received a 334 challenge without supplying credentials;
the authenticated result still requires the account owner's configured terminal.

The account owner subsequently confirmed successful LOGIN authentication after
updating the Google App Password. To use it for the mock message in the already
configured terminal, set `$env:DJANGO_EMAIL_AUTH_METHOD = "LOGIN"` before running
send_mock_guardian_email. Do not repeat the earlier uncertain sends automatically.

### Windows certificate-chain compatibility

The Gmail setup script selects academics.email_backend.EmailBackend, which uses
truststore's native OS certificate validation for this SMTP connection only.
Certificate and hostname verification stay enabled. No global SSL monkey-patch
or unverified context is used. Install the pinned dependency with the project
requirements on each deployment.

On the local Windows test, the default OpenSSL context rejected the presented
chain with code 89 (CA Basic Constraints not marked critical); native Windows
validation passed the same SMTP TLS handshake. This does not establish which
product or network supplied the problematic certificate. If native validation
also fails, retain the failure and investigate the chain/administrator trust setup.

To switch an already configured terminal without re-entering credentials:

```powershell
$env:DJANGO_EMAIL_BACKEND = "academics.email_backend.EmailBackend"
.\.venv\Scripts\python.exe manage.py check_email_connection
```

Only attempt the mock send after this check succeeds and earlier uncertain
submissions have been checked in the receiving mailbox. Restart API/worker
processes with the same backend setting for real deployments.

References: https://truststore.readthedocs.io/en/stable/ and
https://docs.python.org/3.13/library/ssl.html .

On 17 October the follow-up connection-only probe passed SMTP greeting, EHLO,
native TLS validation and EHLO after TLS. The verified certificate issuer was
Avast Web/Mail Shield Root, confirming local mail interception. No credentials
were used in that probe; the user's authenticated check still disconnected.
This does not yet prove Avast caused the disconnect. A narrow diagnostic is to
temporarily turn off only Mail Shield's Scan outbound emails (SMTP), rerun the
no-send connection check, then restore that setting and compare results. Leave
other shields and application certificate verification enabled. If behavior
changes, resolve the Avast configuration with its supported settings/administrator
before relying on unattended sending.
Official Windows setting reference:
https://support.avast.com/en-us/article/Antivirus-email-signature/ .

## Test one fictional email

First preview without credentials or network access:

```powershell
.\.venv\Scripts\python.exe manage.py send_mock_guardian_email
```

Then, after configuring Gmail, send exactly one report to your own address or an
agreed test recipient (replace the placeholder):

```powershell
.\.venv\Scripts\python.exe manage.py send_mock_guardian_email --to "YOUR_TEST_RECIPIENT_EMAIL" --send
```

The message is labelled TEST ONLY, uses fictional scores and the actual GPA/CGPA
calculation functions, includes a prior failed attempt, and reads/writes no student
or delivery records. It bypasses the bulk enable switch only for this fictional
single-message test; it does not enable or drain the production queue.

Check Inbox and Spam, sender identity, subject, course scores/units and averages.
The expected display values are GPA 3.29 and CGPA 2.30. Report only success or a
redacted error; keep the App Password private. If the submission is uncertain,
check the mailbox before trying again. A timeout can occur after server acceptance.

## Enable real bulk sending later

Set RESULT_SHARING_ENABLED=true only after the sender, actual recipients,
guardian channel preferences and deployment worker are ready. Preview an
email-only batch with channels=["email"] if WhatsApp is not ready. Existing
guardian-sharing permissions and verified-result checks still apply.

Gmail has sending limits and can temporarily reject further messages; do not
assume --limit 100 is a daily provider quota. Personal Gmail and Workspace limits
differ. See https://support.google.com/mail/answer/22839?hl=en . Keep each
guardian's report separate; never use a group recipient list to evade limits.
Larger deployments can replace SMTP provider settings without changing the HOD's
review and Send workflow.
