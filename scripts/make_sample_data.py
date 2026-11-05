"""Generate sample PDFs for two demo organizations. Run: uv run python scripts/make_sample_data.py"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "sample_data"
ss = getSampleStyleSheet()
TITLE = ParagraphStyle("t", parent=ss["Title"], fontSize=20, spaceAfter=14)
H = ParagraphStyle("h", parent=ss["Heading2"], fontSize=14, spaceBefore=10, spaceAfter=6)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=11, leading=15, spaceAfter=6)


def build(path: Path, title: str, pages: list[list[tuple[str, str]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=title)
    flow = [Paragraph(title, TITLE)]
    for i, page in enumerate(pages):
        if i:
            flow.append(PageBreak())
        for kind, text in page:
            flow.append(Paragraph(text, H if kind == "h" else P))
            if kind == "h":
                flow.append(Spacer(1, 2))
    doc.build(flow)


# ---------------------------------------------------------------- Org A: Northfield University
A = OUT / "northfield"
build(A / "Scholarship_Rules.pdf", "Northfield University Scholarship Rules", [
    [("h", "Merit Scholarship"),
     ("p", "The Merit Scholarship rewards outstanding academic performance. It covers 50% of annual tuition fees "
           "and is renewed every year as long as the student keeps meeting the criteria below."),
     ("h", "Eligibility"),
     ("p", "- To qualify for the Merit Scholarship, a student must be in at least their second year of study."),
     ("p", "- The student must hold a cumulative GPA of 3.5 or higher."),
     ("p", "- The student must not currently hold a Sports Scholarship, because the two scholarships cannot be "
           "combined."),
     ("p", "Students who meet all three conditions are automatically considered by the Scholarship Committee.")],
    [("h", "Sports Scholarship"),
     ("p", "The Sports Scholarship supports students who represent Northfield University in official "
           "competitions. It covers 30% of tuition fees plus the cost of training equipment."),
     ("h", "Eligibility"),
     ("p", "- To qualify for the Sports Scholarship, a student must have a coach recommendation letter."),
     ("p", "- A minimum GPA of 2.8 is required."),
     ("p", "- Students must maintain attendance of at least 80% at team training sessions."),
     ("p", "The Sports Scholarship can be renewed each year after a performance review by the Athletics Office.")],
    [("h", "How to Apply"),
     ("p", "Applications for all scholarships open on 1 March and close on 30 April. Submit the online "
           "application form through the student portal, attach your latest transcript, and upload any supporting "
           "documents."),
     ("p", "Results are announced by 15 June. Successful students receive an award letter by email."),
     ("h", "Appeals"),
     ("p", "A student who disagrees with a decision may appeal in writing to the Scholarship Committee within "
           "14 days of receiving the decision. Appeals are reviewed within 10 working days.")],
])
build(A / "Admissions_FAQ.pdf", "Northfield University Admissions FAQ", [
    [("h", "Deadlines"),
     ("p", "The deadline for undergraduate applications is 31 January. Late applications are accepted until "
           "15 February with a late application fee of $50."),
     ("h", "Documents"),
     ("p", "Applicants must submit a completed application form, official transcripts, two reference letters "
           "and a copy of a passport or national ID."),
     ("h", "Entry Requirements"),
     ("p", "Undergraduate programmes require a minimum secondary school average of 75%. Engineering and "
           "Computer Science programmes additionally require Mathematics at grade B or higher.")],
    [("h", "International Students"),
     ("p", "International applicants must provide proof of English proficiency, such as an IELTS score of 6.5 "
           "or a TOEFL score of 90. A student visa support letter is issued after the enrolment deposit is paid."),
     ("h", "Contact"),
     ("p", "For admissions questions contact admissions@northfield.example or call the Admissions Office, "
           "open Monday to Friday, 9:00 to 17:00.")],
])
build(A / "Fee_Policy.pdf", "Northfield University Fee Policy", [
    [("h", "Tuition Fees"),
     ("p", "Annual tuition is $12,000 for domestic students and $18,000 for international students. Fees may "
           "be paid in two installments, due on 1 August and 1 January."),
     ("h", "Late Payment"),
     ("p", "A late fee of 5% applies to any payment received more than 10 days after the due date. Students "
           "with unpaid balances cannot register for the next semester.")],
    [("h", "Refunds"),
     ("p", "Students who withdraw within 14 days of the semester start receive a full refund. After that, the "
           "refund is 50% until the end of week 4. No refunds are given after week 4."),
     ("h", "Fee Waiver"),
     ("p", "Students facing financial hardship can apply for the Fee Waiver, which reduces tuition by up to "
           "25%. To qualify for the Fee Waiver, a student must have a GPA of at least 3.0 and must submit a "
           "hardship letter from a guardian.")],
])

# ---------------------------------------------------------------- Org B: Acme Corp
B = OUT / "acme"
build(B / "Leave_Policy.pdf", "Acme Corp Leave Policy", [
    [("h", "Annual Leave"),
     ("p", "Full-time employees receive 24 days of paid annual leave per calendar year. Up to 5 unused days "
           "may be carried over to the following year; the rest expire on 31 March."),
     ("p", "Employees must obtain manager approval before taking annual leave. Requests must be submitted at "
           "least 14 days in advance through the HR portal.")],
    [("h", "Sick Leave"),
     ("p", "Employees receive 10 days of paid sick leave per year. A medical certificate is required for "
           "absences longer than 2 consecutive days. Notify your manager before 10:00 on the first day of absence.")],
    [("h", "Parental Leave"),
     ("p", "Eligible employees receive 16 weeks of paid parental leave, which can be taken within the first "
           "12 months after the birth or adoption."),
     ("p", "To qualify for Parental Leave, an employee must have completed at least 12 months of service.")],
])
build(B / "Remote_Work_Policy.pdf", "Acme Corp Remote Work Policy", [
    [("h", "Remote Work"),
     ("p", "Acme supports flexible working. Employees may work remotely up to 3 days per week; the remaining "
           "days are spent in the office."),
     ("h", "Eligibility"),
     ("p", "- To qualify for Remote Work, an employee must have at least 6 months of service."),
     ("p", "- Employees must have an approved remote work agreement signed with their manager."),
     ("p", "Team leads may restrict remote days during project launches.")],
    [("h", "Home Office Allowance"),
     ("p", "Remote employees may claim a one-time Home Office Allowance of $300 for desk and chair purchases."),
     ("p", "To receive the Home Office Allowance, an employee must have completed 3 months of service. "
           "Receipts must be uploaded to the expense portal.")],
])
build(B / "Expense_Policy.pdf", "Acme Corp Expense Policy", [
    [("h", "Expense Approval"),
     ("p", "Expenses up to $500 can be approved by your line manager. Expenses above $500 require approval from "
           "a Director. Expenses above $5,000 require approval from the Finance Committee."),
     ("h", "Submitting Claims"),
     ("p", "Submit expense claims in the expense portal within 30 days of the purchase, attaching the original "
           "receipt. Claims are reimbursed in the next monthly payroll run.")],
    [("h", "Travel"),
     ("p", "Economy class must be used for flights shorter than 6 hours. Hotel stays are capped at $180 per "
           "night in major cities and $120 elsewhere. Meals are reimbursed up to $60 per day while travelling.")],
])
print("Sample PDFs written to", OUT)
