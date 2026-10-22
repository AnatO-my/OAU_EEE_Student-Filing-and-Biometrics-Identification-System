# Guardian email page validation — 18 October 2026

Implemented a separate React HOD page in frontend/guardian-results, linked from
the disposable prototype. The API adapter is reusable when the finished frontend
is merged. It uses the existing authenticated Django APIs, not prototype records.

## Automated checks

- Full backend: 360 tests discovered; successful run with 15 skipped. Command:
  `.\.venv\Scripts\python.exe manage.py test students accounts academics attendance --settings=config.test_settings`.
  Localhost HTTP tests required execution outside the restricted socket sandbox.
- Focused sharing/worker/email setup run: 55 tests passed.
- Frontend: 13 Vitest tests passed; production Vite build passed.
- Migration check: no changes detected with config.test_settings.
- git diff --check: passed.

The SQLite run does not establish PostgreSQL concurrent-worker behavior. Run the
PostgreSQL checks before deployment; passing SQLite checks are not a replacement.

## Browser integration

Used an isolated private SQLite database with one synthetic HOD, three fictional
students and guardian addresses under example.test. Email transport was explicitly
in memory. No production records, credentials or provider submissions were used.

Verified session login and CSRF, student selection, saving guardian email-sharing
permission, report preview and review gating, queuing, email-only worker processing,
status refresh and reopening batch history. Two individual messages were accepted
by the in-memory transport and one unverified result was skipped. No CC/BCC or
shared-recipient submission was produced. Sign-out removed the private workspace.
At a 390-pixel viewport, no horizontal page overflow was observed; the temporary
viewport override was reset afterward.

Screenshot: ../output/guardian-results-browser-check.png (synthetic data only).
The temporary test servers were stopped after verification. Private test databases
were retained; no development/shared database migrations were applied.

The user had separately confirmed receipt of a live synthetic Gmail mock email
during SMTP setup. This browser run did not send another real email.

## Deployment still required

Adapt deploy/result-email-worker.service and privately supply the environment
described by deploy/result-email-worker.env.example. These are prepared templates;
no service/scheduled task has been installed or activated. Use the same PostgreSQL
database and provider settings for the API and worker. See the React README for
local startup, the HOD workflow and production merge instructions.
