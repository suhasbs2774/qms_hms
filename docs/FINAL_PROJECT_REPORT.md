# Final Project Report — Software Quality Management System for Hospital Management Software
**TEAM 2 · HOSPITAL QUALITY OS**

## 1. Purpose and scope
A healthcare organisation is developing a Hospital Management System (patient registration, appointments, doctor records, laboratory information, billing, prescriptions, patient history). Its concerns are incorrect patient information, inconsistent data, system failures, inadequate documentation and defects that affect hospital operations. This project does **not** build that system; it builds the QMS used to manage its development and maintenance quality, demonstrating **PLAN → DEFINE → EXECUTE → VERIFY → MEASURE → REPORT → IMPROVE**.

## 2. Quality objectives (justified)
1. Patient data is accurate — wrong data harms patients; zero unresolved critical defects in patient identity, lab, prescription or billing at release.
2. Data stays consistent — all database and data-validation tests pass; no partial records after failed transactions.
3. Requirements are verified — every approved requirement traces to design, implementation and an executed test.
4. Confidential data is protected — approved security review and passing security tests.
5. Evidence-based release — a gate of 13 mandatory checks; 80% minimum pass rate as a *proposed* baseline.
6. Continuous improvement — every high-impact defect has a CAPA closed only with effectiveness verification.

## 3. Answers to the team's investigation questions
**Which requirements need additional review or verification?** Those with Critical/High risk: patient identity and duplicate detection (REQ-001/002), double booking (004), lab result binding and validation (007/008), billing calculation (009), prescription linkage and allergy/dosage checks (011/012), patient history (013/014), access control and encryption (015/016), transaction integrity (017), backup/recovery (019). They need a requirement review **plus** design/database/security review, and are surfaced as "high/critical-risk requirements not yet verified" on the dashboard and in the release gate.

**How should data-related defects be handled?** Defects in the categories *incorrect patient data, duplicate records, laboratory mismatch, billing errors, prescription errors, authentication/authorization failures, history inconsistency, database failures* with High/Critical severity are automatically given **Highest** priority, appear as patient-data alerts, block release when Critical, and require a CAPA (Five Whys) closed with effectiveness verification. Closure requires resolution details and a *Passed* verification retest.

**Which review and approval activities are mandatory?** Requirement review before a requirement can be baselined; database design and security review for data/security requirements; code review (billing and clinical calculations); test-plan review; documentation review; release review. A review is approved only with a recorded reviewer, a decision and a fully checked mandatory checklist. Security review and release review approvals are mandatory for release.

**Which quality factors matter most?** Data accuracy, data integrity, security and privacy, reliability, availability, auditability (highest); performance efficiency, maintainability, interoperability (lab interfaces) and usability (front-desk errors) are monitored. Each requirement is tagged with a factor and the report shows coverage per factor.

**Which metrics should management monitor?** Requirements coverage, test pass rate, defect density (per requirement), defect resolution rate, open critical defect count, reopen rate, defect aging, review completion, requirement approval rate, CAPA completion, requirement-to-test traceability and release readiness — each with a visible formula, record count, interpretation and status. A composite quality score (weights shown in-app) is provided; metrics without data are labelled *not measurable*.

**How should corrective actions be tracked and verified?** CAPA module: containment → root cause (Five Whys) → corrective → preventive → owner/target date → status (Open … Verification … Closed) → verification evidence → effectiveness review → closure approval. The system refuses closure without these and requires the linked defect to be resolved.

## 4. Implemented QMS (modules)
Dashboard, Requirements (12 hospital categories), Reviews (8 types with checklists), Testing (10 categories, execution workflow, defect creation from failures), Defects (14 hospital categories, 4 severities, 7 statuses), Traceability (bidirectional RTM with gap detection), Quality Analytics (12 metrics, 6 charts, PDF/Excel/CSV/Print report), CAPA, Release Management (GO / NO-GO / CONDITIONAL GO with enforced rules), Documents / QMS Library (the eight mandatory controlled documents, each with Word and Excel downloads generated from its content and live data, View panel, search by content, type/status filters, version history, revision and approval tracking, quality handbook, register; linked from every related module), Settings (editable team and roles). Seed data: 24 requirements, 25 test cases, 13 defects, 12 reviews, 6 CAPAs, 8 controlled documents (16 document versions).

## 5. Verification of the QMS itself
55 automated tests cover seed integrity, every validation/workflow rule, metrics against raw database counts, traceability gaps, release-gate enforcement (including an end-to-end run that drives the data to a valid GO), and all report/document exports. The UI was exercised in a headless browser (all 11 pages load without script errors; validation messages and blocked GO decision confirmed).

## 6. Limitations and assumptions
* The reference `qms_Mohan.zip` was not available to inspect; behaviour was derived from the specification and screenshots.
* Single-user prototype, no login/authentication (the "act as" menu only records who performed an action). Not for real patient data.
* The 80% baseline, quality-score weights and thresholds are project proposals, editable/documented, not regulatory limits.
* This is a quality-management prototype; **no regulatory or clinical-safety compliance is claimed.**

## 7. Current demonstration state
With the seed data the release gate is **NO-GO**: critical defects DEF-001 and DEF-003 remain open, pass rate is 70% (< 80%), security review REV-007 needs rework, and several requirements/documents are unapproved. Working through the workflows (fix defects, retest, review, approve, confirm backup/rollback) moves the gate toward GO — the automated test `test_go_allowed_when_every_check_passes` demonstrates this path.
