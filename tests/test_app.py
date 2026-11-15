"""Automated tests for HOSPITAL QUALITY OS. Run:  python -m unittest discover -s tests -v"""
import io
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

_tmp = tempfile.mkdtemp()
db.DB_PATH = os.path.join(_tmp, "test.db")
import app as A  # noqa: E402
import metrics as M  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        db.init_db(force=True)
        self.c = A.app.test_client()

    def post(self, url, body=None):
        return self.c.post(url, json=body or {})

    def put(self, url, body):
        return self.c.put(url, json=body)


class SeedTests(Base):
    def test_minimum_seed_volumes(self):
        n = lambda t: db.query(f"SELECT COUNT(*) n FROM {t}")[0]["n"]
        self.assertGreaterEqual(n("requirements"), 20)
        self.assertGreaterEqual(n("test_cases"), 20)
        self.assertGreaterEqual(n("defects"), 10)
        self.assertGreaterEqual(n("reviews"), 8)
        self.assertGreaterEqual(n("capas"), 5)
        self.assertEqual(n("documents"), 8)

    def test_all_requirement_categories_present(self):
        from domain import REQ_CATEGORIES
        cats = {r["category"] for r in db.query("SELECT category FROM requirements")}
        self.assertEqual(cats, set(REQ_CATEGORIES))

    def test_no_logistics_content_in_data(self):
        blob = " ".join(str(v) for t in ("requirements", "test_cases", "defects", "capas", "reviews", "documents")
                        for row in db.query(f"SELECT * FROM {t}") for v in row.values()).lower()
        for word in ("logistic", "delivery", "driver", "dispatch", "shipment"):
            self.assertNotIn(word, blob)

    def test_foreign_keys_consistent(self):
        self.assertEqual(db.query("PRAGMA foreign_key_check"), [])


class MetricTests(Base):
    def test_dashboard_matches_database(self):
        k = self.c.get("/api/dashboard").get_json()["kpis"]
        self.assertEqual(k["total_requirements"], db.query("SELECT COUNT(*) n FROM requirements")[0]["n"])
        self.assertEqual(k["passed_tests"], db.query("SELECT COUNT(*) n FROM test_cases WHERE status='Passed'")[0]["n"])
        self.assertEqual(k["failed_tests"], db.query("SELECT COUNT(*) n FROM test_cases WHERE status='Failed'")[0]["n"])

    def test_pass_rate_formula(self):
        p = db.query("SELECT COUNT(*) n FROM test_cases WHERE status='Passed'")[0]["n"]
        f = db.query("SELECT COUNT(*) n FROM test_cases WHERE status='Failed'")[0]["n"]
        m = {x["key"]: x for x in M.metrics()}
        self.assertEqual(m["pass_rate"]["value"], round(100 * p / (p + f), 1))

    def test_metrics_change_when_data_changes(self):
        before = {x["key"]: x["value"] for x in M.metrics()}["pass_rate"]
        self.put("/api/tests/TC-013", {"status": "Passed", "actual": "ok", "tester": "Team2 Test Manager"})
        after = {x["key"]: x["value"] for x in M.metrics()}["pass_rate"]
        self.assertGreater(after, before)

    def test_twelve_metrics_with_required_fields(self):
        ms = M.metrics()
        self.assertEqual(len(ms), 12)
        for m in ms:
            for f in ("name", "formula", "used", "interpretation", "status", "display"):
                self.assertTrue(m[f] != "", f)

    def test_trend_not_invented_with_single_month(self):
        db.execute("UPDATE defects SET date_reported='2026-11-01', closed_on=NULL")
        self.assertFalse(M.chart_data()["trend"]["available"])


class RequirementRules(Base):
    def new_req(self, **kw):
        body = dict(title="T", description="D", category="Billing Management", priority="High", risk="High",
                    owner="Team2 Developer A", status="Draft", acceptance_criteria="AC", req_type="Functional")
        body.update(kw)
        return self.post("/api/requirements", body)

    def test_create_and_validation(self):
        r = self.new_req()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["id"], "REQ-025")
        self.assertEqual(self.new_req(title="").status_code, 422)
        self.assertEqual(self.new_req(category="Logistics").status_code, 422)

    def test_cannot_approve_without_review(self):
        rid = self.new_req().get_json()["id"]
        r = self.put(f"/api/requirements/{rid}", {"status": "Approved"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("review", r.get_json()["error"].lower())

    def test_approve_after_review_and_withdrawal_downgrades(self):
        rid = self.new_req().get_json()["id"]
        rv = self.post("/api/reviews", dict(review_type="Requirement review", title="R", artifact="SRS", reviewer="Team2 Reviewer",
                                            decision="Approved", requirement_ids=[rid],
                                            checklist={i: True for i in db.REVIEW_CHECKLISTS["Requirement review"]}))
        self.assertEqual(rv.status_code, 201, rv.get_json())
        self.assertEqual(self.put(f"/api/requirements/{rid}", {"status": "Approved"}).status_code, 200)
        self.assertEqual(self.c.get(f"/api/requirements/{rid}").get_json()["approved_by"], "Team2 Reviewer")
        self.c.delete(f"/api/reviews/{rv.get_json()['id']}")
        self.assertEqual(self.c.get(f"/api/requirements/{rid}").get_json()["status"], "Under Review")

    def test_verified_requires_passed_tests(self):
        r = self.put("/api/requirements/REQ-004", {"status": "Verified"})  # TC-004 failed
        self.assertEqual(r.status_code, 422)

    def test_search_filter_sort(self):
        r = self.c.get("/api/requirements?q=billing&category=Billing%20Management&sort=risk").get_json()
        self.assertTrue(r and all(x["category"] == "Billing Management" for x in r))

    def test_delete_keeps_links_clean(self):
        self.assertEqual(self.c.delete("/api/requirements/REQ-009").status_code, 200)
        self.assertIsNone(self.c.get("/api/tests/TC-006").get_json()["requirement_id"])
        self.assertEqual(self.c.delete("/api/requirements/REQ-009").status_code, 404)


class ReviewRules(Base):
    def test_decision_needs_reviewer(self):
        r = self.post("/api/reviews", dict(review_type="Code review", title="x", artifact="a", decision="Rework required", comments="c"))
        self.assertEqual(r.status_code, 422)

    def test_approved_needs_full_checklist(self):
        r = self.post("/api/reviews", dict(review_type="Code review", title="x", artifact="a", reviewer="Team2 QA Lead", decision="Approved", checklist={}))
        self.assertEqual(r.status_code, 422)
        self.assertIn("checklist", r.get_json()["error"].lower())

    def test_rework_needs_comments_and_status_derived(self):
        bad = self.post("/api/reviews", dict(review_type="Code review", title="x", artifact="a", reviewer="Team2 QA Lead", decision="Rework required"))
        self.assertEqual(bad.status_code, 422)
        ok = self.post("/api/reviews", dict(review_type="Code review", title="x", artifact="a", reviewer="Team2 QA Lead", decision="Rework required", comments="fix"))
        self.assertEqual(ok.get_json()["approval_status"], "Rework required")

    def test_pending_review_has_pending_status(self):
        r = self.post("/api/reviews", dict(review_type="Design review", title="x", artifact="a")).get_json()
        self.assertEqual(r["approval_status"], "Pending")


class TestAndDefectRules(Base):
    def test_executing_requires_actual_and_tester(self):
        r = self.put("/api/tests/TC-013", {"status": "Failed"})
        self.assertEqual(r.status_code, 422)

    def test_failed_test_creates_linked_defect(self):
        self.put("/api/tests/TC-013", {"status": "Failed", "actual": "slots remained", "tester": "Team2 Test Manager"})
        r = self.post("/api/tests/TC-013/create-defect", {"category": "Doctor record errors", "severity": "Medium"})
        self.assertEqual(r.status_code, 201)
        d = r.get_json()
        self.assertEqual(d["test_case_id"], "TC-013")
        self.assertEqual(d["requirement_id"], "REQ-006")
        self.assertIn(d["id"], self.c.get("/api/tests/TC-013").get_json()["defect_ids"])

    def test_cannot_create_defect_from_passed_test(self):
        self.assertEqual(self.post("/api/tests/TC-001/create-defect").status_code, 422)

    def test_patient_data_critical_gets_highest_priority(self):
        r = self.post("/api/defects", dict(title="x", description="d", category="Prescription errors", severity="High", priority="Low"))
        self.assertEqual(r.get_json()["priority"], "Highest")
        self.assertTrue(r.get_json()["patient_impact"])

    def test_close_needs_resolution_and_verification(self):
        self.assertEqual(self.put("/api/defects/DEF-007", {"status": "Closed"}).status_code, 422)
        self.assertEqual(self.put("/api/defects/DEF-007", {"status": "Closed", "resolution": "indexed"}).status_code, 422)
        ok = self.put("/api/defects/DEF-007", {"status": "Closed", "resolution": "indexed", "verification_result": "Passed"})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.get_json()["closed_on"])

    def test_reopen_increments_counter(self):
        before = self.c.get("/api/defects/DEF-004").get_json()["reopen_count"]
        r = self.put("/api/defects/DEF-004", {"status": "Reopened"}).get_json()
        self.assertEqual(r["reopen_count"], before + 1)
        self.assertIsNone(r["closed_on"])

    def test_assign_requires_developer(self):
        new = self.post("/api/defects", dict(title="x", description="d", category="Application crashes", severity="Low")).get_json()
        self.assertEqual(self.put(f"/api/defects/{new['id']}", {"status": "Assigned"}).status_code, 422)
        self.assertEqual(self.put(f"/api/defects/{new['id']}", {"status": "Assigned", "assigned_to": "Team2 Developer B"}).status_code, 200)


class CapaRules(Base):
    def test_cannot_close_without_effectiveness(self):
        r = self.put("/api/capas/CAPA-004", {"status": "Closed"})
        self.assertEqual(r.status_code, 422)

    def test_can_close_with_full_evidence_and_resolved_defect(self):
        r = self.put("/api/capas/CAPA-004", {"status": "Closed", "verification_evidence": "TC-008 retest", "effectiveness_review": "no recurrence", "closure_approved_by": "Team2 QA Lead"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(r.get_json()["closed_on"])

    def test_cannot_close_while_defect_open(self):
        r = self.put("/api/capas/CAPA-001", {"status": "Closed", "verification_evidence": "x", "effectiveness_review": "y", "closure_approved_by": "Team2 QA Lead"})
        self.assertEqual(r.status_code, 422)

    def test_create_capa_from_defect_once(self):
        self.assertEqual(self.post("/api/defects/DEF-007/create-capa").status_code, 201)
        self.assertEqual(self.post("/api/defects/DEF-007/create-capa").status_code, 422)


class ReleaseRules(Base):
    def test_seed_is_no_go_and_go_is_blocked(self):
        r = self.c.get("/api/release").get_json()
        self.assertEqual(r["recommendation"], "NO-GO")
        res = self.post("/api/release/decision", {"decision": "GO", "rationale": "ship"})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.post("/api/release/decision", {"decision": "CONDITIONAL GO", "rationale": "x", "conditions": "y"}).status_code, 409)

    def test_no_go_can_be_recorded_with_rationale(self):
        self.assertEqual(self.post("/api/release/decision", {"decision": "NO-GO"}).status_code, 422)
        self.assertEqual(self.post("/api/release/decision", {"decision": "NO-GO", "rationale": "critical defects"}).status_code, 201)
        self.assertEqual(len(self.c.get("/api/release").get_json()["decisions"]), 1)

    def test_manual_check_needs_evidence(self):
        self.assertEqual(self.post("/api/release/manual/rollback_plan", {"confirmed": True}).status_code, 422)
        self.assertEqual(self.post("/api/release/manual/rollback_plan", {"confirmed": True, "note": "RB-PLAN-1"}).status_code, 200)

    def test_go_allowed_when_every_check_passes(self):
        """Drive the demo data into a fully ready state through the real workflows."""
        # tests: execute everything and pass
        for t in db.query("SELECT id FROM test_cases WHERE status!='Passed'"):
            self.put(f"/api/tests/{t['id']}", {"status": "Passed", "actual": "ok", "tester": "Team2 Test Manager"})
        # defects: close all
        for d in db.query("SELECT id FROM defects WHERE status!='Closed'"):
            r = self.put(f"/api/defects/{d['id']}", {"status": "Closed", "resolution": "fixed", "verification_result": "Passed", "assigned_to": "Team2 Developer A"})
            self.assertEqual(r.status_code, 200, r.get_json())
        # requirements: review all, then approve
        ids = [r["id"] for r in db.query("SELECT id FROM requirements WHERE status IN ('Draft','Under Review')")]
        chk = {i: True for i in db.REVIEW_CHECKLISTS["Requirement review"]}
        self.assertEqual(self.post("/api/reviews", dict(review_type="Requirement review", title="Final", artifact="SRS", reviewer="Team2 Reviewer", decision="Approved", requirement_ids=ids, checklist=chk)).status_code, 201)
        for i in ids:
            self.put(f"/api/requirements/{i}", {"status": "Approved", "design_ref": "DD-X", "impl_ref": "Impl", "need_id": "SN-01"})
        for r in db.query("SELECT id FROM requirements WHERE design_ref IS NULL OR design_ref=''"):
            self.put(f"/api/requirements/{r['id']}", {"design_ref": "DD-X"})
        # tests for requirements without any
        for r in db.query("SELECT id FROM requirements WHERE id NOT IN (SELECT requirement_id FROM test_cases WHERE requirement_id IS NOT NULL)"):
            self.post("/api/tests", dict(scenario="s", requirement_id=r["id"], category="System Testing", steps="s", expected="e", actual="ok", tester="Team2 Test Manager", status="Passed"))
        # reviews: security + release approved
        for rid, typ in (("REV-007", "Security review"), ("REV-012", "Release review"), ("REV-011", "Documentation review")):
            r = self.put(f"/api/reviews/{rid}", dict(decision="Approved", reviewer="Team2 Reviewer", finding_severity="Low", checklist={i: True for i in db.REVIEW_CHECKLISTS[typ]}))
            self.assertEqual(r.status_code, 200, r.get_json())
        # documents approved
        for d in db.query("SELECT id FROM documents WHERE approval_status!='Approved'"):
            self.put(f"/api/documents/{d['id']}", {"approval_status": "Approved"})
        # manual confirmations
        self.post("/api/release/manual/backup_recovery", {"confirmed": True, "note": "BK-LOG-7"})
        self.post("/api/release/manual/rollback_plan", {"confirmed": True, "note": "RB-PLAN-1"})
        s = self.c.get("/api/release").get_json()
        failing = [(c["name"], c["detail"]) for c in s["checks"] if c["status"] != "Passed"]
        self.assertEqual(failing, [])
        self.assertEqual(s["recommendation"], "GO")
        self.assertEqual(self.post("/api/release/decision", {"decision": "GO", "rationale": "all gates passed"}).status_code, 201)


class TraceabilityTests(Base):
    def test_gaps_detected(self):
        t = self.c.get("/api/rtm").get_json()
        rows = {r["id"]: r for r in t["rows"]}
        self.assertIn("No test case", rows["REQ-012"]["gaps"])
        self.assertIn("Failed test", rows["REQ-002"]["gaps"])
        self.assertIn("No approval", rows["REQ-014"]["gaps"])
        self.assertEqual(t["summary"]["without_tests"], sum(1 for r in t["rows"] if "No test case" in r["gaps"]))

    def test_chain_to_capa(self):
        r = {x["id"]: x for x in self.c.get("/api/rtm").get_json()["rows"]}["REQ-007"]
        self.assertEqual([c["id"] for c in r["capas"]], ["CAPA-002"])


class ExportTests(Base):
    def test_pdf_xlsx_csv_print(self):
        pdf = self.c.get("/api/report/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        x = self.c.get("/api/report/xlsx")
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(x.data))
        for sheet in ("Summary", "Metrics", "Requirements", "Test Cases", "Defects", "RTM", "CAPA", "Release Gate", "Charts"):
            self.assertIn(sheet, wb.sheetnames)
        self.assertEqual(wb["Requirements"].max_row - 1, 24)
        self.assertIn(b"Test Pass Rate", self.c.get("/api/report/csv").data)
        self.assertIn(b"Quality Management Report", self.c.get("/api/report/print").data)

    def test_report_reflects_new_data(self):
        self.post("/api/requirements", dict(title="Zebra unique requirement", description="d", category="Performance", priority="Low", risk="Low", owner="Team2 Architect", acceptance_criteria="a"))
        wb = __import__("openpyxl").load_workbook(io.BytesIO(self.c.get("/api/report/xlsx").data))
        titles = [c.value for c in wb["Requirements"]["B"]]
        self.assertIn("Zebra unique requirement", titles)

    def test_rtm_and_entity_exports(self):
        self.assertEqual(self.c.get("/api/rtm/export.xlsx").status_code, 200)
        self.assertIn(b"Requirement ID", self.c.get("/api/rtm/export.csv").data)
        self.assertEqual(self.c.get("/api/export/requirements.csv?category=Billing%20Management").status_code, 200)
        self.assertEqual(self.c.get("/api/export/defects.xlsx").status_code, 200)

    def test_all_documents_download_as_word_and_excel(self):
        from docx import Document
        from openpyxl import load_workbook
        for i in range(1, 9):
            w = self.c.get(f"/api/documents/DOC-{i:03d}/download/word")
            self.assertEqual(w.status_code, 200)
            self.assertTrue(Document(io.BytesIO(w.data)).paragraphs)
            e = self.c.get(f"/api/documents/DOC-{i:03d}/download/excel")
            self.assertEqual(e.status_code, 200)
            self.assertTrue(load_workbook(io.BytesIO(e.data)).sheetnames)
        self.assertEqual(self.c.get("/api/handbook.docx").status_code, 200)

    def test_release_checklist_document_is_live(self):
        from docx import Document
        d = Document(io.BytesIO(self.c.get("/api/documents/DOC-007/download/word").data))
        text = " ".join(c.text for t in d.tables for r in t.rows for c in r.cells)
        self.assertIn("Critical defect verification", text)
        self.assertIn("Failed", text)


class DocumentLibraryTests(Base):
    TITLES = ["Project Quality Plan", "Requirements Development & Management Procedure", "Requirement Review Checklist", "Change Request Form",
              "Requirements Traceability Matrix", "Peer Review Procedure", "Release Readiness Checklist", "CAPA Procedure"]

    def docx_text(self, doc_id):
        from docx import Document
        d = Document(io.BytesIO(self.c.get(f"/api/documents/{doc_id}/download/word").data))
        return " ".join(p.text for p in d.paragraphs) + " " + " ".join(c.text for t in d.tables for r in t.rows for c in r.cells)

    def test_exactly_the_eight_mandatory_documents_in_order(self):
        docs = self.c.get("/api/documents").get_json()
        self.assertEqual([d["title"] for d in docs], self.TITLES)
        for d in docs:
            for f in ("id", "title", "version", "owner", "created_on", "review_date", "approval_status"):
                self.assertTrue(d[f], f)

    def test_every_required_section_is_in_the_word_file(self):
        required = {
            "DOC-001": ["Project scope", "Quality objectives", "Quality factors", "Quality responsibilities", "Quality standards and procedures", "Quality assurance activities", "Quality control activities", "Quality gates", "Quality metrics", "Risk management", "Approval responsibilities"],
            "DOC-002": ["Requirement identification", "Requirement classification", "Requirement analysis", "Requirement documentation", "Requirement validation", "Requirement baseline", "Requirement change management", "Requirement traceability", "Approval workflow"],
            "DOC-003": ["Requirement completeness", "Requirement correctness", "Requirement consistency", "Requirement feasibility", "Requirement testability", "Data accuracy considerations", "Security and privacy considerations", "Performance requirements", "Acceptance criteria", "Reviewer approval"],
            "DOC-004": ["Change request ID", "Change title", "Change description", "Reason for change", "Affected hospital software module", "Impact analysis", "Risk assessment", "Cost and time impact", "Recommendation", "Approval decision", "Implementation status", "Closure details"],
            "DOC-006": ["Review objectives", "Review scope", "Review participants", "Entry criteria", "Review preparation", "Review checklist", "Review findings", "Defect classification", "Rework procedure", "Exit criteria", "Approval and sign-off"],
            "DOC-007": ["Requirements approval", "Test execution completion", "Test pass rate", "Critical defect verification", "High-risk defect assessment", "Security testing", "Database integrity verification", "Documentation approval", "Backup and recovery readiness", "Rollback plan", "Final release approval"],
            "DOC-008": ["Problem identification", "Immediate containment", "Root cause analysis", "Five Whys", "Corrective action", "Preventive action", "Action ownership", "Implementation evidence", "Effectiveness verification", "CAPA closure approval"],
        }
        for doc_id, heads in required.items():
            text = self.docx_text(doc_id)
            for h in heads:
                self.assertIn(h, text, f"{doc_id} missing '{h}'")
        for doc_id in ("DOC-001", "DOC-005"):
            self.assertIn("Version history", self.docx_text(doc_id))
        self.assertIn("Review date", self.docx_text("DOC-003"))

    def test_rtm_excel_has_exact_columns_and_live_rows(self):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(self.c.get("/api/documents/DOC-005/download/excel").data))
        ws = wb["RTM"]
        head = [c.value for c in ws[1]]
        self.assertEqual(head, ["Stakeholder need", "Requirement ID", "Requirement description", "Hospital module", "Priority", "Risk level", "Design reference", "Implementation reference", "Test case ID", "Test result", "Defect ID", "Approval status"])
        self.assertEqual(ws.max_row - 1, 24)

    def test_excel_templates_have_purpose_built_sheets(self):
        from openpyxl import load_workbook
        sheets = lambda i: load_workbook(io.BytesIO(self.c.get(f"/api/documents/DOC-00{i}/download/excel").data)).sheetnames
        self.assertTrue({"Quality Objectives", "Responsibilities", "Quality Metrics", "Quality Gates"} <= set(sheets(1)))
        self.assertIn("Requirements Tracker", sheets(2))
        self.assertIn("Review Checklist", sheets(3))
        self.assertIn("Change Request Register", sheets(4))
        self.assertTrue({"Peer Review Tracker", "Findings Register"} <= set(sheets(6)))
        self.assertIn("Release Readiness", sheets(7))
        self.assertTrue({"CAPA Register", "Effectiveness Verification"} <= set(sheets(8)))
        wb = load_workbook(io.BytesIO(self.c.get("/api/documents/DOC-003/download/excel").data))
        ws = wb["Review Checklist"]
        self.assertTrue(ws.data_validations.dataValidation)  # interactive status drop-down
        self.assertGreaterEqual(ws.max_row, 30)
        capa = load_workbook(io.BytesIO(self.c.get("/api/documents/DOC-008/download/excel").data))["CAPA Register"]
        self.assertGreaterEqual(capa.max_row - 1, 6)

    def test_release_checklist_live_status_in_excel(self):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(self.c.get("/api/documents/DOC-007/download/excel").data))["Release Readiness"]
        vals = [c.value for r in ws.iter_rows(min_row=2) for c in r]
        self.assertIn("Failed", vals)
        self.assertIn("Critical defect verification", vals)

    def test_search_by_title_and_content_and_filters(self):
        ids = lambda q: [d["id"] for d in self.c.get("/api/documents?" + q).get_json()]
        self.assertIn("DOC-005", ids("q=traceability"))
        self.assertIn("DOC-008", ids("q=five%20whys"))     # found by content, not title
        self.assertIn("DOC-007", ids("q=rollback"))
        self.assertEqual(set(ids("doc_type=CHECKLIST")), {"DOC-003", "DOC-007"})
        self.assertEqual(ids("approval_status=Draft"), ["DOC-007"])
        self.assertEqual(ids("q=zzzznothing"), [])

    def test_version_history_and_revision_workflow(self):
        c = self.c.get("/api/documents/DOC-001/content").get_json()
        self.assertEqual([v["version"] for v in c["versions"]], ["1.2", "1.1", "1.0"])
        self.assertTrue(c["outline"]["sections"])
        self.assertEqual(self.post("/api/documents/DOC-001/revise", {"version": "1.2", "summary": "x"}).status_code, 422)
        self.assertEqual(self.post("/api/documents/DOC-001/revise", {"version": "1.3"}).status_code, 422)
        r = self.post("/api/documents/DOC-001/revise", {"version": "1.3", "summary": "Added hospital risk table"}).get_json()
        self.assertEqual((r["version"], r["approval_status"], r["approved_by"]), ("1.3", "Under Review", None))
        vers = self.c.get("/api/documents/DOC-001/content").get_json()["versions"]
        self.assertEqual(vers[0]["version"], "1.3")
        self.assertIn("1.3", self.docx_text("DOC-001"))  # Word file shows the new history row

    def test_approval_is_recorded_and_tracked(self):
        r = self.put("/api/documents/DOC-008", {"approval_status": "Approved", "change_summary": "CAPA v1.0 approved"}).get_json()
        self.assertEqual(r["approved_by"], "Team2 QA Lead")
        self.assertTrue(r["approved_on"])
        top = self.c.get("/api/documents/DOC-008/content").get_json()["versions"][0]
        self.assertEqual((top["approval_status"], top["approved_by"]), ("Approved", "Team2 QA Lead"))
        # editing the version of an approved doc re-opens approval
        r2 = self.put("/api/documents/DOC-008", {"version": "1.1"}).get_json()
        self.assertEqual(r2["approval_status"], "Under Review")

    def test_documents_linked_to_modules(self):
        d = {x["doc_key"]: x for x in self.c.get("/api/documents").get_json()}
        self.assertIn("requirements", d["req_procedure"]["modules"])
        self.assertIn("capa", d["capa_procedure"]["modules"])
        self.assertIn("release", d["release_checklist"]["modules"])
        self.assertIn("reviews", d["peer_review"]["modules"])
        self.assertIn("analytics", d["quality_plan"]["modules"])
        self.assertIn("testing", d["rtm"]["modules"])

    def test_library_revision_setting(self):
        self.assertEqual(self.c.get("/api/settings").get_json()["library_revision"], "1.0")


class TeamAndSettings(Base):
    def test_rename_cascades(self):
        tid = [t for t in self.c.get("/api/team").get_json() if t["name"] == "Team2 Architect"][0]["id"]
        self.put(f"/api/team/{tid}", {"name": "Dr Example Architect"})
        self.assertEqual(self.c.get("/api/requirements/REQ-015").get_json()["owner"], "Dr Example Architect")

    def test_settings_validation(self):
        self.assertEqual(self.put("/api/settings", {"min_pass_rate": "abc"}).status_code, 422)
        self.assertEqual(self.put("/api/settings", {"min_pass_rate": "85"}).status_code, 200)
        self.assertEqual(M.min_pass_rate(), 85.0)

    def test_search_and_alerts(self):
        self.assertTrue(self.c.get("/api/search?q=duplicate").get_json())
        self.assertTrue(any(a["level"] == "critical" for a in self.c.get("/api/alerts").get_json()))

    def test_reset_demo_data(self):
        self.c.delete("/api/requirements/REQ-001")
        self.post("/api/reset-demo-data")
        self.assertEqual(self.c.get("/api/requirements/REQ-001").status_code, 200)


if __name__ == "__main__":
    unittest.main()
