# Frontend source import

This branch imports the reviewed React portal into `frontend/portal/` as a
starting point for integration. It does not make the prototype screens live.
The frontend source is unchanged from the pinned upstream commit.

## Source

- Repository: https://github.com/9iceguy/EEE-project
- Branch reviewed: `main`
- Commit: `d3a4d4c190c3402dcfdebc7a867e676a41e7b769`
- Imported: 18 October 2026
- Our base: `2395e56cb1768fcd069efd3d7dee483e3c03d663` (`origin/main`)

Only tracked source files were imported. Git metadata, dependency directories,
build output and local configuration are excluded. The separate folder keeps
backend files and other frontend packages intact.

## Development

Start the Django API at `http://127.0.0.1:8000`, then from the repository root:

```powershell
cd frontend/portal
npm ci
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Open `http://127.0.0.1:5175`. Configure the Django process with
`DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5175` before starting it; setting
this in a file only works if the launcher loads that file. Use an existing
department-issued account. The portal proxies `/api/` to the backend.
Port 5175 avoids the existing guardian-results development app's port 5173.

## Integration work still required

1. Bind portal routes, displayed roles and data to the authenticated identity
   and permissions. Replace the portal's demo logout with the real sign-out.
2. Load student class attendance through the staff class-record endpoints.
   Remove silent sample-data fallback and false connected/live indicators.
3. Preserve original JSONL bytes and `application/x-ndjson` in capture-upload
   helpers; the current common request function converts them to JSON.
4. Add the password-reset completion form and fix source-directory image URLs
   that do not exist in production build output.
5. Connect the other prototype screens and preserve/integrate the existing
   guardian-results UI. The document-upload feature on main has no portal UI yet.

Attendance and database current-session selection were reviewed against local
uncommitted backend work and are not on this branch's main base. Reconcile and
review that backend work before enabling those features. Adviser capabilities
come from staff permissions and adviser levels, not a separate API role.

## Import validation

The reviewed source passed `npm run lint` and `npm run build` with Node
`v24.22.0` and npm `11.19.1`. The import is checked byte-for-byte against the
pinned upstream Git tree. These checks do not validate the remaining browser
workflows. Submit this branch through a pull request before merging into main.

The upstream API document retains three Markdown hard-break spaces on lines
3–5. The standard Git whitespace check reports those inherited lines; they
are retained so the imported frontend files match the reviewed source exactly.
