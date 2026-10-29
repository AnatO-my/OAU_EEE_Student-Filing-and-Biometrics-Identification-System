# HOD course management

Open **Courses** in the HOD portal (`/portal/hod/courses`). The workspace uses the existing academic and attendance permissions and schema.

1. Create the catalogue course with its unique code and title.
2. Create an academic session if needed. This does not change the department's current session; select that separately under **Academic session**.
3. Add a semester offering: catalogue course, session, Harmattan/Rain semester, level, credit units and a published grading scale. The same course/session/semester cannot be added twice.
4. Select that offering under **Teaching staff assignments** and assign an active staff account. Existing assignments can be deactivated or reactivated; assignment rows are retained.
5. Give the staff member the relevant teaching/attendance permissions under **Account settings**. An assignment supplies course scope, not additional account permissions. Staff teaching access follows the selected current academic session.
6. Confirm the student roster in **Attendance** before testing student access. After creation/assignment, reopen or refresh **Course materials** or **Timetable** to load the new offering. A catalogue course alone is not a semester offering.

HODs can see all offerings. Ordinary staff see only their active assignments in the current session; students see their approved roster offerings. Student material downloads additionally require current roster membership and the current non-withdrawn material version.

## API addition

GET `/api/attendance/offerings/{offering_id}/staff/` is HOD-only and paginated. It returns `id`, `staff`, `staff_username`, `staff_name`, `staff_is_active`, and assignment `is_active`. It includes active and inactive assignments for that offering, with no email addresses or private account fields. The existing PUT on the same endpoint remains the only assignment write, using `{staff, is_active}` and the existing service validation.

Catalogue, session and offering creation reuse the existing POST endpoints; no model or database migration is introduced. Existing catalogue/offering records are listed; editing/deleting catalogue or offering history is outside this change.

## Activation and validation

The backend was not restarted by this background task. Restart it through the normal configured terminal to load the new assignment GET endpoint, then refresh the browser. No real course, offering, assignment, notification or migration was created during implementation.

Isolated course-management/attendance/teaching API tests passed (43); targeted course UI/navigation tests passed (12); the complete portal suite passed (151 tests in 20 files, with two workers); portal build and changed-file lint passed; Django checks and migration drift checks passed. An initial unrestricted parallel portal run had one guardian element-wait timeout while the student list was still loading; the bounded full rerun passed without code changes to that test or workflow. These checks do not replace the owner's course-material upload/download operational test, which was blocked because no course offering was available.
