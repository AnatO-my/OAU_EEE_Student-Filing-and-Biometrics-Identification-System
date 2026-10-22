# Project Report Materials Review

Review date: 17 October 2026

Approved project title: **Design and Implementation of an Integrated Fingerprint Biometric and Web-Based Student Management System**

The report needs a change in its central argument before sentence-level polishing. The supplied drafts mostly describe a fingerprint attendance project with a web interface. The intended report should first establish the departmental filing and student-records problem, explain the web application's responsibilities, and then motivate biometric identification within a defined records workflow. One integrated problem statement and two research questions can express these connected responsibilities.

The project owner clarified on 17 October 2026 that records are predominantly hard copies, are difficult to retrieve, and require considerable effort to review, update and correct. The owner also confirmed that the filing system includes **both structured records and uploaded documents**. These clarifications ground the problem statement and establish document management as required scope. They are project-owner observations, not a completed interview study, quantified baseline or claim that every departmental record is on paper.

There are also substantive corrections to make: an incorrect bibliographic entry, unsupported numerical comparisons, descriptions of hardware different from the tested prototype, and descriptions of integration that go beyond the saved evidence. The original supplied files have been preserved. This review and the companion Chapter One proposal are separate working documents.

## 1 Review coverage and document roles

All 16 supplied files were inventoried and their text extracted, including the DjVu book. The four apparent project drafts were reviewed throughout: F01, F03, F10 and F11. F01 actually includes Chapters One and Two; F03 contains material labelled Chapters Three through Five. The books and the 114-page reference thesis were screened and relevant sections consulted rather than read exhaustively. Journal papers were checked for their actual architecture, reported evaluation and limitations. Selected PDF pages were rendered to verify layout, tables and page references.

DOCX review covers text, paragraph structure, headings, tables and reference content. The packaged renderer could not run because bundled LibreOffice was unavailable, so this review does not certify Word pagination or visual layout. PDF extraction sometimes joins words or produces large spaces; those extraction effects have not been treated as typographical errors in the originals.

PDF locations below use **physical PDF page numbers**, counting the first page as 1. Printed page numbers are added where useful. Word locations use section headings, distinctive wording or table items, rather than unverified page numbers. Roles are inferred from content and can be adjusted if the team identifies a different authoritative draft.

| ID | Supplied material | Role and review decision |
| --- | --- | --- |
| F01 | Chapter_1_Introduction.pdf, 12 pages | Project draft containing Chapter One on pages 1-4 and Chapter Two on pages 5-12. Use as a starting outline; revise its attendance-first argument. |
| F02 | FNAS-JCAA-36-2-2-2025-99-110.pdf, 12 pages | Odulaja (2025), fingerprint attendance study. Useful comparator for hardware, timing and reported recognition results; assess its evidence critically. |
| F03 | CHAPTER 3 METHODOLOGY.txt, 213 lines | Project scaffold for Chapters Three, Four and Five. Retain useful caution about unperformed tests, but replace instructions and placeholders with the actual methods and results. |
| F04 | DESIGN AND IMPLIMENTATION OF WEB BASED ACADEMIC INFORMATION SYSTEM.pdf, 114 pages | Aliyu's 2015 MSc thesis on WeBAIS. Important records and academic-system reference; do not adopt its numerical conclusions or older implementation choices uncritically. |
| F05 | ejoseph,+253+-+265+A+FINGERPRINT+BASED+STUDENTS+ATTENDANCE.pdf, 13 pages | Olasupo et al. (2022), Olabisi Onabanjo University attendance system. This is the supplied Olasupo paper, with C# and SQL Server. |
| F06 | GJETA-2026-0110.pdf, 10 pages | Adediran, Adetutu and Semilore (2026), OmniAttend. Useful recent integration comparator; its perceptual-hash threshold is not an accuracy percentage. |
| F07 | 2020_05_023_NJSTR-c.pdf, 8 pages | Osasuyi, Oghogho and Ihedi-Okonkwo (2020), fingerprint attendance management. Crossref confirms Osasuyi as the first author's family name despite the paper's inconsistent running header. |
| F08 | OBCAMS_-_An_Online_Biometrics-based_Class_Attendance.pdf, 14 pages | Adetiba et al. (2013), online biometric attendance. Essential prior art against an unrestricted claim that web and fingerprint integration is new. |
| F09 | ajol-file-journals_90_articles_247067_submission_proof_247067-1069-592014-1-10-20230505.docx | Omorogiuwa, Nwelih and Aweh (2023), biometric student information retrieval. Particularly relevant to connecting filing and identity. |
| F10 | Chap.2 Literature review.docx | Project Chapter Two draft; no reference list appears at its end. Substantially overlaps F11. |
| F11 | DOC-20261014-WA0017.docx | Another version of the same Chapter Two, with a reference list. Treat as a version to reconcile with F10, not as an independent reference. Its citations need repair. |
| F12 | 2019(5).pdf, 5 pages | Mardaniyan (2019), web-based student information management. Publisher record was located. Useful records-first comparator, with narrow synthetic loopback benchmarks. |
| F13 | Biometric Systems Technology Design and Performance Evaluation, 380 PDF pages | Wayman, Jain, Maltoni and Maio, editors (2005). Foundational biometric architecture and evaluation reference. Consulted relevant introductory and evaluation sections. |
| F14 | 2021 International Conference on Information Technology paper, 4 pages | Milivojevic et al., MTseng-v online handwritten-signature classification. Peripheral metric reference; this is not a fingerprint-recognition paper. |
| F15 | File Management and Information Retrieval Systems, 296 PDF pages | Gill (1993), third edition. Foundational filing and records-lifecycle reference; useful for the report's conceptual starting point. |
| F16 | Computational Algorithms for Fingerprint Recognition, 208 DjVu pages | Bhanu and Tan (2004). Text successfully decoded. Useful for recognition concepts; not evidence that its algorithms run inside the project's AS608. |

Source file links and verified bibliographic details appear in Section 12.

## 2 The argument the report should make

The organising sequence should be:

1. Define the departmental student record and the activities it supports.
2. Establish how records are currently created, classified, updated, retrieved and protected, using local evidence.
3. Explain the consequences of the specific shortcomings actually observed.
4. Derive the web-based filing and student-management requirements.
5. Identify the activity that requires confirmation of a student's identity, such as the agreed attendance workflow.
6. Explain the biometric subsystem and its link to the permanent student record.
7. Evaluate records management, biometric recognition and integration separately and together.

A fingerprint subsystem can supply identity evidence. It does not, by itself, correct inaccurate results, organise files, enforce staff permissions, prove course eligibility or establish attendance merely because a scan was saved.

Use **filing system** to mean the organisation and controlled management of departmental student records, including both structured database records and scanned or uploaded documents, as the project owner confirmed. The repository supports many structured-record operations, but private document upload, versioning and archival storage are still listed as unresolved work. This is now a gap between confirmed scope and demonstrated implementation. Include it in requirements, design, methodology and evaluation; do not describe the document-management functions as complete before they are implemented and tested.

The local starting point is now available: the project owner's dated observation of predominantly hard-copy records and difficult retrieval, review and correction. The fuller workflow still needs documenting: record categories, custodians, indexing, update authority and retrieval steps. The supplied papers concern other institutions; they cannot prove OAU EEE file losses, a particular retrieval delay or measured impersonation. Do not expand the owner's observation into claims of universal paper storage, proven data loss or quantified inefficiency.

## 3 Corrections to Chapter One and the Chapter Two inside F01

| Priority | Location | Finding | Recommended correction |
| --- | --- | --- | --- |
| High | F01, page 1, Background | The report opens with attendance and registration rather than the broader filing and records problem. | Begin with the student record, academic history, update/retrieval workflows and access responsibilities. Introduce attendance later as an identity-dependent application. |
| High | F01, pages 1-2 | Broad statements about manual practice and institutional shortcomings have no supporting citations in Chapter One. | Separate literature-supported general problems from evidence about this department. Add citations at the claims they support and obtain the local baseline. |
| High | F01, page 2, problem items 1-5 | Proxy attendance dominates; filing is reduced to one item. Item 4 asserts an absence of integration without a defined surveyed population. | Use connected paragraphs: records-management difficulty, consequence, identity requirement, and the integrated engineering problem. Avoid a universal claim about existing systems. |
| High | F01, pages 2-3, research questions | Five overlapping questions divide the hardware, integration and web interface into separate questions. The final question commits to comparison with a manual method. | Use two principal questions, one for records management and one for biometric integration. Only retain a comparative-speed claim if equivalent baseline tasks will be measured. |
| High | F01, page 3, objectives | Hardware and firmware precede the database and application; academic-record functions are under-specified. | Reorder objectives around requirements, records/database, web functions, terminal, integration and evaluation. Tie each to evidence in Chapter Four. |
| High | F01, page 4, scope | Automatic timestamped attendance is presented as a core function without distinguishing intended operation from completed integration. | State the final intended scope and separately report what the current prototype demonstrates. The latest deferred-capture path stores pending evidence, not identified attendance. |
| Medium | F01, page 4, capacity limitation | The whole system is described as limited by fingerprint-sensor storage. | Distinguish scanner reference-gallery capacity, ESP32 capture storage and backend database capacity. They are different constraints. |
| Medium | F01, pages 1-4 | Registration, enrolment, identification and verification are used without a precise workflow definition. | Define student-profile creation, course registration, biometric enrolment and login-account creation separately. State when recognition is 1:1 or 1:N. |
| Medium | F01, page 1 | Fingerprint wording implies strong resistance to forgery without establishing attack testing. | Say fingerprints provide a biometric basis for recognition, while performance depends on acquisition, enrolment, matching and operational controls. Do not claim spoof resistance or guaranteed presence. |
| Medium | F01, pages 5-8, past works | The author-by-author review repeatedly concludes that a source is relevant and narrower than the present project. | Group studies by records systems, biometric retrieval, and attendance/integration; compare evidence, not just application labels. |
| Checked | F01, page 6, Osasuyi citation | The paper's running header is inconsistent with its registered author metadata. | Crossref confirms Osasuyi, O. O.; Oghogho, E. J.; and Ihedi-Okonkwo, N. O. The draft's first-author surname Osasuyi is correct and should be retained. |
| High | F01, pages 5-7 | Several described works are not supplied as primary papers: Onyishi and Igbinoba; Basila and Danladi; Syahrul et al.; Sidik et al.; Adedoyin et al.; Akanni et al. | Obtain and check the actual papers before retaining detailed component or performance statements. Where only a supplied paper's reference is available, identify it as a secondary citation rather than imply the original was read. |
| Medium | F01, pages 8-10, Review of Problem Solved | The section repeats the problem statement and sometimes describes proposed features as remedies already established. | Convert it into a critical synthesis of findings, limitations and implications. Avoid claiming that the present project has solved a problem before evaluation. |
| Medium | F01, page 9 | Attendance is conditional here, although it is central and definite in Chapter One. | Reconcile scope across the chapters using the team's agreed attendance requirements. |
| Medium | F01, pages 10-12 | Detailed methodology appears inside the literature chapter, with component and framework selections still described as undecided. | Keep a short gap-to-method bridge in Chapter Two; move actual design and procedures into Chapter Three. Update established component choices from the logs. |
| Medium | F01, whole file | The filename suggests only Chapter One, but pages 5-12 are Chapter Two. No reference list is included. | Split or clearly version the chapters and provide one complete, consistent bibliography. |

The companion Chapter One proposal supplies a replacement argument, problem statement, two questions, aim, objectives and a scope framework using the owner's actual observation and confirmed document-management scope.

## 4 Corrections to the standalone Chapter Two versions

F10 and F11 have substantially the same body; a comparison of extracted paragraph text produced approximately 97.6% character similarity including F11's additional bibliography. This is a version-management issue, not evidence of copying from another publication. Reconcile them into one authoritative Chapter Two before revision.

| Priority | Location in F10 and F11 | Finding and correction |
| --- | --- | --- |
| High | Opening and section 2.1 | Sensor technology leads the chapter; filing, information retrieval, academic data integrity and web architecture are largely absent. Rebuild the conceptual sequence around the records system. |
| High | Section 2.1, first paragraph | Terms such as immutable and indisputable overstate the operational conclusion. Distinguish the relative persistence of ridge structure from variable captures and fallible automated decisions. |
| Medium | Sections 2.1.1-2.1.2 | Precise optical, ultrasonic, ESD, contamination and cost claims are mostly uncited, and some are absolute. Retain only sourced comparisons that help justify the actual sensor choice. Do not imply every optical module uses an identical optical design. |
| High | Section 2.1.3, specifications | The draft gives 162/300 reference slots; the tested scanner reports 150. Report the actual measured capability and keep generic catalogue specifications separate. |
| High | Section 2.1.3, specifications | FAR below 0.001%, FRR below 1%, a full-gallery search below one second and IEEE/FBI compliance are asserted without a verified module-specific source or supporting experiment. Remove them as project findings. Nominal 500 dpi alone is not evidence of certification. |
| High | Section 2.1.3, internal processing | The draft specifies median filtering, adaptive binarisation, thinning and Euclidean-distance matching as the AS608's internal algorithm. The project evidence does not establish these proprietary internals. Describe documented commands and observed behaviour; present general algorithms as background only. |
| High | Section 2.1.3, 512-byte statement | A 512-byte template is assumed, while the saved hardware export measured 1,536 bytes for the tested opaque reference. Specify the actual transferred representation and distinguish payload length, UART packet size and reference slots. Do not generalise one export to all modules or buffers. |
| High | Sections 2.2.1 and 2.4 | ESP32-S3 is described as the installed controller. The upload/test evidence identifies a regular ESP32-D0WD-V3, revision 3.1, with 4 MB flash. Replace the part description and use the appropriate datasheet. |
| High | Sections 2.2.2 and 2.4 | DS3231 is described as the installed RTC; the recorded pilot used DS1307. Update the actual bill of materials and distinguish any future component change. |
| High | Section 2.4 | Millisecond-accurate calendar timestamps are attributed to DS3231. Its calendar registers provide seconds; resolution, oscillator accuracy and elapsed-millisecond timing are different quantities. The current deferred capture path deliberately leaves calendar time null. |
| Medium | Section 2.2.2 | Even as a DS3231 background statement, +/-2 ppm across -40 to +85 C is incorrect. The manufacturer specifies +/-2 ppm from 0 to +40 C and +/-3.5 ppm over the wider industrial range. At 2 ppm, a year corresponds to about 63 seconds before other errors are considered, not less than a minute. |
| High | Sections 2.2.3 and 2.4 | Battery operation, regulation, transistor-driven buzzer and a fully mobile assembly are stated as facts without corresponding assembly evidence. Use the actual schematic, part markings, wiring, power measurements and photographs. |
| Medium | Sections 2.2.4-2.2.6 | Alternative displays and generic component catalogues obscure the selected build. Separate alternatives considered from the final parts, with part numbers and justified electrical connections. |
| High | Section 2.3 and Table 2.1 | Six studies support precise claims such as 98.2% accuracy, 85% bandwidth reduction, 15-30 second delays and more than 45 second boot times without verified source passages. Quarantine these figures and rebuild the table from papers actually available. |
| High | Section 2.3, Olasupo row | The supplied Olasupo study is from 2022 and uses C# and Microsoft SQL Server, not the cited 2020 C#/Access paper. F05 does not establish the table's 98.2% figure. Do not silently relabel one paper as the other. |
| High | Section 2.4, gap synthesis | The draft infers corruption from lack of an RTC, treats cloud-dependent systems as a uniform category, and assumes older processors cannot support adequate communication. These causal claims need evidence. State the precise limitation actually documented for each source. |
| High | Section 2.4, integration paragraph | Automatic HTTPS posting, student-dashboard updates and automatic batch synchronisation are written as completed behaviour. Saved evidence supports offline capture, USB export and pending backend ingestion; identity reconciliation and the complete browser workflow remain unfinished. |
| High | Section 2.4, course-credit validation | Course credit units do not by themselves establish student registration or eligibility for a particular class. Describe the approved course roster, class session, identity resolution and permission checks. |
| Medium | Whole chapter | Unsupported evaluative language includes ideal, massive performance leap, prohibitive and guarantees. Replace it with a requirement, documented specification or measured comparison. |

Manufacturer correction source: [Analog Devices DS3231 datasheet, pages 1 and 3](https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf). The actual RTC's functions should instead be referenced to the [DS1307 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds1307.pdf), alongside the project test log.

### 4.1 Bibliography decisions for F11

An unsuccessful title search is not proof that a paper does not exist. The statuses below distinguish an identified mismatch from references that remain unverified. None should be used to support a numerical comparison until the actual paper and passage have been checked.

| Entry | Status and action |
| --- | --- |
| Adegboyega, Omidiora and Olabiyisi (2021), GSM biometric attendance, IJECE 11(4), 3120-3129 | No matching primary publication was located in the targeted title searches during this review. Obtain the full paper/DOI or replace it; do not retain its alleged delay and cost findings. |
| Al-Haitamy and Hassan (2024), lightweight RESTful API, IEEE Transactions on Human-Machine Systems 54(2), 145-156 | Unverified. Obtain the publisher record and full article before using the claimed 85% traffic reduction. |
| Chandramohan et al. (2021), JPCS 1911(1), 012015 | **Confirmed bibliographic mismatch.** DOI 10.1088/1742-6596/1911/1/012015 is registered for *Improving Throughput in Sub-Nyquist Spectrum Sensing using a Cluster Model for Cognitive Radio Networks*, not the quoted fingerprint paper. Remove or correct the entry from the true original source. |
| Ezema and Chukwuma (2022), cloud-integrated student management | Unverified. The Firebase, TLS and corrupted-timestamp narrative is unsupported until its source is obtained. |
| Memane, Kulkarni and Deshmukh (2023), smart campus portal, IEEE Access | Unverified. Remove the Raspberry Pi power/boot-time comparison until the actual article and measurement conditions are available. |
| Olasupo and Bamidele (2020), PC-tethered attendance, NIJOTECH | Not established by the supplied material. The available Olasupo et al. paper is F05 from 2022, with different authors, title and database. Replace it only if F05 is the intended reference; rewrite the associated claims too. |
| Espressif Systems (2023), ESP32-S3 manual version 1.4 | A manufacturer manual can be an appropriate source, but verify the revision and use the manual for the actual regular ESP32 when describing the built terminal. |
| Synochip (2022), AS608 manual revision 2.1 | This exact publication/version was not supplied or established in this review. Obtain the purchased module's documentation; do not treat a generic compatible-protocol manual as proof of its internal matcher, accuracy or certification. |

The confirmed DOI mismatch was checked against the [Crossref registration record](https://api.crossref.org/works/10.1088/1742-6596/1911/1/012015). The local audit retains the returned metadata under the temporary review folder.

## 5 Corrections to the methodology results and conclusion scaffold

| Priority | F03 location | Finding and proposed treatment |
| --- | --- | --- |
| High | Lines 3-18, Figures of Merit | The metrics are useful but almost entirely attendance-oriented and not operationally defined. Add filing correctness, update consistency, retrieval tasks, permissions, academic calculations and data-import outcomes where in scope. Define denominators and timing boundaries. Use the plural heading Figures of Merit. |
| Medium | Lines 7, 48 and 132 | Odulaja's 100 students, reported 95% success and approximately seven-second processing time are supported by F02, but are repeatedly restated. Keep them in related work and a qualified comparison, not as the project's methodology or conclusion. |
| High | Lines 20-40, block diagram | No actual block diagram is supplied here. The sequence assumes immediate sensor-side identification and network attendance updates. Replace it with the selected architecture and show the present deferred-capture path separately. |
| High | Lines 42-54, Mathematical Model for Sensitivity | The section contains neither a mathematical model nor defined input/output variables. It also mixes sensitivity to operating conditions with classification sensitivity. Rename it Performance Measures and Operating Conditions, or supply a defensible model using measured variables. |
| High | Lines 56-64, circuit design | General advice cannot substitute for circuit analysis. Add the actual board, sensor, RTC, pin table, supply and logic requirements, shared grounds, bus pull-ups, feedback connections and measured operating conditions. |
| High | Whole Chapter Three | Database design, academic rules, web architecture, access policy, interface/API contracts, data preparation, development method and requirements traceability are missing. These are central to the approved title. |
| High | Lines 67-145, proposed Chapter Four | Results are instructions, conditional descriptions and blank test outcomes. Replace them with actual tables, figures, observations and limits after evidence is assembled. Preserve unperformed work as planned work, not results. |
| Medium | Lines 79-87, PCB Layout | The text correctly cautions against claiming a fabricated PCB. Make the final heading match the actual assembly: breadboard, stripboard or PCB, supported by a photograph and connection diagram. |
| High | Lines 95-130, checklist | Pass/fail fields have no datasets, sample counts, expected results, observed results or evidence identifiers. Use a test matrix with those fields; include denied access, duplicate retries and incomplete identity/timing cases. |
| Medium | Lines 147-183, comparison | Changing ATmega328P to ESP32 and serial to Wi-Fi is a design difference, not evidence of improved speed or reliability. Compare timing only with equivalent definitions and qualify differing datasets. |
| High | Lines 185-195, conclusion | The conclusion discusses another paper's performance and promises a future determination of this project's success. The final conclusion must answer this project's questions using its own recorded results and limitations. |
| Medium | Lines 54, 77, 87, 179 and 191 | Editorial instructions and export residue remain, including references to what the group should insert, a merged sentence and the literal HTML entity `&#x20;`. Remove them from final chapter prose. |
| Medium | Whole scaffold | Repeated labels such as the group's prototype, our project and general advice change the register. Choose consistent academic prose and past tense for performed procedures; reserve future tense for plans. |

For a 1:1 genuine/impostor decision experiment, sensitivity or recall can be defined as TP / (TP + FN), specificity as TN / (TN + FP), false-positive rate as FP / (FP + TN), and false-negative rate as FN / (FN + TP), with percentages multiplied by 100. These describe the defined decision protocol. Do not automatically call all of them matcher-level FMR/FNMR or apply 1:1 terminology unchanged to a 1:N search. Include wrong-identity, failed-acquisition and no-decision outcomes separately.

## 6 What the current project evidence supports

These statements are based on saved project documentation and relevant implementation structure available during this review. Historical test results were not rerun as part of the document review. A final submission should record the code revision, build/profile, dataset and evidence date behind each reported result.

| Area | Supported description | Boundary on the claim |
| --- | --- | --- |
| Records backend | Django models/services/APIs exist for student and guardian records, academic records and calculations, permissions and other documented workflows. | Implemented backend operations do not prove that the React/browser workflow is connected, deployed or accepted by departmental users. |
| Uploaded filing documents | Confirmed project scope includes scanned/uploaded student documents as well as structured records. | Private upload/download, file categorisation, revisions, retention and access-controlled storage are not established as implemented by the reviewed evidence. They need design and tests as required work. |
| Database validation | The 16 October attendance validation record reports 337 tests passing on an isolated PostgreSQL 16.15 cluster, including contention and HTTP cases. | This supersedes older statements that all PostgreSQL validation is pending. It does not establish shared-database reconciliation or production migration. |
| Fingerprint terminal | Hardware logs identify regular ESP32-D0WD-V3, AS608-labelled scanner, capacity 150 and 57,600-baud scanner communication. | Module firmware and internal matching implementation remain uncertain. Do not substitute S3 catalogue specifications. |
| Reference transfer | A tested reference was exported, restored and read back as 1,536 opaque bytes with matching integrity checks. | Transfer integrity does not prove a standard minutiae format, second-module compatibility or software-only server matching. |
| Recognition pilot on 15 October | Separate 1:N and selected-slot 1:1 Search experiments each contain 10 genuine and 10 designated unenrolled-finger attempts, with 20 correct decisions in that experiment. | One participant, one stored reference and correlated repetitions do not establish population accuracy or multi-identity identification. Do not pool later feasibility checks into these denominators. |
| Timing in that pilot | Recorded processing medians are approximately 898-982 ms across the four cases; exact values are in the pilot record. | Timers exclude human waiting, cooldown and the RTC read. They are not complete class attendance throughput or a comparable benchmark against another paper's full workflow. |
| RTC in that pilot | DS1307 supplied trial-linked timestamps after PC synchronisation. | One-second calendar resolution; no calibrated absolute accuracy, long-term drift or battery-retention result is established. |
| Deferred capture on 16 October | Unidentified probes were saved in ESP32 LittleFS, exported over USB and checked after an operator-reported power cycle. Saved-probe comparison was performed using the scanner. | This is feasibility and persistence evidence, not a new accuracy study or a software-only matcher. The current capture records intentionally have no trusted calendar timestamp. |
| Pending backend ingestion | Authorised preview/import/list, immutable capture evidence, retry receipts and append-only batches are implemented and tested. | An accepted capture import creates pending evidence, not a student identity, attendance, absence or warning. Identity/timing review and reconciliation are still required. |
| Full integration | Several foundations are present, with a documented continuation path. | Completed scanner-assisted identity orchestration, attendance reconciliation, device authentication, browser integration and field evaluation are not established by the reviewed evidence. |
| Physical assembly | Hardware operation and enclosure design evidence exist. | Use actual photographs and fit/fabrication checks to establish the final packaged build. A CAD design is not a fabricated enclosure or PCB. |

The evidence documents are [fingerprint-pilot-results.md](<C:/Users/Ot/Downloads/EEE-Project/docs/fingerprint-pilot-results.md>), [fingerprint-hardware-test-log.md](<C:/Users/Ot/Downloads/EEE-Project/docs/fingerprint-hardware-test-log.md>), [attendance-device-handoff.md](<C:/Users/Ot/Downloads/EEE-Project/docs/attendance-device-handoff.md>), [attendance-pending-batches.md](<C:/Users/Ot/Downloads/EEE-Project/docs/attendance-pending-batches.md>) and [attendance-validation.md](<C:/Users/Ot/Downloads/EEE-Project/docs/attendance-validation.md>). Earlier README and planning-guide statements must be reconciled with these later checkpoints rather than copied as current status.

## 7 How to use the supplied references

| Source | Useful contribution | Limitation to carry into the report |
| --- | --- | --- |
| Gill, F15 | Records lifecycle, organisation, retrieval and documented filing procedures provide the conceptual entry point. Consulted printed pages 3-6, PDF pages 23-26, and the contents. | A 1993 management manual is not evidence about today's departmental practice, current web security or present legal requirements. Treat classification, retention and centralisation chapters as further reading where needed. |
| Aliyu, F04 | WeBAIS connects academic records, user categories, departmental functions, web architecture and appraisal. Relevant passages: PDF pages 15-20, 66-77. | Treat appraisal as user feedback, not objective proof of percentage efficiency/security gains. Its implementation and institutional scale differ from this prototype. |
| Mardaniyan, F12 | Records-first design, relational structure, role separation and functional testing. Methods on pages 2-3; results on page 4. | Measurements use 2,000 synthetic records on one host over loopback. Values around 0.70-1.08 ms are not Internet/browser latency or production guarantees. Publisher metadata supports the stated 2019 citation; the downloaded PDF's later creation date alone does not invalidate it. |
| Omorogiuwa et al., F09 | Direct prior art for fingerprint-linked retrieval of student information, with a Visual Basic implementation and a simple student data dictionary. | No reproducible biometric error-rate or controlled retrieval-time experiment is supplied. Its update-access approach is not a reason to let a fingerprint match bypass this project's staff permissions. |
| Adetiba et al., F08 | OBCAMS demonstrates that online biometric attendance and role-based web interaction predate this project. Architecture on PDF pages 3-4; evaluation on pages 11-13. | The 89.33% result is average **first-signing-attempt** success over five experiments with 60 students. Later attempts are reported separately. This is not a measured false-acceptance rate. |
| Olasupo et al., F05 | Desktop-client/networked-database attendance design using DigitalPersona, C# Windows Forms and SQL Server. See PDF pages 1-3. | Do not attach the standalone draft's 98.2% claim or Access database to this paper. Screens and features do not establish a general biometric error rate. |
| Odulaja, F02 | Useful embedded attendance comparator: ATmega328P, five RS305 modules, reported 95% success and approximately seven-second identification/verification time. See PDF pages 1, 10-11. | The eight-round table and discussion do not supply a fully reconstructible per-attempt confusion matrix. A reported attendance increase across different semesters is not, by itself, a controlled causal result. |
| Osasuyi et al., F07 | Enrollment, matching, attendance/database linkage and report generation; Java/MySQL with HTML/CSS is described, though parts of the platform terminology are inconsistent. See PDF pages 1-3 and 7. | The source reports enrollment within about 80 seconds and an attendance operation below 10 seconds, without a detailed timing distribution. Do not compare it directly to the project's sensor-command timer. |
| Adediran et al., F06 | Recent React/Firestore/Node bridge integration, QR and fingerprint pathways, unified attendance logging. Architecture on PDF pages 2-4; limitations on pages 8-9. | The 0.80 perceptual-hash similarity threshold is not 80% recognition accuracy. Participant/trial counts and a reproducible confusion matrix are insufficiently specified. Windows support and lack of offline capture are source-reported limitations. |
| Wayman et al., F13 | Generic biometric subsystems and application-dependent evaluation. Consulted Chapter One, printed pages 3, 6 and 9-13, and Chapter Six, pages 151-152. | This is an edited 2005 volume. Cite the relevant chapter author when making a chapter-specific claim. Historical technology results are not current sensor guarantees. |
| Bhanu and Tan, F16 | Feature extraction, recognition modes, indexing and matching concepts. Consulted Chapter One, printed pages 7-11, DjVu pages 28-32, and contents. | General algorithm descriptions do not reveal the AS608's proprietary internal pipeline. Do not claim implementation of genetic algorithms, thinning or template-learning methods unless the team implemented them. |
| Milivojevic et al., F14 | An example of threshold and confusion-matrix reasoning in online handwritten-signature classification. | Different biometric modality and algorithm. It should not be a principal fingerprint or student-records comparator, and its numerical outcomes cannot validate this sensor. |

### 7.1 Reference quality issues that should not be inherited

F04's appraisal has internal reporting discrepancies. On PDF page 71, the listed respondent category counts sum to 93 while the total is stated as 82; whether categories overlap is not explained there. On page 72, Question 4's listed cells sum to 83 although its total is shown as 82. The corresponding favourable responses are 13 + 24, which do not substantiate a measured 56% improvement in service efficiency. The text also turns opinions about security into a percentage security improvement. Use this thesis for architecture and context, not as a numerical performance standard.

F09 is directly relevant, but its reference list also needs independent checking before any entry is reused. For example, the Weaver entry is labelled as fingerprint recognition while the supplied URL points to speech recognition. Bibliographic errors in a published source should not be reproduced in this report.

Do not treat an unmentioned feature as an established absence. Say that a paper **does not report an offline evaluation**, for example, rather than asserting that its implementation corrupts data whenever its network fails. Distinguish an author's stated limitation, a limitation apparent in the presented evidence, and a proposed requirement of this project.

### 7.2 A defensible contribution statement

The supplied set already includes a web-based biometric attendance system from 2013 and a biometric student-information-retrieval system from 2023. Consequently, the broad combination of fingerprint recognition, a database and web access is established prior work.

A defensible contribution is the design, implementation and evaluation of a departmental system that coordinates student and academic records with an explicitly defined fingerprint-assisted workflow, including identity binding, permissions, consistent updates and failure handling. Any narrower claim about a distinctive offline capture/reconciliation design must be supported by its actual implementation and an appropriately targeted literature comparison. Do not claim superiority or a first-of-its-kind system from the current source set.

## 8 Recommended whole-report structure

Use the department's required chapter template if one is provided. The sequence below is a content plan, not a claim that every institution requires these exact headings.

| Chapter | Recommended content and order |
| --- | --- |
| One Introduction | Student records and filing context; verified departmental workflow; statement of the problem; two research questions; aim and objectives; intended significance; scope and limitations; key terms if required. |
| Two Literature Review and Conceptual Foundations | Filing/records lifecycle and retrieval; student/academic information systems; data integrity and relational design; web architecture and permissions; biometric recognition and enrolment; sensor/controller/RTC choices; related systems grouped by function; comparison matrix; evidence-based gap and project contribution. |
| Three Methodology and System Design | Development approach; actual requirements-gathering procedure; requirements and traceability; records model/data dictionary; web/backend design; academic rules; actual terminal hardware and schematic; firmware states; enrolment/identity binding; selected communication and deferred-capture workflow; integration/failure paths; test protocols, datasets, metrics and ethical handling. |
| Four Implementation Results and Discussion | Records/backend outcomes first; interface integration evidence; data correctness and access results; terminal/build/assembly evidence; biometric pilot results and limitations; capture/export/import results; complete integration results only where performed; qualified comparison to prior work; unresolved failures. |
| Five Conclusion and Recommendations | Answer each research question from the project's evidence; state objectives achieved, partly achieved or outstanding; discuss limitations; recommend specific remaining work. Do not introduce another author's results as this project's conclusion. |

Component physics should explain a design choice. It should not displace records management, database design or the software/integration methodology. Keep extended catalogues, raw protocols and code listings in appendices where they are useful.

## 9 Questions objectives and evidence

**RQ1:** How can a web-based departmental filing system be designed and implemented to organise structured student and academic records alongside uploaded documents, while supporting accurate retrieval, controlled updating and authorised access?

**RQ2:** To what extent can a fingerprint biometric subsystem be integrated with that system to associate a presented fingerprint with the appropriate student record and support reliable, defined identity-dependent workflows?

These are two principal questions within one problem statement. The first establishes the records system; the second addresses the identity link and integration. Attendance is the currently documented application, not a replacement for the broader records-management purpose.

| Proposed objective | Question | Required result evidence |
| --- | --- | --- |
| Establish the departmental workflow and functional/access requirements. | RQ1, RQ2 | Dated process description, source of requirements, role/action matrix and identified local shortcomings. |
| Design the student, academic and document records model with stable identifiers and integrity constraints. | RQ1 | ER diagram, data dictionary, document metadata/storage design, uniqueness/reference checks and correction/history rules. |
| Implement the selected web-based record creation, document upload, updating, retrieval and reporting functions. | RQ1 | Actual connected workflows, expected-versus-observed record/document outcomes, permissions tests and measured retrieval tasks. |
| Implement the terminal functions required for fingerprint capture, enrolment/recognition and preservation of capture evidence. | RQ2 | Actual schematic and firmware profile, component checks, recognition protocol and storage/transfer evidence. |
| Integrate identity outcomes with the selected records/attendance workflow and its failure handling. | RQ2 | End-to-end identity binding, roster/permission decisions, duplicate handling, network/retry/recovery and unresolved-outcome cases. |
| Evaluate the records system, biometric subsystem and their integration against defined criteria. | RQ1, RQ2 | Separate functional, timing, recognition and integration datasets with limitations and evidence provenance. |

## 10 Gaps to fill before final prose

| Gap | Minimum information or evidence needed | Why it matters |
| --- | --- | --- |
| Present departmental filing workflow | The owner has reported predominantly hard copies and difficult retrieval/review/correction. Add categories, custodians, indexing method, retrieval/update steps and evidence records. | Grounds the problem locally without turning an observation into a completed formal study. |
| Document-management requirements and implementation | Both structured records and uploaded documents are confirmed scope. Define document categories, metadata, file limits, private storage, access, revision/correction history, retention and retrieval. | This is required work whose implementation and evaluation are not yet established. |
| Final included modules | A supervisor/team-approved list covering profiles, results, attendance, exports, messaging and any other selected functions. | Prevents unrelated screens and prototype ideas expanding the report silently. |
| Institutional academic rules | Authoritative grading, repeated-course, completeness and attendance policies where institutional claims are made. | Implementation choices must not be presented as official university policy without a source. |
| Final hardware | Board identification, module markings, schematic, pin table, power source, feedback parts and photographs. | Resolves the S3/regular ESP32 and DS3231/DS1307 contradictions. |
| Final biometric architecture | Where comparisons occur; enrolment-to-student binding; format/compatibility; scanner/gallery/slot namespace; resolution of unknown or ambiguous probes. | Resolves inconsistent device/server-matching descriptions and unstable identity assumptions. |
| Current deferred path timing | Trusted wall-clock provision and review rules; distinguish boot/uptime from calendar time. | Prevents unreviewed captures becoming falsely timestamped attendance. |
| Browser integration | Connected screens and real browser checks against authenticated APIs. | Backend and static prototypes alone do not demonstrate the complete web workflow. |
| Records evaluation | Defined dataset, tasks, expected outputs, failed/duplicate inputs, permission cases and observation records. | Gives the filing system an evaluation as substantial as the biometric pilot. |
| Biometric evaluation breadth | If broader claims are intended, additional participants and multiple enrolled identities, fresh probes, controlled settings and trial-level ground truth. | The current one-person/one-reference pilot cannot support population claims. |
| Baseline comparison | Comparable manual/current-system tasks, same record set, timing rules and operator conditions. | Needed for claims of faster retrieval, lower workload or improved throughput. |
| Physical packaging | Fabricated enclosure/assembly photographs and fit/power checks where claimed. | Distinguishes CAD or planned packaging from the assembled prototype. |
| Literature integrity | Actual source files/DOIs for unresolved references and a complete bibliography matching all in-text citations. | Prevents unsupported statements becoming the foundation of the research gap. |

### 10.1 Records and integration test plan

Use synthetic records for initial tests. Each case should record its identifier, requirement, dataset, preconditions, expected result, observed result, outcome and evidence location. Suggested tests are proposals unless a corresponding saved result is cited.

| Test group | Useful cases and measurements |
| --- | --- |
| Record identity | Duplicate student identifier rejected; identifier changes preserve stable student UUID and linked academic history. |
| Record retrieval | Retrieve the correct student and session/semester results; name collisions, absent records, filters and pagination return the expected results. Measure task time separately from database-query time. |
| Updating and integrity | Valid corrections persist; invalid or partial changes leave no inconsistent records; duplicate result attempts and invalid references are rejected. |
| Academic correctness | Compare GPA/CGPA and grade boundaries with independently worked examples; preserve the difference between a missing mark and a recorded zero. |
| Access | Test HOD, assigned adviser, out-of-scope adviser, course staff and student-own-record cases through the server/API, including attempted direct requests. |
| Uploaded documents | Upload allowed files into the correct student's file; reject disallowed/oversized inputs; test metadata search, authorised download, denied direct access, correction/version history and retention/recovery rules. Distinguish replacing a document from editing a structured record. |
| Imports and exports | If included, compare source rows with accepted/rejected rows, demonstrate safe re-import, and check export permissions and selected columns. |
| Recognition | Record enrolment, acquisition, genuine/impostor decisions, no match, wrong identity, errors and timing under the chosen 1:1 or 1:N protocol. Report the reference-gallery size. |
| Identity-to-record binding | Verify that the biometric outcome maps to the intended permanent student record, including reassigned slots, inactive mappings, ambiguous outcomes and out-of-roster students. |
| Deferred capture and ingestion | Preserve evidence through export/import/retry; reject conflicts atomically; do not infer identity or attendance from unresolved evidence. |
| Complete attendance workflow | Once implemented, test one record per student/class, roster checks, correction permissions, cancelled/excused cases and incomplete-class handling. |
| Recovery and operation | Demonstrate only the implemented backup/restore, restart and interruption paths. Synthetic failure tests and physical power-loss tests must be labelled separately. |

## 11 Recommended revision order

1. Reconcile one working version of each chapter and adopt the approved title consistently.
2. Document the fuller local workflow around the owner's observation and specify the confirmed uploaded-document requirements.
3. Revise Chapter One around the two connected problems and questions.
4. Rebuild the literature comparison from checked sources; remove the incorrect reference and unsupported numbers.
5. Replace generic methodology with the actual records model, software, hardware and integration design.
6. Assemble Chapter Four from saved evidence, keeping subsystem results distinct from complete integration.
7. Write the conclusion against the questions and measured outcomes.
8. Finish citation consistency, terminology, numbering, grammar, figures and page-layout checks.

The companion [Chapter One revision proposal](<C:/Users/Ot/Downloads/EEE-Project/docs/report-review/chapter-one-revision-2026-10-17.md>) is the concrete starting point for step 3. It incorporates the owner's observation and the confirmed structured-record/document scope; it does not describe unperformed interviews or assume departmental file losses.

## 12 Source register

The links below identify the exact supplied files. Bibliographic details are taken from their title pages or article text unless a publisher check is stated. They are working entries to standardise to the department's required citation style.

- **F01** [Project Chapters One and Two draft](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/Chapter_1_Introduction.pdf>). Project report draft supplied by the team; no individual authorship assigned in this review.

- **F02** [Odulaja 2025 fingerprint attendance study](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/FNAS-JCAA-36-2-2-2025-99-110.pdf>). Odulaja, G. O. (2025). Development of a fingerprint-biometric expert system for student class attendance monitoring. Faculty of Natural and Applied Sciences Journal of Computing and Applications, 2(2), 99-110.

- **F03** [Project Chapters Three through Five scaffold](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/CHAPTER 3 METHODOLOGY.txt>). Methodology, proposed results and proposed conclusion text supplied by the team.

- **F04** [Aliyu 2015 WeBAIS thesis](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/DESIGN AND IMPLIMENTATION OF WEB  BASED ACADEMIC INFORMATION SYSTEM.pdf>). Aliyu, M. M. (2015). Design and implementation of web-based academic information system for Nigerian universities. MSc thesis, Ahmadu Bello University, Zaria. Use the title on the internal title page rather than the misspelling in the filename.

- **F05** [Olasupo and colleagues 2022 OOU attendance paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/ejoseph,+253+-+265+A+FINGERPRINT+BASED+STUDENTS+ATTENDANCE.pdf>). Olasupo, A. O., and colleagues (2022). A fingerprint based students attendance management system for Olabisi Onabanjo University. FUDMA Journal of Sciences, 6(1), 253-265. DOI 10.33003/fjs-2022-0601-896. Expand the full author list from the article for the final bibliography.

- **F06** [Adediran Adetutu and Semilore 2026 OmniAttend paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/GJETA-2026-0110.pdf>). Adediran, O. S., Adetutu, S. A., and Semilore, O. A. (2026). Design and implementation of a web-based hybrid attendance management system using QR code and biometric fingerprint verification. Global Journal of Engineering and Technology Advances, 27(3), 129-138. DOI 10.30574/gjeta.2026.27.3.0110.

- **F07** [Osasuyi Oghogho and Ihedi Okonkwo 2020 attendance paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/2020_05_023_NJSTR-c.pdf>). Osasuyi, O. O., Oghogho, E. J., and Ihedi-Okonkwo, N. O. (2020). Design and implementation of a fingerprint-based attendance management system. NIPES Journal of Science and Technology Research, 2(2), 228-235. DOI 10.37933/nipes/2.2.2020.23. First-author family name confirmed against the Crossref record.

- **F08** [Adetiba and colleagues 2013 OBCAMS paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/OBCAMS_-_An_Online_Biometrics-based_Class_Attendance.pdf>). Adetiba, E., Iortim, O., Olajide, A. T., and Awoseyin, R. (2013). OBCAMS: An online biometrics-based class attendance management system. African Journal of Computing and ICT, 6(3), 25-38.

- **F09** [Omorogiuwa Nwelih and Aweh 2023 student information retrieval paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/ajol-file-journals_90_articles_247067_submission_proof_247067-1069-592014-1-10-20230505.docx>). Omorogiuwa, O., Nwelih, E., and Aweh, O. (2023). Design and implementation of biometric-based student information retrieval system using finger prints recognition. Journal of Applied Sciences and Environmental Management, 27(4), 823-827. DOI 10.4314/jasem.v27i4.25. Supplied as a Word article proof.

- **F10** [Standalone Chapter Two draft](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/Chap.2 Literature review.docx>). Project literature-review draft. Its body overlaps F11; it does not contain F11's closing reference list.

- **F11** [Alternate Chapter Two draft with bibliography](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/DOC-20261014-WA0017.docx>). Project literature-review draft with a reference list. The bibliography is subject to the corrections and verification statuses in Section 4.1.

- **F12** [Mardaniyan 2019 student information management paper](<C:/Users/Ot/Downloads/Miscelleanous/EEE Project materials/2019(5).pdf>). Mardaniyan, K. (2019). Design and implementation of a web-based student information management system. International Journal on Advanced Computer Theory and Engineering, 8(1), 23-27. Publisher record located and checked.

- **F13** [Wayman and colleagues edited biometric systems volume](<C:/Users/Ot/Downloads/Biometric Systems_ Technology, Design and Performance -- James Wayman, Anil Jain, Davide Maltoni, Dario Maio (auth_), -- 10_1007_b1, 2005 -- Springer -- doi 10_1007_b138151 -- 4b94555936ac3cd7b7c0f9795e07a2ad -- Anna’.pdf>). Wayman, J., Jain, A., Maltoni, D., and Maio, D. (Eds.). (2005). Biometric systems: Technology, design and performance evaluation. Springer. DOI 10.1007/b138151. These names are editors, not necessarily the authors of each chapter.

- **F14** [Milivojevic and colleagues 2021 handwritten signature paper](<C:/Users/Ot/Downloads/[2021 25th International Conference on Information -- Milivojevic, Zoran N_ (author);Milivojevic, Marina Z_ -- 2021 25th International Conference on -- doi 10_1109_it51528_2021_9390142 -- 1556ab53bd676822faaeed82a2bcc.pdf>). Milivojevic, Z. N., Milivojevic, M. Z., and Velickovic, Z. S. (2021). Accuracy of the MTseng-v algorithm for on-line biometric signature classification. 25th International Conference on Information Technology (IT). The supplied filename identifies DOI 10.1109/IT51528.2021.9390142. This is a handwritten-signature study.

- **F15** [Gill 1993 file management and information retrieval manual](<C:/Users/Ot/Downloads/File management and information retrieval systems _ a manual -- Gill, Suzanne L -- 3rd ed_, Englewood, Colo, Colorado, 1993 -- Englewood, Colo_ _ -- isbn13 9781563080500 -- 823fdbe4ff754ed62b92bdbccf96dee4 -- Anna’s A.pdf>). Gill, S. L. (1993). File management and information retrieval systems: A manual for managers and technicians (3rd ed.). Libraries Unlimited. ISBN 9781563080500.

- **F16** [Bhanu and Tan 2004 fingerprint recognition book](<C:/Users/Ot/Downloads/Computational Algorithms for Fingerprint Recognition -- Bir Bhanu, Xuejun Tan (auth_) -- Kluwer international series on biometrics 1, 1, 2004 -- isbn13 9781402076510 -- 9b36edeb6d6d284639c51f1a13e445aa -- Anna’s Arch.djvu>). Bhanu, B., and Tan, X. (2004). Computational algorithms for fingerprint recognition. Originally Kluwer Academic Publishers; supplied Springer reprint. Electronic DOI on the supplied copyright page: 10.1007/978-1-4615-0491-7. The supplied format is DjVu.

### Additional primary checks

- [Mardaniyan publisher record](https://journals.mriindia.com/index.php/ijacte/article/view/4636): author, title, 2019 volume 8 issue 1, pages 23-27 and the controlled-benchmark abstract.
- [Odulaja publisher record](https://www.fnasjournals.com/index.php/FNAS-JCA/article/view/676): title and 2025 bibliographic details; full source is F02.
- [GJETA June 2026 issue](https://gjeta.com/ArchiveIssue-2026-Vol27-Issue3): confirms the OmniAttend article's title, authors and DOI; full source is F06.
- [Crossref DOI record](https://api.crossref.org/works/10.1088/1742-6596/1911/1/012015): confirms the incorrect JPCS bibliographic assignment in F11.
- [Analog Devices DS3231 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf) and [DS1307 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds1307.pdf): distinguish the RTC models, calendar functions and manufacturer accuracy specifications.

These checks establish the particular metadata or specification cited, not blanket endorsement of every statement in a source.
