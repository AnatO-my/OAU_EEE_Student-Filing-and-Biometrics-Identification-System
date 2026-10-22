# EEE frontend prototypes

Two standalone responsive directions for the OAU EEE departmental portal. Serve with `python -m http.server 5174 --bind 127.0.0.1 --directory frontend/prototypes` from the repository root.

- `index.html?theme=files` (default): selected cream, forest green and sage filing-room workspace, using Funnel Sans with comfortable text sizing. Student, lecturer/staff, part adviser and HOD screens share connected demo journeys.
- `index.html?theme=motion`: preserved charcoal/orange original direction study with motion pause and reduced-motion support.

The selected prototype covers the expanded checklist: registration drafts and adviser decisions; score entry/CSV and HOD approval; academic summaries; timetable changes; resources; requests and escalation; advising notes and appointments; communication; assignments; reports; history; and sign-in, recovery, expiry and screen-state previews.

Use Preview workspace to switch roles. Changes persist locally in this browser; Reset demo restores the seed. Demo credentials are `demo / demo123`. No real credentials, student data or backend connections are used. Binary upload contents last until page reload. Academic rules and course data are illustrative. Production permissions and authentication must be enforced by the backend.

Files: `workspace.js` (UI), `demo-model.js` (state/workflows), `portal.css` (styling), `demo-model.test.js` (tests). `portal.js` is a compatibility loader; `app.js` retains the motion study. See [WORKFLOWS.md](WORKFLOWS.md) for role coverage, journeys, boundaries and verification.

Fonts load optionally from Google Fonts with Segoe UI/Arial fallbacks. Original visual references were the supplied departmental images, video frames and the project-management dashboard reference used in the earlier studies.


Guardian result emails now has a separate live React page in ../guardian-results/.
The demo header opens its local development URL (port 5173); start that app first.
It uses real departmental HOD authentication and the existing APIs. The demo role
switch and browser sample data do not authorize or trigger live report sends.
This link can be replaced by the finished frontend router when merged later.
