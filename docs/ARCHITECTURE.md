# Architecture

```
Browser (SPA: index.html + app.js / modules.js / pages.js, Chart.js)
   │  JSON over HTTP  (/api/...)
Flask app (app.py)  ── validation + workflow rules ──► SQLite (db.py, data/hospital_qms.db)
   │                                                        ▲
   ├─ metrics.py   quality metrics, RTM, release gate, dashboard, alerts (all computed from DB)
   ├─ reports.py   PDF (reportlab+matplotlib), Excel (openpyxl), CSV, print HTML
   ├─ docs_content.py  content + Word/Excel generators for the 8 controlled documents (live data + version history)
   └─ domain.py    hospital-specific enumerations, quality objectives/factors, lifecycle definition
```
* **Frontend**: hash-routed single page app. `listModule()` (app.js) is a generic CRUD engine (search, filters, sort, drawer, form, delete confirmation, CSV/Excel export) configured per module in modules.js. Custom pages (dashboard, analytics, RTM, release, documents, settings) are in pages.js.
* **Backend**: generic REST routes per entity (`GET/POST /api/<entity>`, `GET/PUT/DELETE /api/<entity>/<id>`) with a per-entity rule function that enforces the quality rules below. Errors return `{error}` with 422/409/404.
* **Persistence**: SQLite with foreign keys ON; no browser storage is used for data.

## Quality rules enforced on the server
| Area | Rule |
|---|---|
| Requirements | Approved/Implemented/Verified require an approved *Requirement review* covering the requirement; Verified also needs ≥1 test, all Passed, no open defects. Withdrawing/deleting the review downgrades the requirement. |
| Reviews | A decision needs a reviewer; *Approved* needs every checklist item checked and no Critical finding; *Approved with actions* needs findings; *Rework/Rejected* need comments; a Requirement review must cover ≥1 requirement. Approval status is derived from the decision. |
| Tests | Passed/Failed need actual result and tester; a defect can only be raised from a Failed test and is auto-linked (requirement inherited). |
| Defects | Critical severity, or High/Critical in patient-data categories (patient data, duplicates, lab, billing, prescriptions, authentication/authorization, history, database) ⇒ priority forced to *Highest*. Closed needs resolution + verification Passed; reopen counter and dates maintained. |
| CAPA | Root cause required past Investigation; corrective action for In Progress; preventive for Verification; **Closed needs verification evidence + effectiveness review + approver, and the linked defect Resolved/Closed.** |
| Release | 13 mandatory checks; GO only if all pass; CONDITIONAL GO only if critical-defect, pass-rate, security-test and approval checks pass and conditions are written; NO-GO needs rationale. Decisions are stored with a snapshot. |

## Lifecycle mapping
PLAN → Documents · DEFINE → Requirements · EXECUTE → Testing, Defects · VERIFY → Reviews, Traceability · MEASURE → Quality Analytics · REPORT → Release Management + reports · IMPROVE → CAPA.
Stage progress on the dashboard is calculated from records (e.g. DEFINE = approved ÷ active requirements; REPORT = 100% only once a report has been generated).

## Document control
`documents` (id, key, title, type, version, owner, created, review date, last updated, approval status, approver) and `document_versions` (every revision/approval event). Rules: a new revision, or a version change on an approved document, returns it to *Under Review* and clears the approval; approving records the approver/date and a history row. `GET /api/documents/<id>/content` returns outline + history; `POST /api/documents/<id>/revise`; downloads at `/api/documents/<id>/download/word|excel`; `/api/handbook.docx` combines all eight.
