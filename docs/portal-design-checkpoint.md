# Inner portal design — 22 October 2026

The inner portal follows the supplied student-portal and UniConnect references:
rounded panels, a quiet canvas, consistent spacing and clear content hierarchy.
The implementation keeps the department's blue theme. Reference calendars,
search controls and sample statistics are not added as application features.

The scope is the authenticated HOD/staff/student shell and its shared inner-page
components, including the embedded guardian workspace. The public login and the
standalone guardian application retain their existing designs.

Student registration stays in **Students**. **Upload results** retains the
results-only PDF-to-CSV workflow, automatic source-field extraction and one
conversion/matching preview action. Unknown matric numbers hold the batch until
staff register students separately and refresh it. Review, corrections and
receipt recovery continue to use the existing API.

The visual review uses isolated synthetic PostgreSQL and loopback test services;
no Aiven credentials or departmental records are used for screenshots.

The shell now has blue icon navigation, role-aware workspace cards, grouped forms,
rounded tables and consistent page headers. Registration appears above the student
directory. Account settings is beneath the avatar/username, with its own active
state and a role-preserving account route.

Accessibility checks cover the compact mobile menu, Escape/route-close behavior,
focus on the new page, skip-to-main link, visible keyboard focus, labelled table
scroll regions and column scopes. Forms and navigation provide 44px control targets;
the layout respects reduced-motion preferences. Main muted text and primary
button text were checked for contrast; control borders were strengthened during
review. This is a targeted implementation review, not a complete accessibility
conformance audit.

The portal passed **63 tests**, ESLint and the production build after account
administration was integrated. Desktop and 390px mobile review covered the HOD
dashboard, student directory/registration, results upload, embedded guardian
workspace and Account settings. Checked pages had no horizontal document overflow;
wide tables stayed within their scroll regions.

Proof images:

- `output/local-integration/portal-redesign-desktop.png`
- `output/local-integration/portal-account-mobile.png`
- `output/local-integration/account-handover-preview.png`

See [account administration](account-administration.md) for staff, part-adviser
and HOD-transfer behavior and the required audit migration.
