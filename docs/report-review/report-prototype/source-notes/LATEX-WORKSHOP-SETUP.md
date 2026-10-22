# Portable LaTeX Workshop setup

Use a generic default recipe in VS Code User Settings. Keep repository-specific
scripts and search paths in that repository's Workspace Settings instead.

```json
{
  "latex-workshop.latex.recipe.default": "first",
  "latex-workshop.latex.build.fromFolder": "",
  "latex-workshop.latex.outDir": "%DIR%/build",
  "latex-workshop.latex.auxDir": "%OUTDIR%",
  "latex-workshop.latex.build.enableMagicComments": true,
  "latex-workshop.latex.tools": [
    {
      "name": "portable-latexmk",
      "command": "latexmk",
      "args": [
        "-cd", "-pdf", "-synctex=1", "-interaction=nonstopmode",
        "-file-line-error", "-halt-on-error", "-outdir=%OUTDIR%", "%DOC_EXT%"
      ]
    }
  ],
  "latex-workshop.latex.recipes": [
    {"name": "Portable: latexmk", "tools": ["portable-latexmk"]}
  ]
}
```

These are settings to merge, not a replacement for unrelated editor preferences.
The current fix has already merged them into the user's settings and preserved a
backup. LaTeX-lab's existing workspace-specific recipe was left unchanged.

## Each new project

1. Keep main.tex and latexmkrc in the project root. Bundle custom classes/styles
   or supply documented project-local search paths.
2. In each chapter beside main.tex, put `% !TeX root = main.tex` at the top.
   In an included file inside tables/, use `% !TeX root = ../main.tex`.
3. Keep document-specific build settings in latexmkrc. A basic PDF project needs:

   ```perl
   $pdf_mode = 1;
   $max_repeat = 8;
   ```

4. Open the project folder in VS Code. After changing settings, use
   **Developer: Reload Window**, then **LaTeX Workshop: Build LaTeX project**
   (Ctrl+Alt+B). If selecting a recipe manually, choose **Portable: latexmk**.
5. The PDF and SyncTeX data will be in build/ beside main.tex. Preview that output
   rather than an older PDF in output/ or beside a different copy of the source.
6. For another compiler, such as LuaLaTeX, put its recipe in the project's
   Workspace Settings; the generic recipe above is for pdfLaTeX documents.

MiKTeX/TeX Live, latexmk, Perl and any required bibliography tool must be available
on PATH. An unavailable tool is a different problem from a missing project script.

## Windows Biber startup issue

This report's latexmkrc now selects a dedicated temporary extraction cache on
Windows if PAR_GLOBAL_TEMP is not already configured. This avoids the damaged
default Biber runtime observed on this workstation. It does not change the
reference entries and does not affect Overleaf/Linux.

## Quick diagnosis

- Missing scripts/...ps1: a repository-specific recipe leaked into a different workspace.
- latexmk not found: check PATH and the installed compiler launchers. This session
  restored missing MiKTeX launchers using its links-install command.
- Chapter compiled alone: check its TeX root comment and the root shown by the extension.
- Bibliography startup assertions: check the Biber runtime/cache before changing references.
- PDF appears stale: check the build exit status and the preview's output path.

Official reference: https://github.com/James-Yu/LaTeX-Workshop/wiki/Compile
