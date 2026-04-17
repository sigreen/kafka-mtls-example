#!/usr/bin/env python3
"""
Generate professional PDF from README.md with proper formatting
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted, Image, KeepTogether
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import markdown
import re
from io import BytesIO
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.graphics import renderPDF

# Custom page template with header/footer
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.drawRightString(7.5 * inch, 0.5 * inch,
                            f"Page {self._pageNumber} of {page_count}")
        self.drawString(1 * inch, 0.5 * inch,
                       "Kafka mTLS on OpenShift 4.20")

def create_styles():
    """Create custom styles for the document"""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#CC0000'),  # Red Hat red
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    # H1 style
    styles.add(ParagraphStyle(
        name='CustomH1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#000000'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        borderPadding=5,
        borderColor=HexColor('#CC0000'),
        borderWidth=0,
        leftIndent=0,
        backColor=HexColor('#F5F5F5')
    ))

    # H2 style
    styles.add(ParagraphStyle(
        name='CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#333333'),
        spaceAfter=10,
        spaceBefore=16,
        fontName='Helvetica-Bold'
    ))

    # H3 style
    styles.add(ParagraphStyle(
        name='CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=HexColor('#555555'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    ))

    # Code style
    styles.add(ParagraphStyle(
        name='CustomCode',
        parent=styles['Code'],
        fontSize=8,
        fontName='Courier',
        backColor=HexColor('#F8F8F8'),
        borderColor=HexColor('#CCCCCC'),
        borderWidth=1,
        borderPadding=8,
        leftIndent=10,
        rightIndent=10,
        spaceAfter=12
    ))

    # Body text
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    ))

    # Bullet style
    styles.add(ParagraphStyle(
        name='CustomBullet',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=6
    ))

    return styles

def create_architecture_diagram():
    """Create a cleaner architecture diagram"""
    d = Drawing(500, 280)

    # Colors
    azure_blue = HexColor('#0078D4')
    openshift_red = HexColor('#CC0000')
    kafka_gray = HexColor('#231F20')
    bg_gray = HexColor('#F5F5F5')
    border_gray = HexColor('#CCCCCC')

    # Main Azure container
    d.add(Rect(10, 10, 480, 260, fillColor=HexColor('#E8F4FD'), strokeColor=azure_blue, strokeWidth=2))
    d.add(String(250, 255, 'OpenShift 4.20 on Azure', textAnchor='middle', fontSize=12, fontName='Helvetica-Bold', fillColor=azure_blue))

    # OpenShift namespace container
    d.add(Rect(30, 50, 440, 180, fillColor=HexColor('#FFF5F5'), strokeColor=openshift_red, strokeWidth=1.5))
    d.add(String(250, 215, 'Kafka Namespace', textAnchor='middle', fontSize=11, fontName='Helvetica-Bold', fillColor=openshift_red))

    # Kafka brokers
    broker_y = 130
    broker_x = [80, 220, 360]
    for i, x in enumerate(broker_x):
        d.add(Rect(x, broker_y, 80, 60, fillColor=bg_gray, strokeColor=kafka_gray, strokeWidth=1.5))
        d.add(String(x + 40, broker_y + 45, f'Kafka-{i}', textAnchor='middle', fontSize=10, fontName='Helvetica-Bold'))
        d.add(String(x + 40, broker_y + 30, '(Broker)', textAnchor='middle', fontSize=8, fontName='Helvetica'))
        d.add(String(x + 40, broker_y + 15, 'mTLS', textAnchor='middle', fontSize=8, fontName='Helvetica', fillColor=HexColor('#00AA00')))

    # Controllers
    d.add(Rect(150, 70, 200, 30, fillColor=HexColor('#E8E8E8'), strokeColor=kafka_gray, strokeWidth=1))
    d.add(String(250, 80, '3 Controller Nodes (KRaft)', textAnchor='middle', fontSize=9, fontName='Helvetica'))

    # Routes box
    d.add(Rect(170, 30, 160, 25, fillColor=HexColor('#FFFACD'), strokeColor=HexColor('#FF8C00'), strokeWidth=1.5))
    d.add(String(250, 40, 'OpenShift Routes (TLS Passthrough)', textAnchor='middle', fontSize=9, fontName='Helvetica-Bold'))

    # External client
    d.add(Rect(210, -40, 80, 50, fillColor=HexColor('#E0FFE0'), strokeColor=HexColor('#00AA00'), strokeWidth=1.5))
    d.add(String(250, -10, 'External', textAnchor='middle', fontSize=10, fontName='Helvetica-Bold'))
    d.add(String(250, -23, 'Client', textAnchor='middle', fontSize=10, fontName='Helvetica-Bold'))
    d.add(String(250, -35, '(cert)', textAnchor='middle', fontSize=8, fontName='Helvetica'))

    # Connection lines
    # Brokers to routes
    for x in broker_x:
        d.add(Line(x + 40, broker_y, x + 40, 55, strokeColor=kafka_gray, strokeWidth=1))
    d.add(Line(120, broker_y, 250, 55, strokeColor=kafka_gray, strokeWidth=1))
    d.add(Line(260, broker_y, 250, 55, strokeColor=kafka_gray, strokeWidth=1))
    d.add(Line(400, broker_y, 250, 55, strokeColor=kafka_gray, strokeWidth=1))

    # Route to client
    d.add(Line(250, 30, 250, 10, strokeColor=HexColor('#00AA00'), strokeWidth=2))

    # mTLS Port label
    d.add(String(265, 15, 'mTLS', textAnchor='start', fontSize=9, fontName='Helvetica-Bold', fillColor=HexColor('#00AA00')))
    d.add(String(265, 5, 'Port 443', textAnchor='start', fontSize=8, fontName='Helvetica'))

    return d

def parse_markdown_to_pdf(md_file, pdf_file):
    """Convert markdown to PDF with improved formatting"""

    # Read markdown content
    with open(md_file, 'r') as f:
        content = f.read()

    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        rightMargin=1*inch,
        leftMargin=1*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )

    # Get styles
    styles = create_styles()
    story = []

    # Split into lines
    lines = content.split('\n')
    i = 0
    in_code_block = False
    code_block = []
    code_lang = None
    in_table = False
    table_data = []
    skip_next_code_block = False

    while i < len(lines):
        line = lines[i]

        # Handle code blocks
        if line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                code_block = []
            else:
                in_code_block = False
                # Add code block (skip ASCII art diagram)
                code_text = '\n'.join(code_block)
                if code_text.strip() and not skip_next_code_block:
                    p = Preformatted(code_text, styles['CustomCode'])
                    story.append(p)
                    story.append(Spacer(1, 0.1*inch))
                skip_next_code_block = False
                code_block = []
            i += 1
            continue

        if in_code_block:
            code_block.append(line)
            i += 1
            continue

        # Handle title (first H1)
        if line.startswith('# ') and len(story) == 0:
            title = line[2:].strip()
            p = Paragraph(title, styles['CustomTitle'])
            story.append(p)
            story.append(Spacer(1, 0.2*inch))

        # Handle H2
        elif line.startswith('## '):
            heading = line[3:].strip()

            # Insert architecture diagram after "Architecture" heading
            if heading == 'Architecture':
                p = Paragraph(heading, styles['CustomH1'])
                diagram = create_architecture_diagram()
                # Keep heading and diagram together
                story.append(KeepTogether([
                    p,
                    Spacer(1, 0.15*inch),
                    diagram,
                    Spacer(1, 0.2*inch)
                ]))
                # Skip the ASCII art code block that follows
                skip_next_code_block = True
            else:
                p = Paragraph(heading, styles['CustomH1'])
                story.append(p)
                story.append(Spacer(1, 0.1*inch))

        # Handle H3
        elif line.startswith('### '):
            heading = line[4:].strip()
            p = Paragraph(heading, styles['CustomH2'])
            story.append(p)
            story.append(Spacer(1, 0.08*inch))

        # Handle H4
        elif line.startswith('#### '):
            heading = line[5:].strip()
            p = Paragraph(heading, styles['CustomH3'])
            story.append(p)

        # Handle tables
        elif '|' in line and line.strip().startswith('|'):
            if not in_table:
                in_table = True
                table_data = []

            # Parse table row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            # Skip separator rows
            if not all(re.match(r'^-+$', cell.replace(':', '').strip()) for cell in cells):
                table_data.append(cells)

        # End of table
        elif in_table and not line.strip().startswith('|'):
            in_table = False
            if table_data:
                # Create table
                t = Table(table_data, hAlign='LEFT')
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#CC0000')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('TOPPADDING', (0, 1), (-1, -1), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F8F8F8')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.15*inch))
                table_data = []

        # Handle bullet points
        elif re.match(r'^[\s]*[-*]\s+', line):
            indent_level = len(line) - len(line.lstrip())
            bullet_text = re.sub(r'^[\s]*[-*]\s+', '', line)
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            bullet_text = re.sub(r'`(.*?)`', r'<font face="Courier" size="9" backColor="#F0F0F0">\1</font>', bullet_text)

            style = ParagraphStyle(
                name='TempBullet',
                parent=styles['CustomBullet'],
                leftIndent=20 + (indent_level * 10),
                bulletIndent=10 + (indent_level * 10)
            )
            p = Paragraph(f'• {bullet_text}', style)
            story.append(p)

        # Handle regular paragraphs
        elif line.strip() and not line.startswith('#'):
            # Format inline code (using backColor not backgroundColor)
            text = re.sub(r'`(.*?)`', r'<font face="Courier" size="9" backColor="#F0F0F0">\1</font>', line)
            # Format bold
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            # Format links (just show text for now)
            text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)

            p = Paragraph(text, styles['CustomBody'])
            story.append(p)

        # Empty line
        elif not line.strip():
            story.append(Spacer(1, 0.08*inch))

        i += 1

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Professional PDF created: {pdf_file}")

if __name__ == '__main__':
    parse_markdown_to_pdf('README.md', 'kafka-mtls-setup-guide.pdf')
