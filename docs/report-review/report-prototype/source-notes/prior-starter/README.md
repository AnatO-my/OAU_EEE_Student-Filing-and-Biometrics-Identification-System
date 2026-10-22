# Start writing with OT on Overleaf

Prepared 30 September 2026. These are private learning starters supplied by
your mentor, not a public package release.

## 1. Choose a starter

- **otengineering-overleaf-starter.zip:** engineering notes, ideas, experiments,
  decisions and risks. Start with this if you are new to LaTeX.
- **oteeereport-overleaf-starter.zip:** a departmental project report with a
  cover, front matter, chapters, IEEE references and an appendix.

Upload each ZIP as a separate Overleaf project. The files required from the OT
repository are already bundled; you do not need MiKTeX or a local repository.
Keep an untouched copy of the ZIP so you can start fresh later.

## 2. Create an account

1. Visit https://www.overleaf.com/register in your browser.
2. Register with your email address and a password, or choose an available
   sign-in option such as Google.
3. Complete any verification instructions shown, then sign in.
4. Open your Projects dashboard. You can begin with a free account; these
   small starters do not require premium features.

Official registration page: https://www.overleaf.com/register

## 3. Upload and see your first PDF

1. Download the starter ZIP you want to use. You can upload it without unzipping.
2. On the Projects dashboard, choose **New Project → Upload Project**.
3. Select the ZIP, or drag it into the upload window.
4. Wait for the project editor to open. Rename the project to something useful,
   such as “My LaTeX Practice”.
5. Open project **Settings** (gear icon; some layouts use a Menu), then the
   **Compiler** settings. Choose **pdfLaTeX** and **Main document: main.tex**.
   Use a recent TeX Live version offered by Overleaf; do not select an old version.
6. Open **main.tex** in the editor and click **Recompile**.
7. The PDF appears in the preview pane. Change the title or name in main.tex
   and click Recompile again to see your first change.

Overleaf runs the build steps for you, including the report's Biber bibliography.
If a reference initially shows `??`, recompile again. Persistent `??` or `[?]`
means a label/citation is missing or compilation failed; see troubleshooting.

Official upload guide:
https://www.overleaf.com/learn/latex/Kb/Uploading_a_project

Main-document settings:
https://docs.overleaf.com/getting-started/recompiling-your-project/the-main-document

Compiler settings:
https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler

## 4. Which files should I edit?

| File | What it does |
| --- | --- |
| main.tex | Your project details and the overall document structure |
| dummy_practice.tex | Worked examples and small practice exercises; edit this first |
| references.bib (report only) | Bibliography records used by citations |
| otengineering.cls, otcore.sty, ottheme.sty | Bundled OT formatting files; leave them unchanged while learning |
| oteeereport.sty (report only) | Departmental report formatting; leave unchanged while learning |
| README.md | This guide |
| VERSION.txt | Identifies the bundled source snapshot |

**Always compile main.tex.** dummy_practice.tex is a content file already included
by `\input{dummy_practice}`. It deliberately has no document preamble. You do not
need to change the Main document setting when editing it.

## 5. Your first practice session

Make one change at a time and recompile after each change.

1. In main.tex, replace the sample project title and personal details.
2. In dummy_practice.tex, replace “Your Name” and add a paragraph.
3. Add an item inside a list using `\item`.
4. Try `\textbf{bold}`, `\emph{emphasis}` and inline maths such as `$V=IR$`.
5. Change the current and resistance in the equation and calculate the answer.
6. Add a table row. Separate columns with `&`; finish a row with `\\`.
7. Rename the diagram blocks and its caption.
8. Use `\label{...}` and `\ref{...}` to refer to an equation, table or figure.
   Labels must be unique. Do not type the displayed number yourself.
9. In the notebook, edit a decision and risk and look at their registers at the end.
10. In the report, change a chapter title and inspect the cover, contents and lists.
    Try the existing `\cite{sample}` and locate the matching References entry.

Lines starting with `%` contain instructions that do not appear in the PDF.
A blank line starts a new paragraph. Commands begin with a backslash; braces
group their arguments. Environments begin with `\begin{name}` and end with
`\end{name}`. Match the names exactly.

## 6. Make this your own project

Once you are comfortable, make a copy of the project from your Overleaf dashboard
and rename it. Replace the practice text, sample data and metadata. Keep your
learning project for reference.

You may rename dummy_practice.tex to a more useful name such as introduction.tex,
but also change `\input{dummy_practice}` in main.tex to `\input{introduction}`.
For a longer report, create one file per chapter and add an `\input{...}` for
each in main.tex, after `\mainmatter` and before `\printbibliography`.
Chapter files should contain content only, just like dummy_practice.tex.

To add a photograph, upload a JPG or PNG into the project. Put
`\usepackage{graphicx}` in main.tex before `\begin{document}`, then use
`\includegraphics[width=0.7\linewidth]{prototype.jpg}` inside a figure or plate.
Use the exact uploaded filename, including capitalization.

For reports, add source records to references.bib and cite their keys with
`\cite{key}`. Keep `\printbibliography` in main.tex. Do not add otbib or another
bibliography package; the report already selects IEEE formatting.
The margin defaults are provisional: confirm exact departmental measurements
with your mentor before submitting a real report.

## 7. If something goes wrong

| Problem | What to try |
| --- | --- |
| No PDF or a red error | Open the error/log panel and fix the first error first; later errors may be consequences |
| `File otengineering.cls not found` | Upload the complete starter ZIP; the class and styles must stay beside main.tex |
| `Missing $ inserted` | Put maths between `$...$`; use `\_` for a literal underscore in ordinary text |
| `Undefined control sequence` | Check spelling and capitalization of the command; undo your last change and recompile |
| Table error about alignment | Check the number of columns, `&` separators and row-ending `\\` |
| `??` or `[?]` remains | Match the label/citation key exactly, check references.bib, then recompile from scratch using the option beside Recompile |
| Picture does not appear | Check filename/capitalization and load graphicx; use normal compilation rather than a fast draft |
| Table or figure moves | Floats are placed where they fit; `[htbp]` allows several suitable locations |
| Register looks out of date | Recompile again; the engineering registers read data from the preceding pass |

Write literal percent and ampersand characters as `\%` and `\&` in text.
An unescaped `%` hides the rest of that source line. In a table, unescaped `&`
separates columns. Do not delete bundled class/style files to fix an error.

## 8. Save and share your work

Use the PDF preview's download control to save your finished PDF. Also download
the project's source ZIP periodically from the project menu as a backup.
If you want your mentor to review the source, use Overleaf's Share controls or
send the source ZIP, following the sharing options available to your account.
Keep personal details out of a project you choose to make public.

More learning material: https://www.overleaf.com/learn/latex/Learn_LaTeX_in_30_minutes

## About this starter

All diagrams are drawn in LaTeX, so no image downloads are needed. Practice
measurements are invented. The report reference is a real textbook used only
to demonstrate citation syntax. The notebook retains the ordinary engineering
layout; the report enables `\documentclass[eee-report]{otengineering}`.

The ZIP contains source files only. A separately supplied preview PDF shows the
expected starting result. These starters were compiled locally with MiKTeX,
pdfLaTeX and Biber where applicable; they have not been tested in a signed-in
Overleaf account. Overleaf uses TeX Live, so its initial compile is the final
check of the hosted environment.
