# Student records, accounts and semester calculation session

**Staged only. No operator result has been recorded.** Use the master README and the isolated scratch site. Do not use your ordinary website/database, real email, real documents, real student accounts or a real HOD transfer. The scratch seed deliberately contains invented people, a test grading scale and protected local files.

## Before starting

1. Complete the master scratch preparation and verify its database/media paths and local ports. The usual working database must remain untouched. Record run ID, repository revision, date/time/timezone, device, browser/version and operator in the run manifest.
2. Seed handles are EVAL-HOD, EVAL-HOD-SUCCESSOR, EVAL-ADVISER (also assigned lecturer), EVAL-UNASSIGNED, EVAL-STUDENT-A (EVAL/001), EVAL-STUDENT-B (EVAL/002), and EVAL-SETUP (EVAL/003). These are role handles, not necessarily login usernames: Student A/B logins are EVAL/001 and EVAL/002, and setup login is EVAL/003. Use the actual manifest account names, IDs and links; never invent a model UUID. Use only the operator-chosen scratch password; never put passwords, sessions or reset tokens in evidence sheets.
3. In separate browser profiles sign in as the relevant synthetic role. Confirm identity before every change. Use the named student selector in Documents and requests. Keep identity/matric corrections, HOD transfer and student archival **after all CSV, teaching, attendance and device checks**, since they intentionally change identifiers or access. A fresh separate scratch run may be used for these terminal cases.
4. Use the two supplied PDFs in `fixtures/` (versions 1 and 2). They are visibly fake test files, not certificates or personal data. Open both before use. The optional `scripts/evaluation_document_fixture.py --output-dir <fresh-scratch-folder>` reproduces them without overwriting existing files. Creating or inspecting a fixture is not a measured filing result.

The scratch OCR backend is a placeholder. A file may be active for filing while its separate quality status says manual quality review is needed; record both states rather than treating quality review as replacement approval.

## Document and correction cases

| Case | Operator action | Expected result |
|---|---|---|
| DOC-01 | As Student A upload v1 into clearance, JAMB, WAEC, birth, state-of-origin and biodata categories. | Six initial records are active without approval. Each is attached to A, not B. Record per-category outcome. |
| DOC-02 | Download and open each active document as A; repeat as adviser and HOD. | Correct bytes/version available privately to all three authorised roles. Record content hash or visible version and browser outcomes. |
| DOC-03 | As B and then unassigned staff try A's document list/download using the same document URL. | Access denied; no file bytes or protected metadata disclosed. Do not copy session cookies or tokens to evidence. |
| DOC-04 | As A upload v2 as a replacement for clearance; inspect as A/adviser/HOD. | Candidate pending, v1 remains active. Pending state and previous version are visible. |
| DOC-05 | Adviser rejects with a written reason. A submits another v2 replacement. | Rejection reason visible; v1 active; resubmission allowed. |
| DOC-06 | HOD approves the fresh replacement. Download current and archived versions as A/adviser/HOD. | v2 active, v1 archived and retained; authorised history/download works. |
| DOC-07 | Submit another student replacement, then let staff upload a newer active version before approving that candidate. | Stale approval refused; newer active file is not overwritten. |
| ACC-01 | A proposes contact and guardian changes; adviser approves. | Active details unchanged until approval, then approved fields update; request/reason/history retained. |
| ACC-02 | After the GPA and other journeys, A proposes name/programme/matric correction; reviewer attempts each permitted action. Do not change EVAL/001 before importing the supplied CSVs. | Students cannot edit protected fields directly. Existing authority rules apply; HOD identifier correction preserves UUID and old identifier reservation. Use a fresh synthetic value. |
| ACC-03 | A opens B's requests/file routes. | Denied without changing or disclosing B's record. |

Measure upload only from **Upload click to success/error rendered**, retrieval only from **Download click to file fully available locally**, and review only from **Save review click to updated state rendered**. These are operator task durations, including browser/network/server work, not pure database latency. Do at least three repetitions of any timed comparable case, record file size and device; do not time manual reading as retrieval. No speed-improvement claim is justified without an equivalent timed manual baseline.

## Full synthetic semester: independent arithmetic

This is a complete **synthetic** semester fixture, not evidence that the department's institutional grading/repeat policy has been approved. The test scale is 70+=5, 60+=4, 50+=3, 45+=2, 40+=1, below40=0. The current implemented calculation includes every saved verified attempt. Expected figures below are computed from explicit units and grade points, independently of the application's calculator. Exact fractions are provided so presentation rounding does not masquerade as a calculation error.

Both students start with three prior verified results: `3*5 + 2*4 + 3*0 = 23` quality points over `8` units (prior GPA23/8=2.875). Current results are intentionally **not** seeded; import them yourself.

| Case | Action | Independent expectation |
|---|---|---|
| GPA-01 | HOD/adviser uploads `fixtures/results-semester.csv`, checks preview, commits; before verifying scores try the current GPA/CGPA. | Ten rows (five per student), correct student/course/period mapping. Unverified results must not be presented as a verified calculated average. |
| GPA-02 | Verify all current scores and review both students' GPA and CGPA. | Current `15+12+6+4+0=37` points /11units =3.36 to2dp. Cumulative `(23+37)/(8+11)=60/19` =3.16 to2dp. Compare every course/units/score against `gpa-manual-ledger.csv`. |
| GPA-03 | Import and verify `results-repeat-b.csv` for B. | B current `(37+15)/(11+3)=52/14` =3.71. B cumulative `(60+15)/(19+3)=75/22` =3.41. A stays3.36/3.16. |
| GPA-04 | Import/approve correction `results-score-correction-a.csv`; before reverification check averages. | EVAL209 changes35->72; verification resets. Do not accept a certified/verified average until the revised score is verified. |
| GPA-05 | Verify corrected A score and calculate again. | A current42/11=3.82, cumulative65/19=3.42; B unaffected. |
| GPA-06 | As A try to access B's results/calculations and as unassigned staff try private calculations. | Only authorised scope succeeds. Record exact denial and no data disclosure. |

The expected file `gpa-independent-expected.csv` contains these figures. Never replace its expected columns with application outputs. Record raw returned values and display rounding separately. Log actual outcome, screenshot/API evidence and discrepancy if any. Do not alter grading rules merely to make a fixture pass.

## Optional guardian PDF preview (before terminal identity/handover/archive cases)

Use only a synthetic guardian with an `@example.invalid` email and an explicitly labelled test-only sharing preference. Do not queue or drain result deliveries. The scratch configuration disables result dispatch; memory-only preview validation is separate from actual email delivery.

| Case | Operator action | Expected result |
|---|---|---|
| GUA-01 | After verifying the semester results, HOD prepares an original result preview for synthetic Student A and opens the saved PDF. | Correct student/period and selected-semester rows; GPA/CGPA agree with the current oracle stage. Preview itself sends nothing. |
| GUA-02 | Following the verified score correction, HOD creates a fresh revised preview with a unique internal reason, then opens the saved replacement PDF. | Revised Result label; correct updated values; internal reason absent from PDF. Keep the earlier preview as history. |
| GUA-03 | As student and ordinary staff attempt the HOD PDF/dispatch routes; inspect an unchanged old preview after the correction. | HOD-only access enforced; earlier saved bytes are preserved. Stale source cannot be silently sent. Do not enable dispatch or claim inbox delivery. |

If fixture guardians/preferences are unavailable, record BLOCKED with the missing prerequisite; do not use a real guardian to fill the gap. Record download/open time separately from PDF-generation request time, using the matching start/end events.

## Password, HOD handover and archive cases (run last)

| Case | Operator action | Expected result |
|---|---|---|
| ACC-04 | Sign in as EVAL-SETUP using the chosen scratch password; try another workspace before changing it, then choose a new password. | Mandatory-change page, other APIs blocked; after change access activates without another approval. Old password no longer signs in. |
| ACC-05 | Review isolated automated credential/reset evidence separately. | Generated temporary-password mail and single-use reset-token handling may be verified with isolated-memory email tests. This is **not** proof of actual SMTP delivery or a complete manually received-email journey. No public mailbox route is added. |
| ACC-06 | Current synthetic HOD offers handover to EVAL-HOD-SUCCESSOR, inspect both profiles, then successor accepts. | Before acceptance no role change. Afterwards sender loses HOD authority, successor gains it. Repeat acceptance has no second effect. Unrelated staff cannot accept. |
| ACC-07 | New synthetic HOD archives B (or changes terminal academic status), records reason; attempt B sign-in and inspect retained history as authorised staff. | Login inactive, records/documents/results retained; no deletion. |

Use a fresh scratch run for another full session rather than undoing a handover or deleting history to conceal a failed case. Complete one row per case/repetition in the master results template. All rows begin NOT_RUN; staging and existing automated passes do not constitute today's operator results.
