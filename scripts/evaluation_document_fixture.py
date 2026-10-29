"""Create two visibly synthetic upload files; never overwrite existing files."""
import argparse
from pathlib import Path


def create_documents(output):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    output = output.resolve()
    names = [output / f'synthetic-student-document-v{version}.pdf' for version in (1, 2)]
    if any(path.exists() for path in names):
        raise SystemExit('Refusing to overwrite an existing test document. Choose a fresh output directory.')
    output.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('FixtureTitle', fontName='Helvetica-Bold', fontSize=19,
                             leading=24, textColor=colors.HexColor('#18364b'), spaceAfter=16))
    styles.add(ParagraphStyle('FixtureBody', fontName='Helvetica', fontSize=11, leading=17, spaceAfter=12))
    for version, path in enumerate(names, 1):
        doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=48, rightMargin=48,
                                topMargin=48, bottomMargin=48, invariant=1,
                                title=f'Synthetic upload test - version {version}', author='Synthetic evaluation fixture')
        story = [Paragraph('SYNTHETIC TEST DOCUMENT', styles['FixtureTitle']),
                 Paragraph('NOT A REAL CERTIFICATE OR STUDENT RECORD', styles['Heading3']),
                 Spacer(1, 16), Paragraph(f'VERSION {version}', styles['FixtureTitle'])]
        table = Table([['Test identity', 'Synthetic Student A'], ['Test registration', 'EVAL/001'],
                       ['Purpose', 'Private document filing evaluation'],
                       ['Visible revision', 'Original test content' if version == 1 else 'Replacement test content - revised version']],
                      colWidths=[150, 349])
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),10),
                                   ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eef3f5')),
                                   ('BOTTOMPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12)]))
        story.extend([table, Spacer(1,24), Paragraph(
            'This file contains invented information only. Use it to check upload, private retrieval, '
            'approval, rejection and retained document history in the isolated evaluation site. '
            'It does not certify birth, examination performance, clearance, state of origin or any personal status.',
            styles['FixtureBody']), Paragraph(
            'The same test file may be uploaded under each of the six required document categories to verify '
            'category handling. That checks the filing software; it is not a test of the authenticity or '
            'semantic content of a real departmental document.', styles['FixtureBody']), Paragraph(
            f'Expected visible content: version {version}. Record whether the correct version is downloaded '
            'before and after replacement approval. Keep the previous approved file accessible in its archive.',
            styles['FixtureBody'])])
        def footer(canvas, document):
            canvas.saveState()
            canvas.setFont('Helvetica',8)
            canvas.setFillColor(colors.HexColor('#465a66'))
            canvas.drawString(48,30,'SYNTHETIC FIXTURE ONLY - No real personal data - Page 1')
            canvas.restoreState()
        doc.build(story, onFirstPage=footer)
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    for path in create_documents(args.output_dir):
        print(path)


if __name__ == '__main__':
    main()
