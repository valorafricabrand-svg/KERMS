from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import Report, Risk, RiskTreatment


def risk_summary(organization):
    risks = Risk.objects.filter(organization=organization)
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    breaches = []
    overdue = []
    for risk in risks:
        counts[risk.rating] += 1
        if risk.appetite and risk.residual_score > risk.appetite.tolerance_threshold:
            breaches.append(risk)
        if risk.next_review_date and risk.next_review_date < timezone.localdate():
            overdue.append(risk)
    treatments = RiskTreatment.objects.filter(risk__organization=organization)
    aging = treatments.exclude(status="complete")
    narrative = (
        f"The register contains {risks.count()} risks: {counts['Critical']} critical, "
        f"{counts['High']} high, {counts['Medium']} medium, and {counts['Low']} low. "
        f"{len(breaches)} residual-risk score(s) are currently outside configured appetite. "
        f"{overdue.__len__()} risk(s) are past their next review date and {aging.count()} treatment action(s) remain active."
    )
    return risks, counts, breaches, overdue, aging, narrative


def generate_report(report):
    organization = report.organization
    risks, counts, breaches, overdue, aging, narrative = risk_summary(organization)
    if report.report_format == Report.Format.PDF:
        buffer = make_pdf(report.title, narrative, risks, breaches, aging)
        suffix, mimetype = "pdf", "application/pdf"
    elif report.report_format == Report.Format.DOCX:
        buffer = make_docx(report.title, narrative, risks, breaches, aging)
        suffix, mimetype = "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        buffer = make_pptx(report.title, narrative, risks, breaches, aging)
        suffix, mimetype = "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    safe_title = report.title.lower().replace(" ", "-").replace("/", "-")[:80]
    report.file.save(f"{safe_title}-{timezone.now():%Y%m%d%H%M}.{suffix}", ContentFile(buffer.getvalue()), save=True)
    report.executive_summary = narrative
    report.content_source = "Verified organizational risk register; management commentary and external/AI content remain separately identified"
    report.save(update_fields=["executive_summary", "content_source"])
    return report.file.url, mimetype


def make_pdf(title, narrative, risks, breaches, aging):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet(); story = [Paragraph(title, styles["Title"]), Spacer(1, 12), Paragraph("Executive summary", styles["Heading2"]), Paragraph(narrative, styles["BodyText"]), Spacer(1, 12), Paragraph("Risk register", styles["Heading2"])]
    rows = [["Reference", "Risk", "Type", "Residual", "Rating"]]
    for risk in risks[:20]: rows.append([risk.reference, risk.title[:45], risk.get_risk_type_display(), str(risk.residual_score), risk.rating])
    table = Table(rows, repeatRows=1, colWidths=[65, 230, 90, 55, 60])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#12314A")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [table, Spacer(1, 12), Paragraph("Appetite breaches", styles["Heading2"]), Paragraph("None." if not breaches else "<br/>".join(f"{r.reference}: {r.title}" for r in breaches), styles["BodyText"]), Spacer(1, 12), Paragraph("Action aging", styles["Heading2"]), Paragraph(f"{aging.count()} active treatment actions.", styles["BodyText"]), Spacer(1, 12), Paragraph("Content provenance", styles["Heading2"]), Paragraph("Original record: risk register. AI-generated content: none in this export. External data: none included unless separately identified.", styles["BodyText"])]
    doc.build(story)
    return buffer


def make_docx(title, narrative, risks, breaches, aging):
    document = Document(); document.add_heading(title, 0); document.add_heading("Executive summary", level=1); document.add_paragraph(narrative)
    document.add_heading("Risk register", level=1)
    table = document.add_table(rows=1, cols=5); table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, ["Reference", "Risk", "Type", "Residual", "Rating"]): cell.text = text
    for risk in risks[:20]:
        cells = table.add_row().cells
        for cell, text in zip(cells, [risk.reference, risk.title, risk.get_risk_type_display(), str(risk.residual_score), risk.rating]): cell.text = text
    document.add_heading("Appetite breaches", level=1)
    document.add_paragraph("None." if not breaches else "\n".join(f"{r.reference}: {r.title}" for r in breaches))
    document.add_heading("Action aging and assurance", level=1); document.add_paragraph(f"{aging.count()} active treatment actions remain.")
    document.add_heading("Content provenance", level=1); document.add_paragraph("Original record: risk register. Management-approved commentary: where recorded. AI-generated content: none in this export. External data: none included unless separately identified.")
    buffer = BytesIO(); document.save(buffer); return buffer


def make_pptx(title, narrative, risks, breaches, aging):
    presentation = Presentation(); presentation.slide_width = Inches(13.333); presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6]); box = slide.shapes.add_textbox(Inches(.7), Inches(.8), Inches(12), Inches(1)); box.text = title
    for shape in box.text_frame.paragraphs: shape.font.size = Pt(30); shape.font.bold = True
    slide.shapes.add_textbox(Inches(.7), Inches(2), Inches(11.8), Inches(1.5)).text = narrative
    slide = presentation.slides.add_slide(presentation.slide_layouts[6]); slide.shapes.add_textbox(Inches(.7), Inches(.5), Inches(12), Inches(.7)).text = "Priority risks"
    lines = [f"{r.reference} | {r.title} | {r.rating} | Residual {r.residual_score}" for r in list(risks)[:8]] or ["No risks registered"]
    slide.shapes.add_textbox(Inches(.7), Inches(1.6), Inches(12), Inches(4.8)).text = "\n".join(lines)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6]); slide.shapes.add_textbox(Inches(.7), Inches(.5), Inches(12), Inches(.7)).text = "Governance and action"
    slide.shapes.add_textbox(Inches(.7), Inches(1.6), Inches(12), Inches(4.8)).text = f"Appetite breaches: {len(breaches)}\nActive treatments: {aging.count()}\n\nContent provenance: organizational register only; no external or AI-generated claims have been inserted in this export."
    buffer = BytesIO(); presentation.save(buffer); return buffer
