# Registration and import frontend — 21 October 2026

The portal exposes **Register student** under Students and **Upload results**
for permitted HOD/adviser accounts. It uses the signed-in identity,
effective permissions and current adviser levels; no public role selection or
automatic account creation is introduced.

Registration checks the textual matriculation/UTME identifier first. A known
scoped student opens the existing record. Missing students can be registered
with approved biodata; optional phone/surname may remain blank. Authorized staff
can complete profile details. Only the HOD can promote a UTME identifier to
matriculation, with expected-current-identity and explicit review guards.

Result uploads provide PDF conversion, a result CSV template, strict UTF-8 reading,
stable request UUIDs, complete proposed rows/counts, per-correction approvals/reasons
and a final reviewed commit. File changes invalidate review. Stale previews require refresh;
uncertain commits offer saved receipt recovery. Own-batch history resumes a
preview or receipt after navigation/reload. No personal data is saved in localStorage.

CSV limits are 1000 rows and 2 MiB. Unknown students link to registration;
conflicts link to authorized record review. Historical results do not change
current level. The source-preparation update accepts the existing converter's
student/table CSV exports and supported text-based master-sheet PDFs for results.
Converted sources require explicit attempt context. Conversion and database
matching are combined in one preview action, with extraction issues/reports and
matched scores reviewed together before committing. Raw table CSV needs its
original session/semester supplied. Normal result CSV goes directly to matching.
There is no student-list upload mode in this result workspace. Unknown matric
numbers wait for registration in Students and a saved-preview refresh afterward.
Unsupported/scanned PDF and XLSX require a separate reviewed conversion. Downloads
include normalized CSV, issues, trace and a report with source hash/context. The
saved database batch contains the normalized CSV only. See
[the shared converter](pdf-student-extraction.md).

Validated: **34 portal tests**, lint and production build passed; **13 standalone
guardian tests** passed. A browser check against isolated synthetic PostgreSQL
confirmed registration, CSV preview/commit and history receipt recovery. No Aiven
student data or real email credentials were used.

See [import contracts](student-result-imports.md), [identity rules](student-registration.md)
and [combined validation](registration-import-validation.md). Aiven activation
requires two new migrations and a restart via `scripts/update-local.ps1`.

Converter follow-up: **39 portal tests**, lint and production build passed.
Browser preparation of a synthetic `*_students.csv` followed by explicit
extraction review correctly showed an existing result as **Already recorded**.
This follow-up needs a launcher restart, with no new migration; see the
[current validation notes](registration-import-validation.md).
