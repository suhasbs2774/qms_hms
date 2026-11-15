"""All quality calculations. Every number is computed from persisted records - nothing is hardcoded."""
from datetime import date, datetime

import db
from domain import (APPROVED_REQ, APPROVING, DEFECT_DONE, LIFECYCLE, PATIENT_CRITICAL_CATEGORIES, REQ_CATEGORIES,
                    DEFECT_STATUS, TEST_STATUS, SEVERITIES)


def _today():
    return date.today()


def _days(d):
    try:
        return (_today() - datetime.strptime(d[:10], "%Y-%m-%d").date()).days
    except Exception:
        return None


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def min_pass_rate():
    try:
        return float(db.get_setting("min_pass_rate", "80"))
    except ValueError:
        return 80.0


def patient_impact(d):
    return d["severity"] in ("Critical", "High") and d["category"] in PATIENT_CRITICAL_CATEGORIES


# ------------------------------------------------------------------ traceability
def rtm():
    reqs = db.query("SELECT r.*, n.title AS need_title FROM requirements r "
                    "LEFT JOIN stakeholder_needs n ON n.id=r.need_id ORDER BY r.id")
    tests = db.query("SELECT id, requirement_id, status, scenario FROM test_cases")
    defects = db.query("SELECT id, requirement_id, test_case_id, status, severity, title FROM defects")
    capas = db.query("SELECT id, defect_id, status FROM capas")
    appr = db.query("SELECT rr.requirement_id, rv.id, rv.review_type FROM review_requirements rr "
                    "JOIN reviews rv ON rv.id=rr.review_id WHERE rv.decision IN ('Approved','Approved with actions')")
    rows = []
    for r in reqs:
        t = [x for x in tests if x["requirement_id"] == r["id"]]
        d = [x for x in defects if x["requirement_id"] == r["id"]]
        dids = {x["id"] for x in d}
        c = [x for x in capas if x["defect_id"] in dids]
        reviews = [a for a in appr if a["requirement_id"] == r["id"]]
        sts = [x["status"] for x in t]
        if not t:
            result = "No test"
        elif "Failed" in sts:
            result = "Failed"
        elif "Blocked" in sts:
            result = "Blocked"
        elif all(s == "Passed" for s in sts):
            result = "Passed"
        else:
            result = "Pending"
        open_def = [x for x in d if x["status"] not in DEFECT_DONE]
        approved = r["status"] in APPROVED_REQ and any(a["review_type"] == "Requirement review" for a in reviews)
        approval = "Approved" if approved else ("Rejected" if r["status"] == "Rejected" else "Not approved")
        gaps = []
        if r["status"] != "Rejected":
            if not t:
                gaps.append("No test case")
            if approval != "Approved":
                gaps.append("No approval")
            if result == "Failed":
                gaps.append("Failed test")
            if open_def:
                gaps.append("Open defect")
            if r["status"] != "Draft" and not (r["design_ref"] or "").strip():
                gaps.append("Missing design link")
            if r["status"] in ("Implemented", "Verified") and not (r["impl_ref"] or "").strip():
                gaps.append("Missing implementation link")
            if not r["need_id"]:
                gaps.append("Missing stakeholder need")
        verified = bool(t) and result == "Passed" and not open_def and r["status"] != "Rejected"
        rows.append({
            "id": r["id"], "title": r["title"], "description": r["description"], "category": r["category"],
            "priority": r["priority"], "risk": r["risk"], "status": r["status"],
            "need_id": r["need_id"], "need_title": r["need_title"],
            "design_ref": r["design_ref"], "impl_ref": r["impl_ref"],
            "tests": [{"id": x["id"], "status": x["status"]} for x in t], "test_result": result,
            "defects": [{"id": x["id"], "status": x["status"], "severity": x["severity"]} for x in d],
            "capas": [{"id": x["id"], "status": x["status"]} for x in c],
            "approval": approval, "approving_reviews": [a["id"] for a in reviews],
            "gaps": gaps, "verified": verified,
        })
    orphan_tests = db.query("SELECT id, scenario, status FROM test_cases WHERE requirement_id IS NULL")
    orphan_defects = db.query("SELECT id, title, status FROM defects WHERE requirement_id IS NULL")
    active = [x for x in rows if x["status"] != "Rejected"]
    summary = {
        "total": len(rows),
        "without_tests": sum(1 for x in active if not x["tests"]),
        "without_approval": sum(1 for x in active if x["approval"] != "Approved"),
        "with_failed_tests": sum(1 for x in active if x["test_result"] == "Failed"),
        "with_open_defects": sum(1 for x in active if any(d["status"] not in DEFECT_DONE for d in x["defects"])),
        "missing_links": sum(1 for x in active if any(g.startswith("Missing") for g in x["gaps"])),
        "unverified": sum(1 for x in active if not x["verified"]),
        "orphan_tests": len(orphan_tests), "orphan_defects": len(orphan_defects),
    }
    return {"rows": rows, "summary": summary, "orphan_tests": orphan_tests, "orphan_defects": orphan_defects}


# ------------------------------------------------------------------ release gate
MANUAL_CHECKS = {
    "backup_recovery": "Backup and recovery readiness confirmed",
    "rollback_plan": "Rollback plan documented",
}


def release_checks():
    tests = db.query("SELECT * FROM test_cases")
    defects = db.query("SELECT * FROM defects")
    reqs = [r for r in db.query("SELECT * FROM requirements") if r["status"] != "Rejected"]
    docs = db.query("SELECT * FROM documents WHERE approval_status != 'Obsolete'")
    reviews = db.query("SELECT * FROM reviews")
    manual = {m["check_key"]: m for m in db.query("SELECT * FROM release_manual")}
    tr = rtm()
    threshold = min_pass_rate()
    checks = []

    def add(key, name, status, detail, manual_flag=False):
        m = manual.get(key)
        checks.append({"key": key, "name": name, "status": status, "detail": detail, "manual": manual_flag,
                       "confirmed": bool(m and m["confirmed"]), "note": (m or {}).get("note", "") or "",
                       "updated_by": (m or {}).get("updated_by", ""), "updated_on": (m or {}).get("updated_on", "")})

    crit_open = [d for d in defects if d["severity"] == "Critical" and d["status"] not in DEFECT_DONE]
    add("critical_defects", "Critical defects resolved", "Passed" if not crit_open else "Failed",
        "No open critical defects." if not crit_open else f"{len(crit_open)} open: " + ", ".join(d["id"] for d in crit_open))

    high = [d for d in defects if d["severity"] == "High"]
    undisp = [d for d in high if d["status"] not in ("Resolved", "Closed", "Retesting") and not (d["resolution"] or "").strip()]
    add("high_defects", "High-risk defects dispositioned", "Passed" if not undisp else "Failed",
        f"All {len(high)} high-severity defects have a resolution or are closed/retesting." if not undisp
        else f"{len(undisp)} without disposition: " + ", ".join(d["id"] for d in undisp))

    unappr = [r for r in reqs if r["status"] not in APPROVED_REQ]
    add("req_approved", "Requirements approved", "Passed" if not unappr and reqs else "Failed",
        f"All {len(reqs)} active requirements approved." if not unappr and reqs
        else f"{len(unappr)} of {len(reqs)} requirements not approved: " + ", ".join(r["id"] for r in unappr[:8]) + ("..." if len(unappr) > 8 else ""))

    s = tr["summary"]
    incomplete = s["without_tests"] + s["missing_links"] + s["without_approval"]
    add("traceability", "Traceability complete", "Passed" if incomplete == 0 and reqs else "Failed",
        "Every active requirement is linked to need, design, test and approval." if incomplete == 0 and reqs else
        f"{s['without_tests']} without tests, {s['missing_links']} with missing links, {s['without_approval']} without approval.")

    notrun = [t for t in tests if t["status"] in ("Not Run", "In Progress", "Blocked")]
    add("test_execution", "Test execution completed", "Passed" if tests and not notrun else "Failed",
        f"All {len(tests)} test cases executed." if tests and not notrun else f"{len(notrun)} of {len(tests)} not completed: " + ", ".join(t["id"] for t in notrun[:8]) + ("..." if len(notrun) > 8 else ""))

    passed = sum(1 for t in tests if t["status"] == "Passed")
    failed = sum(1 for t in tests if t["status"] == "Failed")
    rate = pct(passed, passed + failed)
    add("pass_rate", f"Minimum {threshold:g}% test pass rate achieved",
        "Pending" if rate is None else ("Passed" if rate >= threshold else "Failed"),
        "No executed tests." if rate is None else f"Pass rate {rate}% ({passed} passed / {passed + failed} executed); baseline {threshold:g}% (proposed project baseline).")

    link = {d["test_case_id"] for d in defects if d["test_case_id"]}
    unrev = [t for t in tests if t["status"] == "Failed" and t["id"] not in link]
    add("failed_reviewed", "Failed tests reviewed", "Passed" if not unrev else "Failed",
        f"All {failed} failed tests have a linked defect." if not unrev else "Failed tests without defect: " + ", ".join(t["id"] for t in unrev))

    def category_check(key, name, cats):
        ts = [t for t in tests if t["category"] in cats]
        if not ts:
            add(key, name, "Pending", "No tests of this category exist.")
            return
        bad = [t for t in ts if t["status"] != "Passed"]
        add(key, name, "Passed" if not bad else "Failed",
            f"All {len(ts)} tests passed." if not bad else f"{len(bad)} of {len(ts)} not passed: " + ", ".join(t["id"] for t in bad))

    category_check("security_testing", "Security testing completed", {"Security Testing"})
    category_check("db_integrity", "Database integrity verified", {"Database Testing", "Data Validation Testing"})

    notappr = [d for d in docs if d["approval_status"] != "Approved"]
    add("documentation", "Documentation approved", "Passed" if docs and not notappr else "Failed",
        f"All {len(docs)} controlled documents approved." if docs and not notappr else f"{len(notappr)} of {len(docs)} not approved: " + ", ".join(d["id"] for d in notappr))

    rec = [t for t in tests if t["category"] == "Recovery Testing"]
    rec_ok = bool(rec) and all(t["status"] == "Passed" for t in rec)
    m = manual.get("backup_recovery")
    if not m or not m["confirmed"]:
        st = "Pending"
        det = "Awaiting confirmation by QA/Project Manager." + ("" if rec_ok else " Recovery tests not all passed.")
    elif not rec_ok:
        st, det = "Failed", "Confirmed manually but recovery tests are not all passed."
    else:
        st, det = "Passed", "Confirmed and all recovery tests passed."
    add("backup_recovery", MANUAL_CHECKS["backup_recovery"], st, det, True)

    m = manual.get("rollback_plan")
    add("rollback_plan", MANUAL_CHECKS["rollback_plan"], "Passed" if m and m["confirmed"] and (m["note"] or "").strip() else "Pending",
        "Rollback plan reference recorded." if m and m["confirmed"] and (m["note"] or "").strip() else "Record the rollback plan reference and confirm.", True)

    def approved(t):
        return any(r["review_type"] == t and r["decision"] in APPROVING for r in reviews)

    missing = [t for t in ("Security review", "Release review") if not approved(t)]
    add("approvals", "Required approvals recorded", "Passed" if not missing else "Failed",
        "Security review and release review approved." if not missing else "Approval missing: " + ", ".join(missing))
    return checks


def release_summary():
    checks = release_checks()
    passed = sum(1 for c in checks if c["status"] == "Passed")
    failed = sum(1 for c in checks if c["status"] == "Failed")
    pending = sum(1 for c in checks if c["status"] == "Pending")
    by = {c["key"]: c["status"] for c in checks}
    all_pass = passed == len(checks)
    conditional_ok = all(by[k] == "Passed" for k in ("critical_defects", "pass_rate", "security_testing", "approvals"))
    if all_pass:
        rec = "GO"
    elif conditional_ok:
        rec = "CONDITIONAL GO"
    else:
        rec = "NO-GO"
    return {"checks": checks, "passed": passed, "failed": failed, "pending": pending, "total": len(checks),
            "readiness_pct": pct(passed, len(checks)), "recommendation": rec,
            "go_allowed": all_pass, "conditional_allowed": conditional_ok}


# ------------------------------------------------------------------ metrics
def _status(v, good, warn, higher=True):
    if v is None:
        return "n/a"
    if higher:
        return "good" if v >= good else ("warning" if v >= warn else "critical")
    return "good" if v <= good else ("warning" if v <= warn else "critical")


def metrics():
    reqs = db.query("SELECT * FROM requirements")
    active = [r for r in reqs if r["status"] != "Rejected"]
    tests = db.query("SELECT * FROM test_cases")
    defects = db.query("SELECT * FROM defects")
    reviews = db.query("SELECT * FROM reviews")
    capas = db.query("SELECT * FROM capas")
    tr = rtm()
    rel = release_summary()
    thr = min_pass_rate()
    out = []

    def add(key, name, value, unit, formula, used, interp, status, extra=None):
        d = {"key": key, "name": name, "value": value, "unit": unit, "formula": formula, "used": used,
             "interpretation": interp, "status": status,
             "display": "Not measurable" if value is None else (f"{value}{unit}" if unit == "%" else (f"{value} {unit}".strip()))}
        if extra:
            d.update(extra)
        out.append(d)

    executed_reqs = len({t["requirement_id"] for t in tests if t["requirement_id"] and t["status"] in ("Passed", "Failed")
                         and any(r["id"] == t["requirement_id"] for r in active)})
    v = pct(executed_reqs, len(active))
    add("req_coverage", "Requirements Coverage", v, "%", "Active requirements with >=1 executed test / active requirements x 100",
        f"{executed_reqs} of {len(active)} requirements",
        "Share of requirements that have at least one executed test. Gaps leave requirements unverified.", _status(v, 90, 70))

    passed = sum(1 for t in tests if t["status"] == "Passed")
    failed = sum(1 for t in tests if t["status"] == "Failed")
    v = pct(passed, passed + failed)
    add("pass_rate", "Test Pass Rate", v, "%", "Passed tests / (Passed + Failed tests) x 100",
        f"{passed} passed, {failed} failed ({len(tests)} total tests)",
        f"Compared with the {thr:g}% proposed project baseline. Failures on data-integrity tests are weighted heavily in release decisions.",
        _status(v, thr, 60))

    dens = round(len(defects) / len(active), 2) if active else None
    add("defect_density", "Defect Density", dens, "defects/requirement", "Total defects / active requirements",
        f"{len(defects)} defects over {len(active)} requirements",
        "Requirements are the available size measure (code size is not collected), so density is per requirement.", _status(dens, 0.3, 0.6, False))

    resolved = sum(1 for d in defects if d["status"] in DEFECT_DONE)
    v = pct(resolved, len(defects))
    add("resolution_rate", "Defect Resolution Rate", v, "%", "Defects Resolved or Closed / total defects x 100",
        f"{resolved} of {len(defects)} defects", "Share of reported defects that have a documented fix.", _status(v, 80, 50))

    crit = sum(1 for d in defects if d["severity"] == "Critical" and d["status"] not in DEFECT_DONE)
    pcrit = sum(1 for d in defects if d["status"] not in DEFECT_DONE and patient_impact(d))
    add("critical_defects", "Critical Defect Count", crit, "open", "Defects with severity Critical not Resolved/Closed",
        f"{sum(1 for d in defects if d['severity'] == 'Critical')} critical defects in total; {pcrit} open defects affect patient data, prescriptions, labs, billing or access",
        "Any open critical defect blocks release.", "good" if crit == 0 else "critical")

    reopened = sum(1 for d in defects if d["reopen_count"] > 0)
    v = pct(reopened, len(defects))
    add("reopen_rate", "Defect Reopen Rate", v, "%", "Defects reopened at least once / total defects x 100",
        f"{reopened} of {len(defects)} defects", "High reopen rates indicate ineffective fixes or weak verification.", _status(v, 10, 20, False))

    open_d = [d for d in defects if d["status"] not in DEFECT_DONE]
    ages = [a for a in (_days(d["date_reported"]) for d in open_d) if a is not None]
    avg = round(sum(ages) / len(ages), 1) if ages else (0 if not open_d else None)
    add("defect_aging", "Defect Aging", avg, "days", "Average (today - date reported) for unresolved defects",
        f"{len(open_d)} unresolved defects; oldest {max(ages) if ages else 0} days",
        "Long-running defects increase operational and patient-data risk.", _status(avg, 14, 30, False))

    done = sum(1 for r in reviews if r["decision"])
    v = pct(done, len(reviews))
    add("review_completion", "Review Completion Rate", v, "%", "Reviews with recorded decision / total reviews x 100",
        f"{done} of {len(reviews)} reviews", "Reviews without a decision are not complete.", _status(v, 90, 70))

    appr = sum(1 for r in active if r["status"] in APPROVED_REQ)
    v = pct(appr, len(active))
    add("approval_rate", "Requirements Approval Rate", v, "%", "Requirements Approved/Implemented/Verified / active requirements x 100",
        f"{appr} of {len(active)} requirements", "Requirements still Draft or Under Review are not baselined.", _status(v, 90, 70))

    closed = sum(1 for c in capas if c["status"] == "Closed")
    v = pct(closed, len(capas))
    add("capa_rate", "CAPA Completion Rate", v, "%", "CAPAs Closed (with effectiveness verification) / total CAPAs x 100",
        f"{closed} of {len(capas)} CAPAs", "Closure requires documented effectiveness verification.", _status(v, 80, 50))

    full = sum(1 for x in tr["rows"] if x["status"] != "Rejected" and x["tests"] and x["need_id"] and (x["design_ref"] or "").strip())
    v = pct(full, len(active))
    add("traceability", "Requirements-to-Test Traceability", v, "%", "Requirements with stakeholder need + design link + >=1 test / active requirements x 100",
        f"{full} of {len(active)} requirements", "Complete forward traceability supports impact analysis and audit.", _status(v, 95, 75))

    add("release_readiness", "Release Readiness", rel["readiness_pct"], "%", "Mandatory gate checks passed / total checks x 100",
        f"{rel['passed']} of {rel['total']} checks", f"Recommendation: {rel['recommendation']}.",
        _status(rel["readiness_pct"], 100, 75))
    return out


def quality_score():
    m = {x["key"]: x for x in metrics()}
    weights = [("pass_rate", 25), ("req_coverage", 15), ("approval_rate", 15), ("resolution_rate", 15),
               ("review_completion", 10), ("capa_rate", 10), ("traceability", 10)]
    total = sum(w for _, w in weights)
    base = sum((m[k]["value"] or 0) * w for k, w in weights) / total
    crit = m["critical_defects"]["value"] or 0
    penalty = min(30, 10 * crit)
    score = max(0.0, round(base - penalty, 1))
    rating = "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs improvement" if score >= 50 else "At risk"
    return {"score": score, "rating": rating, "penalty": penalty, "base": round(base, 1),
            "formula": "Weighted average of Test Pass Rate 25, Requirements Coverage 15, Approval Rate 15, Defect Resolution 15, Review Completion 10, CAPA Completion 10, Traceability 10; minus 10 per open critical defect (max 30)."}


# ------------------------------------------------------------------ charts + dashboard
def chart_data():
    defects = db.query("SELECT * FROM defects")
    tests = db.query("SELECT status, COUNT(*) n FROM test_cases GROUP BY status")
    reqs = db.query("SELECT status, COUNT(*) n FROM requirements GROUP BY status")
    sev = {s: sum(1 for d in defects if d["severity"] == s) for s in SEVERITIES}
    by_module = {c: 0 for c in REQ_CATEGORIES}
    rq = {r["id"]: r["category"] for r in db.query("SELECT id, category FROM requirements")}
    for d in defects:
        mod = rq.get(d["requirement_id"], "Unassigned")
        by_module[mod] = by_module.get(mod, 0) + 1
    by_module = {k: v for k, v in by_module.items() if v}
    months = {}
    for d in defects:
        k = (d["date_reported"] or "")[:7]
        if k:
            months.setdefault(k, {"reported": 0, "closed": 0})["reported"] += 1
        if d["closed_on"]:
            months.setdefault(d["closed_on"][:7], {"reported": 0, "closed": 0})["closed"] += 1
    keys = sorted(months)
    trend = {"labels": keys, "reported": [months[k]["reported"] for k in keys], "closed": [months[k]["closed"] for k in keys],
             "available": len(keys) >= 2}
    tmap = {t["status"]: t["n"] for t in tests}
    rmap = {r["status"]: r["n"] for r in reqs}
    from domain import REQ_STATUS
    return {
        "severity": {"labels": SEVERITIES, "values": [sev[s] for s in SEVERITIES]},
        "tests": {"labels": TEST_STATUS, "values": [tmap.get(s, 0) for s in TEST_STATUS]},
        "requirements": {"labels": REQ_STATUS, "values": [rmap.get(s, 0) for s in REQ_STATUS]},
        "defect_status": {"labels": DEFECT_STATUS, "values": [sum(1 for d in defects if d["status"] == s) for s in DEFECT_STATUS]},
        "modules": {"labels": list(by_module), "values": list(by_module.values())},
        "trend": trend,
    }


def lifecycle_progress():
    docs = db.query("SELECT approval_status FROM documents")
    reqs = db.query("SELECT status FROM requirements WHERE status!='Rejected'")
    tests = db.query("SELECT status FROM test_cases")
    reviews = db.query("SELECT decision FROM reviews")
    capas = db.query("SELECT status FROM capas")
    reports = db.query("SELECT COUNT(*) n FROM activity_log WHERE action='report'", one=True)["n"]
    ms = metrics()
    measured = sum(1 for m in ms if m["value"] is not None)
    rel = release_summary()
    vals = {
        "PLAN": pct(sum(1 for d in docs if d["approval_status"] == "Approved"), len(docs)),
        "DEFINE": pct(sum(1 for r in reqs if r["status"] in APPROVED_REQ), len(reqs)),
        "EXECUTE": pct(sum(1 for t in tests if t["status"] in ("Passed", "Failed")), len(tests)),
        "VERIFY": pct(sum(1 for r in reviews if r["decision"]), len(reviews)),
        "MEASURE": pct(measured, len(ms)),
        "REPORT": 100.0 if reports else 0.0,
        "IMPROVE": pct(sum(1 for c in capas if c["status"] == "Closed"), len(capas)),
    }
    out = []
    for stage, desc, modules, route in LIFECYCLE:
        out.append({"stage": stage, "description": desc, "modules": modules, "route": route, "progress": vals[stage] or 0.0})
    # REPORT progress is 100 only after a report has been generated; blend with release readiness for the gate
    return out


def risk_summary():
    tr = rtm()
    reqs = tr["rows"]
    high = [x for x in reqs if x["risk"] in ("Critical", "High") and x["status"] != "Rejected"]
    unverified_high = [x for x in high if not x["verified"]]
    defects = db.query("SELECT * FROM defects")
    open_pat = [d for d in defects if d["status"] not in DEFECT_DONE and patient_impact(d)]
    return {
        "by_risk": {lv: sum(1 for x in reqs if x["risk"] == lv and x["status"] != "Rejected") for lv in ("Critical", "High", "Medium", "Low")},
        "high_risk_total": len(high), "high_risk_unverified": len(unverified_high),
        "high_risk_unverified_ids": [x["id"] for x in unverified_high],
        "patient_data_defects_open": len(open_pat), "patient_data_defect_ids": [d["id"] for d in open_pat],
        "failed_tests_without_defect": [t["id"] for t in db.query(
            "SELECT t.id FROM test_cases t WHERE t.status='Failed' AND NOT EXISTS (SELECT 1 FROM defects d WHERE d.test_case_id=t.id)")],
    }


def alerts():
    out = []
    defects = db.query("SELECT * FROM defects")
    for d in defects:
        if d["status"] in DEFECT_DONE:
            continue
        if d["severity"] == "Critical":
            out.append({"level": "critical", "text": f"{d['id']} (Critical, {d['category']}) is {d['status']}: {d['title']}", "route": "defects", "id": d["id"]})
        elif patient_impact(d):
            out.append({"level": "warning", "text": f"{d['id']} (High, {d['category']}) affects patient data and is {d['status']}", "route": "defects", "id": d["id"]})
    for t in risk_summary()["failed_tests_without_defect"]:
        out.append({"level": "warning", "text": f"Failed test {t} has no linked defect", "route": "testing", "id": t})
    for r in db.query("SELECT * FROM reviews WHERE decision IS NULL OR decision=''"):
        dd = _days(r["due_date"])
        if dd is not None and dd > 0:
            out.append({"level": "warning", "text": f"{r['id']} {r['review_type']} is overdue by {dd} days", "route": "reviews", "id": r["id"]})
    for r in db.query("SELECT * FROM reviews WHERE decision IN ('Rework required','Rejected') AND finding_severity='Critical'"):
        out.append({"level": "critical", "text": f"{r['id']} {r['review_type']} needs rework with a critical finding", "route": "reviews", "id": r["id"]})
    for c in db.query("SELECT * FROM capas WHERE status!='Closed'"):
        dd = _days(c["target_date"])
        if dd is not None and dd > 0:
            out.append({"level": "warning", "text": f"{c['id']} is overdue by {dd} days", "route": "capa", "id": c["id"]})
    rel = release_summary()
    if rel["recommendation"] == "NO-GO":
        out.append({"level": "critical", "text": f"Release gate: NO-GO - {rel['failed']} checks failed, {rel['pending']} pending", "route": "release", "id": ""})
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda a: order[a["level"]])
    return out


def deadlines():
    out = []
    for r in db.query("SELECT * FROM reviews WHERE decision IS NULL OR decision=''"):
        out.append({"kind": "Review", "id": r["id"], "title": r["title"], "due": r["due_date"], "owner": r["reviewer"], "route": "reviews"})
    for c in db.query("SELECT * FROM capas WHERE status!='Closed'"):
        out.append({"kind": "CAPA", "id": c["id"], "title": c["problem"], "due": c["target_date"], "owner": c["owner"], "route": "capa"})
    for x in out:
        dd = _days(x["due"]) if x["due"] else None
        x["days_left"] = None if dd is None else -dd
        x["overdue"] = dd is not None and dd > 0
    out.sort(key=lambda x: (x["due"] or "9999"))
    return out[:10]


def dashboard():
    reqs = db.query("SELECT status FROM requirements")
    tests = db.query("SELECT status FROM test_cases")
    defects = db.query("SELECT * FROM defects")
    reviews = db.query("SELECT decision FROM reviews")
    ms = {m["key"]: m for m in metrics()}
    rel = release_summary()
    qs = quality_score()
    capas = db.query("SELECT status FROM capas")
    kpis = {
        "total_requirements": len(reqs),
        "approved_requirements": sum(1 for r in reqs if r["status"] in APPROVED_REQ),
        "pending_review_requirements": sum(1 for r in reqs if r["status"] in ("Draft", "Under Review")),
        "total_tests": len(tests), "passed_tests": sum(1 for t in tests if t["status"] == "Passed"),
        "failed_tests": sum(1 for t in tests if t["status"] == "Failed"),
        "open_defects": sum(1 for d in defects if d["status"] not in DEFECT_DONE),
        "critical_defects": ms["critical_defects"]["value"],
        "completed_reviews": sum(1 for r in reviews if r["decision"]),
        "pending_approvals": sum(1 for r in reviews if not r["decision"]),
        "pass_rate": ms["pass_rate"]["value"], "traceability": ms["traceability"]["value"],
        "capa_rate": ms["capa_rate"]["value"], "quality_score": qs["score"], "quality_rating": qs["rating"],
        "release_readiness": rel["readiness_pct"], "release_recommendation": rel["recommendation"],
        "total_capas": len(capas),
    }
    act = db.query("SELECT * FROM activity_log ORDER BY id DESC LIMIT 8")
    return {"kpis": kpis, "charts": chart_data(), "lifecycle": lifecycle_progress(), "risk": risk_summary(),
            "alerts": alerts()[:8], "deadlines": deadlines(), "activity": act, "score": qs,
            "quality_performance": {"labels": [ms[k]["name"] for k in ("pass_rate", "req_coverage", "approval_rate", "resolution_rate", "review_completion", "capa_rate", "traceability")],
                                    "values": [ms[k]["value"] or 0 for k in ("pass_rate", "req_coverage", "approval_rate", "resolution_rate", "review_completion", "capa_rate", "traceability")]}}
