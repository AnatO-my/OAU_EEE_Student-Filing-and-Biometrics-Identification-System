# Full EEE report prototype

Compile **main.tex** for the entire report. Do not compile chapter files alone.
All required custom OT class/style files are included beside main.tex.

```text
main.tex                 Entire report, cover details and chapter order
frontmatter.tex          Draft status, acknowledgements, lists and abstract
chapter_1.tex            Introduction (incorporated Markdown draft)
chapter_2.tex            Literature Review and Conceptual Framework (incorporated draft)
chapter_3.tex            Methodology and System Design (incorporated draft)
chapter_4.tex            Implementation Results and Discussion (completion outline)
chapter_5.tex            Conclusions and Recommendations (completion outline)
appendix_a.tex           Supporting Evaluation Evidence (placeholder)
appendix_b.tex           Supplementary Design Material (placeholder)
folder/                  Four diagrams: PNG, SVG and editable Mermaid sources
plates/                  Photographs; no photographs supplied yet
tables/                  Thirteen separate, chapter-included longtable files
refernences/             references.bib and bibliography notes
source-notes/            Original Markdown, materials review and conversion manifest
otengineering.cls        OT base class
otcore.sty               OT shared layout
ottheme.sty              OT colours/hyperlinks
oteeereport.sty           Departmental format, including APPENDICES division
```

`folder` and `refernences` preserve the names requested for this layout.
You can rename them later, updating the paths in main.tex and chapter files.

## Incorporated material

The academic text from the three chapter revisions dated 17 October 2026 was
converted into chapters 1–3. Manual chapter/section/table/figure heading numbers
were replaced by LaTeX numbering. All 13 source tables and four rendered diagrams
are included. Seventeen supplied bibliography entries were transcribed to BibLaTeX,
and narrative author-year citations were adapted to IEEE numeric citations.

The drafts' implementation/proposal distinctions, limitations and experimental
denominators remain unchanged. Source metadata was not independently verified,
and conversion does not validate the research claims. The materials review
informs the completion outlines and remains available with the team notes in
source-notes/. Those internal notes are not mixed into the submitted chapters.

No Chapters Four/Five drafts, final abstract, author names, matriculation numbers
or assembly photographs were supplied in this Markdown set. Their placeholders
are explicitly labelled. Replace them with reviewed material before submission.
Any content describing implementation refers to the drafts' dated checkpoint,
not an automatic assessment of the repository as of today.

## Compile locally

Use MiKTeX or TeX Live with pdfLaTeX, Biber and the standard dependencies.
From this folder run `latexmk -pdf main.tex`, or use `build-report.ps1` on Windows.
The Windows helper writes the PDF and auxiliary files to build/. Compilation
must complete successfully; an older PDF is not proof that a new build passed.

If the installed Windows Biber reports startup assertions before reading the
bibliography, use a fresh extraction cache and run the helper again:

```powershell
$env:PAR_GLOBAL_TEMP = Join-Path $env:TEMP 'ot-report-biber'
.\build-report.ps1
```

This isolates Biber's temporary runtime; it does not change the bibliography.

## Use on Overleaf

ZIP this directory's source contents, upload as a new project, choose pdfLaTeX
and main.tex, and Recompile. Biber is detected from the report's bibliography
configuration. Do not include build/ when uploading. No external repository
paths or custom fonts are required. This prototype has been checked locally;
it has not been compiled in a signed-in Overleaf account.

## Finish the report

1. Replace cover placeholders and confirm the approved submission description.
2. Confirm exact departmental margins; defaults are 1.5in left, 1in right/top/bottom.
3. Reconcile source-notes completion/evidence notes against the final code/build.
4. Add actual results to Chapter Four and evidence-based conclusions to Chapter Five.
5. Complete the abstract, acknowledgements and appendices; remove Draft Status.
6. Verify every source, citation, image, table, section reference and measured claim.

Use `\chapter{...}` after `\appendix` for individual appendices. The included
style adds the APPENDICES division and groups appendix entries in the contents.
Pages remain Arabic, top-centred. Appendix float numbers become A.1, B.1 etc.

Tables retain source row data and are single spaced with booktabs conventions.
Very wide tables are landscape. Keep the full bibliography and long quotations
double spaced; do not manually reset their spacing to shorten the report.

## Provenance

Source: the sibling chapter-one, chapter-two and chapter-three revision Markdown
files and materials-review-2026-10-17.md under docs/report-review. Conversion
prepared 19 October 2026. The original source files remain unchanged. The bundled
source-notes copies retain original local evidence links, which are useful in
this project checkout but may need relinking for another user's computer.
