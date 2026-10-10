# Expected PostgreSQL model columns

Generated from the active models on 8 October 2026 without connecting to a database.
This describes column types/nullability and keys; committed Django migrations are
the source of schema creation and seeded data. Defaults are generally Python-side,
not persistent database defaults. Choices/validators are not automatically SQL CHECKs.
PROTECT/SET_NULL are Django deletion policies, not claims about ON DELETE clauses.

Use this alongside postgres-integration-review.md and the live inventory.

## students_student

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| student_id | uuid | no | PK |
| user_id | bigint | yes | UNIQUE; FK accounts_user.id |
| identifier_type | varchar(20) | no |  |
| identifier_value | varchar(100) | no | UNIQUE |
| full_name | varchar(200) | no |  |
| phone_number | varchar(30) | no |  |
| admission_year | smallint | no |  |
| mode_of_admission | varchar(20) | no |  |
| current_level | smallint | no |  |
| academic_status | varchar(20) | no |  |
| is_active | boolean | no |  |

## students_guardian

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| guardian_id | uuid | no | PK |
| student_id | uuid | no | FK students_student.student_id |
| full_name | varchar(200) | no |  |
| phone_number | varchar(30) | no |  |
| relationship | varchar(100) | no |  |
| email | varchar(254) | yes |  |
| address | text | no |  |

## accounts_user_groups

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| user_id | bigint | no | FK accounts_user.id |
| group_id | integer | no | FK auth_group.id |

Unique together: `(('user', 'group'),)`.

## accounts_user_user_permissions

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| user_id | bigint | no | FK accounts_user.id |
| permission_id | integer | no | FK auth_permission.id |

Unique together: `(('user', 'permission'),)`.

## accounts_user

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| password | varchar(128) | no |  |
| last_login | timestamp with time zone | yes |  |
| is_superuser | boolean | no |  |
| username | varchar(150) | no | UNIQUE |
| first_name | varchar(150) | no |  |
| last_name | varchar(150) | no |  |
| email | varchar(254) | no |  |
| is_staff | boolean | no |  |
| is_active | boolean | no |  |
| date_joined | timestamp with time zone | no |  |

## accounts_adviserassignment

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| staff_id | bigint | no | FK accounts_user.id |
| academic_session | varchar(9) | no |  |
| level | smallint | no |  |
| is_active | boolean | no |  |

Model constraint: `unique_adviser_staff_session_level` on `staff, academic_session, level`.

## accounts_advisermessage_recipients

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| advisermessage_id | bigint | no | FK accounts_advisermessage.id |
| student_id | uuid | no | FK students_student.student_id |

Unique together: `(('advisermessage', 'student'),)`.

## accounts_advisermessage

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| assignment_id | bigint | no | FK accounts_adviserassignment.id |
| audience | varchar(20) | no |  |
| subject | varchar(200) | no |  |
| body | text | no |  |
| created_at | timestamp with time zone | no |  |

## accounts_hodmessage_recipients

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| hodmessage_id | bigint | no | FK accounts_hodmessage.id |
| student_id | uuid | no | FK students_student.student_id |

Unique together: `(('hodmessage', 'student'),)`.

## accounts_hodmessage_adviser_recipients

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| hodmessage_id | bigint | no | FK accounts_hodmessage.id |
| user_id | bigint | no | FK accounts_user.id |

Unique together: `(('hodmessage', 'user'),)`.

## accounts_hodmessage

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| sender_id | bigint | no | FK accounts_user.id |
| audience | varchar(20) | no |  |
| academic_session | varchar(9) | no |  |
| level | smallint | yes |  |
| subject | varchar(200) | no |  |
| body | text | no |  |
| created_at | timestamp with time zone | no |  |

## academics_academicsession

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| name | varchar(9) | no | UNIQUE |

## academics_course

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| code | varchar(30) | no | UNIQUE |
| title | varchar(200) | no |  |

## academics_courseoffering

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| grading_scale_id | bigint | no | FK academics_gradingscale.id |
| course_id | bigint | no | FK academics_course.id |
| academic_session_id | bigint | no | FK academics_academicsession.id |
| semester | varchar(10) | no |  |
| level | smallint | no |  |
| credit_units | smallint | no |  |

Model constraint: `unique_course_session_semester` on `course, academic_session, semester`.

## academics_result

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| grading_scale_id | bigint | no | FK academics_gradingscale.id |
| student_id | uuid | no | FK students_student.student_id |
| offering_id | bigint | no | FK academics_courseoffering.id |
| attempt_number | smallint | no |  |
| score | numeric(5, 2) | yes |  |
| credit_units | smallint | no |  |
| is_verified | boolean | no |  |

Model constraint: `unique_student_offering_attempt` on `student, offering, attempt_number`.

## academics_gradingscale

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| name | varchar(100) | no | UNIQUE |
| bands | jsonb | no |  |
| is_published | boolean | no |  |

## academics_courserequirement

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| student_id | uuid | no | FK students_student.student_id |
| offering_id | bigint | no | FK academics_courseoffering.id |
| resolution | varchar(20) | no |  |
| reason | text | no |  |
| recorded_by_id | bigint | no | FK accounts_user.id |

Model constraint: `unique_student_course_requirement` on `student, offering`.

## academics_graduationreview

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| student_id | uuid | no | UNIQUE; FK students_student.student_id |
| reviewed_by_id | bigint | no | FK accounts_user.id |
| reviewed_at | timestamp with time zone | no |  |
| notes | text | no |  |
| history_digest | varchar(64) | no |  |
| cgpa_snapshot | varchar(100) | no |  |

## academics_guardiansharingpreference

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| guardian_id | uuid | no | UNIQUE; FK students_guardian.guardian_id |
| email_enabled | boolean | no |  |
| whatsapp_enabled | boolean | no |  |
| evidence | text | no |  |
| updated_by_id | bigint | no | FK accounts_user.id |
| updated_at | timestamp with time zone | no |  |

## academics_resultsharebatch

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | uuid | no | PK |
| created_by_id | bigint | no | FK accounts_user.id |
| academic_session_id | bigint | no | FK academics_academicsession.id |
| semester | varchar(10) | no |  |
| student_ids | jsonb | no |  |
| channels | jsonb | no |  |
| preview | jsonb | no |  |
| history_digest | varchar(64) | no |  |
| queued_at | timestamp with time zone | yes |  |
| created_at | timestamp with time zone | no |  |

## academics_resultsharedelivery

| Column | PostgreSQL type | Nullable | Key / reference |
|---|---|---|---|
| id | bigint | no | PK |
| batch_id | uuid | no | FK academics_resultsharebatch.id |
| student_id | uuid | no | FK students_student.student_id |
| guardian_id | uuid | yes | FK students_guardian.guardian_id |
| channel | varchar(10) | no |  |
| destination | varchar(254) | no |  |
| part_number | smallint | no |  |
| subject | varchar(200) | no |  |
| body | text | no |  |
| status | varchar(20) | no |  |
| diagnostic_code | varchar(50) | no |  |
| provider_id | varchar(200) | no |  |
| attempts | smallint | no |  |
| updated_at | timestamp with time zone | no |  |

Model constraint: `unique_guardian_channel_part_per_share_batch` on `batch, guardian, channel, part_number`.
