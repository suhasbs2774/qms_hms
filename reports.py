"""Report + controlled-document generation: PDF, Excel, CSV, Word. All figures come from persisted data."""
import csv
import io
import json
from datetime import date, datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import db
import metrics as M
from domain import (DISCLAIMER, FACTOR_INFO, QUALITY_FACTORS, QUALITY_OBJECTIVES, REQ_CATEGORIES, REVIEW_TYPES,
                    TEST_CATEGORIES, DEFECT_DONE)

NAVY, BLUE, TEAL, ICE = "14243A", "2563EB", "0F9D91", "EFF6FF"
RED, AMBER = "DC2626", "F59E0B"
PRODUCT = "HOSPITAL QUALITY OS"


# =============================================================== report data
def report_data():
    s = {r["key"]: r["value"] for r in db.query("SELECT * FROM settings")}
    team = db.query("SELECT name, role, email FROM team_members ORDER BY id")
    reqs = db.query("SELECT * FROM requirements ORDER BY id")
    reviews = db.query("SELECT * FROM reviews ORDER BY id")
    tests = db.query("SELECT t.*, (SELECT GROUP_CONCAT(d.id, ', ') FROM defects d WHERE d.test_case_id=t.id) AS defect_ids FROM test_cases t ORDER BY t.id")
    defects = db.query("SELECT * FROM defects ORDER BY id")
    capas = db.query("SELECT * FROM capas ORDER BY id")
    docs = db.query("SELECT * FROM documents ORDER BY id")
    ms = M.metrics()
    rel = M.release_summary()
    qs = M.quality_score()
    tr = M.rtm()
    risk = M.risk_summary()
    ch = M.chart_data()
    thr = M.min_pass_rate()
    mm = {m["key"]: m for m in ms}

    cat_rows = []
    for c in REQ_CATEGORIES:
        rs = [r for r in reqs if r["category"] == c]
        cat_rows.append([c, len(rs), sum(1 for r in rs if r["status"] in ("Approved", "Implemented", "Verified")),
                         sum(1 for r in rs if r["risk"] in ("Critical", "High"))])

    factor_rows = []
    for f in QUALITY_FACTORS:
        fr = [r for r in reqs if r["quality_factor"] == f]
        factor_rows.append([f, FACTOR_INFO[f], len(fr), sum(1 for r in fr if r["status"] in ("Approved", "Implemented", "Verified"))])

    exec_summary = (
        f"The {s.get('project_name')} for {s.get('team_name')} currently tracks {len(reqs)} requirements "
        f"({mm['approval_rate']['display']} approved), {len(tests)} test cases ({mm['pass_rate']['display']} pass rate against a "
        f"proposed {thr:g}% baseline) and {len(defects)} defects, of which {sum(1 for d in defects if d['status'] not in DEFECT_DONE)} are open "
        f"and {mm['critical_defects']['value']} are critical. The computed quality score is {qs['score']} ({qs['rating']}). "
        f"The release gate recommendation is {rel['recommendation']} with {rel['passed']} of {rel['total']} mandatory checks passed.")

    risks = []
    if mm["critical_defects"]["value"]:
        risks.append(f"{mm['critical_defects']['value']} open critical defect(s) threaten patient data integrity or confidential access.")
    if risk["patient_data_defects_open"]:
        risks.append(f"{risk['patient_data_defects_open']} open defect(s) affect patient data, laboratory results, prescriptions, billing or access: " + ", ".join(risk["patient_data_defect_ids"]) + ".")
    if risk["high_risk_unverified"]:
        risks.append(f"{risk['high_risk_unverified']} of {risk['high_risk_total']} high/critical-risk requirements are not yet verified.")
    if tr["summary"]["without_tests"]:
        risks.append(f"{tr['summary']['without_tests']} requirement(s) have no test case, so their behaviour is unverified.")
    if risk["failed_tests_without_defect"]:
        risks.append("Failed tests without a linked defect: " + ", ".join(risk["failed_tests_without_defect"]) + ".")
    if mm["capa_rate"]["value"] is not None and mm["capa_rate"]["value"] < 80:
        risks.append(f"Only {mm['capa_rate']['display']} of CAPAs are closed; recurrence risk remains for the remaining root causes.")
    if not risks:
        risks.append("No significant risks identified from the recorded data.")

    recs = []
    for c in rel["checks"]:
        if c["status"] != "Passed":
            recs.append(f"{c['name']}: {c['detail']}")
    if tr["summary"]["without_tests"]:
        recs.append("Create test cases for requirements without tests, starting with high-risk requirements.")
    if not recs:
        recs.append("Maintain current quality controls and proceed with the release review.")

    verdict = {"GO": "The recorded evidence supports a GO decision for the release candidate.",
               "CONDITIONAL GO": "The evidence supports a CONDITIONAL GO only if the failed and pending checks are tracked with owners and dates.",
               "NO-GO": "The evidence does not support release. Mandatory conditions are not satisfied."}[rel["recommendation"]]
    final = f"{verdict} Quality score {qs['score']} ({qs['rating']}). {DISCLAIMER}"

    return {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "project": s, "team": team, "reqs": reqs,
            "reviews": reviews, "tests": tests, "defects": defects, "capas": capas, "docs": docs, "metrics": ms,
            "release": rel, "score": qs, "rtm": tr, "risk": risk, "charts": ch, "threshold": thr,
            "category_rows": cat_rows, "factor_rows": factor_rows, "exec_summary": exec_summary,
            "risks": risks, "recommendations": recs, "final": final, "objectives": QUALITY_OBJECTIVES}


# =============================================================== charts (matplotlib -> PNG bytes)
def _fig_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_png(kind, d):
    ch = d["charts"]
    palette = {"Critical": "#DC2626", "High": "#F59E0B", "Medium": "#2563EB", "Low": "#0F9D91"}
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    if kind == "severity":
        labels, vals = ch["severity"]["labels"], ch["severity"]["values"]
        ax.bar(labels, vals, color=[palette[l] for l in labels])
        ax.set_title("Defects by severity", fontsize=10, color="#14243A")
    elif kind == "tests":
        cols = {"Passed": "#0F9D91", "Failed": "#DC2626", "Blocked": "#F59E0B", "Not Run": "#94A3B8", "In Progress": "#2563EB"}
        ax.bar(ch["tests"]["labels"], ch["tests"]["values"], color=[cols[l] for l in ch["tests"]["labels"]])
        ax.set_title("Test execution results", fontsize=10, color="#14243A")
    elif kind == "requirements":
        ax.bar(ch["requirements"]["labels"], ch["requirements"]["values"], color="#2563EB")
        ax.set_title("Requirements by status", fontsize=10, color="#14243A")
    elif kind == "modules":
        ax.barh(ch["modules"]["labels"], ch["modules"]["values"], color="#0F9D91")
        ax.invert_yaxis()
        ax.set_title("Defects by hospital module", fontsize=10, color="#14243A")
    elif kind == "performance":
        qp = [(m["name"], m["value"]) for m in d["metrics"] if m["unit"] == "%" and m["key"] != "release_readiness" and m["value"] is not None]
        ax.barh([n for n, _ in qp], [v for _, v in qp], color="#2563EB")
        ax.set_xlim(0, 100)
        ax.invert_yaxis()
        ax.set_title("Quality performance (%)", fontsize=10, color="#14243A")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7)
    plt.setp(ax.get_xticklabels(), rotation=0 if kind in ("severity", "performance", "modules") else 20)
    fig.tight_layout()
    return _fig_bytes(fig)


# =============================================================== PDF
def build_pdf(d):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
                                    KeepTogether)

    navy, blue, teal = colors.HexColor("#" + NAVY), colors.HexColor("#" + BLUE), colors.HexColor("#" + TEAL)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, textColor=navy, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5)
    cell = ParagraphStyle("c", parent=body, fontSize=7.5, leading=9)
    cellb = ParagraphStyle("cb", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    buf = io.BytesIO()
    proj = d["project"]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(18 * mm, 10 * mm, f"{PRODUCT} - {proj.get('project_name')} - {proj.get('team_name')}")
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}   |   Generated {d['generated']}")
        canvas.restoreState()

    def cover(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(blue)
        canvas.rect(0, 150 * mm, A4[0], 4, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(22 * mm, 255 * mm, PRODUCT)
        canvas.setFont("Helvetica-Bold", 30)
        canvas.drawString(22 * mm, 195 * mm, "Software Quality")
        canvas.drawString(22 * mm, 183 * mm, "Management Report")
        canvas.setFont("Helvetica", 14)
        canvas.drawString(22 * mm, 168 * mm, proj.get("project_name", ""))
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.HexColor("#BFD4FF"))
        canvas.drawString(22 * mm, 140 * mm, f"{proj.get('team_name')}  |  {proj.get('project_version')}")
        canvas.drawString(22 * mm, 133 * mm, proj.get("organisation", ""))
        canvas.drawString(22 * mm, 126 * mm, f"Report date: {d['generated']}")
        canvas.setFillColor(colors.HexColor("#" + TEAL))
        canvas.roundRect(22 * mm, 95 * mm, 80 * mm, 22 * mm, 3, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(26 * mm, 110 * mm, "QUALITY SCORE")
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawString(26 * mm, 100 * mm, f"{d['score']['score']}  {d['score']['rating']}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#BFD4FF"))
        canvas.drawString(22 * mm, 25 * mm, "Prototype QMS - not a certified clinical safety system. No regulatory compliance is claimed.")
        canvas.restoreState()

    def P(t, st=cell):
        return Paragraph(str(t if t is not None else "").replace("&", "&amp;").replace("<", "&lt;"), st)

    def table(head, rows, widths, status_col=None):
        data = [[Paragraph(h, cellb) for h in head]] + [[P(c) for c in r] for r in rows]
        t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
        st = [("BACKGROUND", (0, 0), (-1, 0), navy), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FB")]),
              ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        t.setStyle(TableStyle(st))
        return t

    def kv(rows):
        t = Table([[P(k, cellb if False else cell), P(v)] for k, v in rows], colWidths=[45 * mm, 125 * mm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#" + ICE)), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def img(kind, w=82):
        return Image(chart_png(kind, d), width=w * mm, height=w * 0.62 * mm)

    S = []
    S.append(PageBreak())
    n = [0]

    def H(title):
        n[0] += 1
        S.append(Paragraph(f"{n[0]}. {title}", h1))

    H("Project Information")
    S.append(kv([("Project", proj.get("project_name")), ("Team", proj.get("team_name")), ("Release", proj.get("project_version")),
                 ("Organisation", proj.get("organisation")), ("Project start", proj.get("project_start") or "-"),
                 ("Lifecycle", "PLAN > DEFINE > EXECUTE > VERIFY > MEASURE > REPORT > IMPROVE"), ("Report generated", d["generated"])]))
    H("Team Information")
    S.append(table(["Name", "Role", "Email"], [[t["name"], t["role"], t["email"] or "-"] for t in d["team"]], [60, 60, 50]))
    H("Executive Summary")
    S.append(Paragraph(d["exec_summary"], body))
    S.append(Spacer(1, 4))
    S.append(table(["Metric", "Value", "Status"], [[m["name"], m["display"], m["status"]] for m in d["metrics"]], [85, 50, 35]))
    H("Quality Objectives")
    S.append(table(["Objective", "Target"], [list(o) for o in d["objectives"]], [55, 115]))
    H("Quality Factors")
    S.append(table(["Factor", "Why it matters", "Requirements", "Approved"], d["factor_rows"], [38, 92, 20, 20]))
    H("Requirements Analysis")
    S.append(table(["Category", "Total", "Approved", "High/Critical risk"], d["category_rows"], [70, 30, 35, 35]))
    S.append(Spacer(1, 4))
    S.append(Table([[img("requirements"), img("modules")]]))
    H("Requirements Verification Status")
    rs = d["rtm"]["summary"]
    S.append(kv([("Requirements without test cases", rs["without_tests"]), ("Requirements without approval", rs["without_approval"]),
                 ("Requirements with failed tests", rs["with_failed_tests"]), ("Requirements with open defects", rs["with_open_defects"]),
                 ("Requirements with missing links", rs["missing_links"]), ("Unverified requirements", f"{rs['unverified']} of {rs['total']}")]))
    H("Review and Approval Summary")
    S.append(table(["ID", "Type", "Artifact", "Reviewer", "Due", "Decision"],
                   [[r["id"], r["review_type"], r["artifact"], r["reviewer"], r["due_date"], r["decision"] or "Pending"] for r in d["reviews"]],
                   [16, 32, 52, 28, 20, 22]))
    H("Testing Summary")
    S.append(Table([[img("tests"), img("performance")]]))
    S.append(Spacer(1, 4))
    cat_rows = []
    for c in TEST_CATEGORIES:
        ts = [t for t in d["tests"] if t["category"] == c]
        cat_rows.append([c, len(ts), sum(1 for t in ts if t["status"] == "Passed"), sum(1 for t in ts if t["status"] == "Failed"),
                         sum(1 for t in ts if t["status"] in ("Not Run", "In Progress", "Blocked"))])
    S.append(table(["Category", "Total", "Passed", "Failed", "Not complete"], cat_rows, [60, 25, 25, 25, 35]))
    H("Defect Analysis")
    S.append(Table([[img("severity"), img("modules")]]))
    S.append(Spacer(1, 4))
    S.append(table(["ID", "Title", "Category", "Severity", "Status", "Assigned"],
                   [[x["id"], x["title"], x["category"], x["severity"], x["status"], x["assigned_to"]] for x in d["defects"]],
                   [15, 62, 33, 17, 20, 23]))
    H("Quality Metrics")
    S.append(table(["Metric", "Value", "Formula", "Records used", "Status"],
                   [[m["name"], m["display"], m["formula"], m["used"], m["status"]] for m in d["metrics"]], [32, 22, 52, 42, 22]))
    S.append(Spacer(1, 3))
    S.append(Paragraph(f"Overall quality score: <b>{d['score']['score']}</b> ({d['score']['rating']}). {d['score']['formula']}", small))
    H("Traceability Analysis")
    S.append(table(["Req", "Category", "Risk", "Tests", "Result", "Defects", "Approval", "Gaps"],
                   [[x["id"], x["category"], x["risk"], ", ".join(t["id"] for t in x["tests"]) or "-", x["test_result"],
                     ", ".join(t["id"] for t in x["defects"]) or "-", x["approval"], "; ".join(x["gaps"]) or "-"] for x in d["rtm"]["rows"]],
                   [14, 26, 12, 22, 14, 20, 17, 45]))
    H("CAPA Summary")
    S.append(table(["CAPA", "Defect", "Problem", "Owner", "Target", "Status"],
                   [[c["id"], c["defect_id"], c["problem"], c["owner"], c["target_date"], c["status"]] for c in d["capas"]], [16, 16, 70, 28, 20, 20]))
    H("Release Readiness Assessment")
    S.append(Paragraph(f"Recommendation: <b>{d['release']['recommendation']}</b> &nbsp; Readiness: {d['release']['readiness_pct']}% ({d['release']['passed']} passed, {d['release']['failed']} failed, {d['release']['pending']} pending).", body))
    S.append(Spacer(1, 3))
    S.append(table(["Mandatory check", "Status", "Detail"], [[c["name"], c["status"], c["detail"]] for c in d["release"]["checks"]], [55, 18, 97]))
    H("Identified Risks")
    for r in d["risks"]:
        S.append(Paragraph("&bull; " + r.replace("&", "&amp;"), body))
    H("Recommendations")
    for r in d["recommendations"]:
        S.append(Paragraph("&bull; " + r.replace("&", "&amp;"), body))
    H("Final Quality Assessment")
    S.append(Paragraph(d["final"], body))

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Software Quality Management Report", author=proj.get("team_name", ""))
    from reportlab.platypus import Spacer as _S
    doc.build([_S(1, 1)] + S, onFirstPage=cover, onLaterPages=footer)
    return buf.getvalue()


# =============================================================== Excel helpers
def _hdr(ws, row, headers, widths=None):
    thin = Side(style="thin", color="CBD5E1")
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _rows(ws, start, rows):
    thin = Side(style="thin", color="E2E8F0")
    for r, row in enumerate(rows, start):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name="Arial", size=9)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    return start + len(rows)


def _title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color=NAVY)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(name="Arial", italic=True, size=9, color="64748B")


def build_xlsx(d):
    wb = Workbook()
    proj = d["project"]
    ws = wb.active
    ws.title = "Summary"
    _title(ws, f"{PRODUCT} - Software Quality Management Report", f"{proj.get('project_name')} | {proj.get('team_name')} | {proj.get('project_version')} | generated {d['generated']}")
    ws["A4"], ws["B4"] = "Quality score", d["score"]["score"]
    ws["A5"], ws["B5"] = "Rating", d["score"]["rating"]
    ws["A6"], ws["B6"] = "Release recommendation", d["release"]["recommendation"]
    ws["A7"], ws["B7"] = "Release readiness %", d["release"]["readiness_pct"]
    for r in range(4, 8):
        ws[f"A{r}"].font = Font(name="Arial", bold=True)
        ws[f"B{r}"].font = Font(name="Arial", bold=True, color=BLUE, size=12)
    ws["A9"] = "Executive summary"
    ws["A9"].font = Font(name="Arial", bold=True, color=NAVY)
    ws["A10"] = d["exec_summary"]
    ws.merge_cells("A10:F13")
    ws["A10"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A10"].font = Font(name="Arial", size=10)
    ws["A15"] = "Team"
    ws["A15"].font = Font(name="Arial", bold=True, color=NAVY)
    _hdr(ws, 16, ["Name", "Role", "Email"], [34, 28, 30, 18, 18, 18])
    ws.freeze_panes = None
    _rows(ws, 17, [[t["name"], t["role"], t["email"] or ""] for t in d["team"]])
    ws.cell(row=17 + len(d["team"]) + 1, column=1, value=DISCLAIMER).font = Font(name="Arial", italic=True, size=8, color="64748B")

    ws = wb.create_sheet("Metrics")
    _title(ws, "Quality metrics (calculated from database records)")
    _hdr(ws, 3, ["Metric", "Current value", "Unit", "Calculation formula", "Records used", "Interpretation", "Quality status"], [32, 14, 18, 52, 40, 60, 14])
    _rows(ws, 4, [[m["name"], m["value"] if m["value"] is not None else "Not measurable", m["unit"], m["formula"], m["used"], m["interpretation"], m["status"]] for m in d["metrics"]])
    fills = {"good": "D1FAE5", "warning": "FEF3C7", "critical": "FEE2E2"}
    for r in range(4, 4 + len(d["metrics"])):
        st = ws.cell(row=r, column=7).value
        if st in fills:
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor=fills[st])
    ws.cell(row=5 + len(d["metrics"]), column=1, value="Overall quality score formula:").font = Font(name="Arial", bold=True, size=9)
    ws.cell(row=6 + len(d["metrics"]), column=1, value=d["score"]["formula"]).font = Font(name="Arial", size=9)

    ws = wb.create_sheet("Requirements")
    _hdr(ws, 1, ["ID", "Title", "Category", "Type", "Priority", "Risk", "Owner", "Status", "Acceptance criteria", "Design ref", "Implementation ref", "Need", "Approved by", "Approved on"], [10, 40, 24, 14, 10, 10, 20, 13, 50, 28, 26, 9, 18, 12])
    _rows(ws, 2, [[r["id"], r["title"], r["category"], r["req_type"], r["priority"], r["risk"], r["owner"], r["status"], r["acceptance_criteria"], r["design_ref"], r["impl_ref"], r["need_id"], r["approved_by"], r["approved_on"]] for r in d["reqs"]])

    ws = wb.create_sheet("Reviews")
    _hdr(ws, 1, ["ID", "Type", "Title", "Artifact", "Version", "Reviewer", "Review date", "Due date", "Findings", "Finding severity", "Decision", "Approval status"], [10, 22, 44, 36, 9, 20, 12, 12, 44, 12, 20, 18])
    _rows(ws, 2, [[r["id"], r["review_type"], r["title"], r["artifact"], r["artifact_version"], r["reviewer"], r["review_date"], r["due_date"], r["findings"], r["finding_severity"], r["decision"] or "", r["approval_status"]] for r in d["reviews"]])

    ws = wb.create_sheet("Test Cases")
    _hdr(ws, 1, ["ID", "Scenario", "Requirement", "Category", "Expected result", "Actual result", "Tester", "Execution date", "Status", "Evidence", "Linked defect"], [10, 46, 12, 24, 40, 40, 20, 13, 12, 28, 14])
    _rows(ws, 2, [[t["id"], t["scenario"], t["requirement_id"], t["category"], t["expected"], t["actual"], t["tester"], t["exec_date"], t["status"], t["evidence"], t["defect_ids"] or ""] for t in d["tests"]])

    ws = wb.create_sheet("Defects")
    _hdr(ws, 1, ["ID", "Title", "Category", "Severity", "Priority", "Status", "Assigned", "Reported", "Requirement", "Test case", "Resolution", "Verification", "Reopen count"], [10, 46, 28, 10, 10, 12, 20, 12, 12, 10, 44, 12, 8])
    _rows(ws, 2, [[x["id"], x["title"], x["category"], x["severity"], x["priority"], x["status"], x["assigned_to"], x["date_reported"], x["requirement_id"], x["test_case_id"], x["resolution"], x["verification_result"], x["reopen_count"]] for x in d["defects"]])

    ws = wb.create_sheet("RTM")
    _rtm_sheet(ws, d["rtm"])

    ws = wb.create_sheet("CAPA")
    _hdr(ws, 1, ["ID", "Defect", "Problem", "Root cause", "Corrective action", "Preventive action", "Owner", "Target", "Status", "Effectiveness review", "Closure approved by"], [10, 10, 44, 40, 40, 40, 20, 12, 14, 44, 18])
    _rows(ws, 2, [[c["id"], c["defect_id"], c["problem"], c["root_cause"], c["corrective"], c["preventive"], c["owner"], c["target_date"], c["status"], c["effectiveness_review"], c["closure_approved_by"]] for c in d["capas"]])

    ws = wb.create_sheet("Release Gate")
    _title(ws, f"Release readiness: {d['release']['recommendation']} ({d['release']['readiness_pct']}%)")
    _hdr(ws, 3, ["Mandatory check", "Status", "Detail"], [46, 12, 100])
    _rows(ws, 4, [[c["name"], c["status"], c["detail"]] for c in d["release"]["checks"]])
    pf = {"Passed": "D1FAE5", "Failed": "FEE2E2", "Pending": "FEF3C7"}
    for r in range(4, 4 + len(d["release"]["checks"])):
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=pf[ws.cell(row=r, column=2).value])

    ws = wb.create_sheet("Risks & Recommendations")
    _hdr(ws, 1, ["Type", "Statement"], [20, 140])
    rows = [["Risk", r] for r in d["risks"]] + [["Recommendation", r] for r in d["recommendations"]] + [["Final assessment", d["final"]]]
    _rows(ws, 2, rows)

    ws = wb.create_sheet("Documents")
    _hdr(ws, 1, ["ID", "Title", "Type", "Version", "Owner", "Created", "Last updated", "Approval status"], [10, 52, 12, 9, 22, 12, 12, 16])
    _rows(ws, 2, [[x["id"], x["title"], x["doc_type"], x["version"], x["owner"], x["created_on"], x["updated_on"], x["approval_status"]] for x in d["docs"]])

    # chart data + native charts
    ws = wb.create_sheet("Charts")
    ch = d["charts"]
    _title(ws, "Charts (data from database)")
    ws["A3"], ws["B3"] = "Severity", "Defects"
    for i, (l, v) in enumerate(zip(ch["severity"]["labels"], ch["severity"]["values"]), 4):
        ws.cell(row=i, column=1, value=l)
        ws.cell(row=i, column=2, value=v)
    ws["D3"], ws["E3"] = "Test status", "Tests"
    for i, (l, v) in enumerate(zip(ch["tests"]["labels"], ch["tests"]["values"]), 4):
        ws.cell(row=i, column=4, value=l)
        ws.cell(row=i, column=5, value=v)
    ws["G3"], ws["H3"] = "Requirement status", "Requirements"
    for i, (l, v) in enumerate(zip(ch["requirements"]["labels"], ch["requirements"]["values"]), 4):
        ws.cell(row=i, column=7, value=l)
        ws.cell(row=i, column=8, value=v)
    ws["J3"], ws["K3"] = "Module", "Defects"
    for i, (l, v) in enumerate(zip(ch["modules"]["labels"], ch["modules"]["values"]), 4):
        ws.cell(row=i, column=10, value=l)
        ws.cell(row=i, column=11, value=v)
    for c in ("A3", "B3", "D3", "E3", "G3", "H3", "J3", "K3"):
        ws[c].font = Font(name="Arial", bold=True)
    for col, w in zip("ABCDEFGHIJK", [14, 10, 3, 14, 10, 3, 20, 14, 3, 28, 10]):
        ws.column_dimensions[col].width = w
    b = BarChart()
    b.title = "Defects by severity"
    b.add_data(Reference(ws, min_col=2, min_row=3, max_row=3 + len(ch["severity"]["labels"])), titles_from_data=True)
    b.set_categories(Reference(ws, min_col=1, min_row=4, max_row=3 + len(ch["severity"]["labels"])))
    ws.add_chart(b, "A14")
    p = PieChart()
    p.title = "Test execution results"
    p.add_data(Reference(ws, min_col=5, min_row=3, max_row=3 + len(ch["tests"]["labels"])), titles_from_data=True)
    p.set_categories(Reference(ws, min_col=4, min_row=4, max_row=3 + len(ch["tests"]["labels"])))
    ws.add_chart(p, "G14")
    b2 = BarChart()
    b2.title = "Requirements by status"
    b2.add_data(Reference(ws, min_col=8, min_row=3, max_row=3 + len(ch["requirements"]["labels"])), titles_from_data=True)
    b2.set_categories(Reference(ws, min_col=7, min_row=4, max_row=3 + len(ch["requirements"]["labels"])))
    ws.add_chart(b2, "A31")
    if ch["modules"]["labels"]:
        b3 = BarChart()
        b3.type = "bar"
        b3.title = "Defects by hospital module"
        b3.add_data(Reference(ws, min_col=11, min_row=3, max_row=3 + len(ch["modules"]["labels"])), titles_from_data=True)
        b3.set_categories(Reference(ws, min_col=10, min_row=4, max_row=3 + len(ch["modules"]["labels"])))
        ws.add_chart(b3, "G31")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _rtm_sheet(ws, tr):
    _hdr(ws, 1, ["Requirement ID", "Requirement description", "Category", "Priority", "Risk", "Stakeholder need", "Design reference",
                 "Implementation reference", "Test case ID(s)", "Test result", "Related defect(s)", "CAPA", "Approval status", "Gaps"],
         [12, 50, 24, 10, 10, 30, 30, 26, 22, 12, 22, 16, 14, 40])
    _rows(ws, 2, [[x["id"], x["title"] + " - " + x["description"], x["category"], x["priority"], x["risk"],
                   f"{x['need_id'] or ''} {x['need_title'] or ''}".strip(), x["design_ref"] or "", x["impl_ref"] or "",
                   ", ".join(t["id"] for t in x["tests"]), x["test_result"],
                   ", ".join(f"{t['id']} ({t['status']})" for t in x["defects"]), ", ".join(c["id"] for c in x["capas"]),
                   x["approval"], "; ".join(x["gaps"])] for x in tr["rows"]])
    ws.auto_filter.ref = f"A1:N{1 + len(tr['rows'])}"


def build_rtm_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "RTM"
    tr = M.rtm()
    _rtm_sheet(ws, tr)
    ws2 = wb.create_sheet("Gaps summary")
    s = tr["summary"]
    _hdr(ws2, 1, ["Gap", "Count"], [48, 10])
    _rows(ws2, 2, [["Requirements without test cases", s["without_tests"]], ["Requirements without approval", s["without_approval"]],
                   ["Requirements with failed tests", s["with_failed_tests"]], ["Requirements with open defects", s["with_open_defects"]],
                   ["Requirements with missing traceability links", s["missing_links"]], ["Unverified requirements", s["unverified"]],
                   ["Test cases without a requirement", s["orphan_tests"]], ["Defects without a requirement", s["orphan_defects"]]])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# =============================================================== CSV
def build_csv(d):
    out = io.StringIO()
    w = csv.writer(out)

    def section(title, head, rows):
        w.writerow([f"## {title}"])
        w.writerow(head)
        w.writerows(rows)
        w.writerow([])

    w.writerow([f"{PRODUCT} quality data export", d["project"].get("project_name"), d["project"].get("team_name"), d["generated"]])
    w.writerow([])
    section("Metrics", ["Metric", "Value", "Unit", "Formula", "Records used", "Status"], [[m["name"], m["value"], m["unit"], m["formula"], m["used"], m["status"]] for m in d["metrics"]])
    section("Requirements", ["ID", "Title", "Category", "Priority", "Risk", "Owner", "Status"], [[r["id"], r["title"], r["category"], r["priority"], r["risk"], r["owner"], r["status"]] for r in d["reqs"]])
    section("Test cases", ["ID", "Scenario", "Requirement", "Category", "Status", "Tester", "Execution date"], [[t["id"], t["scenario"], t["requirement_id"], t["category"], t["status"], t["tester"], t["exec_date"]] for t in d["tests"]])
    section("Defects", ["ID", "Title", "Category", "Severity", "Status", "Assigned", "Requirement", "Test case"], [[x["id"], x["title"], x["category"], x["severity"], x["status"], x["assigned_to"], x["requirement_id"], x["test_case_id"]] for x in d["defects"]])
    section("Reviews", ["ID", "Type", "Title", "Reviewer", "Due", "Decision"], [[r["id"], r["review_type"], r["title"], r["reviewer"], r["due_date"], r["decision"]] for r in d["reviews"]])
    section("CAPA", ["ID", "Defect", "Status", "Owner", "Target"], [[c["id"], c["defect_id"], c["status"], c["owner"], c["target_date"]] for c in d["capas"]])
    section("Release gate", ["Check", "Status", "Detail"], [[c["name"], c["status"], c["detail"]] for c in d["release"]["checks"]])
    return out.getvalue().encode("utf-8-sig")


def table_csv(headers, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    w.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def rtm_csv():
    tr = M.rtm()
    return table_csv(["Requirement ID", "Requirement", "Category", "Priority", "Risk", "Need", "Design ref", "Implementation ref", "Tests", "Test result", "Defects", "CAPA", "Approval", "Gaps"],
                     [[x["id"], x["title"], x["category"], x["priority"], x["risk"], x["need_id"], x["design_ref"], x["impl_ref"],
                       ", ".join(t["id"] for t in x["tests"]), x["test_result"], ", ".join(t["id"] for t in x["defects"]),
                       ", ".join(c["id"] for c in x["capas"]), x["approval"], "; ".join(x["gaps"])] for x in tr["rows"]])


# =============================================================== printable HTML report
def build_print_html(d):
    import base64
    from html import escape as e

    def img(kind):
        return "data:image/png;base64," + base64.b64encode(chart_png(kind, d).read()).decode()

    def tbl(head, rows):
        return "<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>" + "".join(
            "<tr>" + "".join(f"<td>{e(str(c if c is not None else ''))}</td>" for c in r) + "</tr>" for r in rows) + "</table>"

    p = d["project"]
    secs = [
        ("Project Information", tbl(["Field", "Value"], [["Project", p.get("project_name")], ["Team", p.get("team_name")], ["Release", p.get("project_version")], ["Organisation", p.get("organisation")]])),
        ("Team Information", tbl(["Name", "Role"], [[t["name"], t["role"]] for t in d["team"]])),
        ("Executive Summary", f"<p>{e(d['exec_summary'])}</p>"),
        ("Quality Objectives", tbl(["Objective", "Target"], [list(o) for o in d["objectives"]])),
        ("Quality Factors", tbl(["Factor", "Why it matters", "Reqs", "Approved"], d["factor_rows"])),
        ("Requirements Analysis", tbl(["Category", "Total", "Approved", "High/Critical"], d["category_rows"]) + f"<img src='{img('requirements')}'>"),
        ("Review and Approval Summary", tbl(["ID", "Type", "Reviewer", "Decision"], [[r["id"], r["review_type"], r["reviewer"], r["decision"] or "Pending"] for r in d["reviews"]])),
        ("Testing Summary", f"<img src='{img('tests')}'>"),
        ("Defect Analysis", f"<img src='{img('severity')}'><img src='{img('modules')}'>" + tbl(["ID", "Title", "Severity", "Status"], [[x["id"], x["title"], x["severity"], x["status"]] for x in d["defects"]])),
        ("Quality Metrics", tbl(["Metric", "Value", "Formula", "Records", "Status"], [[m["name"], m["display"], m["formula"], m["used"], m["status"]] for m in d["metrics"]]) + f"<img src='{img('performance')}'>"),
        ("Traceability Analysis", tbl(["Req", "Tests", "Result", "Defects", "Approval", "Gaps"], [[x["id"], ", ".join(t["id"] for t in x["tests"]), x["test_result"], ", ".join(t["id"] for t in x["defects"]), x["approval"], "; ".join(x["gaps"])] for x in d["rtm"]["rows"]])),
        ("CAPA Summary", tbl(["CAPA", "Defect", "Status", "Owner"], [[c["id"], c["defect_id"], c["status"], c["owner"]] for c in d["capas"]])),
        ("Release Readiness Assessment", f"<p><b>{e(d['release']['recommendation'])}</b> - {d['release']['readiness_pct']}%</p>" + tbl(["Check", "Status", "Detail"], [[c["name"], c["status"], c["detail"]] for c in d["release"]["checks"]])),
        ("Identified Risks", "<ul>" + "".join(f"<li>{e(r)}</li>" for r in d["risks"]) + "</ul>"),
        ("Recommendations", "<ul>" + "".join(f"<li>{e(r)}</li>" for r in d["recommendations"]) + "</ul>"),
        ("Final Quality Assessment", f"<p>{e(d['final'])}</p>"),
    ]
    body = "".join(f"<h2>{i}. {e(t)}</h2>{c}" for i, (t, c) in enumerate(secs, 1))
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Quality Management Report</title><style>"
            "body{font-family:Segoe UI,Arial,sans-serif;color:#14243A;margin:30px;font-size:12px}h1{color:#14243A}h2{color:#2563EB;border-bottom:1px solid #CBD5E1;padding-bottom:4px;margin-top:28px}"
            "table{border-collapse:collapse;width:100%;margin:8px 0}th{background:#14243A;color:#fff;text-align:left}td,th{border:1px solid #CBD5E1;padding:4px 6px;vertical-align:top}"
            "img{max-width:48%;margin:6px}.cover{background:#14243A;color:#fff;padding:40px;border-radius:8px}@media print{h2{page-break-after:avoid}}</style></head><body>"
            f"<div class='cover'><div>{PRODUCT}</div><h1 style='color:#fff'>Software Quality Management Report</h1><div>{e(p.get('project_name',''))} | {e(p.get('team_name',''))}</div>"
            f"<div>Quality score {d['score']['score']} ({e(d['score']['rating'])}) | {e(d['generated'])}</div></div>{body}"
            f"<p style='color:#64748B'>{e(DISCLAIMER)}</p><script>window.onload=function(){{window.print()}}</script></body></html>")


# controlled documents are generated in docs_content.py (8 mandatory documents, Word + Excel)
from docs_content import build_doc_docx, build_doc_xlsx, doc_meta  # noqa: E402,F401
