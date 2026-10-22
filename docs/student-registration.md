# Student registration and identity

The application supports one departmental student record with manually entered
or reviewed bulk registration. A student record is separate from a login account.
Part-advisers can create profiles only with `students.add_student` and an active
assignment for that student's level in the current academic session. Profile
edits additionally need `students.change_student`. HOD account provisioning and
academic-status/level transitions retain their existing separate permissions.

## Profile fields

Registration requires identifier type/value, full name, admission year, admission
mode and current level. `phone_number` may be absent or blank; the system does
not fabricate contacts. An optional surname is accepted as a write-only field
for profile completion and never appears in profile or lookup responses. No
login is created as a side effect of registration or result import.
To enable student sign-in afterward, the HOD issues a linked account from
**Student login** on the profile. The student chooses their password through a
one-time setup link; see [student accounts](student-accounts.md).

Identifiers are text: leading zeros, punctuation and separators are preserved.
Matching trims surrounding whitespace and applies Unicode letter case folding.
The displayed identifier retains its spelling, with surrounding whitespace
removed on new writes. No numeric conversion, punctuation removal, `O`/`0`
substitution, name matching or OCR guessing is performed. Blank/nonprintable
identifiers are rejected. Case and whitespace therefore cannot create a second
student for the same identifier.

## Exact lookup and duplicate handling

`GET /api/students/lookup/?identifier_type=matriculation&identifier_value=EEE%2F0001`
returns the existing profile in the adviser's permitted scope. Unknown and
out-of-scope records return the same generic 404. Full name search remains a
directory convenience and is never an import identity key.

`students.identity.identifier_key(value)` and
`resolve_student_identifier(identifier_type, identifier_value, queryset=None)`
provide the shared backend matching contract. The resolver returns a student or
`None` and accepts an optional scoped queryset. Primary identifiers and retained
UTME aliases both resolve to the same immutable student UUID.

Student primary canonical keys and the shared `StudentIdentifier` registry have
database uniqueness constraints. Supported model creation, admin creation and
bulk fixture creation reserve their identifiers in that shared registry inside
the same transaction. Duplicate registrations, including concurrent attempts,
return a generic validation error without disclosing another student's details.
Queryset updates/upserts cannot silently bypass identity reservation.

## UTME to matriculation promotion

Only the HOD can call
`POST /api/students/{student_id}/promote-identifier/` with:

```json
{
  "identifier_value": "EEE/0001",
  "expected_identifier_type": "utme",
  "expected_identifier_value": "000012345"
}
```

The service locks the student, checks that the expected current identity still
matches and rejects an identifier reserved by another student. It changes the
primary type/value, retains the old UTME identity as a lookup alias and records
the actor and previous/new identity. UUID, guardians, linked account, attendance
and results continue to reference the same student. Reusing an old alias for a
new student is rejected. Existing primary identifiers are read-only in Django
admin; the audited promotion action is used for this transition.

Arbitrary identity replacement and merging two student histories are not bulk
import operations. Ambiguous identities require explicit departmental review.

## Migration and verification

`students.0007_student_identifier_registry` adds canonical keys, identifier
reservations, identity-change history and optional phone numbers. It backfills
existing records without rewriting their displayed identity or UUID. If legacy
rows have blank/invalid or case/space-colliding identities, migration stops
atomically and asks for explicit resolution; it never merges or deletes them.

Synthetic regression tests cover adviser scope, private lookup, write-only
surname, missing contacts, canonical duplicates, retained aliases, identity
promotion and preserved account/result links, bulk creation and migration
rollback. PostgreSQL-specific tests exercise simultaneous registrations and
promotion competing with registration for the same matriculation number.
No test or code-generation step applies this migration to Aiven.
