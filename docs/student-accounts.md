# Student profiles and first login

The department registers the student record first. The HOD then opens that
record under **Students** and uses **Student login** to issue a linked account.
Registration and result imports never create accounts automatically. An adviser
with the appropriate assignment and permissions can register the student record;
only the HOD can issue its login.

## First login

1. As HOD, open **Students**, find the existing student or register a test
   student, then open their profile.
2. In **Student login**, use the exact student identifier as the username,
   including slashes and leading zeros, for example `TEST/2026/001`. Enter the
   student's email if access links should be emailed. Email is optional for
   manually sharing the first setup link.
3. Create the password setup link and give it privately to that student. The
   HOD never chooses or receives the student's password in this flow. No email
   is sent by this action.
4. The student opens the link, chooses and confirms a password, then signs in
   at the ordinary **Login** page using the issued username and chosen password.

The account opens the linked student's own profile, verified results,
GPA/CGPA, messages and attendance. It has no staff/HOD privileges. Existing
results and attendance remain attached to the same student UUID.

For the present laptop setup, `127.0.0.1` links work only on this laptop while
the local application is running. A student cannot open that address from a
different device. Remote hosting remains deferred.

## Link handling and recovery

A setup link expires after one hour with the default configuration and works
once. Until the student completes it, the account has no usable password and
cannot sign in. Reissuing a pending setup link invalidates the previous link.
After password setup, manual setup-link issuance cannot reset or replace the
account's password. Existing users change their password under **Account settings**
or use email password recovery. The HOD's email action sends a password-reset link
for an existing usable account; the password changes only when the student uses it.

## Matriculation usernames and email

New student logins use the exact current matriculation or UTME identifier rather
than adding `student.` or replacing `/` with `.`. An older login such as
`student.TEST.2026.001` remains unchanged until the HOD explicitly chooses
**Use matric number** on that student's record. The review shows the old and new
username. Changing it preserves the account, password and academic history, and
rejects a username already in use. Pending setup links are invalidated by a
username change; issue a fresh link afterward. Later UTME-to-matric promotion
also requires this explicit account action to change the sign-in username.

The HOD can save a student's email on the linked account, then explicitly send
a private access link to that reviewed recipient. A pending account receives a
new setup link, invalidating older setup links. An account that already has a
password receives a reset link. Neither email contains a password. SMTP provider
acceptance is displayed as submission, not proof of inbox delivery; an uncertain
outcome is not automatically resent.

Student-access email uses the privately configured SMTP sender and does not
enable the guardian email worker or process its queue. Console/file/dummy mail
backends cannot send student access links. The laptop launcher supplies the
actual frontend origin, including alternate ports, when building these emails.
`127.0.0.1` links still open only on the laptop; email alone does not make the app
reachable on another device.

The portal shows a link only after an explicit creation/reissue, keeps it in
component memory and clears it on leaving the student/account view. The setup
page uses a URL fragment rather than a server-visible query token and clears
that fragment after opening. Refreshing the cleaned page requires reopening the
original link. Keep the link private, since its holder can choose the password
while the account is pending.

If the connection fails during creation, the portal checks the safe account
status before allowing another explicit action. It never repeats account
creation or link reissue automatically. A lost pending link can be reissued by
the HOD; an account with a usable password is shown as ready for sign-in.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/students/{student_id}/account/` | HOD-only linked account status |
| PATCH | `/api/students/{student_id}/account/` | Explicitly update the saved email or adopt the current student identifier as username |
| POST | `/api/students/{student_id}/account/setup-link/` | Create a pending account or explicitly reissue its setup link |
| POST | `/api/students/{student_id}/account/email-link/` | Submit a private setup/reset link to the saved reviewed student email |
| POST | `/api/auth/student/setup/confirm/` | Public, CSRF-protected password setup |

Status returns `{account: null}` or an account object with `id`, `username`,
`email`, `is_active` and `setup_pending`. The top-level response also includes
`preferred_username`, `email_delivery_available` and `email_delivery_detail`.
Initial creation defaults to the student's exact identifier when `username` is
omitted; an explicit username and optional `email` remain accepted for compatibility.
Pending manual reissue uses an empty object. Link issuance returns
the account metadata, `uid`, `token` and `expires_in` in seconds. Confirmation
accepts `uid`, `token` and `new_password`, and returns the username and a safe
completion message without signing in or replacing any existing browser session.

PATCH requires `expected_username` and `expected_email`, plus `email` and/or
`use_student_identifier: true`. Identifier adoption also requires the reviewed
`expected_identifier_value`. Stale values or a duplicate username reject the
whole change. Email submission requires `expected_username`, `expected_email`
and `confirm_reissue: true`; these values must match the linked saved account.
It returns safe account metadata, `kind: "setup" | "reset"`, `recipient`,
`delivery_status: "accepted" | "unknown"` and `detail`, without returning the
emailed token. Invalid delivery configuration returns 503 with
`code: "student_email_not_configured"` before rotating a pending token. A generic
503 may follow a submission and is treated as uncertain. SMTP is attempted once,
after database row locks are released.

Setup tokens use a separate signing purpose from password recovery, are bound
to the linked student and current account state, and are not stored in database
rows or audit records. The server rechecks HOD authorization under row locks;
creation, linking and audit are atomic. Responses containing account status or
tokens disable caching. Password strength validation, CSRF and throttling apply.
The initial setup flow uses the existing account audit table. The later
matriculation-username update adds `accounts.0006_user_username_matriculation`,
a validator migration allowing `/`; it does
not rename existing accounts or alter their passwords.
The older HOD-only password-supplied account creation and existing-account linking
APIs remain compatible. The portal uses the setup-link workflow above.

## Activate on this laptop

Stop the local app with **Ctrl+C**. In the configured Aiven terminal, configure
Gmail privately if student access emails are wanted, then apply the update:

```powershell
. .\scripts\configure-gmail.ps1
.\scripts\update-local.ps1
```

Skip the Gmail helper if SMTP is already configured in that terminal, or if
continuing with manual setup links. The update helper backs up and verifies
restoration before applying the username-validator migration and restarting.
It does not rename accounts, change passwords or send emails automatically.
For a new terminal, first run `. ./private-data/aiven/configure.ps1` and enter the
database password privately. See [local startup](local-laptop.md).

## Verification — 22 October 2026

The full backend suite passed **466 tests on isolated PostgreSQL 18.6** in
255.850 seconds; system checks and migration drift passed. Focused setup,
legacy lifecycle, administration and messaging verification passed 60 tests,
including simultaneous first-password submissions, reissue competing with
completion, and observed setup issuance waiting for a HOD-transfer row lock.
The full-suite cluster was stopped; logs remain in
`tmp/attendance-postgres-cs982s15`.

The portal passed **83 tests**, ESLint and production build. Cases cover HOD
gating, readable username suggestions, pending/ready state, private link handling,
password mismatch, StrictMode, replacing a link in the same open page, stale
responses and uncertain/malformed success responses. A lost response does not
automatically repeat a password write or link reissue.

A synthetic localhost HTTP check created and completed a linked account,
rejected the old reissued link and a reused completed link, blocked pending
sign-in, preserved the HOD session and required a separate student sign-in.
The new student could read its own profile and existing verified result while
the staff directory and account-management endpoints were denied.

Browser checks verified the HOD profile's **Student login** section, ready state,
student sign-in, own profile and verified result. The public setup form was
inspected without entering a password; its fragment was removed from the URL.
At a 390-pixel viewport, its labelled password fields stayed within the document
width. API/component tests exercised password submission. No real student or
Aiven account was created during implementation verification.

Proof images are in `output/local-integration/student-login-hod.png`,
`student-login-ready.png`, `student-password-setup.png`,
`student-password-setup-mobile.png` and `student-first-login-profile.png`.
The test student remains in an isolated local test database, separate from Aiven.

The user subsequently confirmed successful first login on the Aiven-backed
laptop application on 22 October 2026. Their password remained private. The
email and exact-matriculation username update follows that initial verification.

## Email and matriculation update verification — 22 October 2026

The full updated backend suite passed **486 tests on isolated PostgreSQL 18.6**
in 299.034 seconds; system checks and migration drift passed. The cluster was
stopped; its logs remain in `tmp/attendance-postgres-uacym4nu`. Focused account,
email, local-startup and concurrency verification passed 80 tests. SMTP was
mocked for accepted/unknown outcomes, and configuration rejection was checked
before pending-token rotation. No real email was sent during these checks.

The portal passed **104 tests**, ESLint, production build and diff checks. The
tests exercise exact slash/zero usernames, reviewed account/email changes,
pending setup versus existing-account reset emails, fresh recipient confirmation,
configuration-specific and ambiguous failures, plus fragment and legacy-query
reset link handling under StrictMode and same-page navigation.

A synthetic localhost HTTP check explicitly renamed an existing usable account,
preserved its password/account/profile/result links, updated its reviewed email,
and confirmed that an unconfigured sender returns the safe 503 code without
sending mail. A new account defaulted to its exact identifier with slashes and
leading zeros, completed setup and signed in successfully. The HOD change review,
email controls and public reset destination were inspected in the browser.
The email controls stayed within the page at a 390-pixel viewport.

Proof images are `output/local-integration/student-matric-email-controls.png`,
`student-email-controls-mobile.png`, `student-email-reset-page.png` and
`student-matric-sign-in.png`. Live Aiven activation and actual email receipt for
this update remain user-side checks; the initial student-login confirmation
above predates these refinements.
