"""Persistent SQLite layer for HOSPITAL QUALITY OS (Team 2 - Hospital Management Software QMS)."""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get(
    "HQOS_DB",
    os.path.join(BASE_DIR, "data", "hospital_qms.db")
)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, args=(), one=False):
    conn = connect()
    try:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    conn = connect()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS team_members (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL, email TEXT);
CREATE TABLE IF NOT EXISTS stakeholder_needs (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT);
CREATE TABLE IF NOT EXISTS requirements (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
  category TEXT NOT NULL, req_type TEXT NOT NULL DEFAULT 'Functional', quality_factor TEXT,
  priority TEXT NOT NULL, risk TEXT NOT NULL, owner TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft', acceptance_criteria TEXT NOT NULL,
  design_ref TEXT, impl_ref TEXT,
  need_id TEXT REFERENCES stakeholder_needs(id) ON DELETE SET NULL,
  approved_by TEXT, approved_on TEXT, created_on TEXT);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, review_type TEXT NOT NULL, title TEXT NOT NULL,
  artifact TEXT NOT NULL, artifact_version TEXT, reviewer TEXT,
  review_date TEXT, due_date TEXT, findings TEXT, finding_severity TEXT, comments TEXT,
  decision TEXT, approval_status TEXT NOT NULL DEFAULT 'Pending',
  checklist TEXT, created_on TEXT);
CREATE TABLE IF NOT EXISTS review_requirements (
  review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  requirement_id TEXT NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  PRIMARY KEY (review_id, requirement_id));
CREATE TABLE IF NOT EXISTS test_cases (
  id TEXT PRIMARY KEY, scenario TEXT NOT NULL,
  requirement_id TEXT REFERENCES requirements(id) ON DELETE SET NULL,
  category TEXT NOT NULL, preconditions TEXT, steps TEXT NOT NULL, expected TEXT NOT NULL,
  actual TEXT, tester TEXT, exec_date TEXT, status TEXT NOT NULL DEFAULT 'Not Run', evidence TEXT);
CREATE TABLE IF NOT EXISTS defects (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
  category TEXT NOT NULL, severity TEXT NOT NULL, priority TEXT NOT NULL,
  steps TEXT, expected TEXT, actual TEXT, assigned_to TEXT, reported_by TEXT,
  date_reported TEXT NOT NULL,
  requirement_id TEXT REFERENCES requirements(id) ON DELETE SET NULL,
  test_case_id TEXT REFERENCES test_cases(id) ON DELETE SET NULL,
  resolution TEXT, verification_result TEXT, status TEXT NOT NULL DEFAULT 'Open',
  resolved_on TEXT, closed_on TEXT, reopen_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS capas (
  id TEXT PRIMARY KEY,
  defect_id TEXT REFERENCES defects(id) ON DELETE SET NULL,
  problem TEXT NOT NULL, root_cause TEXT,
  why1 TEXT, why2 TEXT, why3 TEXT, why4 TEXT, why5 TEXT,
  containment TEXT, corrective TEXT, preventive TEXT,
  owner TEXT NOT NULL, target_date TEXT, status TEXT NOT NULL DEFAULT 'Open',
  verification_evidence TEXT, effectiveness_review TEXT,
  closure_approved_by TEXT, closed_on TEXT, created_on TEXT);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, doc_key TEXT, title TEXT NOT NULL, doc_type TEXT NOT NULL,
  version TEXT NOT NULL, owner TEXT NOT NULL, created_on TEXT, updated_on TEXT,
  approval_status TEXT NOT NULL DEFAULT 'Draft', description TEXT,
  review_date TEXT, approved_by TEXT, approved_on TEXT);
CREATE TABLE IF NOT EXISTS document_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  version TEXT NOT NULL, changed_on TEXT, changed_by TEXT, summary TEXT, approval_status TEXT, approved_by TEXT);
CREATE TABLE IF NOT EXISTS release_manual (
  check_key TEXT PRIMARY KEY, confirmed INTEGER NOT NULL DEFAULT 0, note TEXT,
  updated_by TEXT, updated_on TEXT);
CREATE TABLE IF NOT EXISTS release_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, release_version TEXT, decision TEXT NOT NULL,
  rationale TEXT, conditions TEXT, decided_by TEXT, decided_on TEXT, snapshot TEXT);
CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, action TEXT,
  entity TEXT, entity_id TEXT, detail TEXT);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


def ahead(n):
    return (date.today() + timedelta(days=n)).isoformat()


def log(actor, action, entity, entity_id, detail=""):
    execute("INSERT INTO activity_log(ts,actor,action,entity,entity_id,detail) VALUES(?,?,?,?,?,?)",
            (now(), actor, action, entity, entity_id, detail))


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))


def init_db(seed=True, force=False):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = connect()
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
    if "review_date" not in cols:  # database from the earlier 10-document build: upgrade in place
        for col in ("review_date", "approved_by", "approved_on"):
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT")
    conn.commit()
    migrate_documents(conn)
    empty = conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0] == 0 and \
        conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
    conn.close()
    if seed and empty:
        seed_data()


# ---------------------------------------------------------------- seed data
TEAM = [
    ("Team2 Project Manager", "Project Manager"), ("Team2 QA Lead", "Quality Assurance Lead"),
    ("Team2 Business Analyst", "Business Analyst"), ("Team2 Architect", "Technical Architect"),
    ("Team2 Developer A", "Developer"), ("Team2 Developer B", "Developer"),
    ("Team2 Test Manager", "Test Manager"), ("Team2 Reviewer", "Reviewer"),
]
PM, QA, BA, ARCH, DEVA, DEVB, TM, REVW = [t[0] for t in TEAM]

NEEDS = [
    ("SN-01", "Every patient is identified uniquely and correctly", "Front desk and clinicians must trust that a record belongs to exactly one real patient."),
    ("SN-02", "Appointments are scheduled without conflicts", "Doctors and patients must never be double booked."),
    ("SN-03", "Doctor information is current and reliable", "Specialisation, availability and profile data drive scheduling and prescriptions."),
    ("SN-04", "Laboratory results are trustworthy", "A result must always be attached to the right patient and sample."),
    ("SN-05", "Billing is accurate and auditable", "Charges, taxes, discounts and payments must reconcile."),
    ("SN-06", "Prescriptions are safe and traceable", "Prescriptions must be tied to the correct patient and prescribing doctor."),
    ("SN-07", "Complete and accurate patient history is available", "Clinicians need a correct chronological record."),
    ("SN-08", "Confidential patient information is protected", "Only authorised roles may view or change patient data."),
    ("SN-09", "The hospital system stays available and responsive", "Failures and slow responses disrupt hospital operations."),
    ("SN-10", "The software remains maintainable and documented", "The organisation must be able to support and change the system safely."),
]

# id, title, description, category, type, factor, priority, risk, owner, status, acceptance, design, impl, need, approver, approved_days_ago
REQS = [
    ("REQ-001", "Register patient with mandatory demographics", "The system shall register a new patient capturing name, date of birth, gender, contact number, address and emergency contact, and assign a unique Medical Record Number (MRN).", "Patient Registration", "Functional", "Data Accuracy", "High", "High", DEVA, "Verified", "All mandatory fields validated; a unique MRN is generated; record is retrievable by MRN.", "DD-PR-01 Registration form & MRN generator", "PatientService.register()", "SN-01", REVW, 38),
    ("REQ-002", "Detect duplicate patient records", "The system shall detect probable duplicate registrations using name, date of birth and phone number matching and require user confirmation before creating a new record.", "Patient Registration", "Functional", "Data Integrity", "Critical", "Critical", DEVA, "Approved", "Duplicates with identical name+DOB are blocked regardless of letter case or spacing.", "DD-PR-02 Duplicate matching rules", "PatientService.findDuplicates()", "SN-01", REVW, 38),
    ("REQ-003", "Book appointment with an available doctor", "The system shall allow booking an appointment only for a doctor who is available in the selected time slot.", "Appointment Management", "Functional", "Reliability", "High", "Medium", DEVB, "Verified", "Booking succeeds for available slots and the slot is marked occupied.", "DD-AP-01 Scheduling workflow", "AppointmentService.book()", "SN-02", REVW, 38),
    ("REQ-004", "Prevent double booking of doctor and time slot", "The system shall prevent two appointments for the same doctor and time slot, including concurrent requests.", "Appointment Management", "Functional", "Data Integrity", "Critical", "High", DEVB, "Approved", "Second booking for an occupied slot is rejected with a clear message even under concurrent submission.", "DD-AP-02 Slot locking strategy", "AppointmentService.lockSlot()", "SN-02", REVW, 38),
    ("REQ-005", "Maintain doctor profile and specialisation", "The system shall maintain doctor profiles including registration number, specialisation, department and contact details.", "Doctor Management", "Functional", "Data Accuracy", "Medium", "Low", DEVA, "Implemented", "Doctor records can be created and edited; specialisation is never saved blank.", "DD-DR-01 Doctor master data", "DoctorService.save()", "SN-03", REVW, 30),
    ("REQ-006", "Maintain doctor availability schedule", "The system shall maintain weekly availability and leave schedules per doctor to drive appointment slots.", "Doctor Management", "Functional", "Reliability", "Medium", "Medium", DEVB, "Approved", "Availability changes are reflected in new slot generation within one minute.", "DD-DR-02 Availability calendar", "DoctorSchedule.generateSlots()", "SN-03", REVW, 30),
    ("REQ-007", "Associate laboratory results with the correct patient", "The system shall bind each laboratory result to the patient and sample identifier, rejecting results whose identifiers do not match.", "Laboratory Management", "Functional", "Data Accuracy", "Critical", "Critical", DEVA, "Approved", "A result posted with a mismatched MRN/sample ID is rejected and logged.", "DD-LB-01 Result-to-patient binding", "LabResultService.attach()", "SN-04", REVW, 30),
    ("REQ-008", "Validate laboratory result values and units", "The system shall validate numeric ranges and units for laboratory results and flag abnormal values for clinician review.", "Laboratory Management", "Functional", "Data Accuracy", "High", "High", DEVB, "Under Review", "Out-of-range and wrong-unit values are flagged before publication.", "DD-LB-02 Reference range engine", "LabValidation.check()", "SN-04", None, None),
    ("REQ-009", "Calculate bill totals accurately", "The system shall compute bill totals from itemised charges, discounts and taxes with correct rounding rules.", "Billing Management", "Functional", "Data Accuracy", "Critical", "High", DEVA, "Approved", "Totals match independently calculated expected values to two decimal places.", "DD-BL-01 Billing calculation rules", "BillingService.calculate()", "SN-05", REVW, 28),
    ("REQ-010", "Record payments and generate receipts", "The system shall record payments against bills, update outstanding balances and generate receipts.", "Billing Management", "Functional", "Auditability", "High", "Medium", DEVB, "Implemented", "Each payment creates exactly one receipt and reduces the outstanding balance correctly.", "DD-BL-02 Payment ledger", "PaymentService.record()", "SN-05", REVW, 28),
    ("REQ-011", "Link prescription to correct patient and doctor", "The system shall associate every prescription with the prescribing doctor and the patient encounter, preventing orphan or mismatched prescriptions.", "Prescription Management", "Functional", "Data Accuracy", "Critical", "Critical", DEVA, "Approved", "Prescription shows the correct patient MRN and prescribing doctor on screen and print.", "DD-RX-01 Prescription aggregate", "PrescriptionService.create()", "SN-06", REVW, 28),
    ("REQ-012", "Validate drug allergy and dosage", "The system shall warn when a prescribed drug conflicts with recorded allergies or exceeds configured dosage limits.", "Prescription Management", "Functional", "Data Accuracy", "Critical", "Critical", DEVB, "Under Review", "Known allergy conflicts produce a blocking warning that requires doctor override with reason.", "DD-RX-02 Clinical rule checks", None, "SN-06", None, None),
    ("REQ-013", "Display chronological patient history", "The system shall display a patient's visits, diagnoses, lab results and prescriptions in correct chronological order.", "Patient History", "Functional", "Data Accuracy", "High", "High", DEVA, "Approved", "History items are ordered by event timestamp; same-day entries preserve entry order.", "DD-PH-01 Timeline aggregation", "HistoryService.timeline()", "SN-07", REVW, 25),
    ("REQ-014", "Maintain immutable audit trail of history changes", "The system shall record who changed patient history, when, and the previous value; audit records cannot be edited.", "Patient History", "Non-functional", "Auditability", "High", "Medium", DEVB, "Draft", "Every change creates an append-only audit entry visible to authorised auditors.", None, None, "SN-07", None, None),
    ("REQ-015", "Enforce role-based access control", "The system shall restrict access to confidential patient information according to user role (doctor, nurse, receptionist, billing, admin).", "Data Security", "Non-functional", "Security and Privacy", "Critical", "Critical", ARCH, "Approved", "Users can only access data permitted by their role; denied attempts are logged.", "DD-SC-01 RBAC matrix", "AuthorizationFilter", "SN-08", REVW, 25),
    ("REQ-016", "Protect confidential data in transit and at rest", "The system shall encrypt confidential data in transit (TLS) and at rest, and mask sensitive fields in logs.", "Data Security", "Non-functional", "Security and Privacy", "High", "High", ARCH, "Approved", "All endpoints use TLS; sensitive columns are encrypted; logs contain no raw identifiers.", "DD-SC-02 Encryption design", "CryptoService", "SN-08", REVW, 25),
    ("REQ-017", "Maintain referential integrity and transaction consistency", "The system shall ensure related records (patient, appointment, billing) stay consistent and roll back fully when a transaction fails.", "Data Integrity", "Non-functional", "Data Integrity", "Critical", "Critical", ARCH, "Approved", "After any failed transaction no partial or orphan records remain.", "DD-DB-01 ERD & transaction boundaries", "TransactionManager", "SN-01", REVW, 25),
    ("REQ-018", "Validate clinical and demographic inputs", "The system shall validate data types, mandatory fields, ranges and formats on all clinical and demographic inputs.", "Data Integrity", "Functional", "Data Accuracy", "High", "Medium", DEVA, "Approved", "Invalid input is rejected with a field-level message; valid input is stored unchanged.", "DD-DB-02 Validation rules catalogue", "ValidationService", "SN-01", REVW, 25),
    ("REQ-019", "Backup and recovery within RPO/RTO", "The system shall support scheduled backups and restoration within the agreed recovery point and recovery time objectives.", "System Reliability", "Non-functional", "Availability", "High", "High", ARCH, "Approved", "A full restore from backup succeeds within the agreed RTO with no data loss beyond RPO.", "DD-OP-01 Backup strategy", "BackupJob", "SN-09", REVW, 20),
    ("REQ-020", "Fail gracefully with meaningful error handling", "The system shall handle faults gracefully, avoid data loss on crash and show non-technical error messages.", "System Reliability", "Non-functional", "Reliability", "Medium", "Medium", DEVB, "Under Review", "Application restarts after a crash without corrupting data; errors are logged.", None, None, "SN-09", None, None),
    ("REQ-021", "Patient search returns within 3 seconds", "The system shall return patient search results in under 3 seconds for databases up to 500,000 patients.", "Performance", "Non-functional", "Performance Efficiency", "Medium", "Medium", ARCH, "Approved", "95th percentile search time is below 3 seconds in the performance test environment.", "DD-PF-01 Index strategy", "PatientSearchIndex", "SN-09", REVW, 20),
    ("REQ-022", "Support 200 concurrent users", "The system shall support 200 concurrent users without functional errors or unacceptable degradation.", "Performance", "Non-functional", "Performance Efficiency", "Medium", "High", ARCH, "Draft", "Load test with 200 users completes with error rate below 1%.", None, None, "SN-09", None, None),
    ("REQ-023", "Modular code structure and coding standard", "The system shall follow a modular architecture and the agreed coding standard enforced through code review.", "Maintainability", "Non-functional", "Maintainability", "Low", "Low", ARCH, "Approved", "Static analysis reports no blocker violations; modules have defined interfaces.", "DD-AR-01 Module structure", "All modules", "SN-10", REVW, 20),
    ("REQ-024", "Maintain current technical and user documentation", "The system shall have approved technical, user and operations documentation updated with every release.", "Maintainability", "Non-functional", "Maintainability", "Medium", "Low", BA, "Under Review", "Documentation set is reviewed and approved before release.", None, None, "SN-10", None, None),
]

# id, type, title, artifact, version, reviewer, review_days_ago, due_offset(days from today), findings, finding_sev, comments, decision, requirement ids
REVIEWS = [
    ("REV-001", "Requirement review", "Requirement review - Patient Registration and Appointments", "Software Requirements Specification: PR & AP", "v1.0", QA, 40, -38, "Duplicate-matching rule wording clarified.", "Low", "Requirements are testable and unambiguous.", "Approved", ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]),
    ("REV-002", "Requirement review", "Requirement review - Doctor and Laboratory", "Software Requirements Specification: DR & LB", "v1.0", QA, 32, -30, "Add result-to-sample identifier check to acceptance criteria.", "Medium", "Approved after the action is recorded.", "Approved with actions", ["REQ-005", "REQ-006", "REQ-007"]),
    ("REV-003", "Requirement review", "Requirement review - Billing and Prescription", "Software Requirements Specification: BL & RX", "v1.0", REVW, 30, -28, "Rounding rule must be explicit; prescription-doctor linkage to be tested end to end.", "Medium", "Approved with actions.", "Approved with actions", ["REQ-009", "REQ-010", "REQ-011"]),
    ("REV-004", "Requirement review", "Requirement review - History, Security and Integrity", "Software Requirements Specification: PH, SC, DI", "v1.1", QA, 27, -25, "", "Low", "Reviewed against hospital data-protection checklist.", "Approved", ["REQ-013", "REQ-015", "REQ-016", "REQ-017", "REQ-018"]),
    ("REV-005", "Requirement review", "Requirement review - Reliability, Performance, Maintainability", "Software Requirements Specification: NFR", "v1.0", REVW, 22, -20, "RTO value to be confirmed with hospital IT.", "Low", "Approved.", "Approved", ["REQ-019", "REQ-021", "REQ-023"]),
    ("REV-006", "Database design review", "Database design review - Hospital core schema", "Hospital DB ERD", "v1.2", ARCH, 24, -22, "Add composite unique index for doctor_id + slot_time; add FK from lab_result to sample.", "High", "Approved with actions; actions tracked under DEF-002 and DEF-003.", "Approved with actions", ["REQ-017", "REQ-002", "REQ-004"]),
    ("REV-007", "Security review", "Security review - Access control and encryption", "Security Design Document", "v0.9", REVW, 12, -10, "Audit logging for denied access attempts is incomplete; receptionist role over-permissive.", "Critical", "Rework required before approval.", "Rework required", ["REQ-015", "REQ-016"]),
    ("REV-008", "Code review", "Code review - Billing module", "BillingService source", "v0.9", QA, 15, -13, "Floating point used for currency in two places.", "High", "Approved after BigDecimal fix confirmed (DEF-004).", "Approved with actions", ["REQ-009", "REQ-010"]),
    ("REV-009", "Test plan review", "Test plan review - System test plan", "Hospital System Test Plan", "v1.0", TM, 20, -18, "", "Low", "Coverage of recovery and security tests confirmed.", "Approved", []),
    ("REV-010", "Requirement review", "Requirement review - Laboratory validation, prescription safety, reliability", "Software Requirements Specification: LB2, RX2, REL2", "v1.0", QA, 5, 3, "Acceptance criteria for allergy override reason missing; dosage limits not defined.", "High", "Rework required.", "Rework required", ["REQ-008", "REQ-012", "REQ-020"]),
    ("REV-011", "Documentation review", "Documentation review - User and operations manuals", "Documentation set", "v0.5", REVW, None, 6, "", "", "", None, ["REQ-024"]),
    ("REV-012", "Release review", "Release review - Release 1.0 candidate", "Release 1.0 candidate package", "RC1", PM, None, 12, "", "", "", None, []),
]

# id, scenario, req, category, precond, steps, expected, actual, tester, days_ago, status, evidence
TESTS = [
    ("TC-001", "Verify patient registration with valid information", "REQ-001", "System Testing", "Front-desk user logged in.", "1. Open registration form\n2. Enter valid demographic details\n3. Submit", "Patient saved with a unique MRN and visible in search.", "Patient saved; MRN generated; visible in search.", TM, 18, "Passed", "EV-TC001-registration.png"),
    ("TC-002", "Prevent duplicate patient registration", "REQ-002", "Data Validation Testing", "Patient 'Test Patient A' (DOB 1990-01-01) already exists.", "1. Register 'test patient a' with the same DOB\n2. Submit", "System blocks registration and shows probable duplicate.", "Duplicate record was created because matching is case sensitive.", TM, 16, "Failed", "EV-TC002-duplicate.png"),
    ("TC-003", "Verify appointment booking for an available doctor", "REQ-003", "System Testing", "Doctor has free slot at 10:00.", "1. Select doctor\n2. Select 10:00 slot\n3. Confirm booking", "Appointment created and slot marked occupied.", "Appointment created; slot occupied.", TM, 18, "Passed", "EV-TC003.png"),
    ("TC-004", "Prevent double booking of the same doctor and time slot", "REQ-004", "Integration Testing", "Slot 10:00 booked for doctor D1.", "1. Book same doctor and slot twice in parallel", "Second booking rejected.", "Two bookings accepted when submitted within one second.", TM, 15, "Failed", "EV-TC004-race.log"),
    ("TC-005", "Verify laboratory result association with the correct patient", "REQ-007", "Integration Testing", "Two patients with similar MRNs exist.", "1. Post result with sample S1\n2. Open patient record", "Result appears only on the patient owning sample S1.", "Result attached to patient with reused MRN suffix.", TM, 14, "Failed", "EV-TC005-lab.png"),
    ("TC-006", "Verify billing calculations and payment records", "REQ-009", "Unit Testing", "Bill with discount and tax configured.", "1. Create bill with 3 items\n2. Apply 10% discount and 5% tax\n3. Compare with expected total", "Total equals independently calculated value.", "Matches expected after BigDecimal fix (retest).", DEVA, 9, "Passed", "EV-TC006-unit.txt"),
    ("TC-007", "Ensure prescriptions are associated with the correct patient and doctor", "REQ-011", "Integration Testing", "Doctor and patient exist.", "1. Create prescription\n2. Print prescription", "Prescription shows correct patient MRN and prescribing doctor.", "Correct patient and doctor shown after fix.", TM, 8, "Passed", "EV-TC007.pdf"),
    ("TC-008", "Verify unauthorized users cannot access confidential patient information", "REQ-015", "Security Testing", "Receptionist account exists.", "1. Log in as receptionist\n2. Request clinical notes URL", "Access denied (HTTP 403) and attempt logged.", "Receptionist could view clinical notes.", TM, 12, "Failed", "EV-TC008-authz.png"),
    ("TC-009", "Verify patient history displays accurate historical records", "REQ-013", "System Testing", "Patient with 5 historical encounters.", "1. Open history timeline", "Entries appear in chronological order with correct data.", "Chronological and accurate.", TM, 10, "Passed", "EV-TC009.png"),
    ("TC-010", "Verify database consistency after a failed transaction", "REQ-017", "Database Testing", "Fault injected after appointment insert.", "1. Start appointment+billing transaction\n2. Inject failure on billing insert\n3. Inspect tables", "No partial appointment or billing rows remain.", "Appointment row remained without billing row.", TM, 11, "Failed", "EV-TC010-db.sql"),
    ("TC-011", "Validate mandatory and format rules on patient input fields", "REQ-018", "Unit Testing", "Validation service available.", "1. Submit empty name\n2. Submit invalid phone\n3. Submit valid data", "Invalid inputs rejected; valid input accepted.", "As expected.", DEVA, 17, "Passed", "EV-TC011.txt"),
    ("TC-012", "Doctor profile create and edit retains specialisation", "REQ-005", "Unit Testing", "Admin logged in.", "1. Create doctor\n2. Edit contact only\n3. Check specialisation", "Specialisation unchanged.", "Specialisation retained after fix.", DEVA, 13, "Passed", "EV-TC012.txt"),
    ("TC-013", "Doctor availability changes regenerate slots", "REQ-006", "System Testing", "Doctor schedule exists.", "1. Mark doctor on leave\n2. Check slots", "Slots for leave day removed.", "", TM, None, "Not Run", ""),
    ("TC-014", "Payment record updates balance and issues receipt", "REQ-010", "Integration Testing", "Open bill of 1000.00.", "1. Pay 400.00\n2. View bill and receipt", "Outstanding balance 600.00 and one receipt.", "Balance 600.00 and one receipt.", TM, 9, "Passed", "EV-TC014.png"),
    ("TC-015", "Verify encryption in transit", "REQ-016", "Security Testing", "Test environment with TLS.", "1. Capture traffic\n2. Inspect protocol", "All traffic encrypted using TLS 1.2+.", "TLS 1.2 confirmed.", TM, 11, "Passed", "EV-TC015.pcap"),
    ("TC-016", "Restore system from backup within RTO", "REQ-019", "Recovery Testing", "Nightly backup available.", "1. Simulate server loss\n2. Restore latest backup\n3. Validate data", "Restore completed within RTO; data consistent.", "Restored in 42 minutes; data consistent.", TM, 7, "Passed", "EV-TC016-restore.log"),
    ("TC-017", "Patient search response time", "REQ-021", "Performance Testing", "100,000 patient records loaded.", "1. Run 100 searches\n2. Measure p95", "p95 below 3 seconds.", "p95 = 1.8 seconds.", TM, 6, "Passed", "EV-TC017-perf.csv"),
    ("TC-018", "Regression of registration after duplicate-check fix", "REQ-002", "Regression Testing", "Fix for DEF-001 deployed to test.", "1. Re-run TC-001 and TC-002", "Both pass.", "", TM, 1, "In Progress", ""),
    ("TC-019", "UAT: front desk registers walk-in patient end to end", "REQ-001", "User Acceptance Testing", "UAT users trained.", "1. Register walk-in patient\n2. Book appointment", "Task completed without assistance.", "Completed in 3 minutes.", REVW, 5, "Passed", "EV-TC019-uat.pdf"),
    ("TC-020", "UAT: doctor creates prescription during consultation", "REQ-011", "User Acceptance Testing", "UAT environment available.", "1. Doctor opens consultation\n2. Issues prescription", "Prescription issued correctly.", "", REVW, None, "Blocked", ""),
    ("TC-021", "Lab result unit and range validation", "REQ-008", "Data Validation Testing", "Reference ranges configured.", "1. Post result with wrong unit\n2. Post out-of-range value", "Both flagged.", "", TM, None, "Not Run", ""),
    ("TC-022", "System under 200 concurrent users", "REQ-022", "Performance Testing", "Load tool configured.", "1. Ramp to 200 users\n2. Run patient search and booking", "Error rate below 1%.", "Error rate 6.4% with search timeouts.", TM, 4, "Failed", "EV-TC022-load.csv"),
    ("TC-023", "Application restart after crash without data loss", "REQ-020", "Recovery Testing", "Test data loaded.", "1. Kill application process\n2. Restart\n3. Verify data", "No data loss or corruption.", "", TM, None, "Not Run", ""),
    ("TC-024", "Session timeout and re-authentication", "REQ-015", "Security Testing", "User logged in.", "1. Wait for timeout\n2. Perform action", "Session expires; login required.", "Session expired after 15 minutes.", TM, 11, "Passed", "EV-TC024.png"),
    ("TC-025", "Referential integrity prevents orphan appointments", "REQ-017", "Database Testing", "Patient with appointments.", "1. Attempt to delete patient with appointments", "Delete blocked by constraint.", "Blocked by foreign key.", TM, 11, "Passed", "EV-TC025.sql"),
]

# id,title,desc,cat,sev,prio,steps,expected,actual,assigned,reported_by,days_ago,req,tc,resolution,verif,status,resolved_days_ago,closed_days_ago,reopen
DEFECTS = [
    ("DEF-001", "Duplicate patient created when name case differs", "Registration allows a second patient with identical name and DOB when letter case differs.", "Duplicate patient records", "Critical", "Highest", "1. Register 'Test Patient A'\n2. Register 'test patient a' same DOB", "Registration blocked as duplicate.", "Second record created.", DEVA, TM, 16, "REQ-002", "TC-002", "", "", "Assigned", None, None, 0),
    ("DEF-002", "Double booking possible with near-simultaneous requests", "Two bookings accepted for the same doctor slot when submitted concurrently.", "Appointment conflicts", "High", "High", "1. Submit two booking requests in parallel", "Second rejected.", "Both accepted.", DEVB, TM, 15, "REQ-004", "TC-004", "Added unique index (doctor_id, slot_time) and row-level lock in booking transaction.", "", "Retesting", 3, None, 0),
    ("DEF-003", "Lab result attached to wrong patient when MRN suffix reused", "Result matching uses MRN suffix only, attaching results to a different patient.", "Laboratory result mismatch", "Critical", "Highest", "1. Post result for sample S1\n2. Open patient with similar MRN", "Result visible only for owning patient.", "Result visible on wrong patient.", DEVA, TM, 14, "REQ-007", "TC-005", "", "", "In Progress", None, None, 0),
    ("DEF-004", "Billing total off by 0.01 with discount and tax", "Floating-point rounding produces incorrect totals when discount and tax combine.", "Billing calculation errors", "High", "High", "1. Create bill with discount+tax", "Exact total.", "Total differs by 0.01.", DEVA, QA, 25, "REQ-009", "TC-006", "Replaced double with BigDecimal and fixed rounding mode; added unit tests.", "Passed", "Closed", 12, 9, 1),
    ("DEF-005", "Receptionist role can view clinical notes", "Authorisation filter does not restrict clinical-notes endpoint for receptionist role.", "Authorization failures", "Critical", "Highest", "1. Login as receptionist\n2. Open clinical notes URL", "HTTP 403.", "Notes displayed.", ARCH, TM, 12, "REQ-015", "TC-008", "RBAC matrix applied to clinical-notes endpoint; denied attempts logged.", "", "Resolved", 2, None, 0),
    ("DEF-006", "Partial appointment record after failed billing transaction", "Appointment row persists when billing insert fails, leaving inconsistent data.", "Database failures", "High", "High", "1. Inject failure on billing insert", "Whole transaction rolled back.", "Appointment row remained.", ARCH, TM, 11, "REQ-017", "TC-010", "", "", "Assigned", None, None, 0),
    ("DEF-007", "Patient search times out under 200 concurrent users", "Search endpoint lacks index on name+DOB; timeouts occur under load.", "Performance issues", "Medium", "Medium", "1. Ramp to 200 users", "Error rate below 1%.", "Error rate 6.4%.", ARCH, TM, 4, "REQ-022", "TC-022", "", "", "Open", None, None, 0),
    ("DEF-008", "Prescription printout shows previous doctor name after profile update", "Printed prescription uses cached doctor name.", "Prescription errors", "High", "Highest", "1. Rename doctor\n2. Print earlier prescription", "Correct current doctor identity.", "Old name printed.", DEVB, REVW, 14, "REQ-011", "TC-007", "Cache invalidated on doctor update; prescription stores doctor id reference.", "Passed", "Closed", 10, 8, 0),
    ("DEF-009", "Patient history timeline mis-ordered for same-day entries", "Entries on the same day are ordered by id, not event time.", "Patient history inconsistency", "Medium", "Medium", "1. Add two same-day entries out of order", "Ordered by event time.", "Ordered by id.", DEVA, REVW, 9, "REQ-013", None, "Order by event timestamp, then entry sequence.", "Failed", "Reopened", 5, None, 1),
    ("DEF-010", "Doctor specialisation saved blank when only contact edited", "Editing contact clears specialisation field.", "Doctor record errors", "Low", "Low", "1. Edit doctor contact", "Specialisation unchanged.", "Specialisation blank.", DEVB, QA, 20, "REQ-005", None, "Form now submits unchanged fields.", "Passed", "Closed", 14, 13, 0),
    ("DEF-011", "Application crash when exporting report for empty date range", "Unhandled null reference when no rows are returned.", "Application crashes", "Medium", "Medium", "1. Export report for date range without data", "Empty report message.", "Application error page.", DEVB, TM, 6, "REQ-020", None, "", "", "Open", None, None, 0),
    ("DEF-012", "Test plan missing data-retention section", "System test plan lacks data-retention and test-data privacy section.", "Documentation defects", "Low", "Low", "Review document", "Section present.", "Section missing.", BA, QA, 21, "REQ-024", None, "Section added in v1.0 and re-reviewed.", "Passed", "Closed", 18, 17, 0),
    ("DEF-013", "Patient age calculated incorrectly for leap-day birthdate", "Age shown one year lower for patients born on 29 February in non-leap years.", "Incorrect patient data", "High", "Highest", "1. Register patient DOB 2000-02-29\n2. View age on 28 Feb", "Correct age.", "Age off by one.", DEVA, TM, 3, "REQ-018", None, "", "", "Open", None, None, 0),
]

# id, defect, problem, root, whys(5), containment, corrective, preventive, owner, target_offset, status, evidence, effectiveness, approver, closed_days_ago
CAPAS = [
    ("CAPA-001", "DEF-001", "Duplicate patient records can be created with differing letter case.", "Duplicate matching is case sensitive and ignores whitespace differences.", ["Why was a duplicate created? Matching rule did not match 'Test Patient A' with 'test patient a'.", "Why? Comparison used exact string equality.", "Why? Matching rule not specified in detail in the requirement.", "Why? Requirement review did not include data-matching test examples.", "Why? Review checklist lacked a data-normalisation item."], "Manual daily duplicate report to registration staff.", "Normalise case/whitespace and add phone+DOB fuzzy match.", "Add data-normalisation item to requirement review checklist and duplicate-scenario tests to regression suite.", DEVA, 7, "In Progress", "", "", "", None),
    ("CAPA-002", "DEF-003", "Lab results attached to wrong patient due to MRN suffix matching.", "Result binding uses partial identifier; sample ID not mandatory.", ["Why was the result mismatched? Binding used MRN suffix.", "Why? Sample ID optional in interface contract.", "Why? Interface spec was not reviewed against patient-safety scenarios.", "Why? No interoperability review for lab interface.", "Why? Review plan lacked interface review type."], "Lab results manually verified by technician before release to doctors.", "Require full MRN + sample ID, reject mismatches.", "Add interface review and integration tests for identifier mismatches.", DEVA, 5, "Action Planned", "", "", "", None),
    ("CAPA-003", "DEF-004", "Billing totals incorrect by 0.01 for discount+tax combinations.", "Currency calculations used floating point arithmetic.", ["Why was total wrong? Floating point rounding.", "Why? double used for money.", "Why? Coding standard silent on currency types.", "Why? Standard not updated after billing design.", "Why? No code-review checklist item for numeric types."], "Finance staff manually checked affected bills.", "Replaced double with BigDecimal and defined rounding mode.", "Added currency-type rule to coding standard and code-review checklist; unit tests for rounding added.", DEVA, -12, "Closed", "Unit test report UT-BILL-14; code review REV-008.", "Reviewed 14 days after fix: no further rounding defects across 60 sample bills.", QA, 6),
    ("CAPA-004", "DEF-005", "Receptionist role could access clinical notes.", "Role-permission matrix not applied to all endpoints.", ["Why was access granted? Endpoint missing authorisation annotation.", "Why? Developers added endpoints without checking RBAC matrix.", "Why? No automated check for unprotected endpoints.", "Why? Security review done only at design level.", "Why? Security testing started late."], "Clinical-notes endpoint disabled for receptionist until fix.", "Applied RBAC matrix to all clinical endpoints.", "Add automated endpoint-authorisation test and mandatory security review before release.", ARCH, 3, "Verification", "Retest evidence pending (TC-008 re-run).", "", "", None),
    ("CAPA-005", "DEF-006", "Failed billing transaction leaves partial appointment record.", "Appointment and billing inserts executed in separate transactions.", ["Why was a partial record left? Separate transactions.", "Why? Transaction boundary not defined.", "Why? Design review did not cover failure scenarios.", "", ""], "Daily reconciliation script identifies orphan appointments.", "", "", ARCH, 10, "Investigation", "", "", "", None),
    ("CAPA-006", "DEF-008", "Prescription printout showed outdated doctor name.", "Cached doctor name used instead of live doctor reference.", ["Why was old name printed? Cached value.", "Why? Cache not invalidated on doctor update.", "Why? No cache-invalidation rule in design.", "Why? Design review focused on happy path.", "Why? Review checklist lacked data-staleness check."], "Prescriptions printed after doctor changes checked manually.", "Store doctor id reference and invalidate cache on update.", "Add data-staleness item to design review checklist.", DEVB, -9, "Closed", "Regression test TC-007 passed; design review checklist v1.1.", "Reviewed 10 days later: no stale-identity incidents in 40 prints.", QA, 5),
]

# id, key, title, type, version, owner, created_days_ago, updated_days_ago, status, description, next_review_in_days, approver, history[(version, days_ago, by, summary, status, approver)]
DOCS = [
    ("DOC-001", "quality_plan", "Project Quality Plan", "PLAN", "1.2", QA, 60, 14, "Approved", "Scope, quality objectives, factors, responsibilities, gates, metrics and risk controls for the hospital software.", 76, PM,
     [("1.0", 60, QA, "Initial issue", "Approved", PM), ("1.1", 35, QA, "Added quality gates and risk management", "Approved", PM), ("1.2", 14, QA, "Aligned metrics with the analytics module", "Approved", PM)]),
    ("DOC-002", "req_procedure", "Requirements Development & Management Procedure", "PROCEDURE", "1.1", BA, 58, 20, "Approved", "Identify, classify, analyse, validate, baseline, trace and change-control hospital software requirements.", 70, QA,
     [("1.0", 58, BA, "Initial issue", "Approved", QA), ("1.1", 20, BA, "Added data-integrity classification and approval workflow", "Approved", QA)]),
    ("DOC-003", "req_checklist", "Requirement Review Checklist", "CHECKLIST", "1.0", QA, 55, 25, "Approved", "Completeness, correctness, consistency, feasibility, testability, data accuracy, privacy and acceptance checks.", 65, REVW,
     [("1.0", 55, QA, "Initial issue", "Approved", REVW)]),
    ("DOC-004", "change_request", "Change Request Form", "TEMPLATE", "1.0", PM, 45, 30, "Approved", "Impact, risk, cost and time analysis, recommendation, decision, implementation and closure of a change.", 60, QA,
     [("1.0", 45, PM, "Initial issue", "Approved", QA)]),
    ("DOC-005", "rtm", "Requirements Traceability Matrix", "TEMPLATE", "1.3", QA, 50, 1, "Approved", "Bidirectional path from stakeholder need through design, tests, defects and approval.", 30, PM,
     [("1.0", 50, QA, "Initial issue", "Approved", PM), ("1.1", 38, QA, "Added defect column", "Approved", PM), ("1.2", 20, QA, "Added approval status", "Approved", PM), ("1.3", 1, QA, "Live generation from QMS data", "Approved", PM)]),
    ("DOC-006", "peer_review", "Peer Review Procedure", "PROCEDURE", "1.0", REVW, 55, 25, "Approved", "Entry criteria, preparation, findings, defect classification, rework and formal sign-off.", 65, QA,
     [("1.0", 55, REVW, "Initial issue", "Approved", QA)]),
    ("DOC-007", "release_checklist", "Release Readiness Checklist", "CHECKLIST", "1.0", PM, 30, 4, "Draft", "Defect, evidence, approval, backup, rollback and final release approval gates.", 20, None,
     [("0.1", 30, PM, "Initial draft", "Draft", None), ("1.0", 4, PM, "Aligned with the 13 release-gate checks", "Draft", None)]),
    ("DOC-008", "capa_procedure", "CAPA Procedure", "PROCEDURE", "1.0", QA, 40, 9, "Under Review", "Containment, root cause, Five Whys, corrective and preventive action, effectiveness verification and closure.", 45, None,
     [("0.1", 40, QA, "Initial draft", "Draft", None), ("1.0", 9, QA, "Submitted for review", "Under Review", None)]),
]

PROJECT = {
    "project_name": "Hospital Management Software QMS",
    "team_name": "TEAM 2",
    "project_version": "Release 1.0 (candidate)",
    "organisation": "Amrita School of Computing - Software Quality Management course",
    "current_user": QA,
    "min_pass_rate": "80",
    "release_version": "Release 1.0",
    "project_start": "",
    "library_revision": "1.0",
}

REVIEW_CHECKLISTS = {
    "Requirement review": ["Requirement is unambiguous and complete", "Acceptance criteria are testable", "Data-integrity rules are stated", "Privacy and access rules are stated", "Risk level and priority justified", "Traceable to a stakeholder need"],
    "Design review": ["Design satisfies all linked requirements", "Failure and rollback scenarios considered", "Interfaces and data contracts defined", "Design is maintainable and modular"],
    "Database design review": ["Primary and foreign keys defined", "Unique constraints prevent duplicates", "Transaction boundaries defined", "Backup and recovery considered", "Sensitive fields identified"],
    "Code review": ["Coding standard followed", "Input validation implemented", "Error handling present", "No hard-coded credentials or patient data", "Unit tests included"],
    "Test plan review": ["All requirements covered by tests", "Security, recovery and data tests planned", "Entry and exit criteria defined", "Test data contains no real patient data"],
    "Security review": ["Role-based access verified", "Authentication and session rules verified", "Encryption in transit and at rest verified", "Audit logging of access verified"],
    "Documentation review": ["Document is complete and current", "Terminology consistent", "Version and owner recorded", "Procedures match implemented process"],
    "Release review": ["Release gate checks reviewed", "Open defects dispositioned", "Rollback plan reviewed", "Backup and recovery confirmed", "Stakeholder sign-off obtained"],
}


def migrate_documents(conn):
    """Make sure the library holds exactly the eight mandatory controlled documents with version history."""
    have = {r[0] for r in conn.execute("SELECT doc_key FROM documents").fetchall()}
    want = {d[1] for d in DOCS}
    if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0 or (have == want):
        return
    conn.execute("DELETE FROM document_versions")
    conn.execute("DELETE FROM documents")
    for dd in DOCS:
        (did, key, title, typ, ver, owner, cdays, udays, status, desc, rev_in, approver, hist) = dd
        conn.execute("INSERT INTO documents(id,doc_key,title,doc_type,version,owner,created_on,updated_on,approval_status,description,review_date,approved_by,approved_on) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (did, key, title, typ, ver, owner, ago(cdays), ago(udays), status, desc, ahead(rev_in), approver if status == "Approved" else None, ago(udays) if status == "Approved" else None))
        for (hv, hd, hby, hsum, hst, hap) in hist:
            conn.execute("INSERT INTO document_versions(doc_id,version,changed_on,changed_by,summary,approval_status,approved_by) VALUES(?,?,?,?,?,?,?)",
                         (did, hv, ago(hd), hby, hsum, hst, hap))
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('library_revision','1.0')")
    conn.commit()


def seed_data():
    conn = connect()
    c = conn.cursor()
    for k, v in PROJECT.items():
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, v))
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('project_start',?)", (ago(70),))
    for name, role in TEAM:
        c.execute("INSERT INTO team_members(name,role,email) VALUES(?,?,?)", (name, role, ""))
    for n in NEEDS:
        c.execute("INSERT INTO stakeholder_needs VALUES(?,?,?)", n)
    for r in REQS:
        (rid, title, desc, cat, typ, factor, prio, risk, owner, status, acc, design, impl, need, appr, appr_days) = r
        c.execute("INSERT INTO requirements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, title, desc, cat, typ, factor, prio, risk, owner, status, acc, design, impl, need,
                   appr, ago(appr_days) if appr_days else None, ago(60)))
    for rv in REVIEWS:
        (rid, rtype, title, art, ver, reviewer, rdays, due, findings, fsev, comments, decision, reqs) = rv
        status = {"Approved": "Approved", "Approved with actions": "Approved with actions",
                  "Rework required": "Rework required", "Rejected": "Rejected"}.get(decision, "Pending")
        checks = REVIEW_CHECKLISTS[rtype]
        checklist = {item: (decision in ("Approved", "Approved with actions")) for item in checks}
        if decision == "Approved with actions":
            checklist[checks[-1]] = False
        c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, rtype, title, art, ver, reviewer if decision else reviewer,
                   ago(rdays) if rdays is not None else None, ahead(due), findings, fsev, comments,
                   decision, status, json.dumps(checklist), ago(45)))
        for q in reqs:
            c.execute("INSERT INTO review_requirements VALUES(?,?)", (rid, q))
    for t in TESTS:
        (tid, sc, req, cat, pre, steps, exp, act, tester, days, status, ev) = t
        c.execute("INSERT INTO test_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (tid, sc, req, cat, pre, steps, exp, act, tester, ago(days) if days is not None else None, status, ev))
    cat_module = {r[0]: r[3] for r in REQS}
    for d in DEFECTS:
        (did, title, desc, cat, sev, prio, steps, exp, act, assigned, rep, days, req, tc, res, ver, status, rdays, cdays, reopen) = d
        c.execute("INSERT INTO defects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (did, title, desc, cat, sev, prio, steps, exp, act, assigned, rep, ago(days), req, tc, res, ver, status,
                   ago(rdays) if rdays is not None else None, ago(cdays) if cdays is not None else None, reopen))
    for k in CAPAS:
        (cid, did, prob, root, whys, cont, corr, prev, owner, toff, status, evid, eff, appr, cdays) = k
        whys = list(whys) + [""] * (5 - len(whys))
        c.execute("INSERT INTO capas VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, did, prob, root, *whys, cont, corr, prev, owner, ahead(toff), status, evid, eff, appr,
                   ago(cdays) if cdays is not None else None, ago(30)))
    for dd in DOCS:
        (did, key, title, typ, ver, owner, cdays, udays, status, desc, rev_in, approver, hist) = dd
        c.execute("INSERT INTO documents(id,doc_key,title,doc_type,version,owner,created_on,updated_on,approval_status,description,review_date,approved_by,approved_on) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (did, key, title, typ, ver, owner, ago(cdays), ago(udays), status, desc, ahead(rev_in), approver if status == "Approved" else None,
                   ago(udays) if status == "Approved" else None))
        for (hv, hd, hby, hsum, hst, hap) in hist:
            c.execute("INSERT INTO document_versions(doc_id,version,changed_on,changed_by,summary,approval_status,approved_by) VALUES(?,?,?,?,?,?,?)",
                      (did, hv, ago(hd), hby, hsum, hst, hap))
    # manual release attestations start unconfirmed (no row = pending)
    events = [
        (15, QA, "created", "reviews", "REV-007", "Security review recorded: rework required"),
        (12, TM, "created", "defects", "DEF-005", "Critical authorization failure reported"),
        (9, DEVA, "updated", "defects", "DEF-004", "Closed after retest - BigDecimal fix verified"),
        (6, QA, "created", "capas", "CAPA-004", "CAPA opened for authorization failure"),
        (4, TM, "executed", "test_cases", "TC-022", "Performance test failed under 200 users"),
        (3, DEVB, "updated", "defects", "DEF-002", "Moved to Retesting after unique index fix"),
        (2, ARCH, "updated", "defects", "DEF-005", "Resolved - RBAC matrix applied"),
        (1, TM, "executed", "test_cases", "TC-018", "Regression run started for duplicate-check fix"),
        (1, PM, "created", "reviews", "REV-012", "Release review scheduled"),
    ]
    for days, actor, action, entity, eid, detail in events:
        ts = (datetime.now() - timedelta(days=days, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO activity_log(ts,actor,action,entity,entity_id,detail) VALUES(?,?,?,?,?,?)",
                  (ts, actor, action, entity, eid, detail))
    conn.commit()
    conn.close()
