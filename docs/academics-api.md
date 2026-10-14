# Academics API

## Access and authentication

All paths below begin with `/api/`. Use Django session authentication and send
`X-CSRFToken` for writes, obtaining a fresh token from `/api/auth/csrf/` after login.
HOD means an authenticated, active staff superuser. Advisers need
students.view_student and academics.view_result, plus academics.add_result for
entry, academics.change_result for corrections, and academics.verify_result for
verification. None of these permissions are granted automatically. Student endpoints resolve the caller's linked Student;
they never accept another student's identifier as authorization.

| Path | Methods | Access |
|---|---|---|
| `results/` | GET, POST | HOD or assigned adviser with action permission |
| `results/<id>/` | GET, PATCH | HOD or assigned adviser with action permission |
| `results/<id>/verify/` | POST | HOD or assigned adviser with verification permission |
| `students/<uuid>/gpa/` | GET | HOD or assigned adviser with result-view permission |
| `students/<uuid>/cgpa/` | GET | HOD or assigned adviser with result-view permission |
| `me/results/` | GET | Linked student; verified results only |
| `me/results/<id>/` | GET | Own verified result only; others return 404 |
| `me/gpa/` | GET | Linked student |
| `me/cgpa/` | GET | Linked student |
| `academic-sessions/` | GET, POST | HOD |
| `courses/` | GET, POST | HOD |
| `course-offerings/` | GET, POST | HOD |
| `grading-scales/` | GET, POST | HOD |
| `grading-scales/<id>/` | GET, PATCH | HOD; only drafts can change |
| `grading-scales/<id>/publish/` | POST | HOD |
| `course-offerings/<id>/grading-scale/` | PATCH | HOD; only offerings without results |

Lists use 20 records per page and return count, next, previous, results.
Result-list filters: student_id (UUID), academic_session (YYYY/YYYY), semester
(harmattan/rain), is_verified (true/false). Filters combine. GPA requires
academic_session (an existing session name) and semester. Unknown student filters
return an empty list; malformed filters return 400. Catalog APIs do not expose general updates or deletion. The only offering
update is selection of a published grading version before any results exist.

## Result writes

Create input:

```json
{"student_id":"00000000-0000-0000-0000-000000000001","offering_id":1,"attempt_number":1,"score":"68.00"}
```

Score is optional/null for a pending result. The service copies credit_units from
the offering and sets is_verified=false. Student/offering/attempt duplicates fail
with 400 and never overwrite a saved score. PATCH accepts an explicit score,
including null to clear it. A changed score resets verification; an identical
score preserves it. Verification POST accepts expected_score, for example
`{"expected_score":"68.00"}`; a missing saved score or a different saved score
blocks verification. A recorded zero can be verified. Identity, offering, units
and attempt number cannot be changed through the score endpoint.

## Calculation rules

The agreed initial five-point scale is 70+:5, 60+:4, 50+:3, 45+:2, 40+:1,
below 40:0, with scores restricted to 0..100. GPA uses one session/semester;
CGPA uses every recorded attempt. Both failures and repeats count, including
units for each attempt. Average = sum(grade_point * saved units) / sum(saved units).
No results returns null; any unverified or missing score in the selected set
blocks calculation with 400. Decimal values are returned as unrounded strings.
Student result lists hide unverified entries, but calculations never silently
omit them. CGPA responses report history_completeness as not_confirmed, hod_reviewed or
review_required. See backend-lifecycle-guide.md for the review workflow.

## CSV handoff and remaining work

The PDF extraction teammate should produce UTF-8 CSV with columns:
identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score.
Preserve identifiers as text, including leading zeros. Unreadable or ambiguous
extraction values require review. Backend will resolve existing students and
offerings and use its saved units; imports start unverified. Preview, all-or-nothing
commit and safe re-import are not implemented yet. They will call the same result
service after the extractor contract is tested against representative documents.

Grading versions and adviser result access are implemented as described below.
Audit history remains pending. Graduation now requires a current HOD completeness
review plus verified unrounded CGPA >=1.00. A calculation alone cannot certify
a complete academic history or other requirements. See backend-lifecycle-guide.md. No development/shared database migration was applied in this batch.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py test students accounts academics --settings=config.test_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

CI includes academics in its PostgreSQL-backed test command.

## Manage grading versions

1. HOD POSTs grading-scales/ with a unique name and the complete bands array.
   The version starts as a draft. Example payload:

```json
{"name":"Reviewed scale v2","bands":[
 {"minimum":"0","maximum":"40","grade_point":"0"},
 {"minimum":"40","maximum":"45","grade_point":"1"},
 {"minimum":"45","maximum":"50","grade_point":"2"},
 {"minimum":"50","maximum":"60","grade_point":"3"},
 {"minimum":"60","maximum":"70","grade_point":"4"},
 {"minimum":"70","maximum":"100","grade_point":"5"}
]}
```

2. PATCH grading-scales/<id>/ to edit name or replace the whole bands array.
   Each valid array covers 0..100 exactly with no overlaps or gaps. Lower limits
   are inclusive and upper limits exclusive; the final upper limit includes 100.
   Boundaries allow two decimal places; grade points are integers 0..5. Sorting
   input bands is supported. Invalid edits do not replace the existing bands.
3. POST grading-scales/<id>/publish/ with an empty object. Publication permanently
   locks the name and bands. Later changes need another version. Drafts cannot
   be used for result calculations.
4. Include grading_scale (published version ID) when creating a course offering,
   or PATCH course-offerings/<id>/grading-scale/ with {"grading_scale":2} before
   results exist. Offerings created without it use the original five-point scale.
   There is no automatic date-based scale switch. The offering's session and
   semester identify where the HOD has chosen the version to apply.
5. Result entry copies the offering's version into the result. Later corrections
   and calculations use that saved version, so new versions do not alter old GPA.

Migrations 0002/0003 seed the original published scale and attach existing
results and offerings to it, preserving scores, units and verification status.
Django admin shows grading versions read-only; editing uses these API services.
Direct bulk ORM/SQL writes are trusted maintenance operations and must not bypass
these services when managing grading rules.

## Assign adviser capabilities

After schema migrations create the permissions, the HOD uses Django admin Users
(or Groups) to grant the relevant permissions. Student Readers/Editors groups
are unchanged and do not automatically grant academic permissions. Use separate
academic groups or direct user permissions: rerunning setup_staff_groups resets
the standard Student Readers/Editors group permission sets.

| Capability | Required permissions |
|---|---|
| Read results and GPA/CGPA | students.view_student + academics.view_result |
| Enter results (future importer will use this action) | Read permissions + academics.add_result |
| Correct scores | Read permissions + academics.change_result |
| Verify scores | Read permissions + academics.verify_result |

Every adviser also needs an active AdviserAssignment for CURRENT_ACADEMIC_SESSION
and the student's current_level. Permission alone grants no student scope. Missing
session, old/revoked assignment, inactive staff, or a student moving outside the
assigned level fails closed. Out-of-scope details return 404; list queries omit
those students. Services repeat scope/action checks under transaction locks.
Access includes historical results for students currently in the adviser's scope.
The HOD retains department-wide access. Publishing scales and changing offering
versions remain HOD-only. Granting verification is a deliberate HOD decision;
entry/edit permissions never imply it.
