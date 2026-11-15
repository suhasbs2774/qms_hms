# Database schema (SQLite)

| Table | Purpose | Key relationships |
|---|---|---|
| settings | project/team name, release, minimum pass rate, current user | – |
| team_members | editable team and roles | – |
| stakeholder_needs | SN-01…SN-10 stakeholder needs | referenced by requirements.need_id |
| requirements | functional/non-functional requirements, approval info, design/implementation refs | need_id → stakeholder_needs (SET NULL) |
| reviews | review records, checklist (JSON), decision, derived approval_status | – |
| review_requirements | many-to-many reviews ↔ requirements | both CASCADE |
| test_cases | test cases with execution data | requirement_id → requirements (SET NULL) |
| defects | defect tracking | requirement_id → requirements, test_case_id → test_cases (SET NULL) |
| capas | CAPA with five whys, actions, effectiveness | defect_id → defects (SET NULL) |
| documents | controlled document register (version, owner, review date, approval status/approver) | – |
| document_versions | version history and approval records per document | doc_id → documents (CASCADE) |
| release_manual | manual release attestations with evidence | – |
| release_decisions | release decision history + snapshot | – |
| activity_log | audit trail / recent activity | – |

The full trace chain (need → requirement → design → implementation → test → result → defect → CAPA) is derived by joins: requirement → tests (test_cases.requirement_id) → defects (defects.test_case_id/requirement_id) → capas (capas.defect_id). A defect's *hospital module* is the category of its requirement. DDL: see `SCHEMA` in `db.py`.
