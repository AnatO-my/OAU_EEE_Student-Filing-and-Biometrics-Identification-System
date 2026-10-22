"""Build the two presentation PDFs from editable Markdown sources."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'pdf'
QA = ROOT / 'tmp' / 'pdfs'
OUT.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)
fontdir = ROOT / 'docs' / 'fonts'
pdfmetrics.registerFont(TTFont('Body', str(fontdir / 'FunnelDisplay-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Bold', str(fontdir / 'FunnelDisplay-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Code', str(fontdir / 'JetBrainsMono-Regular.ttf')))
W, H = 1440, 810
RED = HexColor('#cc100a')
INK = HexColor('#111111')
GRAY = HexColor('#494949')
TITLE = ParagraphStyle('Title', fontName='Body', fontSize=48, leading=59, textColor=INK)
BODY = ParagraphStyle('Body', fontName='Body', fontSize=27, leading=35.1, textColor=INK)
CELL = ParagraphStyle('Cell', fontName='Body', fontSize=23, leading=29, textColor=INK)
HEAD = ParagraphStyle('Head', fontName='Bold', fontSize=23, leading=29, textColor=white)
CODE = ParagraphStyle('Code', fontName='Code', fontSize=24, leading=32, textColor=INK)

TECHNICAL = re.compile(
    r'https?://[^\s]+|`[^`]+`|\b[a-z][a-z0-9_]*\([^\)\n]*\)(?:\s*->\s*[A-Za-z]+)?'
    r'|\b(?:app|students|academics|imports|accounts|identity|reporting|audit|config|docs|contracts|simulators|fixtures|static|services|api|examples|tests|software|templates|deployment)/[\w/{}.-]+/?'
    r'|\b[\w.-]+/[\w/{}.-]*\.[A-Za-z]{1,5}\b'
    r'|\b[A-Za-z][\w.]*(?:_[\w.]+)+\b'
    r'|\b[A-Z][a-z]+(?:[A-Z][A-Za-z]*)+\b'
)

def ptext(text, inline=True):
    if not inline:
        return escape(text).replace('\n', '<br/>')
    parts=[]
    end=0
    for match in TECHNICAL.finditer(text):
        parts.append(escape(text[end:match.start()]))
        token=match.group().strip('`')
        if token.startswith(('http://','https://')) or token in {'PostgreSQL','JavaScript','GitHub','JetBrains','FunnelDisplay'}:
            parts.append(escape(token))
        else:
            parts.append('<font name="Code">'+escape(token)+'</font>')
        end=match.end()
    parts.append(escape(text[end:]))
    return ''.join(parts).replace('\n', '<br/>')

def blocks(text):
    lines = text.strip().splitlines()
    title = lines.pop(0).removeprefix('# ').strip()
    result = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if lines[i].startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                row = [v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', x) for x in row):
                    rows.append(row)
                i += 1
            result.append(('table', rows))
        elif lines[i].startswith('```'):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i])
                i += 1
            i += 1
            result.append(('code', '\n'.join(code)))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('|'):
                para.append(lines[i])
                i += 1
            result.append(('text', '\n'.join(para)))
    return title, result

def build(src, name, label):
    sections = re.split(r'\n---\s*\n', src.read_text(encoding='utf-8'))
    slides = []
    for section in sections:
        title, content = blocks(section)
        _, th = Paragraph(ptext(title), TITLE).wrap(1308,200)
        _, continued_th = Paragraph(ptext(title+' (continued)'), TITLE).wrap(1308,200)
        available = 699-max(th,continued_th)-28-95
        chunk = []
        used = 0
        for kind, value in content:
            if kind == 'table':
                ncols = len(value[0])
                widths = [1308/ncols]*ncols
                if ncols == 3:
                    widths = [420,310,578]
                groups=[]
                current=[value[0]]
                for row in value[1:]:
                    candidate=current+[row]
                    probe=Table([[Paragraph(ptext(v),HEAD if r==0 else CELL) for v in vals] for r,vals in enumerate(candidate)],colWidths=widths)
                    probe.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14)]))
                    _,height=probe.wrap(1308,680)
                    if height+20>available-used and len(current)>1:
                        groups.append(current)
                        current=[value[0],row]
                    else:
                        current=candidate
                groups.append(current)
                for group in groups:
                    probe=Table([[Paragraph(ptext(v),HEAD if r==0 else CELL) for v in vals] for r,vals in enumerate(group)],colWidths=widths)
                    probe.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14)]))
                    _,height=probe.wrap(1308,680)
                    if used+height+20>available and chunk:
                        slides.append((title,chunk))
                        chunk=[]
                        used=0
                    chunk.append((kind,group))
                    used+=height+20
            else:
                _,height=Paragraph(ptext(value,inline=kind!='code'),CODE if kind=='code' else BODY).wrap(1308,680)
                if used+height+20>available and chunk:
                    slides.append((title,chunk))
                    chunk=[]
                    used=0
                chunk.append((kind,value))
                used+=height+20
        if chunk:
            slides.append((title,chunk))
    dest = OUT / name
    canvas = Canvas(str(dest), pagesize=(W, H))
    canvas.setTitle(label)
    canvas.setAuthor('OAU EEE Project Team')
    checks = []
    for number, (title, content) in enumerate(slides, 1):
        if number>1 and slides[number-2][0]==title:
            title+=' (continued)'
        canvas.setFillColor(white)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        canvas.setFillColor(GRAY)
        canvas.setFont('Body', 21)
        canvas.drawString(66, 760, label)
        canvas.drawRightString(W-66, 760, '2026')
        para = Paragraph(ptext(title), TITLE)
        _, th = para.wrap(1308, 200)
        para.drawOn(canvas, 66, 699-th)
        y = 699-th-28
        for kind, value in content:
            if kind == 'table':
                ncols = len(value[0])
                widths = [1308/ncols] * ncols
                if ncols == 3:
                    widths = [420, 310, 578]
                rows = [[Paragraph(ptext(v), HEAD if r == 0 else CELL) for v in row] for r, row in enumerate(value)]
                obj = Table(rows, colWidths=widths, hAlign='LEFT')
                obj.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), RED),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#fff1ef'), HexColor('#fafafa')]),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 14),
                    ('RIGHTPADDING', (0,0), (-1,-1), 14),
                    ('TOPPADDING', (0,0), (-1,-1), 10),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ]))
            else:
                obj = Paragraph(ptext(value,inline=kind!='code'), CODE if kind == 'code' else BODY)
            _, height = obj.wrap(1308, 680)
            if y-height < 95:
                raise ValueError(f'Overflow: {name} slide {number} {title}: bottom={y-height}')
            obj.drawOn(canvas, 66, y-height)
            y -= height+20
        checks.append((number, title, round(y,1)))
        canvas.setFillColor(RED)
        canvas.rect(66,64,56,4,fill=1,stroke=0)
        canvas.setFillColor(GRAY)
        canvas.setFont('Body',17)
        canvas.drawString(66,28,'OAU EEE / Team coding reference')
        canvas.drawRightString(W-66,28,f'{number:02d} / {len(slides):02d}')
        canvas.showPage()
    canvas.save()
    reader = PdfReader(dest)
    assert len(reader.pages) == len(slides)
    for index, (title, _) in enumerate(slides):
        text = reader.pages[index].extract_text()
        assert title[:25] in text, (index,title)
    doc = pdfium.PdfDocument(str(dest))
    thumbs = []
    for i in range(len(doc)):
        im = doc[i].render(scale=.7).to_pil().convert('RGB')
        im.save(QA/f'{dest.stem}-{i+1:02d}.png')
        thumb = im.resize((480,270))
        thumbs.append(thumb)
    for start in range(0,len(thumbs),12):
        batch=thumbs[start:start+12]
        sheet=Image.new('RGB',(1440,((len(batch)+2)//3)*300),'#dddddd')
        draw=ImageDraw.Draw(sheet)
        for j,im in enumerate(batch):
            x=(j%3)*480
            y=(j//3)*300
            sheet.paste(im,(x,y))
            draw.text((x+8,y+274),f'Slide {start+j+1}',fill='black')
        sheet.save(QA/f'{dest.stem}-contact-{start//12+1}.png')
    print(dest)
    print(f'{len(slides)} pages, lowest content edge {min(x[2] for x in checks)}')
    return checks

if __name__ == '__main__':
    a=build(ROOT/'docs/team-coding-cheat-sheet.md','oau-eee-team-coding-cheat-sheet.pdf','Shared data and coding')
    b=build(ROOT/'docs/api-esp32-cheat-sheet.md','oau-eee-api-esp32-cheat-sheet.pdf','API and ESP32 integration')
    (QA/'layout-checks.txt').write_text(str(a)+'\n'+str(b),encoding='utf-8')
