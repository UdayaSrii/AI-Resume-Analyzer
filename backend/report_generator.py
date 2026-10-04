from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm

def create_report(result, path):
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleX", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, spaceAfter=12)
    h = ParagraphStyle("HX", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=6)
    body = styles["BodyText"]
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    story = [Paragraph("AI Resume Analysis Report", title)]
    ats = result.get("ats_analysis", {})
    score = ats.get("score", 0)
    story += [Paragraph(f"ATS Score: {score}/100", h)]
    story += [Paragraph(str(result.get("summary","")), body)]
    for name, key in [("Matched Skills","matched_skills"),("Missing Skills","missing_skills"),
                      ("Strengths","strengths"),("Weaknesses","weaknesses"),("Recommendations","recommendations")]:
        vals = ats.get(key, []) if key in ats else result.get(key, [])
        story.append(Paragraph(name, h))
        if vals:
            data = [[Paragraph("• " + str(v), body)] for v in vals]
            t = Table(data, colWidths=[170*mm])
            t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            story.append(t)
        else:
            story.append(Paragraph("None reported.", body))
    doc.build(story)
