# Filing room prototype — review guide

The cream/green prototype is a standalone browser demo for the expanded wireframe checklist requested on 6 October 2026. Existing backend contracts remain unchanged. Features beyond those contracts are proposed implementation work.

## Try the journeys

1. **Registration:** choose Student, open Courses & registration, select courses, save a draft or submit. Switch to Part adviser and review Adebayo in Registration review. Return with a comment, correct/resubmit as student, then approve as adviser. Student sees the decision and notification. Submitted/approved selections are locked.
2. **Results:** approve a registration first. Choose Lecturer / staff, open Results management, enter scores for approved enrolled students (or upload `student_id,score` CSV), save a draft and submit to HOD. Choose HOD, inspect Approval queue and approve or return with comments. Only approved results appear in student Results, GPA/CGPA and reports.
3. **Requests:** Student submits a request with an optional attachment. Assigned adviser responds or escalates with a reason. HOD reviews escalated cases in Approval queue and can approve, resolve or return them. Student request history and notifications show decisions. Course enquiries also reach assigned lecturers.
4. **Advising:** Student requests an appointment in My adviser. Part adviser confirms/declines in Appointments. Save guidance in Advising records with explicit visibility and follow-up dates. Shared notes appear in student My adviser; private notes appear only in adviser/HOD views.
5. **Resources:** Lecturer uploads a title and PDF/text/image in Learning resources. Student previews/prepares a download and receives a notification. Text contents persist in browser storage; binary files and request attachments last until reload.
6. **Messages:** staff address assigned course cohorts; advisers address individuals/assigned levels; HOD addresses individuals, levels, courses or the sample adviser. Review before confirming. Recipient snapshots survive assignment changes.
7. **Assignments:** HOD adds/deactivates lecturer-course or adviser-level assignments. Switch roles to see updated scope. Production account/permission administration remains in Django admin.
8. **Schedules/reports:** HOD publishes time/venue changes, creating student notifications. Reports filter approved rows by session, semester, level and course. Prepare CSV exports and inspect Decision history.
9. **Account/states:** Log out; test invalid sign-in, then use `demo / demo123`. Forgot password simulates recovery without email. Preview loading, empty, error, access denied and expiry states with the screen-state selector. Expiry leads to sign-in.

## Screen coverage

| Workspace | Screens and actions | Scope / next step |
| --- | --- | --- |
| Student | Dashboard, contact edits, registration, results, timetable, resources, requests/attachments, adviser/appointments, inbox, notifications | Own sample record; submissions lead to staff review |
| Lecturer / staff | Dashboard, profile, courses/rosters, score entry/CSV/drafts, course enquiries, timetable, uploads, class announcements, inbox, notifications | Assigned courses; results lead to HOD review; full files require adviser role |
| Part adviser | Cohort dashboard, directory, academic summary/credit load, registration decisions, requests/escalation, guidance/visibility/follow-up, appointments, messages | Assigned levels; decisions and shared notes reach students |
| HOD | Department metrics, records, academic files, coverage, assignments, guidance oversight, approvals, requests, schedules, resources, announcements, reports/CSV, history, sample import review | Department-wide demo oversight |

Workspace screens include expandable developer notes for data, action, next step and permissions. Forms mark required fields and show validation/success feedback. Tables and navigation scroll within their panels on narrow screens. Search supports level filters and pagination. Controls use labelled inputs, native forms and dialogs.

## Boundaries

- All profiles, contacts, materials, courses, scores and schedules are synthetic. Role switching and demo credentials are layout previews, not production security.
- Browser state is stored under `eee-filing-room-v3`. Reset demo restores the seed. Storage limitations are reported by the UI.
- No external emails/messages, backend writes or database migrations occur.
- Catalogue, credit rules and five-point grade thresholds are illustrative. GPA/CGPA use available approved demo rows. Incomplete history, repeats, exemptions, substitutions and graduation rules need institutional policy. Unknown data is not labelled failed or automatically eligible.
- HOD assignments simulate a proposed workflow; production accounts/permissions remain in Django admin. Imports demonstrate one synthetic conflict; real staging and reconciliation remain unconnected.
- File-ready dialogs use save links and a text/CSV contents fallback. In-app browser automation did not expose completed download events; verify actual file saving in the deployment browser.

## Verification

Run `node --check frontend/prototypes/workspace.js` and `node --test frontend/prototypes/demo-model.test.js`.

Six model tests cover registration corrections/approval, assignment revocation, score validation/review/GPA, request escalation, recipient snapshots, appointments, notes, resource scope and schedule notifications. Browser checks covered all role screens, registration return/resubmit/approval, result submission/HOD approval/student visibility, request escalation/approval, appointment confirmation, CSV upload, text resource upload/preview, invalid/successful login, recovery and expiry. Student screens were checked at a 390-pixel viewport without page overflow.
