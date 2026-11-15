"""Content + generators for the eight mandatory controlled documents (Word .docx and Excel .xlsx).
Every download is generated from this content plus live QMS data (requirements, reviews, CAPAs, release checks)."""
import io
from datetime import date

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import db
import metrics as M
from domain import (DISCLAIMER, FACTOR_INFO, QUALITY_OBJECTIVES, REQ_CATEGORIES, REVIEW_TYPES, TEST_CATEGORIES)

NAVY, BLUE, ICE = "14243A", "2563EB", "EFF6FF"
PRODUCT = "HOSPITAL QUALITY OS"
MODULES = REQ_CATEGORIES  # hospital software modules

# which QMS pages each document supports (used for integration links in the UI)
DOC_MODULES = {
    "quality_plan": ["analytics", "release", "settings"],
    "req_procedure": ["requirements", "traceability"],
    "req_checklist": ["requirements", "reviews"],
    "change_request": ["requirements"],
    "rtm": ["traceability", "requirements", "testing"],
    "peer_review": ["reviews"],
    "release_checklist": ["release", "defects"],
    "capa_procedure": ["capa", "defects"],
}


def doc_meta(doc_id):
    return db.query("SELECT * FROM documents WHERE id=?", (doc_id,), one=True)


# ====================================================================== content
def _plan():
    roles = [["Project Manager", "Schedule, resources, release authorisation", "Authorises business release"],
             ["Quality Assurance Lead", "Owns quality direction; audits; CAPA verification", "Approves quality plan and procedures"],
             ["Business Analyst", "Stakeholder needs, requirements, traceability", "Proposes requirement baseline"],
             ["Technical Architect", "Design, data integrity and security architecture", "Approves design and database design"],
             ["Developer", "Implementation, unit tests, defect fixes", "None (submits for review)"],
             ["Test Manager", "Test planning, execution and evidence", "Approves test results"],
             ["Reviewer", "Independent peer and formal reviews", "Records review decisions"]]
    gates = [["G1", "Requirements baseline", "Requirement reviews approved; acceptance criteria testable", "All active requirements approved with review record", "QA Lead"],
             ["G2", "Design approved", "Design and database design reviews recorded", "Design references linked in RTM; data-integrity rules reviewed", "Technical Architect"],
             ["G3", "Test readiness", "Test plan review approved; every requirement has a test", "Traceability complete; entry criteria met", "Test Manager"],
             ["G4", "Release", "All mandatory release checks evaluated", "Release readiness gate returns GO (or CONDITIONAL GO with documented conditions)", "Project Manager"]]
    risks = [["Patient misidentified or duplicate record", "High", "Duplicate-detection requirement, data-validation tests, CAPA on any duplicate defect"],
             ["Laboratory result attached to wrong patient", "Critical", "Identifier-binding requirement, integration tests, interface review"],
             ["Billing calculation error", "High", "Rounding rules in requirement, unit tests, code review of currency handling"],
             ["Prescription linked to wrong patient/doctor", "Critical", "Prescription aggregate design, integration and UAT tests"],
             ["Unauthorised access to confidential data", "Critical", "Role-based access control, security review and security testing"],
             ["Data loss after failure", "High", "Transaction-consistency requirement, backup and recovery tests"]]
    return {
        "category": "PLAN", "purpose": "Control document that defines how quality is planned, controlled, verified, measured and improved for the Hospital Management Software.",
        "sections": [
            ("Project scope", ["P:The QMS covers the development and maintenance of the Hospital Management Software: " + ", ".join(m.lower() for m in MODULES[:7]) + ", plus cross-cutting security, integrity, reliability, performance and maintainability.",
                               "P:The QMS manages quality of the software project. It does not operate the hospital and is a prototype: no regulatory compliance is claimed."]),
            ("Quality objectives", [f"{a}: {b}" for a, b in QUALITY_OBJECTIVES]),
            ("Quality factors", [f"{k}: {v}" for k, v in FACTOR_INFO.items()]),
            ("Quality responsibilities", ["P:Responsibilities are assigned by role; named holders are maintained in QMS Settings."]),
            ("Quality standards and procedures", ["Requirements Development & Management Procedure (DOC-002)", "Requirement Review Checklist (DOC-003)", "Change Request Form (DOC-004)", "Requirements Traceability Matrix (DOC-005)", "Peer Review Procedure (DOC-006)", "Release Readiness Checklist (DOC-007)", "CAPA Procedure (DOC-008)", "Coding standard enforced through code review (currency types, input validation, error handling)"]),
            ("Quality assurance activities (prevent defects)", ["Process audits of requirement, review, test and CAPA records", "Peer and formal reviews with mandatory checklists", "Traceability audits (need > requirement > design > test > defect)", "Document control with versioned, approved procedures", "Periodic CAPA effectiveness reviews"]),
            ("Quality control activities (detect defects)", ["Test execution across " + ", ".join(TEST_CATEGORIES), "Defect logging, severity classification and verified closure", "Regression testing after every defect fix", "Data-validation and database-integrity testing before release"]),
            ("Quality gates", ["P:Four gates control progress (table below). Work does not pass a gate until its exit criteria are met."]),
            ("Quality metrics", ["P:Metrics are calculated by the QMS from stored records (table below, with current values)."]),
            ("Risk management", ["P:Risks are ranked by consequence for patients and hospital operations (table below). Critical risks receive additional review and verification."]),
            ("Approval responsibilities", ["QA Lead approves this plan and procedures.", "Project Manager authorises the release decision.", "Change Control Board (CCB) approves changes to baselines.", "Hospital stakeholder accepts requirements."]),
        ],
        "tables": {"Quality responsibilities": (["Role", "Responsibility", "Approval authority"], roles),
                   "Quality gates": (["Gate", "Name", "Entry criteria", "Exit criteria", "Approver"], gates),
                   "Quality metrics": "metrics", "Risk management": (["Risk", "Impact", "Mitigation"], risks)},
        "excel_tables": {"Responsibilities": (["Role", "Responsibility", "Approval authority"], roles), "Quality Gates": (["Gate", "Name", "Entry criteria", "Exit criteria", "Approver"], gates)},
    }


def _req_proc():
    return {"category": "PROCEDURE", "purpose": "Identify, classify, analyse, document, validate, baseline, change-control and trace the requirements of the Hospital Management Software.",
            "sections": [
                ("Requirement identification", ["Capture each stakeholder need as SN-xx (e.g. 'Appointments are scheduled without conflicts').", "Derive requirements from needs; assign unique ID REQ-nnn.", "Sources: hospital users, clinicians, front desk, billing, laboratory staff, IT security."]),
                ("Requirement classification", ["Type: Functional or Non-functional.", "Category: " + "; ".join(REQ_CATEGORIES) + ".", "Priority and risk: Critical / High / Medium / Low. Patient-identity, laboratory, prescription, billing and access requirements default to High or Critical risk.", "Quality factor tag (e.g. Data Accuracy, Security and Privacy)."]),
                ("Requirement analysis", ["Check for conflicts, duplicates and missing data-integrity rules.", "Identify interfaces (laboratory devices, payment gateways).", "Estimate effort and risk; flag requirements needing additional review (Critical/High risk)."]),
                ("Requirement documentation", ["Record title, detailed description, acceptance criteria, owner, design reference and implementation reference in the QMS Requirements module.", "Acceptance criteria must be measurable and testable."]),
                ("Requirement validation", ["Hold a Requirement review using the Requirement Review Checklist (DOC-003).", "Critical/High-risk requirements also need design, database or security review.", "Record reviewer, decision and findings in the Reviews module."]),
                ("Requirement baseline", ["A requirement is baselined only when its status is Approved/Implemented/Verified and an approved Requirement review covers it.", "The QMS refuses approval without that review record."]),
                ("Requirement change management", ["Raise a Change Request (DOC-004) for any change to a baselined requirement.", "Assess impact on design, code, tests, documents and release.", "CCB decision recorded; approved changes update the requirement and trigger re-review and retest."]),
                ("Requirement traceability", ["Maintain the RTM (DOC-005): stakeholder need > requirement > design > implementation > test case > result > defect > CAPA.", "Investigate gaps: no test, no approval, failed test, open defect, missing links."]),
                ("Approval workflow", ["Draft > Under Review > Approved > Implemented > Verified (or Rejected).", "Approver: QA Lead / Reviewer; stakeholder acceptance for baseline."])],
            "tables": {"Approval workflow": (["Status", "Meaning", "Condition to enter"], [["Draft", "Being written", "Created"], ["Under Review", "Review in progress", "Submitted for review"], ["Approved", "Baselined", "Approved review covers the requirement"], ["Implemented", "Built", "Approved + implementation reference"], ["Verified", "Proven by tests", "All tests passed, no open defects"], ["Rejected", "Not accepted", "Review decision"]])},
            "excel_tables": {"Workflow": (["Status", "Meaning", "Condition to enter"], [["Draft", "Being written", "Created"], ["Under Review", "Review in progress", "Submitted for review"], ["Approved", "Baselined", "Approved review covers the requirement"], ["Implemented", "Built", "Approved + implementation reference"], ["Verified", "Proven by tests", "All tests passed, no open defects"], ["Rejected", "Not accepted", "Review decision"]])}}


REVIEW_CHECK_SECTIONS = [
    ("Requirement completeness", ["All inputs, outputs and data fields are specified", "Mandatory and optional data are identified", "Error and exception behaviour is described"]),
    ("Requirement correctness", ["Requirement reflects the stakeholder need (SN-xx)", "Clinical and business rules are stated correctly", "Terminology matches hospital usage"]),
    ("Requirement consistency", ["No conflict with other requirements", "Identifiers and statuses are used consistently", "Consistent with existing design and interfaces"]),
    ("Requirement feasibility", ["Technically achievable with agreed architecture", "Achievable within schedule and resources", "Dependencies on external systems identified"]),
    ("Requirement testability", ["Verifiable by at least one test case", "Pass/fail condition is unambiguous", "Test data can be created without real patient data"]),
    ("Data accuracy considerations", ["Patient identity, laboratory, prescription and billing data accuracy rules are explicit", "Duplicate-prevention and validation rules are stated", "Behaviour on transaction failure (rollback) is defined"]),
    ("Security and privacy considerations", ["Roles allowed to view or change data are defined", "Confidential data protection (encryption, masking, audit) is stated", "Access-denied behaviour and logging are defined"]),
    ("Performance requirements", ["Response-time and load targets are quantified", "Availability and recovery objectives (RPO/RTO) are stated"]),
    ("Acceptance criteria", ["Acceptance criteria are measurable", "Criteria cover normal, boundary and failure cases", "Criteria agreed with stakeholder"]),
    ("Reviewer approval", ["All findings recorded with severity", "Decision recorded: Approved / Approved with actions / Rework required / Rejected", "Reviewer name and date recorded"]),
]


def _req_check():
    return {"category": "CHECKLIST", "purpose": "Checklist used in every Requirement review. Approved requires every item to be answered Yes.",
            "sections": [], "checklist": REVIEW_CHECK_SECTIONS, "tables": {}, "excel_tables": {}}


CR_FIELDS = [("Change request ID", "Unique ID, e.g. CR-001"), ("Change title", "Short name of the change"), ("Change description", "What will change"), ("Reason for change", "Defect, new need, regulation, performance, etc."),
             ("Affected hospital software module", "Select: " + ", ".join(MODULES)), ("Impact analysis", "Affected requirements, design, code, tests, documents, data migration"),
             ("Risk assessment", "Risk to patient data, safety, security and schedule (Critical/High/Medium/Low) with mitigation"), ("Cost and time impact", "Effort (person-days), cost, schedule effect"),
             ("Recommendation", "Approve / Reject / Defer with justification"), ("Approval decision", "CCB decision, approver name, date"), ("Implementation status", "Not started / In progress / Implemented / Verified"), ("Closure details", "Verification evidence, baseline updated, closure date and approver")]


def _cr():
    return {"category": "TEMPLATE", "purpose": "Formal request, assessment and approval of a change to a baselined requirement, design or release of the Hospital Management Software.",
            "sections": [("How to use this form", ["Complete sections 1-8, submit to the Change Control Board (CCB), record the decision, then track implementation to closure.", "Attach affected requirement IDs; re-run reviews and regression tests for approved changes."])],
            "form": CR_FIELDS, "tables": {}, "excel_tables": {}}


def _rtm_doc():
    return {"category": "TEMPLATE", "purpose": "Bidirectional traceability from stakeholder need through requirement, design, implementation, test, result, defect and approval.",
            "sections": [("What the matrix shows", ["Forward traceability: each stakeholder need leads to requirements, design and implementation references, test cases and results.", "Backward traceability: each test case or defect leads back to a requirement and need.", "Columns: Stakeholder need, Requirement ID, Requirement description, Hospital module, Priority, Risk level, Design reference, Implementation reference, Test case ID, Test result, Defect ID, Approval status."]),
                         ("Gap analysis rules", ["Requirement without test case", "Requirement without approval", "Failed test cases", "Open defects", "Missing design / implementation / stakeholder-need links", "Unverified requirement (no passing test or open defect)"]),
                         ("Maintenance", ["The Excel download is generated from live QMS data and is editable. Update the QMS records; re-download to refresh."])],
            "tables": {"What the matrix shows": "rtm_sample"}, "excel_tables": {}}


def _peer():
    return {"category": "PROCEDURE", "purpose": "Define how peer reviews of hospital software artefacts are planned, performed, recorded and signed off.",
            "sections": [
                ("Review objectives", ["Find defects early (especially data-integrity, security and privacy defects).", "Confirm the artefact meets its requirements and standards.", "Reach and record a decision before work proceeds."]),
                ("Review scope", ["Review types: " + ", ".join(REVIEW_TYPES) + ".", "Mandatory: Requirement review, Security review, Release review, Test plan review."]),
                ("Review participants", ["Author (presents, answers questions, fixes findings).", "Reviewer (independent of the author; records the decision).", "Moderator/QA Lead (ensures procedure is followed).", "Subject-matter expert (clinical, billing or laboratory) when required."]),
                ("Entry criteria", ["Artefact complete and version identified.", "Related requirements and design linked.", "Relevant checklist available."]),
                ("Review preparation", ["Reviewer reads the artefact and completes the checklist before the meeting.", "Due date recorded in the QMS Reviews module."]),
                ("Review checklist", ["Use the checklist for the review type (Requirement review: DOC-003). Each checklist item is recorded Yes/No/N/A with comments."]),
                ("Review findings", ["Record each finding with location, description and severity (Critical/High/Medium/Low).", "A review with a Critical finding cannot be plainly Approved."]),
                ("Defect classification", ["Classify by hospital defect category (incorrect patient data, duplicate records, billing errors, authorisation failure, etc.).", "Findings affecting patient data, prescriptions, laboratory results, billing or confidential access are treated as highest priority."]),
                ("Rework procedure", ["Author fixes findings; reviewer verifies each fix.", "Decision Rework required returns the artefact to the author with comments."]),
                ("Exit criteria", ["All findings closed or accepted with documented actions.", "Mandatory checklist fully checked for plain approval.", "Decision, reviewer and date recorded."]),
                ("Approval and sign-off", ["Decisions: Approved, Approved with actions, Rework required, Rejected.", "A review is not approved without a recorded reviewer and decision."])],
            "tables": {"Review participants": (["Role", "Responsibility", "Independent of author"], [["Author", "Presents artefact, fixes findings", "No"], ["Reviewer", "Reviews and decides", "Yes"], ["Moderator / QA Lead", "Procedure compliance", "Yes"], ["Subject-matter expert", "Domain accuracy", "Yes"]])},
            "excel_tables": {}}


RELEASE_ROWS = [("Requirements approval", "req_approved"), ("Test execution completion", "test_execution"), ("Test pass rate", "pass_rate"), ("Critical defect verification", "critical_defects"),
                ("High-risk defect assessment", "high_defects"), ("Security testing", "security_testing"), ("Database integrity verification", "db_integrity"),
                ("Documentation approval", "documentation"), ("Backup and recovery readiness", "backup_recovery"), ("Rollback plan", "rollback_plan"),
                ("Final release approval", "approvals"), ("Traceability complete (additional gate check)", "traceability"), ("Failed tests reviewed (additional gate check)", "failed_reviewed")]


def _release():
    return {"category": "CHECKLIST", "purpose": "Formal release-readiness gate. GO is allowed only when every mandatory check passes; CONDITIONAL GO requires documented conditions.",
            "sections": [("Decision rules", ["GO: all 13 checks passed.", "CONDITIONAL GO: no open critical defects, minimum pass rate met, security tests passed, security and release reviews approved, and conditions documented.", "NO-GO: any other state; can always be recorded with a rationale.", "Minimum 80% test pass rate is the proposed project baseline."])],
            "release": True, "tables": {}, "excel_tables": {}}


def _capa():
    return {"category": "PROCEDURE", "purpose": "Contain, investigate and eliminate root causes of significant defects and prevent recurrence in the Hospital Management Software.",
            "sections": [
                ("Problem identification", ["Open a CAPA for every Critical defect, any defect affecting patient data, prescriptions, laboratory results, billing or confidential access, and repeated defects.", "Record the problem description and the linked defect."]),
                ("Immediate containment", ["Apply a temporary control (manual verification, feature disabled, reconciliation script) to protect patient data until the fix is verified."]),
                ("Root cause analysis", ["Investigate process and technical causes; record the root cause statement."]),
                ("Five Whys", ["Ask 'why' up to five times, recording each answer; stop when a process or design cause that can be corrected is reached."]),
                ("Corrective action", ["Fix the defect and its cause (code, design, data)."]),
                ("Preventive action", ["Change the process so the cause cannot recur (checklist item, coding standard, automated test, review type)."]),
                ("Action ownership", ["Every CAPA has a responsible owner and target completion date; overdue CAPAs raise alerts in the QMS."]),
                ("Implementation evidence", ["Attach evidence: retest report, review record, updated procedure or checklist."]),
                ("Effectiveness verification", ["After an agreed period, review whether the problem recurred.", "Documented effectiveness review is mandatory."]),
                ("CAPA closure approval", ["The QMS prevents closure without verification evidence, effectiveness review, closure approver, and the linked defect Resolved/Closed."])],
            "tables": {"Action ownership": (["Status", "Entry condition", "Exit condition"], [["Open", "Defect triggers CAPA", "Owner assigned"], ["Investigation", "Root cause analysis started", "Root cause documented"], ["Action Planned", "Actions defined", "Owner and date agreed"], ["In Progress", "Implementation underway", "Actions complete"], ["Verification", "Evidence collection", "Evidence recorded"], ["Closed", "Effectiveness verified", "Closure approved"]])},
            "excel_tables": {}}


SPEC_BUILDERS = {"quality_plan": _plan, "req_procedure": _req_proc, "req_checklist": _req_check, "change_request": _cr, "rtm": _rtm_doc,
                 "peer_review": _peer, "release_checklist": _release, "capa_procedure": _capa}


def spec(key):
    b = SPEC_BUILDERS.get(key)
    return b() if b else {"category": "CUSTOM", "purpose": "", "sections": [], "tables": {}, "excel_tables": {}}


def outline(meta):
    """Light structure used by the in-app 'View document' panel."""
    sp = spec(meta["doc_key"])
    secs = [{"heading": h, "items": [i[2:] if i.startswith("P:") else i for i in items]} for h, items in sp["sections"]]
    if sp.get("checklist"):
        secs = [{"heading": h, "items": items} for h, items in sp["checklist"]]
    if sp.get("form"):
        secs.append({"heading": "Form fields", "items": [f"{a}: {b}" for a, b in sp["form"]]})
    if sp.get("release"):
        secs.append({"heading": "Mandatory checks (live status)", "items": [f"{n}: {c['status']}" for (n, k) in RELEASE_ROWS for c in M.release_checks() if c["key"] == k]})
    return {"purpose": sp["purpose"], "category": sp["category"], "sections": secs}


def search_text(meta):
    o = outline(meta)
    return (o["purpose"] + " " + " ".join(s["heading"] + " " + " ".join(s["items"]) for s in o["sections"])).lower()


# ====================================================================== live data helpers
def _metrics_rows():
    return [[m["name"], m["formula"], m["display"], m["status"]] for m in M.metrics()]


def _rtm_rows():
    out = []
    for x in M.rtm()["rows"]:
        tests = ", ".join(t["id"] for t in x["tests"])
        out.append([f"{x['need_id'] or ''} {x['need_title'] or ''}".strip(), x["id"], x["title"] + " - " + x["description"], x["category"], x["priority"], x["risk"],
                    x["design_ref"] or "", x["impl_ref"] or "", tests, x["test_result"], ", ".join(d["id"] for d in x["defects"]), x["approval"]])
    return out


def _release_rows():
    checks = {c["key"]: c for c in M.release_checks()}
    return [[i + 1, name, checks[k]["status"], checks[k]["detail"]] for i, (name, k) in enumerate(RELEASE_ROWS)]


# ====================================================================== Word
def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _table(document, head, rows, widths=None, size=9):
    t = document.add_table(rows=1, cols=len(head))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(head):
        c = t.rows[0].cells[i]
        c.text = str(h)
        _shade(c, NAVY)
        for r in c.paragraphs[0].runs:
            r.font.bold = True
            r.font.size = Pt(size)
            r.font.color.rgb = RGBColor(255, 255, 255)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for r in cells[i].paragraphs[0].runs:
                r.font.size = Pt(size)
    if widths:
        t.autofit = False
        for i, w in enumerate(widths):
            t.columns[i].width = Inches(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    document.add_paragraph()
    return t


def _word_doc(document, meta, first=True):
    key = meta["doc_key"]
    sp = spec(key)
    document.add_heading(meta["title"], level=1)
    p = document.add_paragraph(f"{PRODUCT}  |  {db.get_setting('project_name')}  |  {db.get_setting('team_name')}")
    p.runs[0].font.size = Pt(9)
    p.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    _table(document, ["Document ID", "Title", "Version", "Owner", "Creation date", "Review date", "Approval status"],
           [[meta["id"], meta["title"], meta["version"], meta["owner"], meta["created_on"], meta["review_date"] or "-", meta["approval_status"]]], size=8.5)
    if sp["purpose"]:
        document.add_heading("Purpose", level=2)
        document.add_paragraph(sp["purpose"])
    n = 0
    for heading, items in sp["sections"]:
        n += 1
        document.add_heading(f"{n}. {heading}", level=2)
        for it in items:
            if it.startswith("P:"):
                document.add_paragraph(it[2:])
            else:
                document.add_paragraph(it, style="List Bullet")
        tb = sp["tables"].get(heading)
        if tb == "metrics":
            _table(document, ["Metric", "Formula", "Current value", "Status"], _metrics_rows(), size=8)
        elif tb == "rtm_sample":
            document.add_paragraph("Sample of the live matrix (first rows; the Excel download contains all requirements):")
            _table(document, ["Need", "Req ID", "Module", "Priority", "Risk", "Tests", "Result", "Defects", "Approval"],
                   [[r[0][:28], r[1], r[3], r[4], r[5], r[8], r[9], r[10], r[11]] for r in _rtm_rows()[:6]], size=7.5)
        elif tb:
            _table(document, tb[0], tb[1], size=8.5)
    if sp.get("checklist"):
        for i, (heading, items) in enumerate(sp["checklist"], 1):
            document.add_heading(f"{i}. {heading}", level=2)
            _table(document, ["#", "Check item", "Yes", "No", "N/A", "Comment"], [[j + 1, it, "\u2610", "\u2610", "\u2610", ""] for j, it in enumerate(items)], widths=[0.35, 3.3, 0.45, 0.45, 0.45, 1.5], size=8.5)
        document.add_paragraph("Requirement reviewed: ____________   Reviewer: ____________   Date: ____________   Decision: \u2610 Approved  \u2610 Approved with actions  \u2610 Rework required  \u2610 Rejected")
    if sp.get("form"):
        document.add_heading("Change request details", level=2)
        _table(document, ["Field", "Guidance", "Entry"], [[a, b, ""] for a, b in sp["form"]], widths=[1.8, 2.6, 2.1], size=8.5)
    if sp.get("release"):
        document.add_heading("Mandatory release checks (live status from the QMS)", level=2)
        _table(document, ["#", "Check", "Status", "Detail", "Verified by / date"], [r + [""] for r in _release_rows()], widths=[0.3, 1.9, 0.7, 2.7, 1.1], size=8)
        document.add_heading("Final release approval", level=2)
        _table(document, ["Decision", "Approver", "Signature", "Date"], [["GO / NO-GO / CONDITIONAL GO", "Project Manager", "", ""], ["Quality assurance sign-off", "QA Lead", "", ""]])
    document.add_heading("Version history", level=2)
    vh = db.query("SELECT version, changed_on, changed_by, summary, approval_status, approved_by FROM document_versions WHERE doc_id=? ORDER BY id", (meta["id"],))
    _table(document, ["Version", "Date", "Changed by", "Summary", "Status", "Approved by"], [[v["version"], v["changed_on"], v["changed_by"], v["summary"], v["approval_status"], v["approved_by"] or "-"] for v in vh], widths=[0.6, 0.8, 1.3, 2.2, 0.8, 1.3], size=8)
    document.add_heading("Approval record", level=2)
    _table(document, ["Role", "Name", "Decision / status", "Date"], [["Document owner", meta["owner"], "Author", meta["updated_on"]], ["Approver", meta["approved_by"] or "Pending", meta["approval_status"], meta["approved_on"] or "-"]])
    f = document.add_paragraph("Approvals: QA Lead owns quality direction. Project Manager authorises release. CCB controls baseline changes. Hospital stakeholder accepts requirements.")
    f.runs[0].font.size = Pt(8)
    d2 = document.add_paragraph(DISCLAIMER)
    d2.runs[0].font.size = Pt(8)


def build_doc_docx(meta=None, handbook=False):
    document = Document()
    document.styles["Normal"].font.name = "Arial"
    document.styles["Normal"].font.size = Pt(10)
    if handbook:
        document.add_heading(f"{PRODUCT} - Quality Handbook", 0)
        document.add_paragraph(f"{db.get_setting('project_name')} | {db.get_setting('team_name')} | Library revision {db.get_setting('library_revision', '1.0')} | generated {date.today().isoformat()}")
        for m in db.query("SELECT * FROM documents ORDER BY id"):
            document.add_page_break()
            _word_doc(document, m)
    else:
        _word_doc(document, meta)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


# ====================================================================== Excel
_thin = Side(style="thin", color="CBD5E1")
_border = Border(top=_thin, bottom=_thin, left=_thin, right=_thin)


def _sheet(wb, title, head, rows, widths=None, first=False, note=None):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title[:31]
    r0 = 1
    if note:
        ws["A1"] = note
        ws["A1"].font = Font(name="Arial", italic=True, size=9, color="64748B")
        r0 = 3
    for i, h in enumerate(head, 1):
        c = ws.cell(row=r0, column=i, value=h)
        c.font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = _border
    for ri, row in enumerate(rows, r0 + 1):
        for ci, v in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.font = Font(name="Arial", size=9)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = _border
    for i, h in enumerate(head, 1):
        w = (widths or {}).get(i) or min(46, max(12, len(str(h)) + 4))
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=r0 + 1, column=1)
    return ws, r0


def _dv(ws, col, r_from, r_to, options):
    dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{get_column_letter(col)}{r_from}:{get_column_letter(col)}{r_to}")


def _info_sheet(wb, meta, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = "Document Control"
    ws["A1"] = meta["title"]
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color=NAVY)
    rows = [("Document ID", meta["id"]), ("Title", meta["title"]), ("Version", meta["version"]), ("Owner", meta["owner"]), ("Creation date", meta["created_on"]),
            ("Review date", meta["review_date"] or "-"), ("Last updated", meta["updated_on"]), ("Approval status", meta["approval_status"]), ("Approved by", meta["approved_by"] or "-"),
            ("Project", db.get_setting("project_name")), ("Team", db.get_setting("team_name")), ("Generated from", PRODUCT + " on " + date.today().isoformat())]
    for i, (a, b) in enumerate(rows, 3):
        ws.cell(row=i, column=1, value=a).font = Font(name="Arial", bold=True, size=10)
        ws.cell(row=i, column=2, value=b).font = Font(name="Arial", size=10)
    ws.cell(row=3 + len(rows) + 1, column=1, value=DISCLAIMER).font = Font(name="Arial", italic=True, size=8, color="64748B")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 70
    r = 3 + len(rows) + 3
    ws.cell(row=r, column=1, value="Version history").font = Font(name="Arial", bold=True, color=NAVY)
    vh = db.query("SELECT version, changed_on, changed_by, summary, approval_status FROM document_versions WHERE doc_id=? ORDER BY id", (meta["id"],))
    for ci, h in enumerate(["Version", "Date", "Changed by", "Summary", "Status"], 1):
        c = ws.cell(row=r + 1, column=ci, value=h)
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
    for ri, v in enumerate(vh, r + 2):
        for ci, val in enumerate([v["version"], v["changed_on"], v["changed_by"], v["summary"], v["approval_status"]], 1):
            ws.cell(row=ri, column=ci, value=val).font = Font(name="Arial", size=9)
    for col, w in zip("CDE", [26, 50, 16]):
        ws.column_dimensions[col].width = w
    return ws


def build_doc_xlsx(meta):
    key = meta["doc_key"]
    sp = spec(key)
    wb = Workbook()
    ws = _info_sheet(wb, meta, first=True)
    team = [t["name"] for t in db.query("SELECT name FROM team_members ORDER BY id")]

    if key == "quality_plan":
        _sheet(wb, "Quality Objectives", ["Objective", "Target", "Owner", "Evidence in QMS"], [[a, b, "QA Lead", "Quality Analytics / Release Management"] for a, b in QUALITY_OBJECTIVES], {1: 30, 2: 80, 3: 18, 4: 36})
        roles = sp["excel_tables"]["Responsibilities"]
        holders = {t["role"]: t["name"] for t in db.query("SELECT name, role FROM team_members")}
        rmap = {"Project Manager": "Project Manager", "Quality Assurance Lead": "Quality Assurance Lead", "Business Analyst": "Business Analyst", "Technical Architect": "Technical Architect", "Developer": "Developer", "Test Manager": "Test Manager", "Reviewer": "Reviewer"}
        _sheet(wb, "Responsibilities", roles[0] + ["Current holder"], [r + [holders.get(rmap[r[0]], "")] for r in roles[1]], {1: 24, 2: 50, 3: 36, 4: 24})
        _sheet(wb, "Quality Metrics", ["Metric", "Calculation formula", "Current value (live)", "Quality status", "Target / threshold (proposed)"],
               [r + ["see formula; pass-rate baseline " + db.get_setting("min_pass_rate", "80") + "%" if r[0] == "Test Pass Rate" else "per metric thresholds"] for r in _metrics_rows()], {1: 32, 2: 60, 3: 20, 4: 14, 5: 34})
        g = sp["excel_tables"]["Quality Gates"]
        ws2, r0 = _sheet(wb, "Quality Gates", g[0] + ["Gate status", "Sign-off date"], [r + ["Pending", ""] for r in g[1]], {1: 8, 2: 24, 3: 50, 4: 60, 5: 20, 6: 14, 7: 14})
        _dv(ws2, 6, r0 + 1, r0 + 20, ["Pending", "Passed", "Failed"])

    elif key == "req_procedure":
        reqs = db.query("SELECT r.*, (SELECT GROUP_CONCAT(review_id,', ') FROM review_requirements WHERE requirement_id=r.id) AS rv FROM requirements r ORDER BY r.id")
        head = ["Requirement ID", "Title", "Category", "Type", "Priority", "Risk", "Owner", "Status", "Stakeholder need", "Acceptance criteria", "Review record(s)", "Approved by", "Approved on", "Baseline version", "Change request ref", "Comments"]
        rows = [[r["id"], r["title"], r["category"], r["req_type"], r["priority"], r["risk"], r["owner"], r["status"], r["need_id"] or "", r["acceptance_criteria"], r["rv"] or "", r["approved_by"] or "", r["approved_on"] or "", "v" + meta["version"] if r["status"] in ("Approved", "Implemented", "Verified") else "", "", ""] for r in reqs]
        ws2, r0 = _sheet(wb, "Requirements Tracker", head, rows, {2: 40, 3: 24, 7: 22, 10: 50, 11: 18, 12: 22})
        n = len(rows) + 60
        _dv(ws2, 3, r0 + 1, r0 + n, REQ_CATEGORIES)
        _dv(ws2, 4, r0 + 1, r0 + n, ["Functional", "Non-functional"])
        _dv(ws2, 5, r0 + 1, r0 + n, ["Critical", "High", "Medium", "Low"])
        _dv(ws2, 6, r0 + 1, r0 + n, ["Critical", "High", "Medium", "Low"])
        _dv(ws2, 7, r0 + 1, r0 + n, team)
        _dv(ws2, 8, r0 + 1, r0 + n, ["Draft", "Under Review", "Approved", "Implemented", "Verified", "Rejected"])
        w = sp["excel_tables"]["Workflow"]
        _sheet(wb, "Status Workflow", w[0], w[1], {1: 16, 2: 24, 3: 60})
        cnt = wb.create_sheet("Summary")
        cnt["A1"], cnt["B1"] = "Status", "Count (formula)"
        for i, s in enumerate(["Draft", "Under Review", "Approved", "Implemented", "Verified", "Rejected"], 2):
            cnt.cell(row=i, column=1, value=s)
            cnt.cell(row=i, column=2, value=f"=COUNTIF('Requirements Tracker'!H:H,A{i})")
        cnt.column_dimensions["A"].width = 18
        cnt.column_dimensions["B"].width = 18

    elif key == "req_checklist":
        rows = []
        for sec, items in sp["checklist"]:
            for j, it in enumerate(items, 1):
                rows.append([sec, j, it, "Pending", "", "", ""])
        ws2, r0 = _sheet(wb, "Review Checklist", ["Section", "#", "Check item", "Status", "Comments", "Reviewer", "Date"], rows, {1: 32, 2: 5, 3: 70, 4: 12, 5: 50, 6: 22, 7: 12},
                         note="Interactive checklist: choose Status (Yes / No / N/A / Pending) per item. Approved requires every item = Yes or N/A.")
        _dv(ws2, 4, r0 + 1, r0 + len(rows), ["Yes", "No", "N/A", "Pending"])
        _dv(ws2, 6, r0 + 1, r0 + len(rows), team)
        last = r0 + len(rows)
        s = wb.create_sheet("Checklist Summary")
        s["A1"], s["B1"] = "Measure", "Value"
        items = [("Total items", f"=COUNTA('Review Checklist'!C{r0+1}:C{last})"), ("Yes", f"=COUNTIF('Review Checklist'!D{r0+1}:D{last},\"Yes\")"), ("No", f"=COUNTIF('Review Checklist'!D{r0+1}:D{last},\"No\")"),
                 ("N/A", f"=COUNTIF('Review Checklist'!D{r0+1}:D{last},\"N/A\")"), ("Pending", f"=COUNTIF('Review Checklist'!D{r0+1}:D{last},\"Pending\")"),
                 ("Ready for plain approval?", "=IF(AND(B6=0,B4=0),\"YES - may be Approved\",\"NO - items outstanding\")")]
        for i, (a, f) in enumerate(items, 2):
            s.cell(row=i, column=1, value=a)
            s.cell(row=i, column=2, value=f)
        s.column_dimensions["A"].width = 28
        s.column_dimensions["B"].width = 28
        _sheet(wb, "Review Decision", ["Requirement(s) reviewed", "Review ID", "Reviewer", "Decision", "Severity of findings", "Date"], [["", "", "", "", "", ""]] * 5, {1: 36, 2: 14, 3: 22, 4: 24, 5: 18, 6: 14})
        wb["Review Decision"].cell(row=2, column=4)
        _dv(wb["Review Decision"], 4, 2, 6, ["Approved", "Approved with actions", "Rework required", "Rejected"])

    elif key == "change_request":
        head = ["CR ID", "Change title", "Change description", "Reason for change", "Affected hospital module", "Impact analysis", "Risk assessment", "Cost impact", "Time impact (days)", "Recommendation", "Approval decision", "Decided by", "Decision date", "Implementation status", "Closure date", "Closure details"]
        ex = ["CR-001 (EXAMPLE)", "Normalise patient name before duplicate check", "Convert names to a normalised form (case, spacing) before matching.", "Defect DEF-001: duplicate patients created.", "Patient Registration",
              "REQ-002 design DD-PR-02, PatientService, tests TC-002/TC-018", "High - affects patient identity data", "2 person-days", 3, "Approve", "Approved", "CCB", date.today().isoformat(), "In progress", "", ""]
        ws2, r0 = _sheet(wb, "Change Request Register", head, [ex] + [[""] * 16 for _ in range(14)], {1: 18, 2: 34, 3: 44, 4: 36, 5: 24, 6: 40, 7: 28, 8: 14, 9: 12, 10: 16, 11: 16, 12: 18, 13: 14, 14: 18, 15: 14, 16: 40},
                         note="Change request tracking register. Row 4 is an EXAMPLE showing the expected format; overwrite or delete it.")
        end = r0 + 15
        _dv(ws2, 5, r0 + 1, end + 100, MODULES)
        _dv(ws2, 10, r0 + 1, end + 100, ["Approve", "Reject", "Defer"])
        _dv(ws2, 11, r0 + 1, end + 100, ["Pending", "Approved", "Rejected", "Deferred"])
        _dv(ws2, 14, r0 + 1, end + 100, ["Not started", "In progress", "Implemented", "Verified", "Closed"])
        _sheet(wb, "Change Request Form", ["Field", "Guidance", "Entry"], [[a, b, ""] for a, b in sp["form"]], {1: 36, 2: 80, 3: 50})

    elif key == "rtm":
        head = ["Stakeholder need", "Requirement ID", "Requirement description", "Hospital module", "Priority", "Risk level", "Design reference", "Implementation reference", "Test case ID", "Test result", "Defect ID", "Approval status"]
        rows = _rtm_rows()
        ws2, r0 = _sheet(wb, "RTM", head, rows, {1: 34, 2: 12, 3: 60, 4: 24, 5: 10, 6: 10, 7: 32, 8: 26, 9: 20, 10: 12, 11: 18, 12: 14})
        ws2.auto_filter.ref = f"A{r0}:L{r0 + len(rows)}"
        extra = r0 + len(rows) + 40
        _dv(ws2, 4, r0 + 1, extra, MODULES)
        _dv(ws2, 5, r0 + 1, extra, ["Critical", "High", "Medium", "Low"])
        _dv(ws2, 6, r0 + 1, extra, ["Critical", "High", "Medium", "Low"])
        _dv(ws2, 10, r0 + 1, extra, ["Passed", "Failed", "Blocked", "Pending", "No test"])
        _dv(ws2, 12, r0 + 1, extra, ["Approved", "Not approved", "Rejected"])
        s = M.rtm()["summary"]
        _sheet(wb, "Gap Summary", ["Gap", "Count"], [["Requirements without test cases", s["without_tests"]], ["Requirements without approval", s["without_approval"]], ["Requirements with failed tests", s["with_failed_tests"]],
                                                       ["Requirements with open defects", s["with_open_defects"]], ["Requirements with missing links", s["missing_links"]], ["Unverified requirements", s["unverified"]]], {1: 40, 2: 10})
        _sheet(wb, "Legend", ["Column", "Meaning"], [["Stakeholder need", "SN-xx need the requirement satisfies"], ["Design reference", "Design document/section"], ["Implementation reference", "Code module/class"], ["Test result", "Passed / Failed / Blocked / Pending / No test"], ["Defect ID", "Defects linked to the requirement"]], {1: 28, 2: 70})

    elif key == "peer_review":
        rv = db.query("SELECT v.*, (SELECT GROUP_CONCAT(requirement_id,', ') FROM review_requirements WHERE review_id=v.id) AS reqs FROM reviews v ORDER BY v.id")
        rows = [[r["id"], r["review_type"], r["title"], r["artifact"], r["artifact_version"], r["reviewer"], r["review_date"] or "", r["due_date"] or "", r["reqs"] or "", r["finding_severity"] or "", r["decision"] or "Pending", r["approval_status"]] for r in rv]
        ws2, r0 = _sheet(wb, "Peer Review Tracker", ["Review ID", "Review type", "Title", "Artifact", "Version", "Reviewer", "Review date", "Due date", "Requirements covered", "Highest finding severity", "Decision", "Approval status"], rows,
                         {1: 10, 2: 24, 3: 46, 4: 36, 5: 9, 6: 22, 7: 12, 8: 12, 9: 26, 10: 14, 11: 20, 12: 20})
        _dv(ws2, 2, r0 + 1, r0 + len(rows) + 50, REVIEW_TYPES)
        _dv(ws2, 11, r0 + 1, r0 + len(rows) + 50, ["Pending", "Approved", "Approved with actions", "Rework required", "Rejected"])
        frows = []
        for r in rv:
            if (r["findings"] or "").strip():
                frows.append([f"FND-{len(frows) + 1:03d}", r["id"], r["artifact"], r["findings"], "", r["finding_severity"] or "Medium", r["reviewer"], "", "Rework" if r["decision"] in ("Rework required",) else "Open", "", ""])
        frows += [[""] * 11 for _ in range(15)]
        ws3, r1 = _sheet(wb, "Findings Register", ["Finding ID", "Review ID", "Artifact / location", "Finding description", "Defect classification", "Severity", "Raised by", "Assigned to", "Rework status", "Verified by", "Closed date"], frows,
                         {1: 11, 2: 10, 3: 30, 4: 60, 5: 28, 6: 10, 7: 22, 8: 22, 9: 14, 10: 22, 11: 12})
        from domain import DEFECT_CATEGORIES
        _dv(ws3, 5, r1 + 1, r1 + len(frows) + 50, DEFECT_CATEGORIES)
        _dv(ws3, 6, r1 + 1, r1 + len(frows) + 50, ["Critical", "High", "Medium", "Low"])
        _dv(ws3, 9, r1 + 1, r1 + len(frows) + 50, ["Open", "Rework", "Fixed", "Verified", "Accepted"])

    elif key == "release_checklist":
        rows = [r + ["", "", "", r[2]] for r in _release_rows()]
        ws2, r0 = _sheet(wb, "Release Readiness", ["#", "Mandatory check", "System status (live)", "Detail", "Evidence reference", "Verified by", "Date", "Final status"], rows, {1: 5, 2: 46, 3: 18, 4: 70, 5: 30, 6: 22, 7: 12, 8: 14})
        _dv(ws2, 8, r0 + 1, r0 + len(rows), ["Passed", "Failed", "Pending"])
        _dv(ws2, 6, r0 + 1, r0 + len(rows), team)
        last = r0 + len(rows)
        s = wb.create_sheet("Decision")
        s["A1"], s["B1"] = "Measure", "Value"
        lines = [("Checks passed", f"=COUNTIF('Release Readiness'!H{r0+1}:H{last},\"Passed\")"), ("Checks failed", f"=COUNTIF('Release Readiness'!H{r0+1}:H{last},\"Failed\")"),
                 ("Checks pending", f"=COUNTIF('Release Readiness'!H{r0+1}:H{last},\"Pending\")"), ("Readiness %", f"=ROUND(100*B2/COUNTA('Release Readiness'!B{r0+1}:B{last}),1)"),
                 ("Allowed decision", "=IF(B2=COUNTA('Release Readiness'!B" + str(r0 + 1) + ":B" + str(last) + "),\"GO\",IF(B3=0,\"CONDITIONAL GO (document conditions)\",\"NO-GO or CONDITIONAL GO if critical checks pass\"))"),
                 ("Final decision (select)", ""), ("Approver", "Project Manager"), ("Signature / date", "")]
        for i, (a, f) in enumerate(lines, 2):
            s.cell(row=i, column=1, value=a)
            s.cell(row=i, column=2, value=f)
        _dv(s, 2, 7, 7, ["GO", "NO-GO", "CONDITIONAL GO"])
        s.column_dimensions["A"].width = 26
        s.column_dimensions["B"].width = 60
        hist = db.query("SELECT release_version, decision, decided_by, decided_on, rationale, conditions FROM release_decisions ORDER BY id DESC")
        _sheet(wb, "Decision History", ["Release", "Decision", "Decided by", "Date", "Rationale", "Conditions"], [[h["release_version"], h["decision"], h["decided_by"], h["decided_on"], h["rationale"], h["conditions"]] for h in hist] or [["", "", "", "", "", ""]], {1: 14, 2: 16, 3: 22, 4: 20, 5: 50, 6: 50})

    elif key == "capa_procedure":
        capas = db.query("SELECT * FROM capas ORDER BY id")
        head = ["CAPA ID", "Defect", "Problem", "Root cause", "Why 1", "Why 2", "Why 3", "Why 4", "Why 5", "Containment", "Corrective action", "Preventive action", "Owner", "Target date", "Status"]
        rows = [[c["id"], c["defect_id"] or "", c["problem"], c["root_cause"] or "", c["why1"] or "", c["why2"] or "", c["why3"] or "", c["why4"] or "", c["why5"] or "", c["containment"] or "", c["corrective"] or "", c["preventive"] or "", c["owner"], c["target_date"] or "", c["status"]] for c in capas]
        ws2, r0 = _sheet(wb, "CAPA Register", head, rows, {1: 10, 2: 10, 3: 40, 4: 36, 5: 30, 6: 30, 7: 30, 8: 30, 9: 30, 10: 34, 11: 34, 12: 34, 13: 22, 14: 12, 15: 16})
        _dv(ws2, 15, r0 + 1, r0 + len(rows) + 50, ["Open", "Investigation", "Action Planned", "In Progress", "Verification", "Closed"])
        _dv(ws2, 13, r0 + 1, r0 + len(rows) + 50, team)
        vrows = [[c["id"], c["defect_id"] or "", c["verification_evidence"] or "", c["effectiveness_review"] or "", "Effective" if c["effectiveness_review"] else "Pending", c["closure_approved_by"] or "", c["closed_on"] or ""] for c in capas]
        ws3, r1 = _sheet(wb, "Effectiveness Verification", ["CAPA ID", "Defect", "Implementation / verification evidence", "Effectiveness review", "Result", "Closure approved by", "Closed on"], vrows, {1: 10, 2: 10, 3: 50, 4: 50, 5: 16, 6: 24, 7: 12},
                         note="A CAPA may be closed only with verification evidence, an effectiveness review and a named closure approver.")
        _dv(ws3, 5, r1 + 1, r1 + len(vrows) + 50, ["Effective", "Not effective", "Pending"])
        w = sp["tables"]["Action ownership"]
        _sheet(wb, "Status Definitions", w[0], w[1], {1: 16, 2: 36, 3: 36})

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
