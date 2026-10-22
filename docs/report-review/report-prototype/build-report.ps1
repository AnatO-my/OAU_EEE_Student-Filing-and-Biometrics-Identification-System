param([string]$PdfLatex = 'pdflatex', [string]$Biber = 'biber')
$ErrorActionPreference = 'Stop'
$build = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $build | Out-Null
Push-Location $PSScriptRoot
try {
    foreach ($pass in 1..4) {
        & $PdfLatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape "-output-directory=$build" main.tex
        if ($LASTEXITCODE) { throw "pdfLaTeX pass $pass failed. Check build/main.log." }
        if ($pass -eq 1) {
            & $Biber "--input-directory=$build" "--output-directory=$build" main
            if ($LASTEXITCODE) { throw 'Biber failed. Check build/main.blg.' }
        }
    }
    Write-Host "Report compiled: $build/main.pdf"
} finally { Pop-Location }
