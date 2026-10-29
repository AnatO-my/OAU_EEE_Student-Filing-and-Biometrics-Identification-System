# Student workflow batch

The portal's Documents and requests workspace uses authenticated, no-store APIs under `/api/workflows/`. Departmental data and files are never public-media URLs.

## Filing

The supported inventory includes clearance, JAMB, WAEC, birth certificate (the legacy API code `birth_cecrtificate` is retained for compatibility), state of origin, and biodata. Existing result/other categories remain compatible. Students may upload their own files; assigned part advisers and the HOD may upload for their students subject to existing upload permissions. File signatures, bounded PDF/JPEG/PNG uploads and optional quality checks remain enforced.

First uploads become active immediately. Student replacement candidates remain pending, referencing the active version. Staff replacement uploads take effect directly. Either the assigned adviser or HOD may approve or reject a student replacement with a reason. Approval checks that the referenced active version has not changed. Rejection retains the current version and permits a new submission. Prior approved files remain archived. Student owners, current part advisers and HOD may list and download versions through authenticated routes; unrelated accounts receive no document access.

- GET/POST `/api/students/{student_uuid}/documents/`
- GET `/api/documents/{document_uuid}/download/`
- POST `/api/documents/{document_uuid}/review/`: `approve` and `reason`

Document migrations map previously superseded uploads to archived state. Migration files are generated only and must be applied through normal deployment.

## Student corrections

GET `/api/workflows/students/{student_uuid}/` returns the permitted student's contact details, guardian records, pending/reviewed requests and retained source-GPA comparisons. Students POST `action=change_request`, `kind=contact|guardian|identity`, proposed `values` and a written `reason`. Existing details remain active. Reviewer POST `/api/workflows/requests/{request_id}/review/` with `approve` and `reason`. A stale active-value snapshot rejects approval rather than overwriting a newer change. Identity corrections use the existing staff student-update policy. HOD-reviewed identifier corrections preserve the permanent UUID, reserve previous identifiers and append identity history; UTME-to-matriculation promotion retains its existing dedicated checks. Generic profile PATCH cannot rewrite identity. Programme is an explicit optional profile field.

Only the owner may submit student requests; active current advisers or HOD review them. The staff's existing protected identity/level permissions still apply. Source-reported values remain unchanged when a discrepancy is reviewed. POST `/api/workflows/source-comparisons/{id}/review/` records the reason and attempts a brief HOD email notification; history retains pending/accepted/unknown delivery status. Missing HOD email addresses leave the notification pending and visibly unsubmitted; transport errors preserve the written review reason and mark notification outcome unknown, with no automatic resend.

## Credentials and archival

An authorised part adviser/HOD POSTs `action=temporary_password` and `email` to the student's workflow route. A cryptographically generated temporary password is emailed, only its hash is persisted, and no credential is returned in the API or audit. Credential email issuance requires SMTP (including the project OS-trust SMTP wrapper) or isolated-memory backend: console/file backends are rejected to avoid logging secrets. Email acceptance is not proof of inbox delivery. An unknown transport outcome retains the pending account and does not retry automatically; explicit reissue invalidates the earlier temporary password.

The account's `must_change_password` flag gates API access to identity, CSRF, logout and password change only. The portal displays mandatory password change before other workspaces. Changing the password removes the gate immediately. Existing password recovery remains an expiring, single-use email reset link. Legacy setup links may be reissued only for pre-existing unusable-password accounts, and already-issued tokens remain supported. New setup-link account provisioning is rejected; new accounts use the temporary-password workflow.

HOD POST `action=archive` with a reason deactivates the student record and linked login without deleting information. Graduation, withdrawal and left-department status transitions also deactivate the linked account, including supported bulk-status actions. Records, results, documents and historical references remain retained.

## HOD handover

GET `/api/workflows/handover/` lists only offers sent to or from the caller. Current HOD POSTs `target_id` for an existing eligible staff member. Roles remain unchanged until that recipient POSTs `handover_id`. Acceptance atomically demotes the sender and promotes the recipient, retaining an audit. Exact repeated acceptance does not transfer again. Ineligible, unrelated and inactive accounts cannot accept. A replacement offer cancels the prior pending offer. The former immediate-transfer API rejects transfers; portal administration now offers the reviewed acceptance workflow. Other pre-existing administrator accounts retain the established policy; this increment does not invent a new department/tenant ownership model.

## Revised guardian reports

New HOD preview requests support `is_revised=true` with an internal `revision_reason`. The saved reviewed PDF carries Revised Result; the reason is retained only in HOD metadata and is absent from the PDF and guardian email. Queue/worker reconstruction includes the revision mode, preserving exact reviewed bytes, digest checks, provider-outcome safeguards and legacy batch format.

All automated validation uses synthetic records, temporary private file storage and isolated-memory email. It does not replace the owner's still-pending document, full-semester, timetable, handover or end-user operational evaluation. No live database migration, deployment or real guardian email was performed.
