"""HOSPITAL QUALITY OS - Flask backend for the Team 2 Hospital Management Software QMS."""
import json
import os
from datetime import date

from flask import Flask, Response, jsonify, request, send_from_directory

import db
import metrics as M
import reports as R
import docs_content as DC
from domain import *  # noqa: F401,F403

app = Flask(__name__, static_folder="static", static_url_path="/static")


class ValidationError(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ValidationError)
def _ve(e):
    return jsonify({"error": e.message}), e.status


@app.errorhandler(404)
def _nf(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory("static", "index.html")


@app.errorhandler(Exception)
def _err(e):
    if hasattr(e, "code") and isinstance(e.code, int):
        return jsonify({"error": getattr(e, "description", str(e))}), e.code
    app.logger.exception(e)
    return jsonify({"error": "Internal error: " + str(e)}), 500


def today():
    return date.today().isoformat()


def actor():
    return db.get_setting("current_user", "System")


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def clean(data, fields):
    out = {}
    for f in fields:
        if f in data:
            v = data[f]
            out[f] = v.strip() if isinstance(v, str) else v
    return out


def need(data, names, label=""):
    miss = [n for n in names if blank(data.get(n))]
    if miss:
        raise ValidationError("Required: " + ", ".join(n.replace("_", " ") for n in miss))


def enum(data, field, allowed, optional=False):
    v = data.get(field)
    if blank(v):
        if optional:
            return
        raise ValidationError(f"{field.replace('_', ' ')} is required")
    if v not in allowed:
        raise ValidationError(f"Invalid {field.replace('_', ' ')}: '{v}'. Allowed: {', '.join(a for a in allowed if a)}")


def valid_date(data, field):
    v = data.get(field)
    if blank(v):
        return
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValidationError(f"{field.replace('_', ' ')} must be a date (YYYY-MM-DD)")


def next_id(table, prefix, pad=3):
    rows = db.query(f"SELECT id FROM {table} WHERE id LIKE ?", (prefix + "-%",))
    n = 0
    for r in rows:
        try:
            n = max(n, int(r["id"].split("-")[1]))
        except (ValueError, IndexError):
            pass
    return f"{prefix}-{n + 1:0{pad}d}"


def exists(table, id_):
    return db.query(f"SELECT 1 FROM {table} WHERE id=?", (id_,), one=True) is not None


# ============================================================ entity definitions
ENT = {}


def entity(name, **kw):
    ENT[name] = kw


entity("requirements", table="requirements", prefix="REQ",
       fields=["title", "description", "category", "req_type", "quality_factor", "priority", "risk", "owner", "status",
               "acceptance_criteria", "design_ref", "impl_ref", "need_id"],
       base=("SELECT r.*, (SELECT GROUP_CONCAT(id, ', ') FROM test_cases WHERE requirement_id=r.id) AS test_ids, "
             "(SELECT GROUP_CONCAT(id, ', ') FROM defects WHERE requirement_id=r.id) AS defect_ids, "
             "(SELECT GROUP_CONCAT(review_id, ', ') FROM review_requirements WHERE requirement_id=r.id) AS review_ids FROM requirements r"),
       search=["id", "title", "description", "owner", "category"],
       filters=["category", "priority", "risk", "status", "owner", "req_type", "quality_factor"],
       sorts=["id", "title", "category", "priority", "risk", "status", "owner"])
entity("reviews", table="reviews", prefix="REV",
       fields=["review_type", "title", "artifact", "artifact_version", "reviewer", "review_date", "due_date", "findings",
               "finding_severity", "comments", "decision"],
       base=("SELECT v.*, (SELECT GROUP_CONCAT(requirement_id, ',') FROM review_requirements WHERE review_id=v.id) AS requirement_ids FROM reviews v"),
       search=["id", "title", "artifact", "reviewer", "findings"],
       filters=["review_type", "approval_status", "reviewer", "decision"],
       sorts=["id", "review_type", "due_date", "review_date", "approval_status", "reviewer"])
entity("tests", table="test_cases", prefix="TC",
       fields=["scenario", "requirement_id", "category", "preconditions", "steps", "expected", "actual", "tester",
               "exec_date", "status", "evidence"],
       base=("SELECT t.*, (SELECT GROUP_CONCAT(id, ', ') FROM defects WHERE test_case_id=t.id) AS defect_ids FROM test_cases t"),
       search=["id", "scenario", "requirement_id", "tester", "expected"],
       filters=["category", "status", "requirement_id", "tester"],
       sorts=["id", "category", "status", "exec_date", "requirement_id", "tester"])
entity("defects", table="defects", prefix="DEF",
       fields=["title", "description", "category", "severity", "priority", "steps", "expected", "actual", "assigned_to",
               "reported_by", "date_reported", "requirement_id", "test_case_id", "resolution", "verification_result", "status"],
       base=("SELECT d.*, (SELECT category FROM requirements WHERE id=d.requirement_id) AS module, "
             "CASE WHEN d.severity IN ('Critical','High') AND d.category IN ({cats}) THEN 1 ELSE 0 END AS patient_impact, "
             "CASE WHEN d.status IN ('Resolved','Closed') THEN NULL ELSE CAST(julianday('now','localtime') - julianday(d.date_reported) AS INTEGER) END AS age_days "
             "FROM defects d").format(cats=",".join("'" + c + "'" for c in sorted(PATIENT_CRITICAL_CATEGORIES))),
       search=["id", "title", "description", "assigned_to", "requirement_id", "test_case_id"],
       filters=["category", "severity", "priority", "status", "assigned_to", "module", "requirement_id", "patient_impact"],
       sorts=["id", "severity", "priority", "status", "date_reported", "category", "age_days"])
entity("capas", table="capas", prefix="CAPA",
       fields=["defect_id", "problem", "root_cause", "why1", "why2", "why3", "why4", "why5", "containment", "corrective",
               "preventive", "owner", "target_date", "status", "verification_evidence", "effectiveness_review", "closure_approved_by"],
       base=("SELECT c.*, (SELECT title FROM defects WHERE id=c.defect_id) AS defect_title, "
             "(SELECT severity FROM defects WHERE id=c.defect_id) AS defect_severity FROM capas c"),
       search=["id", "problem", "root_cause", "owner", "defect_id"],
       filters=["status", "owner", "defect_id"], sorts=["id", "status", "target_date", "owner"])
entity("documents", table="documents", prefix="DOC",
       fields=["title", "doc_type", "version", "owner", "approval_status", "description", "review_date"],
       base="SELECT d.*, (SELECT COUNT(*) FROM document_versions WHERE doc_id=d.id) AS version_count FROM documents d",
       search=["id", "title", "description", "owner", "doc_type", "version"],
       filters=["doc_type", "approval_status", "owner"], sorts=["id", "title", "updated_on", "approval_status", "review_date", "version"])


def sev_rank(s):
    return {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(s, 9)


# ============================================================ validation / business rules
def approving_req_review(req_id):
    return db.query("SELECT v.* FROM reviews v JOIN review_requirements rr ON rr.review_id=v.id "
                    "WHERE rr.requirement_id=? AND v.review_type='Requirement review' AND v.decision IN ('Approved','Approved with actions') "
                    "ORDER BY v.review_date DESC", (req_id,))


def rule_requirement(d, existing, rid):
    d["req_type"] = d.get("req_type") or "Functional"
    d["status"] = d.get("status") or "Draft"
    need(d, ["title", "description", "category", "priority", "risk", "owner", "acceptance_criteria"])
    enum(d, "category", REQ_CATEGORIES)
    enum(d, "priority", LEVELS)
    enum(d, "risk", LEVELS)
    enum(d, "status", REQ_STATUS)
    enum(d, "req_type", REQ_TYPES)
    enum(d, "quality_factor", QUALITY_FACTORS, optional=True)
    if not blank(d.get("need_id")) and not exists("stakeholder_needs", d["need_id"]):
        raise ValidationError(f"Stakeholder need {d['need_id']} does not exist")
    d["need_id"] = d.get("need_id") or None
    if d["status"] in APPROVED_REQ:
        revs = approving_req_review(rid) if rid else []
        if not revs:
            raise ValidationError("A requirement cannot be Approved/Implemented/Verified without an approved Requirement review "
                                  "(Approved or Approved with actions) that covers it. Record the review decision first.")
        d["approved_by"], d["approved_on"] = revs[0]["reviewer"], revs[0]["review_date"]
        if d["status"] == "Verified":
            tests = db.query("SELECT status FROM test_cases WHERE requirement_id=?", (rid,))
            if not tests or any(t["status"] != "Passed" for t in tests):
                raise ValidationError("Verified requires at least one test case and all linked tests Passed.")
            if db.query("SELECT 1 FROM defects WHERE requirement_id=? AND status NOT IN ('Resolved','Closed')", (rid,)):
                raise ValidationError("Verified requires all linked defects to be Resolved or Closed.")
    else:
        d["approved_by"], d["approved_on"] = None, None
    if d["status"] == "Implemented" and blank(d.get("impl_ref")):
        raise ValidationError("Implemented requires an implementation reference.")
    d.setdefault("created_on", today())


def rule_review(d, existing, rid):
    need(d, ["review_type", "title", "artifact"])
    enum(d, "review_type", REVIEW_TYPES)
    enum(d, "finding_severity", FINDING_SEVERITIES, optional=True)
    dec = d.get("decision") or None
    if dec and dec not in REVIEW_DECISIONS:
        raise ValidationError("Invalid decision. Allowed: " + ", ".join(REVIEW_DECISIONS))
    d["decision"] = dec
    for f in ("review_date", "due_date"):
        valid_date(d, f)
    items = REVIEW_CHECKLISTS_MAP[d["review_type"]]
    chk = d.get("checklist") or {}
    if isinstance(chk, str):
        chk = json.loads(chk or "{}")
    chk = {i: bool(chk.get(i, False)) for i in items}
    d["checklist"] = json.dumps(chk)
    reqs = d.get("requirement_ids") or []
    if isinstance(reqs, str):
        reqs = [x for x in reqs.split(",") if x]
    for q in reqs:
        if not exists("requirements", q):
            raise ValidationError(f"Requirement {q} does not exist")
    d["_reqs"] = reqs
    if dec:
        if blank(d.get("reviewer")):
            raise ValidationError("A reviewer must be recorded before a decision can be saved.")
        if blank(d.get("review_date")):
            d["review_date"] = today()
        if dec == "Approved" and not all(chk.values()):
            missing = [k for k, v in chk.items() if not v]
            raise ValidationError("Approved requires every mandatory checklist item to be checked. Unchecked: " + "; ".join(missing))
        if dec == "Approved" and d.get("finding_severity") == "Critical":
            raise ValidationError("A review with a Critical finding cannot be plainly Approved; use Approved with actions or Rework required.")
        if dec == "Approved with actions" and blank(d.get("findings")):
            raise ValidationError("Approved with actions requires the findings/actions to be recorded.")
        if dec in ("Rework required", "Rejected") and blank(d.get("comments")):
            raise ValidationError(f"{dec} requires reviewer comments explaining the decision.")
        if dec in APPROVING and d["review_type"] == "Requirement review" and not reqs:
            raise ValidationError("A Requirement review must cover at least one requirement before it can approve.")
    d["approval_status"] = dec if dec else "Pending"
    d.setdefault("created_on", today())


def rule_test(d, existing, rid):
    need(d, ["scenario", "category", "steps", "expected"])
    enum(d, "category", TEST_CATEGORIES)
    d["status"] = d.get("status") or "Not Run"
    enum(d, "status", TEST_STATUS)
    valid_date(d, "exec_date")
    if not blank(d.get("requirement_id")) and not exists("requirements", d["requirement_id"]):
        raise ValidationError(f"Requirement {d['requirement_id']} does not exist")
    d["requirement_id"] = d.get("requirement_id") or None
    if d["status"] in ("Passed", "Failed"):
        if blank(d.get("actual")):
            raise ValidationError(f"Record the actual result before marking the test {d['status']}.")
        if blank(d.get("tester")):
            raise ValidationError("Record the tester before marking the test as executed.")
    if d["status"] != "Not Run" and blank(d.get("exec_date")):
        d["exec_date"] = today()


def rule_defect(d, existing, rid):
    need(d, ["title", "description", "category", "severity"])
    enum(d, "category", DEFECT_CATEGORIES)
    enum(d, "severity", SEVERITIES)
    d["status"] = d.get("status") or "Open"
    enum(d, "status", DEFECT_STATUS)
    enum(d, "priority", DEFECT_PRIORITIES, optional=True)
    if d.get("verification_result") not in VERIFICATION and not blank(d.get("verification_result")):
        raise ValidationError("Invalid verification result")
    d["verification_result"] = d.get("verification_result") or ""
    d["date_reported"] = d.get("date_reported") or today()
    valid_date(d, "date_reported")
    if not blank(d.get("test_case_id")):
        tc = db.query("SELECT requirement_id FROM test_cases WHERE id=?", (d["test_case_id"],), one=True)
        if not tc:
            raise ValidationError(f"Test case {d['test_case_id']} does not exist")
        if blank(d.get("requirement_id")):
            d["requirement_id"] = tc["requirement_id"]
    d["test_case_id"] = d.get("test_case_id") or None
    if not blank(d.get("requirement_id")) and not exists("requirements", d["requirement_id"]):
        raise ValidationError(f"Requirement {d['requirement_id']} does not exist")
    d["requirement_id"] = d.get("requirement_id") or None
    # data-integrity / patient-safety defects get the highest quality priority
    if d["severity"] == "Critical" or (d["severity"] in ("Critical", "High") and d["category"] in PATIENT_CRITICAL_CATEGORIES):
        d["priority"] = "Highest"
    d["priority"] = d.get("priority") or {"Critical": "Highest", "High": "High", "Medium": "Medium", "Low": "Low"}[d["severity"]]
    if d["status"] in ("Assigned", "In Progress") and blank(d.get("assigned_to")):
        raise ValidationError("Assign a developer before moving the defect to Assigned/In Progress.")
    if d["status"] in ("Resolved", "Retesting", "Closed") and blank(d.get("resolution")):
        raise ValidationError(f"Resolution details are required for status {d['status']}.")
    if d["status"] == "Closed" and d["verification_result"] != "Passed":
        raise ValidationError("A defect can only be Closed after verification result 'Passed'.")
    prev = existing or {}
    d["reopen_count"] = prev.get("reopen_count", 0)
    if d["status"] == "Reopened" and prev.get("status") in ("Resolved", "Retesting", "Closed"):
        d["reopen_count"] += 1
        d["resolved_on"] = d["closed_on"] = None
        d["verification_result"] = "Failed" if d["verification_result"] in ("", "Passed") else d["verification_result"]
    else:
        d["resolved_on"] = prev.get("resolved_on")
        d["closed_on"] = prev.get("closed_on")
    if d["status"] in DEFECT_DONE and not d["resolved_on"]:
        d["resolved_on"] = today()
    if d["status"] == "Closed" and not d["closed_on"]:
        d["closed_on"] = today()
    if d["status"] not in DEFECT_DONE and d["status"] != "Reopened" and d["status"] != "Retesting":
        pass
    if d["status"] not in ("Closed",):
        d["closed_on"] = None if d["status"] != "Closed" else d["closed_on"]
    d.setdefault("reported_by", actor())


def rule_capa(d, existing, rid):
    need(d, ["problem", "owner"])
    d["status"] = d.get("status") or "Open"
    enum(d, "status", CAPA_STATUS)
    valid_date(d, "target_date")
    if not blank(d.get("defect_id")) and not exists("defects", d["defect_id"]):
        raise ValidationError(f"Defect {d['defect_id']} does not exist")
    d["defect_id"] = d.get("defect_id") or None
    st = d["status"]
    if st in ("Action Planned", "In Progress", "Verification", "Closed") and blank(d.get("root_cause")):
        raise ValidationError("Document the root cause before moving the CAPA beyond Investigation.")
    if st in ("Action Planned", "In Progress", "Verification", "Closed") and blank(d.get("target_date")):
        raise ValidationError("A target completion date is required once actions are planned.")
    if st in ("In Progress", "Verification", "Closed") and blank(d.get("corrective")):
        raise ValidationError("A corrective action is required for In Progress, Verification and Closed.")
    if st in ("Verification", "Closed") and blank(d.get("preventive")):
        raise ValidationError("A preventive action is required for Verification and Closed.")
    d["closed_on"] = None
    if st == "Closed":
        if blank(d.get("verification_evidence")) or blank(d.get("effectiveness_review")):
            raise ValidationError("A CAPA cannot be closed without documented verification evidence and an effectiveness review.")
        if blank(d.get("closure_approved_by")):
            raise ValidationError("Closure approval (name) is required to close a CAPA.")
        if d["defect_id"]:
            df = db.query("SELECT status FROM defects WHERE id=?", (d["defect_id"],), one=True)
            if df["status"] not in DEFECT_DONE:
                raise ValidationError(f"Linked defect {d['defect_id']} must be Resolved or Closed before the CAPA is closed.")
        d["closed_on"] = (existing or {}).get("closed_on") or today()
    d.setdefault("created_on", today())


def rule_document(d, existing, rid):
    need(d, ["title", "doc_type", "version", "owner"])
    enum(d, "doc_type", DOC_TYPES)
    d["approval_status"] = d.get("approval_status") or "Draft"
    enum(d, "approval_status", DOC_STATUS)
    valid_date(d, "review_date")
    d["review_date"] = d.get("review_date") or None
    prev = existing or {}
    ver_changed = bool(existing) and d["version"] != prev["version"]
    if ver_changed and prev["approval_status"] == "Approved" and d["approval_status"] == "Approved":
        d["approval_status"] = "Under Review"  # a new revision must be re-approved
    if d["approval_status"] == "Approved":
        if prev.get("approval_status") == "Approved" and not ver_changed:
            d["approved_by"], d["approved_on"] = prev.get("approved_by"), prev.get("approved_on")
        else:
            d["approved_by"], d["approved_on"] = actor(), today()
    else:
        d["approved_by"], d["approved_on"] = None, None
    d["updated_on"] = today()
    d.setdefault("created_on", today())
    d.setdefault("doc_key", prev.get("doc_key") or "custom")


def doc_history(doc_id, existing, data, summary):
    def add(text):
        db.execute("INSERT INTO document_versions(doc_id,version,changed_on,changed_by,summary,approval_status,approved_by) VALUES(?,?,?,?,?,?,?)",
                   (doc_id, data["version"], today(), actor(), text, data["approval_status"], data.get("approved_by")))
    if not existing:
        add(summary or "Initial issue")
    elif data["version"] != existing["version"]:
        add(summary or f"Revised to version {data['version']}")
    elif data["approval_status"] != existing["approval_status"]:
        add(summary or f"Approval status changed to {data['approval_status']}")


RULES = {"requirements": rule_requirement, "reviews": rule_review, "tests": rule_test, "defects": rule_defect,
         "capas": rule_capa, "documents": rule_document}
REVIEW_CHECKLISTS_MAP = db.REVIEW_CHECKLISTS

# columns persisted per table (besides editable fields) for insert/update
EXTRA = {"requirements": ["approved_by", "approved_on", "created_on"], "reviews": ["approval_status", "checklist", "created_on"],
         "tests": [], "defects": ["resolved_on", "closed_on", "reopen_count"], "capas": ["closed_on", "created_on"],
         "documents": ["doc_key", "updated_on", "created_on", "approved_by", "approved_on"]}


def resync_requirements():
    """Downgrade approved requirements whose approving review was withdrawn or deleted."""
    for r in db.query("SELECT id FROM requirements WHERE status IN ('Approved','Implemented','Verified')"):
        if not approving_req_review(r["id"]):
            db.execute("UPDATE requirements SET status='Under Review', approved_by=NULL, approved_on=NULL WHERE id=?", (r["id"],))
            db.log(actor(), "downgraded", "requirements", r["id"], "Approval withdrawn: no approved requirement review remains")


def shape(name, row):
    if name == "reviews":
        row["requirement_ids"] = [x for x in (row.get("requirement_ids") or "").split(",") if x]
        try:
            row["checklist"] = json.loads(row.get("checklist") or "{}")
        except ValueError:
            row["checklist"] = {}
        if not row["checklist"]:
            row["checklist"] = {i: False for i in REVIEW_CHECKLISTS_MAP[row["review_type"]]}
    if name == "defects":
        row["patient_impact"] = bool(row.get("patient_impact"))
    if name == "documents":
        row["modules"] = DC.DOC_MODULES.get(row.get("doc_key"), [])
    return row


def fetch_list(name, q=None):
    e = ENT[name]
    where, args = [], []
    q = (request.args.get("q", "") if q is None else q).strip()
    if q:
        where.append("(" + " OR ".join(f"CAST({c} AS TEXT) LIKE ?" for c in e["search"]) + ")")
        args += [f"%{q}%"] * len(e["search"])
    for f in e["filters"]:
        v = request.args.get(f)
        if v not in (None, ""):
            where.append(f"{f} = ?")
            args.append(v)
    sort = request.args.get("sort", "id")
    if sort not in e["sorts"]:
        sort = "id"
    direction = "DESC" if request.args.get("dir", "asc").lower() == "desc" else "ASC"
    sql = f"SELECT * FROM ({e['base']}) x" + (" WHERE " + " AND ".join(where) if where else "")
    if sort == "severity":
        sql += f" ORDER BY CASE severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END {direction}, id"
    elif sort == "priority":
        sql += (" ORDER BY CASE priority WHEN 'Highest' THEN 0 WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END " + direction + ", id")
    elif sort == "risk":
        sql += f" ORDER BY CASE risk WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END {direction}, id"
    else:
        sql += f" ORDER BY {sort} {direction}, id"
    return [shape(name, r) for r in db.query(sql, args)]


def fetch_one(name, id_):
    row = db.query(f"SELECT * FROM ({ENT[name]['base']}) x WHERE id=?", (id_,), one=True)
    if not row:
        raise ValidationError(f"{id_} not found", 404)
    return shape(name, row)


def save(name, id_=None):
    e = ENT[name]
    payload = request.get_json(force=True, silent=True) or {}
    existing = None
    if id_:
        existing = db.query(f"SELECT * FROM {e['table']} WHERE id=?", (id_,), one=True)
        if not existing:
            raise ValidationError(f"{id_} not found", 404)
        merged = dict(existing)
        if name == "reviews":
            merged["requirement_ids"] = [r["requirement_id"] for r in db.query("SELECT requirement_id FROM review_requirements WHERE review_id=?", (id_,))]
        merged.update(clean(payload, e["fields"] + (["requirement_ids", "checklist"] if name == "reviews" else [])))
        data = merged
    else:
        data = clean(payload, e["fields"] + (["requirement_ids", "checklist"] if name == "reviews" else []))
        if name == "documents" and payload.get("doc_key"):
            data["doc_key"] = payload["doc_key"]
    rid = id_ or (payload.get("id") if name != "requirements" else None)
    RULES[name](data, existing, id_)
    cols = e["fields"] + EXTRA[name]
    if id_:
        cols_set = [c for c in cols if c in data]
        db.execute(f"UPDATE {e['table']} SET " + ",".join(f"{c}=?" for c in cols_set) + " WHERE id=?",
                   [data[c] for c in cols_set] + [id_])
        action = "updated"
    else:
        id_ = next_id(e["table"], e["prefix"])
        cols_set = [c for c in cols if c in data]
        db.execute(f"INSERT INTO {e['table']}(id," + ",".join(cols_set) + ") VALUES(?," + ",".join("?" * len(cols_set)) + ")",
                   [id_] + [data[c] for c in cols_set])
        action = "created"
    if name == "reviews":
        db.execute("DELETE FROM review_requirements WHERE review_id=?", (id_,))
        for q in dict.fromkeys(data["_reqs"]):
            db.execute("INSERT INTO review_requirements VALUES(?,?)", (id_, q))
        resync_requirements()
    if name == "documents":
        doc_history(id_, existing, data, (payload.get("change_summary") or "").strip())
    db.log(actor(), action, name, id_, data.get("title") or data.get("scenario") or data.get("problem") or "")
    return fetch_one(name, id_), (201 if action == "created" else 200)


# ============================================================ generic CRUD routes
def register(name):
    def lst():
        rows = fetch_list(name)
        if name == "documents" and request.args.get("q", "").strip():  # also search inside document content
            q = request.args["q"].strip().lower()
            have = {r["id"] for r in rows}
            for r in fetch_list(name, q=""):
                if r["id"] not in have and q in DC.search_text(r):
                    rows.append(r)
            rows.sort(key=lambda r: r["id"])
        return jsonify(rows)

    def get(id_):
        return jsonify(fetch_one(name, id_))

    def post():
        row, code = save(name)
        return jsonify(row), code

    def put(id_):
        row, code = save(name, id_)
        return jsonify(row), code

    def delete(id_):
        e = ENT[name]
        if not exists(e["table"], id_):
            raise ValidationError(f"{id_} not found", 404)
        db.execute(f"DELETE FROM {e['table']} WHERE id=?", (id_,))
        if name == "reviews":
            resync_requirements()
        db.log(actor(), "deleted", name, id_, "")
        return jsonify({"deleted": id_})

    app.add_url_rule(f"/api/{name}", f"list_{name}", lst, methods=["GET"])
    app.add_url_rule(f"/api/{name}/<id_>", f"get_{name}", get, methods=["GET"])
    app.add_url_rule(f"/api/{name}", f"post_{name}", post, methods=["POST"])
    app.add_url_rule(f"/api/{name}/<id_>", f"put_{name}", put, methods=["PUT"])
    app.add_url_rule(f"/api/{name}/<id_>", f"del_{name}", delete, methods=["DELETE"])


for _n in ENT:
    register(_n)


# ============================================================ workflow routes
@app.get("/api/requirements/<id_>/detail")
def req_detail(id_):
    r = fetch_one("requirements", id_)
    r["tests"] = db.query("SELECT id, scenario, status FROM test_cases WHERE requirement_id=?", (id_,))
    r["defects"] = db.query("SELECT id, title, severity, status FROM defects WHERE requirement_id=?", (id_,))
    r["reviews"] = db.query("SELECT v.id, v.review_type, v.title, v.decision, v.reviewer FROM reviews v JOIN review_requirements rr ON rr.review_id=v.id WHERE rr.requirement_id=?", (id_,))
    r["need"] = db.query("SELECT * FROM stakeholder_needs WHERE id=?", (r["need_id"],), one=True) if r["need_id"] else None
    return jsonify(r)


@app.post("/api/tests/<id_>/create-defect")
def test_create_defect(id_):
    t = db.query("SELECT * FROM test_cases WHERE id=?", (id_,), one=True)
    if not t:
        raise ValidationError("Test case not found", 404)
    if t["status"] != "Failed":
        raise ValidationError("A defect can only be raised from a Failed test case. Execute the test and mark it Failed first.")
    body = request.get_json(silent=True) or {}
    cat = body.get("category") or "Incorrect patient data"
    sev = body.get("severity") or "High"
    d = {"title": body.get("title") or f"Failed test {id_}: {t['scenario']}", "description": body.get("description") or f"Raised from failed test case {id_}.",
         "category": cat, "severity": sev, "steps": t["steps"], "expected": t["expected"], "actual": t["actual"],
         "requirement_id": t["requirement_id"], "test_case_id": id_, "status": "Open", "assigned_to": body.get("assigned_to"),
         "reported_by": actor()}
    rule_defect(d, None, None)
    did = next_id("defects", "DEF")
    cols = ENT["defects"]["fields"] + EXTRA["defects"]
    cs = [c for c in cols if c in d]
    db.execute(f"INSERT INTO defects(id,{','.join(cs)}) VALUES(?,{','.join('?' * len(cs))})", [did] + [d[c] for c in cs])
    db.log(actor(), "created", "defects", did, f"Raised from failed test {id_}")
    return jsonify(fetch_one("defects", did)), 201


@app.post("/api/defects/<id_>/create-capa")
def defect_create_capa(id_):
    d = db.query("SELECT * FROM defects WHERE id=?", (id_,), one=True)
    if not d:
        raise ValidationError("Defect not found", 404)
    if db.query("SELECT 1 FROM capas WHERE defect_id=?", (id_,)):
        raise ValidationError(f"A CAPA already exists for {id_}.")
    cid = next_id("capas", "CAPA")
    db.execute("INSERT INTO capas(id,defect_id,problem,owner,status,created_on) VALUES(?,?,?,?,?,?)",
               (cid, id_, f"{d['title']}. {d['description']}", d["assigned_to"] or actor(), "Open", today()))
    db.log(actor(), "created", "capas", cid, f"CAPA opened for {id_}")
    return jsonify(fetch_one("capas", cid)), 201


@app.get("/api/meta")
def meta():
    return jsonify({
        "requirement_categories": REQ_CATEGORIES, "levels": LEVELS, "req_status": REQ_STATUS, "req_types": REQ_TYPES,
        "quality_factors": QUALITY_FACTORS, "review_types": REVIEW_TYPES, "review_decisions": REVIEW_DECISIONS,
        "finding_severities": FINDING_SEVERITIES, "test_categories": TEST_CATEGORIES, "test_status": TEST_STATUS,
        "defect_categories": DEFECT_CATEGORIES, "severities": SEVERITIES, "defect_priorities": DEFECT_PRIORITIES,
        "defect_status": DEFECT_STATUS, "verification": VERIFICATION, "capa_status": CAPA_STATUS, "doc_types": DOC_TYPES,
        "doc_status": DOC_STATUS, "release_decisions": RELEASE_DECISIONS, "team_roles": TEAM_ROLES,
        "team": db.query("SELECT * FROM team_members ORDER BY id"), "needs": db.query("SELECT * FROM stakeholder_needs ORDER BY id"),
        "checklists": db.REVIEW_CHECKLISTS, "lifecycle": [{"stage": a, "description": b, "modules": c, "route": r} for a, b, c, r in LIFECYCLE],
        "settings": {r["key"]: r["value"] for r in db.query("SELECT * FROM settings")}, "disclaimer": DISCLAIMER,
        "objectives": QUALITY_OBJECTIVES, "factor_info": FACTOR_INFO,
        "requirement_ids": [r["id"] for r in db.query("SELECT id FROM requirements ORDER BY id")],
        "test_ids": [r["id"] for r in db.query("SELECT id FROM test_cases ORDER BY id")],
        "defect_ids": [r["id"] for r in db.query("SELECT id FROM defects ORDER BY id")],
    })


@app.get("/api/dashboard")
def dashboard():
    return jsonify(M.dashboard())


@app.get("/api/metrics")
def metrics_api():
    return jsonify({"metrics": M.metrics(), "score": M.quality_score(), "charts": M.chart_data(), "min_pass_rate": M.min_pass_rate()})


@app.get("/api/rtm")
def rtm_api():
    return jsonify(M.rtm())


@app.get("/api/alerts")
def alerts_api():
    return jsonify(M.alerts())


@app.get("/api/activity")
def activity_api():
    return jsonify(db.query("SELECT * FROM activity_log ORDER BY id DESC LIMIT 60"))


@app.get("/api/search")
def global_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    like = f"%{q}%"
    out = []
    for route, table, idc, tc, extra in [("requirements", "requirements", "id", "title", ""), ("testing", "test_cases", "id", "scenario", ""),
                                         ("defects", "defects", "id", "title", ""), ("reviews", "reviews", "id", "title", ""),
                                         ("capa", "capas", "id", "problem", ""), ("documents", "documents", "id", "title", "")]:
        for r in db.query(f"SELECT {idc} AS id, {tc} AS title FROM {table} WHERE {idc} LIKE ? OR {tc} LIKE ? LIMIT 5", (like, like)):
            out.append({"route": route, "id": r["id"], "title": r["title"]})
    return jsonify(out)


# ---------------------------------------------------------------- release management
@app.get("/api/release")
def release_get():
    s = M.release_summary()
    s["decisions"] = db.query("SELECT * FROM release_decisions ORDER BY id DESC")
    s["release_version"] = db.get_setting("release_version", "Release 1.0")
    return jsonify(s)


@app.post("/api/release/manual/<key>")
def release_manual(key):
    if key not in M.MANUAL_CHECKS:
        raise ValidationError("Unknown manual check", 404)
    b = request.get_json(force=True, silent=True) or {}
    confirmed = 1 if b.get("confirmed") else 0
    note = (b.get("note") or "").strip()
    if confirmed and not note:
        raise ValidationError("Record evidence/reference (e.g. backup log ID or rollback plan document) before confirming.")
    db.execute("INSERT INTO release_manual(check_key,confirmed,note,updated_by,updated_on) VALUES(?,?,?,?,?) "
               "ON CONFLICT(check_key) DO UPDATE SET confirmed=excluded.confirmed, note=excluded.note, updated_by=excluded.updated_by, updated_on=excluded.updated_on",
               (key, confirmed, note, actor(), today()))
    db.log(actor(), "updated", "release", key, ("Confirmed: " if confirmed else "Unconfirmed: ") + M.MANUAL_CHECKS[key])
    return jsonify(M.release_summary())


@app.post("/api/release/decision")
def release_decision():
    b = request.get_json(force=True, silent=True) or {}
    dec = b.get("decision")
    enum({"decision": dec}, "decision", RELEASE_DECISIONS)
    s = M.release_summary()
    if dec == "GO" and not s["go_allowed"]:
        bad = [c["name"] for c in s["checks"] if c["status"] != "Passed"]
        raise ValidationError("GO is not allowed: mandatory checks not satisfied (" + "; ".join(bad) + ").", 409)
    if dec == "CONDITIONAL GO":
        if not s["conditional_allowed"]:
            raise ValidationError("CONDITIONAL GO is not allowed: critical defects must be resolved, the pass-rate baseline met, security testing passed and security/release reviews approved.", 409)
        if blank(b.get("conditions")):
            raise ValidationError("CONDITIONAL GO requires the conditions to be documented.")
    if blank(b.get("rationale")):
        raise ValidationError("Record the rationale for the release decision.")
    snap = json.dumps({"passed": s["passed"], "failed": s["failed"], "pending": s["pending"], "readiness": s["readiness_pct"],
                       "recommendation": s["recommendation"], "checks": [(c["name"], c["status"]) for c in s["checks"]]})
    db.execute("INSERT INTO release_decisions(release_version,decision,rationale,conditions,decided_by,decided_on,snapshot) VALUES(?,?,?,?,?,?,?)",
               (db.get_setting("release_version", "Release 1.0"), dec, b["rationale"].strip(), (b.get("conditions") or "").strip(), actor(), db.now(), snap))
    db.log(actor(), "decided", "release", dec, b["rationale"].strip()[:120])
    return jsonify({"ok": True, "decision": dec}), 201


# ---------------------------------------------------------------- settings + team
@app.get("/api/settings")
def settings_get():
    return jsonify({r["key"]: r["value"] for r in db.query("SELECT * FROM settings")})


@app.put("/api/settings")
def settings_put():
    b = request.get_json(force=True, silent=True) or {}
    allowed = {"project_name", "team_name", "project_version", "organisation", "current_user", "min_pass_rate", "release_version", "project_start", "library_revision"}
    for k, v in b.items():
        if k not in allowed:
            continue
        if k == "min_pass_rate":
            try:
                f = float(v)
                assert 0 <= f <= 100
            except Exception:
                raise ValidationError("Minimum pass rate must be a number between 0 and 100")
        db.set_setting(k, v)
    db.log(actor(), "updated", "settings", "project", ", ".join(b))
    return settings_get()


@app.get("/api/team")
def team_list():
    return jsonify(db.query("SELECT * FROM team_members ORDER BY id"))


@app.post("/api/team")
def team_add():
    b = request.get_json(force=True, silent=True) or {}
    need(b, ["name", "role"])
    enum(b, "role", TEAM_ROLES)
    if db.query("SELECT 1 FROM team_members WHERE name=?", (b["name"].strip(),)):
        raise ValidationError("A team member with this name already exists")
    i = db.execute("INSERT INTO team_members(name,role,email) VALUES(?,?,?)", (b["name"].strip(), b["role"], (b.get("email") or "").strip()))
    db.log(actor(), "created", "team", str(i), b["name"])
    return jsonify(db.query("SELECT * FROM team_members WHERE id=?", (i,), one=True)), 201


@app.put("/api/team/<int:i>")
def team_update(i):
    old = db.query("SELECT * FROM team_members WHERE id=?", (i,), one=True)
    if not old:
        raise ValidationError("Team member not found", 404)
    b = request.get_json(force=True, silent=True) or {}
    name = (b.get("name") or old["name"]).strip()
    role = b.get("role") or old["role"]
    enum({"role": role}, "role", TEAM_ROLES)
    if not name:
        raise ValidationError("Name is required")
    if name != old["name"] and db.query("SELECT 1 FROM team_members WHERE name=?", (name,)):
        raise ValidationError("A team member with this name already exists")
    db.execute("UPDATE team_members SET name=?, role=?, email=? WHERE id=?", (name, role, (b.get("email") if "email" in b else old["email"]) or "", i))
    if name != old["name"]:  # keep records consistent when a member is renamed
        for t, c in [("requirements", "owner"), ("requirements", "approved_by"), ("reviews", "reviewer"), ("test_cases", "tester"),
                     ("defects", "assigned_to"), ("defects", "reported_by"), ("capas", "owner"), ("capas", "closure_approved_by"),
                     ("documents", "owner"), ("activity_log", "actor")]:
            db.execute(f"UPDATE {t} SET {c}=? WHERE {c}=?", (name, old["name"]))
        if db.get_setting("current_user") == old["name"]:
            db.set_setting("current_user", name)
    db.log(actor(), "updated", "team", str(i), name)
    return jsonify(db.query("SELECT * FROM team_members WHERE id=?", (i,), one=True))


@app.delete("/api/team/<int:i>")
def team_delete(i):
    old = db.query("SELECT * FROM team_members WHERE id=?", (i,), one=True)
    if not old:
        raise ValidationError("Team member not found", 404)
    if db.query("SELECT COUNT(*) n FROM team_members", one=True)["n"] <= 1:
        raise ValidationError("At least one team member is required")
    db.execute("DELETE FROM team_members WHERE id=?", (i,))
    db.log(actor(), "deleted", "team", str(i), old["name"])
    return jsonify({"deleted": i})


@app.post("/api/reset-demo-data")
def reset_demo():
    db.init_db(seed=True, force=True)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- exports + reports
def _download(data, name, mime):
    return Response(data, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.get("/api/export/<name>.<fmt>")
def export_entity(name, fmt):
    if name not in ENT or fmt not in ("csv", "xlsx"):
        raise ValidationError("Unknown export", 404)
    rows = fetch_list(name)
    if not rows:
        raise ValidationError("Nothing to export for the current filters", 404)
    cols = [c for c in rows[0].keys() if c not in ("checklist",)]
    data = [[(", ".join(r[c]) if isinstance(r[c], list) else r[c]) for c in cols] for r in rows]
    if fmt == "csv":
        return _download(R.table_csv(cols, data), f"{name}.csv", "text/csv")
    from openpyxl import Workbook
    import io
    wb = Workbook()
    ws = wb.active
    ws.title = name[:30]
    R._hdr(ws, 1, [c.replace("_", " ").title() for c in cols], [18] * len(cols))
    R._rows(ws, 2, data)
    out = io.BytesIO()
    wb.save(out)
    return _download(out.getvalue(), f"{name}.xlsx", XLSX)


@app.get("/api/report/<fmt>")
def report(fmt):
    d = R.report_data()
    stamp = date.today().isoformat()
    db.log(actor(), "report", "report", fmt, f"Quality report generated ({fmt})")
    if fmt == "pdf":
        return _download(R.build_pdf(d), f"Hospital_QMS_Quality_Report_{stamp}.pdf", "application/pdf")
    if fmt == "xlsx":
        return _download(R.build_xlsx(d), f"Hospital_QMS_Quality_Report_{stamp}.xlsx", XLSX)
    if fmt == "csv":
        return _download(R.build_csv(d), f"Hospital_QMS_Quality_Data_{stamp}.csv", "text/csv")
    if fmt == "print":
        return Response(R.build_print_html(d), mimetype="text/html")
    raise ValidationError("Unknown report format", 404)


@app.get("/api/rtm/export.<fmt>")
def rtm_export(fmt):
    if fmt == "xlsx":
        return _download(R.build_rtm_xlsx(), "Requirements_Traceability_Matrix.xlsx", XLSX)
    if fmt == "csv":
        return _download(R.rtm_csv(), "Requirements_Traceability_Matrix.csv", "text/csv")
    raise ValidationError("Unknown format", 404)


@app.get("/api/documents/<id_>/download/<fmt>")
def doc_download(id_, fmt):
    meta_ = R.doc_meta(id_)
    if not meta_:
        raise ValidationError("Document not found", 404)
    base = meta_["title"].replace(" ", "_")
    if fmt == "word":
        return _download(R.build_doc_docx(meta_), f"{meta_['id']}_{base}.docx", DOCX)
    if fmt == "excel":
        return _download(R.build_doc_xlsx(meta_), f"{meta_['id']}_{base}.xlsx", XLSX)
    raise ValidationError("Unknown format", 404)


@app.get("/api/documents/<id_>/content")
def doc_content(id_):
    m = fetch_one("documents", id_)
    m["outline"] = DC.outline(m)
    m["versions"] = db.query("SELECT * FROM document_versions WHERE doc_id=? ORDER BY id DESC", (id_,))
    return jsonify(m)


@app.post("/api/documents/<id_>/revise")
def doc_revise(id_):
    old = db.query("SELECT * FROM documents WHERE id=?", (id_,), one=True)
    if not old:
        raise ValidationError("Document not found", 404)
    b = request.get_json(force=True, silent=True) or {}
    ver = (b.get("version") or "").strip()
    if not ver or ver == old["version"]:
        raise ValidationError("Enter a new version number different from the current version (" + old["version"] + ").")
    if blank(b.get("summary")):
        raise ValidationError("Describe what changed in this revision.")
    valid_date(b, "review_date")
    status = "Draft" if b.get("status") == "Draft" else "Under Review"
    db.execute("UPDATE documents SET version=?, approval_status=?, approved_by=NULL, approved_on=NULL, updated_on=?, review_date=COALESCE(?, review_date) WHERE id=?",
               (ver, status, today(), b.get("review_date") or None, id_))
    db.execute("INSERT INTO document_versions(doc_id,version,changed_on,changed_by,summary,approval_status,approved_by) VALUES(?,?,?,?,?,?,NULL)",
               (id_, ver, today(), actor(), b["summary"].strip(), status))
    db.log(actor(), "revised", "documents", id_, f"v{old['version']} -> v{ver}: {b['summary'].strip()[:80]}")
    return jsonify(fetch_one("documents", id_))


@app.get("/api/handbook.docx")
def handbook():
    return _download(R.build_doc_docx(handbook=True), "Hospital_QMS_Quality_Handbook.docx", DOCX)


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


def create_app():
    db.init_db()
    return app


if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  HOSPITAL QUALITY OS running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
