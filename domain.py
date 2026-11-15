"""Hospital-domain constants used by validation, metrics, reports and the UI."""

REQ_CATEGORIES = ["Patient Registration", "Appointment Management", "Doctor Management", "Laboratory Management",
                  "Billing Management", "Prescription Management", "Patient History", "Data Security",
                  "Data Integrity", "System Reliability", "Performance", "Maintainability"]
LEVELS = ["Critical", "High", "Medium", "Low"]
REQ_STATUS = ["Draft", "Under Review", "Approved", "Implemented", "Verified", "Rejected"]
APPROVED_REQ = ("Approved", "Implemented", "Verified")
REQ_TYPES = ["Functional", "Non-functional"]
QUALITY_FACTORS = ["Data Accuracy", "Data Integrity", "Reliability", "Security and Privacy", "Availability",
                   "Performance Efficiency", "Maintainability", "Usability", "Interoperability", "Auditability"]

REVIEW_TYPES = ["Requirement review", "Design review", "Database design review", "Code review", "Test plan review",
                "Security review", "Documentation review", "Release review"]
REVIEW_DECISIONS = ["Approved", "Approved with actions", "Rework required", "Rejected"]
APPROVING = ("Approved", "Approved with actions")
FINDING_SEVERITIES = ["Critical", "High", "Medium", "Low"]

TEST_CATEGORIES = ["Unit Testing", "Integration Testing", "System Testing", "Regression Testing",
                   "User Acceptance Testing", "Security Testing", "Performance Testing",
                   "Data Validation Testing", "Database Testing", "Recovery Testing"]
TEST_STATUS = ["Not Run", "In Progress", "Passed", "Failed", "Blocked"]

DEFECT_CATEGORIES = ["Incorrect patient data", "Duplicate patient records", "Appointment conflicts",
                     "Doctor record errors", "Laboratory result mismatch", "Billing calculation errors",
                     "Prescription errors", "Patient history inconsistency", "Authentication failures",
                     "Authorization failures", "Database failures", "Performance issues", "Application crashes",
                     "Documentation defects"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
DEFECT_PRIORITIES = ["Highest", "High", "Medium", "Low"]
DEFECT_STATUS = ["Open", "Assigned", "In Progress", "Resolved", "Retesting", "Closed", "Reopened"]
DEFECT_DONE = ("Resolved", "Closed")
VERIFICATION = ["", "Passed", "Failed", "Pending"]
# defects in these categories affect patient data, prescriptions, labs, billing or confidential access
PATIENT_CRITICAL_CATEGORIES = {"Incorrect patient data", "Duplicate patient records", "Laboratory result mismatch",
                               "Billing calculation errors", "Prescription errors", "Authentication failures",
                               "Authorization failures", "Patient history inconsistency", "Database failures"}

CAPA_STATUS = ["Open", "Investigation", "Action Planned", "In Progress", "Verification", "Closed"]

DOC_TYPES = ["PLAN", "PROCEDURE", "CHECKLIST", "TEMPLATE"]
DOC_STATUS = ["Draft", "Under Review", "Approved", "Obsolete"]
RELEASE_DECISIONS = ["GO", "NO-GO", "CONDITIONAL GO"]
TEAM_ROLES = ["Project Manager", "Quality Assurance Lead", "Business Analyst", "Technical Architect", "Developer",
              "Test Manager", "Reviewer"]

QUALITY_OBJECTIVES = [
    ("Patient data is accurate", "Zero unresolved critical defects affecting patient identity, lab results, prescriptions or billing at release."),
    ("Data stays consistent", "All database and data-validation tests pass; no orphan or partial records after failed transactions."),
    ("Requirements are verified", "Every approved requirement is traceable to design, implementation and an executed test."),
    ("Confidential data is protected", "Role-based access and encryption verified by an approved security review and passing security tests."),
    ("Evidence-based release", "Release proceeds only when mandatory gate checks pass, with minimum 80% test pass rate (proposed project baseline)."),
    ("Continuous improvement", "Every high-impact defect has a CAPA with documented effectiveness verification before closure."),
]

FACTOR_INFO = {
    "Data Accuracy": "Patient, lab, billing and prescription data must be correct. Highest priority: wrong data can harm patients.",
    "Data Integrity": "Records remain consistent across modules and transactions; no duplicates or orphans.",
    "Reliability": "Software behaves correctly under normal and faulty conditions.",
    "Security and Privacy": "Only authorised roles access confidential patient information.",
    "Availability": "Hospital staff can use the system when needed; backup and recovery work.",
    "Performance Efficiency": "Searches and bookings respond quickly under hospital load.",
    "Maintainability": "Code and documentation can be changed safely and understood by the team.",
    "Usability": "Front-desk and clinical users can complete tasks with few errors.",
    "Interoperability": "Interfaces (e.g. laboratory devices) exchange data correctly and unambiguously.",
    "Auditability": "Who changed what and when is recorded and reviewable.",
}

# lifecycle stage -> (description, QMS modules, route names)
LIFECYCLE = [
    ("PLAN", "Quality plan, objectives, controlled procedures", "Documents", "documents"),
    ("DEFINE", "Requirements, risks, acceptance criteria", "Requirements", "requirements"),
    ("EXECUTE", "Testing and defect capture", "Testing, Defects", "testing"),
    ("VERIFY", "Reviews, approvals and traceability", "Reviews, Traceability", "reviews"),
    ("MEASURE", "Quality metrics and analytics", "Quality Analytics", "analytics"),
    ("REPORT", "Quality report and release gate", "Release Management", "release"),
    ("IMPROVE", "Corrective and preventive action", "CAPA", "capa"),
]

DISCLAIMER = ("This is a software quality management prototype built for a course project. It is not a certified "
              "clinical safety system and makes no claim of regulatory compliance.")
