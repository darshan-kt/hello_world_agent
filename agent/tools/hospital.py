"""
agent/tools/hospital.py — Hospital Tool (POC)
------------------------------------------------
SQL-backed patient records: demographics, admissions, prescriptions,
lab reports, and surgeries. Mirrors memory_tool.py's pattern (lazy
DB init + seed) but backed by SQLite instead of a flat JSON file.

*** ALL DATA IS SYNTHETIC — generated with a fixed random seed for
*** reproducibility. This is a learning/demo project, not a real
*** medical records system. See README.md for what would be required
*** before any real patient data could go anywhere near this code
*** (auth, encryption at rest, a compliant hosting/LLM setup, etc.)

Design note: each tool call returns one self-contained block of text
(a search result list, or one patient's full combined record) rather
than many small fields, so the agent can usually answer in a single
tool call. The ReAct loop's prompt parser is a plain regex over the
LLM's text output, not a structured function-calling API — keeping
each tool "chunky" avoids stressing that parser with multi-step chains.
"""

import random
import re
import sqlite3
from datetime import date, timedelta

from agent.tools.registry import tool
import config

config.HOSPITAL_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

_DOCUMENTS_DIR = config.HOSPITAL_DB_FILE.parent / "documents"
_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id   INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    age          INTEGER NOT NULL,
    gender       TEXT NOT NULL,
    blood_group  TEXT NOT NULL,
    phone        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admissions (
    admission_id   INTEGER PRIMARY KEY,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    admission_date TEXT NOT NULL,
    discharge_date TEXT,
    diagnosis      TEXT NOT NULL,
    ward           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id INTEGER PRIMARY KEY,
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    medicine        TEXT NOT NULL,
    dosage          TEXT NOT NULL,
    prescribed_date TEXT NOT NULL,
    prescribed_by   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_reports (
    report_id    INTEGER PRIMARY KEY,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    test_name    TEXT NOT NULL,
    result       TEXT NOT NULL,
    normal_range TEXT NOT NULL,
    test_date    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surgeries (
    surgery_id   INTEGER PRIMARY KEY,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    surgery_name TEXT NOT NULL,
    surgery_date TEXT NOT NULL,
    surgeon      TEXT NOT NULL,
    outcome      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_id   INTEGER PRIMARY KEY,
    patient_id    INTEGER NOT NULL REFERENCES patients(patient_id),
    document_type TEXT NOT NULL,
    title         TEXT NOT NULL,
    content       TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    created_date  TEXT NOT NULL
);
"""

_FIRST_NAMES = [
    "Aarav", "Vivaan", "Ishaan", "Rohan", "Kabir", "Arjun", "Sai", "Aditya",
    "Ananya", "Diya", "Priya", "Meera", "Kavya", "Riya", "Sanya", "Isha",
    "John", "Michael", "David", "James", "Robert", "William", "Emma", "Olivia",
    "Sophia", "Grace", "Chen", "Wei", "Yuki", "Hana", "Fatima", "Amara",
]
_LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Patel", "Singh",
    "Smith", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson",
    "Zhang", "Tanaka", "Khan", "Okafor", "Rossi",
]
_GENDERS = ["Male", "Female", "Other"]
_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_DIAGNOSES = [
    "Type 2 Diabetes Mellitus", "Hypertension", "Acute Appendicitis",
    "Community-Acquired Pneumonia", "Fractured Femur", "Migraine",
    "Gastroenteritis", "Asthma Exacerbation", "Coronary Artery Disease",
    "Chronic Kidney Disease Stage 3", "Dengue Fever", "Malaria",
]
_WARDS = ["General Ward A", "General Ward B", "ICU", "Cardiology", "Orthopedics", "Pediatrics"]
_MEDICINES = [
    ("Metformin", "500mg twice daily"), ("Amlodipine", "5mg once daily"),
    ("Amoxicillin", "500mg three times daily"), ("Ibuprofen", "400mg as needed"),
    ("Atorvastatin", "20mg once nightly"), ("Salbutamol Inhaler", "2 puffs as needed"),
    ("Paracetamol", "650mg every 6 hours"), ("Omeprazole", "20mg once daily"),
]
_DOCTORS = [
    "Dr. Nisha Rao", "Dr. Alan Cooper", "Dr. Priyanka Desai", "Dr. Mark Ellison",
    "Dr. Sunita Rangan", "Dr. Thomas Wright",
]
_LAB_TESTS = [
    ("Hemoglobin", "g/dL", 11.5, 16.5),
    ("Fasting Blood Sugar", "mg/dL", 70, 110),
    ("WBC Count", "cells/uL", 4000, 11000),
    ("Serum Creatinine", "mg/dL", 0.6, 1.3),
    ("Total Cholesterol", "mg/dL", 125, 200),
]
_SURGERIES = ["Appendectomy", "Knee Arthroscopy", "Cataract Surgery", "Coronary Angioplasty", "Cesarean Section"]
_OUTCOMES = ["Successful, no complications", "Successful, minor post-op complications resolved", "Successful"]

_SCAN_TYPES = [
    ("Chest X-Ray", "No acute cardiopulmonary abnormality. Lung fields are clear bilaterally. Heart size within normal limits.", "Unremarkable chest X-ray."),
    ("CT Abdomen", "Liver, spleen, pancreas, and kidneys appear normal in size and attenuation. No free fluid or lymphadenopathy identified.", "No acute intra-abdominal pathology."),
    ("MRI Brain", "No evidence of acute infarct, hemorrhage, or mass lesion. Ventricles are normal in size and configuration.", "Unremarkable MRI of the brain."),
    ("Ultrasound Abdomen", "Liver is normal in echotexture. Gallbladder shows no calculi. Kidneys are normal in size with no hydronephrosis.", "Normal abdominal ultrasound."),
    ("Chest CT", "No pulmonary nodules or consolidation. Mediastinal contours are within normal limits.", "No acute findings on chest CT."),
]
_SYMPTOMS = [
    "mild fatigue and occasional dizziness", "persistent cough for the past few days",
    "intermittent abdominal discomfort", "generalized weakness and reduced appetite",
    "mild joint pain, worse in the mornings", "difficulty sleeping and low energy levels",
]
_PLANS = [
    "Continue current medications, reassess in 2 weeks.",
    "Adjust dosage as needed and monitor symptoms; follow up if no improvement.",
    "Order follow-up labs and review results at next visit.",
    "Advise rest, hydration, and symptomatic management; return if symptoms worsen.",
]

_PATIENT_COUNT = 25
_SEED = 42


def _tokenize(text: str) -> set:
    """Lowercase word tokens, filtering short/common words — a minimal keyword-overlap
    retrieval scorer. No embedding model or vector DB needed for a POC this size."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "with", "by", "at", "this", "that", "patient", "report",
    "date", "any", "his", "her", "has", "had", "not", "per",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.HOSPITAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _random_date(rng: random.Random, start_days_ago: int, end_days_ago: int) -> date:
    days_ago = rng.randint(end_days_ago, start_days_ago)
    return date.today() - timedelta(days=days_ago)


def _seed_if_empty() -> None:
    """
    Populate the DB with synthetic data on first run — patients and documents
    are seeded independently so adding the documents table later doesn't
    require deleting an existing hospital.db to pick up the new data.
    """
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)

        if conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
            _seed_patients(conn)

        if conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0:
            _seed_documents(conn)

        conn.commit()
    finally:
        conn.close()


def _seed_patients(conn: sqlite3.Connection) -> None:
    rng = random.Random(_SEED)
    for patient_id in range(1, _PATIENT_COUNT + 1):
        name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
        age = rng.randint(1, 90)
        gender = rng.choice(_GENDERS)
        blood_group = rng.choice(_BLOOD_GROUPS)
        phone = f"+91-9{rng.randint(100000000, 999999999)}"
        conn.execute(
            "INSERT INTO patients (patient_id, name, age, gender, blood_group, phone) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, name, age, gender, blood_group, phone),
        )

        # 1-3 admissions per patient
        for _ in range(rng.randint(1, 3)):
            admit = _random_date(rng, 900, 30)
            discharge = admit + timedelta(days=rng.randint(1, 10))
            conn.execute(
                "INSERT INTO admissions (patient_id, admission_date, discharge_date, diagnosis, ward) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient_id, admit.isoformat(), discharge.isoformat(),
                 rng.choice(_DIAGNOSES), rng.choice(_WARDS)),
            )

        # 1-4 prescriptions per patient
        for _ in range(rng.randint(1, 4)):
            medicine, dosage = rng.choice(_MEDICINES)
            conn.execute(
                "INSERT INTO prescriptions (patient_id, medicine, dosage, prescribed_date, prescribed_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient_id, medicine, dosage,
                 _random_date(rng, 600, 1).isoformat(), rng.choice(_DOCTORS)),
            )

        # 1-3 lab reports per patient
        for _ in range(rng.randint(1, 3)):
            test_name, unit, lo, hi = rng.choice(_LAB_TESTS)
            value = round(rng.uniform(lo * 0.7, hi * 1.3), 1)
            conn.execute(
                "INSERT INTO lab_reports (patient_id, test_name, result, normal_range, test_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient_id, test_name, f"{value} {unit}", f"{lo}-{hi} {unit}",
                 _random_date(rng, 400, 1).isoformat()),
            )

        # 0-1 surgeries per patient
        if rng.random() < 0.4:
            conn.execute(
                "INSERT INTO surgeries (patient_id, surgery_name, surgery_date, surgeon, outcome) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient_id, rng.choice(_SURGERIES), _random_date(rng, 800, 30).isoformat(),
                 rng.choice(_DOCTORS), rng.choice(_OUTCOMES)),
            )


def _seed_documents(conn: sqlite3.Connection) -> None:
    """
    Generate synthetic unstructured documents per patient (discharge summaries,
    scan reports, doctor's notes) — the RAG corpus. Content is saved both in the
    DB (for fast retrieval) and as a .txt file under data/documents/ (standing in
    for a scanned/uploaded PDF, per the original pdf_path design).
    """
    rng = random.Random(_SEED + 1)  # different stream than patient seeding
    patients = conn.execute("SELECT patient_id, name FROM patients").fetchall()

    for patient in patients:
        patient_id, name = patient["patient_id"], patient["name"]
        docs: list[tuple[str, str, str, str]] = []  # (type, title, content, created_date)

        latest_admission = conn.execute(
            "SELECT * FROM admissions WHERE patient_id = ? ORDER BY admission_date DESC LIMIT 1",
            (patient_id,),
        ).fetchone()
        if latest_admission:
            diagnosis = latest_admission["diagnosis"]
            doctor = rng.choice(_DOCTORS)
            content = (
                f"DISCHARGE SUMMARY\n\n"
                f"Patient: {name} (ID {patient_id})\n"
                f"Admission Date: {latest_admission['admission_date']}\n"
                f"Discharge Date: {latest_admission['discharge_date']}\n"
                f"Diagnosis: {diagnosis}\n\n"
                f"Hospital Course:\n"
                f"{name} was admitted to {latest_admission['ward']} with {diagnosis}. "
                f"During the stay, the patient was managed with supportive care and "
                f"appropriate medications per protocol. The patient's condition improved "
                f"steadily and vital signs stabilized prior to discharge.\n\n"
                f"Discharge Condition: Stable\n"
                f"Follow-up: Advised to follow up with primary care physician in 2 weeks. "
                f"Continue prescribed medications as directed.\n\n"
                f"Discharging Physician: {doctor}"
            )
            docs.append(("Discharge Summary", f"Discharge Summary — {latest_admission['admission_date']}",
                         content, latest_admission["discharge_date"]))

        if rng.random() < 0.4:
            scan_name, finding, impression = rng.choice(_SCAN_TYPES)
            doctor = rng.choice(_DOCTORS)
            scan_date = _random_date(rng, 300, 1).isoformat()
            content = (
                f"RADIOLOGY REPORT\n\n"
                f"Patient: {name} (ID {patient_id})\n"
                f"Study: {scan_name}\n"
                f"Date: {scan_date}\n\n"
                f"Findings:\n{finding}\n\n"
                f"Impression: {impression}\n\n"
                f"Reporting Radiologist: {doctor}"
            )
            docs.append((scan_name, f"{scan_name} — {scan_date}", content, scan_date))

        if rng.random() < 0.5:
            doctor = rng.choice(_DOCTORS)
            note_date = _random_date(rng, 200, 1).isoformat()
            symptom = rng.choice(_SYMPTOMS)
            plan = rng.choice(_PLANS)
            content = (
                f"CLINICAL NOTES\n\n"
                f"Patient: {name} (ID {patient_id})\n"
                f"Date: {note_date}\n"
                f"Attending: {doctor}\n\n"
                f"Subjective: Patient reports {symptom}.\n\n"
                f"Objective: Vitals stable, within normal limits on examination.\n\n"
                f"Assessment: Findings consistent with reported symptoms; no acute "
                f"concerns identified at this visit.\n\n"
                f"Plan: {plan}"
            )
            docs.append(("Doctor's Notes", f"Clinical Note — {note_date}", content, note_date))

        for document_type, title, content, created_date in docs:
            cursor = conn.execute(
                "INSERT INTO documents (patient_id, document_type, title, content, file_path, created_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (patient_id, document_type, title, content, "", created_date),
            )
            document_id = cursor.lastrowid
            file_path = _DOCUMENTS_DIR / f"patient_{patient_id}_{document_id}.txt"
            file_path.write_text(content)
            conn.execute(
                "UPDATE documents SET file_path = ? WHERE document_id = ?",
                (str(file_path), document_id),
            )


_seed_if_empty()


@tool(
    name="list_patients",
    description="List patients in the hospital database. Use this to browse when no name/ID is given yet.",
    parameters={
        "limit": {"type": "integer", "description": "Max number of patients to return (default 20)"},
    },
    examples=[{"limit": 10, "result": "1. Aarav Sharma (ID 1, Age 34, Male)..."}],
)
def list_patients(limit: int = 20) -> str:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT patient_id, name, age, gender FROM patients ORDER BY patient_id LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No patients found in the database."
    lines = [f"{r['patient_id']}. {r['name']} (ID {r['patient_id']}, Age {r['age']}, {r['gender']})" for r in rows]
    return "Patients:\n" + "\n".join(lines)


@tool(
    name="search_patient",
    description=(
        "Search for a patient by name (partial match, case-insensitive) or exact patient ID. "
        "Returns matching patients with their patient_id — use that ID with get_patient_record "
        "to fetch full medical history."
    ),
    parameters={
        "query": {"type": "string", "description": "Patient name (or part of it) or numeric patient ID"},
    },
    examples=[{"query": "John Smith", "result": "Found: John Smith (ID 7, Age 52, Male)"}],
)
def search_patient(query: str) -> str:
    query = query.strip()
    conn = _connect()
    try:
        if query.isdigit():
            rows = conn.execute(
                "SELECT patient_id, name, age, gender, blood_group FROM patients WHERE patient_id = ?",
                (int(query),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT patient_id, name, age, gender, blood_group FROM patients WHERE name LIKE ? ORDER BY name",
                (f"%{query}%",),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return f"No patient found matching '{query}'."
    lines = [
        f"{r['name']} (ID {r['patient_id']}, Age {r['age']}, {r['gender']}, Blood Group {r['blood_group']})"
        for r in rows
    ]
    return "Found:\n" + "\n".join(lines)


@tool(
    name="get_patient_record",
    description=(
        "Get a patient's full medical record by patient_id: demographics, admission history, "
        "prescriptions, lab reports, and surgeries — everything needed to summarize their history "
        "in one call. Use search_patient first if you only have a name."
    ),
    parameters={
        "patient_id": {"type": "integer", "description": "The patient's numeric ID"},
    },
    examples=[{"patient_id": 7, "result": "Patient: John Smith...\nAdmissions:...\nPrescriptions:..."}],
)
def get_patient_record(patient_id: int) -> str:
    conn = _connect()
    try:
        patient = conn.execute(
            "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return f"No patient found with ID {patient_id}. Try search_patient to find the correct ID."

        admissions = conn.execute(
            "SELECT * FROM admissions WHERE patient_id = ? ORDER BY admission_date DESC", (patient_id,)
        ).fetchall()
        prescriptions = conn.execute(
            "SELECT * FROM prescriptions WHERE patient_id = ? ORDER BY prescribed_date DESC", (patient_id,)
        ).fetchall()
        labs = conn.execute(
            "SELECT * FROM lab_reports WHERE patient_id = ? ORDER BY test_date DESC", (patient_id,)
        ).fetchall()
        surgeries = conn.execute(
            "SELECT * FROM surgeries WHERE patient_id = ? ORDER BY surgery_date DESC", (patient_id,)
        ).fetchall()
    finally:
        conn.close()

    parts = [
        f"Patient: {patient['name']} (ID {patient['patient_id']}, Age {patient['age']}, "
        f"{patient['gender']}, Blood Group {patient['blood_group']}, Phone {patient['phone']})"
    ]

    parts.append("\nAdmissions:")
    if admissions:
        for a in admissions:
            parts.append(
                f"  - {a['admission_date']} to {a['discharge_date']}: {a['diagnosis']} ({a['ward']})"
            )
    else:
        parts.append("  None on record.")

    parts.append("\nPrescriptions:")
    if prescriptions:
        for p in prescriptions:
            parts.append(f"  - {p['medicine']} ({p['dosage']}) — prescribed {p['prescribed_date']} by {p['prescribed_by']}")
    else:
        parts.append("  None on record.")

    parts.append("\nLab Reports:")
    if labs:
        for lab in labs:
            parts.append(f"  - {lab['test_name']}: {lab['result']} (normal range {lab['normal_range']}) on {lab['test_date']}")
    else:
        parts.append("  None on record.")

    parts.append("\nSurgeries:")
    if surgeries:
        for s in surgeries:
            parts.append(f"  - {s['surgery_name']} on {s['surgery_date']} by {s['surgeon']} — {s['outcome']}")
    else:
        parts.append("  None on record.")

    return "\n".join(parts)


def patient_exists(patient_id: int) -> bool:
    """Cheap existence check for callers outside the agent loop (e.g. the API server)."""
    conn = _connect()
    try:
        return conn.execute(
            "SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone() is not None
    finally:
        conn.close()


def list_patients_json(query: str = "", limit: int = 50) -> list[dict]:
    """
    Structured (non-LLM) patient listing/search for the web UI's Patients panel —
    instant and free, unlike the agent tools above which round-trip through Gemini.
    """
    conn = _connect()
    try:
        query = query.strip()
        if query.isdigit():
            rows = conn.execute(
                "SELECT patient_id, name, age, gender, blood_group FROM patients "
                "WHERE patient_id = ? LIMIT ?",
                (int(query), limit),
            ).fetchall()
        elif query:
            rows = conn.execute(
                "SELECT patient_id, name, age, gender, blood_group FROM patients "
                "WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT patient_id, name, age, gender, blood_group FROM patients "
                "ORDER BY patient_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_patient_full_json(patient_id: int) -> dict | None:
    """Full structured record (patient + admissions + prescriptions + labs + surgeries + document list)."""
    conn = _connect()
    try:
        patient = conn.execute(
            "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return None

        def rows(table: str, order_col: str) -> list[dict]:
            return [
                dict(r) for r in conn.execute(
                    f"SELECT * FROM {table} WHERE patient_id = ? ORDER BY {order_col} DESC",
                    (patient_id,),
                ).fetchall()
            ]

        return {
            "patient": dict(patient),
            "admissions": rows("admissions", "admission_date"),
            "prescriptions": rows("prescriptions", "prescribed_date"),
            "lab_reports": rows("lab_reports", "test_date"),
            "surgeries": rows("surgeries", "surgery_date"),
            "documents": [
                {k: d[k] for k in ("document_id", "document_type", "title", "created_date")}
                for d in rows("documents", "created_date")
            ],
        }
    finally:
        conn.close()


@tool(
    name="list_patient_documents",
    description=(
        "List the unstructured documents on file for a patient — discharge summaries, "
        "scan/radiology reports, and doctor's notes. Use this to see what's available "
        "before searching, or when the user asks what documents exist for a patient."
    ),
    parameters={
        "patient_id": {"type": "integer", "description": "The patient's numeric ID"},
    },
    examples=[{"patient_id": 7, "result": "Documents for John Smith (ID 7): ..."}],
)
def list_patient_documents(patient_id: int) -> str:
    conn = _connect()
    try:
        patient = conn.execute(
            "SELECT name FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return f"No patient found with ID {patient_id}."
        docs = conn.execute(
            "SELECT document_id, document_type, title, created_date FROM documents "
            "WHERE patient_id = ? ORDER BY created_date DESC",
            (patient_id,),
        ).fetchall()
    finally:
        conn.close()

    if not docs:
        return f"No documents on file for {patient['name']} (ID {patient_id})."
    lines = [f"Documents for {patient['name']} (ID {patient_id}):"]
    for d in docs:
        lines.append(f"  - [{d['document_id']}] {d['document_type']}: {d['title']} ({d['created_date']})")
    return "\n".join(lines)


@tool(
    name="search_patient_documents",
    description=(
        "Search a patient's unstructured documents (discharge summaries, radiology/scan "
        "reports, doctor's notes) for content relevant to a query. Use this for clinical "
        "narrative, specific findings, or notes not captured in the structured record — "
        "e.g. 'what did the scan show', 'any notes about fatigue', 'discharge instructions'."
    ),
    parameters={
        "patient_id": {"type": "integer", "description": "The patient's numeric ID"},
        "query": {"type": "string", "description": "What to search for within the patient's documents"},
    },
    examples=[{"patient_id": 7, "query": "scan findings", "result": "Document search results for 'scan findings'..."}],
)
def search_patient_documents(patient_id: int, query: str) -> str:
    conn = _connect()
    try:
        patient = conn.execute(
            "SELECT name FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return f"No patient found with ID {patient_id}."
        docs = conn.execute(
            "SELECT document_id, document_type, title, content FROM documents WHERE patient_id = ?",
            (patient_id,),
        ).fetchall()
    finally:
        conn.close()

    if not docs:
        return f"No documents on file for {patient['name']} (ID {patient_id})."

    query_words = _tokenize(query)
    if not query_words:
        return "Error: empty or too-generic search query."

    scored = []
    for d in docs:
        overlap = len(query_words & _tokenize(d["content"]))
        if overlap > 0:
            scored.append((overlap, d))

    if not scored:
        available = ", ".join(f"{d['document_type']} ({d['title']})" for d in docs)
        return f"No documents matched '{query}' for {patient['name']}. Available documents: {available}"

    scored.sort(key=lambda pair: pair[0], reverse=True)
    parts = [f"Document search results for '{query}' — {patient['name']} (ID {patient_id}):\n"]
    for _score, d in scored[:3]:
        parts.append(f"--- {d['document_type']}: {d['title']} ---\n{d['content']}\n")
    return "\n".join(parts)
