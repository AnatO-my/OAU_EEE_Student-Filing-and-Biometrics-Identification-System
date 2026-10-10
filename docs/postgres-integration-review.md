# PostgreSQL integration and teammate schema comments

8 October 2026. Source comparison: active app/accounts, app/students and
app/academics versus the preserved legacy/teammate_portal/portal models and
migrations 0001..0004. The teammate repository is Futurescholar/department and
the user confirmed it remains the source. Its live PostgreSQL catalog/data have
not been inspected. The remote page was unavailable during this review; these
comments refer to the preserved local source, not a newly fetched remote revision.

## What we should connect to

A PostgreSQL server is the host; a database is a separate collection of schemas
and tables on that host. We can use the teammate's existing server while creating
a new dedicated database for this backend. Merely changing HOST/NAME does not
translate portal_* tables into accounts_*, students_* and academics_* tables.

Recommended first integration: back up and restore-check the source; keep its
portal tables unchanged; create a separate synthetic staging database; run our
committed migrations there; reconcile and import approved source records through
an explicit mapping; validate before switching the application. Neither a direct
in-place alteration nor a data import has been performed in this task.

Do not copy legacy migrations into the active apps, rename portal tables blindly,
change AUTH_USER_MODEL on an already populated auth database, or use --fake to
hide differences. Default auth_user and our accounts_user have different migration
histories and relationship targets. Existing admin/auth migration dependencies
can become inconsistent when switching user models on the old database.

## Comments to send the database teammate

The following describes the target. Apply it through our Django migrations and a
reviewed data conversion, not a hand-written replacement schema.

| Area / existing source | Requested target change and migration comment |
|---|---|
| portal_student.id (bigint) | Target students_student.student_id is UUID. Allocate once and retain a private source-id-to-UUID mapping; rewrite every dependent reference through it. Never cast a numeric ID to UUID or use matriculation as a permanent PK. |
| matric_number varchar(30), name varchar(150), level | Map matric_number to identifier_value varchar(100), identifier_type=matriculation; name to full_name varchar(200); level to explicit current_level smallint. Preserve identifier leading zeros and original spelling. Do not invent formatting/case normalization while rules are pending. |
| New required student data | Supply reviewed phone_number varchar(30), admission_year smallint and mode_of_admission (utme/direct_entry/transfer). These do not exist in the preserved source; quarantine incomplete rows rather than invent phone/year/mode. |
| Student status ACTIVE/TERMINATED | Map to is_active only after agreeing the operational meaning. Do not equate TERMINATED with graduated. academic_status is undergraduate/graduated and graduation needs current HOD approval plus verified unrounded CGPA >=1.00. Current level remains an explicit integer, not inferred from admission year. |
| Student.email, surname, must_change_password | Account email belongs to accounts_user; preserve source email/provenance until mapped. There is no direct target for surname/password-change flag. Do not silently lose source data or adopt surname-based initial passwords. Our current lifecycle does not enforce first-login change. |
| auth_user + legacy roles | Retain accounts.User as AUTH_USER_MODEL. Explicitly map accounts and student links to accounts_user; student.user_id is nullable and unique. Review username collisions and privilege flags. Compatible secure Django password hashes can be preserved after checking configured hashers; unknown/insecure credentials need recovery. Never set raw password strings directly. Start new sessions after cutover. |
| Guardian email-only records | Target students_guardian has UUID PK, student UUID FK, required full_name/phone_number/relationship, optional email/address. Multiple guardians are supported. Source email-only rows need enrichment/review; do not fabricate required values. There is no target unique(student,email) rule; use a source-ID mapping for idempotent import. |
| Course code/title/credit_units/level/semester | Target academics_course stores unique code varchar(30), title varchar(200). Session-specific level, units, semester and grading version belong to academics_courseoffering. Source title up to 200 fits current target; inspect older data for overlength values. |
| Result.session text | Create academics_academicsession with unique name varchar(9), reviewed consecutive YYYY/YYYY years. Resolve session FK; do not accept malformed or guessed sessions. |
| CourseOffering (new) | Create one offering for (course, academic_session, semester), unique on these three FKs/values. Semester values are lowercase harmattan/rain; source uppercase values need explicit mapping. Level and units must be reviewed for the historical session, not assumed from the current course definition. |
| portal_result(student,course,session,semester,score,grade_point) | Target academics_result references student UUID and offering; score is nullable numeric(5,2). Add attempt_number, saved credit_units, grading_scale FK and is_verified. Unique(student,offering,attempt_number) replaces unique(student,course,session). All attempts including failures count; never overwrite earlier attempts. Unknown attempts require review; do not invent repeats that source uniqueness may already have discarded. |
| Historical units / grade_point | Source calculations read the current course.credit_units; historical values may be unavailable. Reconcile archived evidence before assigning offering/result units. Match saved grading versions to historical evidence; our initial scale is seeded, but do not assume it applied to every old result. grade_point is derived from score and saved version, not independently authoritative in the target. |
| Student.cgpa and portal_semestergpa | Preserve for comparison/provenance, then recalculate using verified results and saved units/versions. Our model does not store these as authoritative student columns/tables. Legacy values round to 2 decimals and use zero for no results; ours returns unrounded Decimal strings or null and blocks calculations containing unverified/missing scores. Never use rounded legacy CGPA to approve graduation. |
| Verification (new) | Source has no verification flag. Imported results start unverified and need authorized review. Migration is not proof of verification. Do not manufacture verification evidence to make calculations pass. |
| Required courses / graduation | Add academics_courserequirement and academics_graduationreview. The HOD reviews the complete required-offering manifest; transfer/exemption resolutions require reasons. Legacy course registrations may be evidence, but are not automatically a complete curriculum or graduation approval. |
| Adviser roles / access | Use accounts_adviserassignment: staff FK, academic_session, level, is_active; unique(staff,session,level). Replace username/role conventions with HOD-assigned Django permissions and current-session level scope. Readers/editors, guardian, export and academic action permissions are separate. Never infer adviser assignments from access to the database. |
| Messaging (new) | Create accounts_advisermessage, accounts_hodmessage and their recipient join tables through migrations. Message recipients use mapped student UUIDs/accounts; never broaden audience during conversion. |
| Calendar, prerequisites, registrations, StudentFile | Preserve in the source/archival area. These have no equivalent full feature in our active schema; do not drop or silently import them into unrelated fields. Academic warning thresholds and course-registration/document features still need explicit scope. |
| Delete semantics | Our academic/guardian/adviser history uses Django PROTECT; student account link uses SET_NULL. Source student-dependent CASCADE policies must not delete target history accidentally. Inspect actual SQL FKs; Django on_delete policies are application behavior, not necessarily SQL ON DELETE actions. |
| Permission and framework tables | Include Django auth_group/auth_permission/content types, accounts_user group/permission join tables, django_admin_log, django_session and django_migrations from our migration graph. Permission IDs cannot be copied blindly: map by app_label/model/codename. No raw legacy django_migrations records should be copied to mark our migrations applied. |

Our migration/model limits are the target; the live source catalog remains the
authority for what actually exists today. Model choices, regex checks, Decimal
range validators and full_clean are NOT automatically PostgreSQL CHECK constraints.
Application services enforce several rules. Do not advertise raw SQL writes as
having the same validations, permission checks, verification or review invalidation.
Positive smallint fields have database nonnegative checks, but stricter >0 and
allowed levels/choice rules may be application validators. Grading bands are jsonb;
no-overlap/full-coverage validation and published-version immutability are enforced
by our services/model, not a PostgreSQL JSON constraint.

## Additional guardian sharing tables

Academic migration 0005 now adds academics_guardiansharingpreference,
academics_resultsharebatch and academics_resultsharedelivery. The source has no
matching delivery history. Preserve guardian UUID mappings; do not invent channel
sharing consent, opt-ins or prior accepted deliveries during migration. Delivery
uniqueness is (batch,guardian,channel,part_number), and reports/contacts are private
snapshots. See guardian-result-sharing.md for worker/provider requirements.

## Inventory to request before data conversion

Use docs/postgres-schema-inventory.sql in pgAdmin Query Tool against the source
with an authorized read-only account. It exports columns, keys/constraints and
indexes, not application records. Alternatively, the teammate can generate:

```powershell
pg_dump --schema-only --no-owner --no-privileges --host=HOST --port=5432 --username=READ_ONLY_USER --file=private-data/source-schema.sql SOURCE_DATABASE
```

Create private-data/ first. Use the password prompt or an authorized local pgpass
file, not command-line passwords. Review the schema output before sharing: it can
contain object names, function definitions, comments and literal defaults. Remove
embedded secrets. Our inventory similarly reports literal defaults. Keep database
backups and any real row data outside GitHub and chat. Separately return the
source django_migrations app/name history if present; no user/student rows needed.

The source owner should privately report counts, duplicate/collision findings,
missing required fields, malformed sessions, unknown units/scales, dangling
references, legacy account linking and whether repeated attempts were overwritten.
Use synthetic examples for issues. Successful schema inspection does not prove
that the existing data can be mapped safely.

## Connection setup for our backend

Added config.postgres_settings, which explicitly requires POSTGRES_DB,
POSTGRES_USER and POSTGRES_HOST; it does not modify default SQLite settings.
psycopg is already pinned in requirements.txt. .env.example is documentation and
is not automatically loaded. Use a distinct database per development/staging/
production. Database role privileges and Django user permissions are different:
the normal runtime role should not be a PostgreSQL superuser or migration owner.

Example for a NEW local synthetic database already created by its owner:

```powershell
$env:POSTGRES_DB = 'filing_dev'
$env:POSTGRES_USER = 'filing_dev_user'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5432'
$env:POSTGRES_SSLMODE = 'disable'  # trusted local development only
# Supply POSTGRES_PASSWORD securely in the process environment, or use pgpass.
.\.venv\Scripts\python.exe manage.py check --settings=config.postgres_settings
.\.venv\Scripts\python.exe manage.py showmigrations --settings=config.postgres_settings
.\.venv\Scripts\python.exe manage.py migrate --plan --settings=config.postgres_settings
```

check validates application configuration; it does not prove connectivity.
showmigrations/migrate --plan read database migration history. Review the plan
against the NEW target. The source database should never be selected accidentally.
The deliberate write step, once that database and plan are verified, is:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --settings=config.postgres_settings
```

No live or development migrations have been run in this task. For a remote
server use POSTGRES_SSLMODE=verify-full with a trusted server certificate and
matching hostname; configure the client trust root outside the repository.
Use a dedicated migration role for DDL and least-privileged runtime role for
application queries. Grant runtime table/sequence access as new tables are added.
Production also needs DEBUG=false, stable secret, hosts, HTTPS, mail and backups;
this database settings module alone is not a full deployment configuration.

## Data conversion sequence and acceptance

1. Source owner makes and tests a full backup restore; freeze/snapshot the input
   consistently. Obtain schema/migration inventory and synthetic fixtures.
2. Create the fresh target using the complete accounts/students/academics migration
   graph. Check the seeded published grading scale and generated permissions.
3. Build private source-to-target maps for users, students, guardians, courses,
   offerings and results. Detect duplicates and missing fields before writing.
   Re-import must consult these maps; a fresh UUID on every import is not safe.
4. Convert accounts/identity, enrich profiles/guardians, review offerings' historical
   units/grading versions, then import every recoverable attempt unverified. Keep
   rejected rows in a private reconciliation report; do not silently skip them.
   Never use the source's rounded CGPA or grade_point to bypass result review.
5. Assign HOD/adviser permissions and sessions deliberately; verify results and
   recompute GPA/CGPA, resolving discrepancies with evidence. HOD graduation
   review remains a separate operation; imported students are not auto-graduated.
6. Validate row counts/maps, nullability/keys/uniqueness, account logins, adviser
   and student isolation, repeats, units, verification and graduation guards. Run
   all backend tests on a separate disposable PostgreSQL test database; Django
   tests create/drop a test database and require an explicitly authorized role.
   Existing GitHub CI uses PostgreSQL 16; local SQLite success is not a replacement.
7. Trial cutover in staging, then agree source freeze, final synchronization and
   rollback. Keep source plus ID maps/backups until acceptance; do not drop legacy
   tables or alter application routing as part of an unreviewed conversion.

Actual importer, live schema inspection, reconciliation, restore test and cutover
remain pending the schema inventory/connection supplied privately by the owner.
No database credentials are needed in chat. Schema reference is documented in
postgres-schema-reference.md; migrations remain the creation authority.

## Embedded credential found during review

The archived teammate settings contained a literal database password. It has been
replaced locally with POSTGRES_PASSWORD environment lookup. If that credential is
still active, its owner should rotate it; editing the file does not revoke a
credential or erase prior repository copies. No connection was attempted with it.

## Validation performed for this preparation

Four opt-in configuration checks passed: missing database, user and host each
fail with a clear diagnostic; a complete synthetic configuration passes Django
check without contacting a database. Isolated settings Django check, migration
drift check and git diff --check passed. PostgreSQL column types were generated
using Django's PostgreSQL backend without a live connection. The inventory SQL
has been reviewed but not executed against PostgreSQL. The earlier 204-test
backend pass was on isolated SQLite; this task does not claim a PostgreSQL test
pass or a successful shared-database connection.
