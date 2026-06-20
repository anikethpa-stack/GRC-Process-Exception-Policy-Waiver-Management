"""
generate_data.py
-----------------
Generates synthetic GRC policy exception data matching the hackathon problem statement:
  - exception_registry.csv  (600 records, full 365-day coverage)
  - exception_labels.csv    (600 records, ground-truth anomaly labels, ~37% anomalous)

Anomaly types (from problem doc) and severities:
  EXPIRED_ACTIVE_EXCEPTION    expiry passed but still marked Active     CRITICAL/HIGH
  CRITICAL_RISK_EXCEPTION     categorised as Critical risk, needs re-review   HIGH
  LONG_RUNNING_EXCEPTION      ran >180 days without renewal              HIGH
  HIGH_RISK_LONG_EXCEPTION    high-risk, active >90 days without review  MEDIUM
  STALLED_REVIEW              pending review for >30 days                MEDIUM

Run:
    python generate_data.py
Outputs into ../data/
"""

import csv
import random
from datetime import datetime, timedelta
import os
from collections import Counter

random.seed(42)

# "Today" anchors the dataset so expiry/age math is reproducible across runs and demos.
TODAY = datetime(2026, 4, 15)

# Dataset spans the full 365 days leading up to TODAY, per the doc's "full year coverage" note.
DATASET_START = TODAY - timedelta(days=365)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

EXCEPTION_TYPES = {
    "admin_access": "HIGH",
    "firewall_rule_open": "MEDIUM",
    "encryption_waiver": "HIGH",
    "data_access_exception": "HIGH",
    "dev_environment_exception": "LOW",
    "vendor_access_waiver": "HIGH",
    "background_check_pending": "MEDIUM",
}

FIRST_NAMES = ["john", "alice", "bob", "carol", "dave", "emma", "frank", "grace",
               "henry", "irene", "jack", "kelly", "leo", "mia", "noah", "olivia",
               "paul", "quinn", "ravi", "sara", "tom", "uma", "victor", "wendy"]
LAST_NAMES = ["doe", "smith", "jones", "patel", "lee", "garcia", "kumar", "chen",
              "brown", "davis", "miller", "wilson", "moore", "taylor", "clark", "lewis"]

REQUESTER_GROUPS = ["dev.lead", "ops.team", "qa.team", "platform.eng", "data.eng",
                     "security.ops", "infra.team", "release.mgmt"]

APPROVERS = ["alice.smith", "bob.jones", "security.lead", "manager.001", "ciso.office",
             "platform.lead", "compliance.officer", "it.director"]

DEPARTMENTS = ["Engineering", "Operations", "Finance", "Sales", "HR", "Legal",
               "Security", "Data & Analytics", "Customer Support", "IT Infrastructure"]

JUSTIFICATIONS_VAGUE = [
    "Business need", "Temporary issue", "Legacy issue", "Emergency",
    "Operational requirement", "Short-term fix"
]
JUSTIFICATIONS_SPECIFIC = [
    "Production troubleshooting for incident INC-{n}",
    "Integration with Partner Ltd API gateway",
    "Legacy system compatibility during migration to v{n}",
    "New hire onboarding pending background check completion",
    "Quarterly penetration test access window",
    "Vendor SOC 2 audit data extraction",
    "Disaster recovery drill access",
    "Database migration support for project {n}",
]

STATUSES_LIFECYCLE = ["REQUESTED", "REVIEWED", "APPROVED", "ACTIVE",
                       "RENEWAL_REQUESTED", "RE-APPROVED", "REVOKED", "EXPIRED"]


def random_date(start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def make_requester():
    return f"{random.choice(FIRST_NAMES)}.{random.choice(LAST_NAMES)}"


def make_justification(vague_chance=0.35):
    if random.random() < vague_chance:
        return random.choice(JUSTIFICATIONS_VAGUE)
    template = random.choice(JUSTIFICATIONS_SPECIFIC)
    return template.format(n=random.randint(100, 999)) if "{n}" in template else template


def generate_exception(idx, scenario):
    """
    scenario in:
      'clean_active', 'clean_expired_revoked', 'expired_active',
      'critical_needs_review', 'long_running', 'high_risk_long', 'stalled_review'
    """
    eid = f"EXC-{idx:04d}"
    etype = random.choice(list(EXCEPTION_TYPES.keys()))
    base_risk = EXCEPTION_TYPES[etype]
    requester = random.choice(REQUESTER_GROUPS) if random.random() < 0.4 else make_requester()
    approver = random.choice(APPROVERS)
    department = random.choice(DEPARTMENTS)
    justification = make_justification()

    risk_level = base_risk
    status = "ACTIVE"
    review_requested_date = None

    if scenario == "clean_active":
        # short, recent, well within its window, not yet near expiry
        start_date = random_date(DATASET_START + timedelta(days=200), TODAY - timedelta(days=5))
        duration = random.choice([
            random.randint(14, 30),    # short-window exceptions (some legitimately expiring soon)
            random.randint(31, 90),    # medium window
            random.randint(91, 180),   # longer-running but still healthy
        ])
        end_date = start_date + timedelta(days=duration)
        if end_date < TODAY:
            end_date = TODAY + timedelta(days=random.randint(35, 150))
        status = "ACTIVE"
        justification = make_justification(vague_chance=0.15)

    elif scenario == "clean_expired_revoked":
        # properly closed out lifecycle - expired AND revoked, no issue
        start_date = random_date(DATASET_START, TODAY - timedelta(days=60))
        duration = random.randint(14, 90)
        end_date = start_date + timedelta(days=duration)
        status = random.choice(["EXPIRED", "REVOKED"])

    elif scenario == "expired_active":
        # CRITICAL/HIGH: end_date passed but status still ACTIVE
        start_date = random_date(DATASET_START, TODAY - timedelta(days=30))
        duration = random.randint(10, 60)
        end_date = start_date + timedelta(days=duration)
        if end_date >= TODAY:
            end_date = TODAY - timedelta(days=random.randint(1, 25))
        status = "ACTIVE"
        risk_level = random.choice(["HIGH", "CRITICAL"])

    elif scenario == "critical_needs_review":
        # HIGH: categorised Critical risk, needs re-review (still within window or just active)
        start_date = random_date(DATASET_START + timedelta(days=100), TODAY - timedelta(days=20))
        duration = random.randint(60, 200)
        end_date = start_date + timedelta(days=duration)
        if end_date < TODAY:
            end_date = TODAY + timedelta(days=random.randint(10, 60))
        status = "ACTIVE"
        risk_level = "CRITICAL"

    elif scenario == "long_running":
        # HIGH: ran >180 days without renewal, still active
        start_date = random_date(DATASET_START, TODAY - timedelta(days=185))
        duration = random.randint(200, 500)
        end_date = start_date + timedelta(days=duration)
        if end_date < TODAY:
            end_date = TODAY + timedelta(days=random.randint(10, 90))
        status = "ACTIVE"
        risk_level = random.choice(["MEDIUM", "HIGH"])
        justification = make_justification(vague_chance=0.5)

    elif scenario == "high_risk_long":
        # MEDIUM: high-risk type, active >90 days without review
        etype = random.choice(["admin_access", "encryption_waiver", "data_access_exception", "vendor_access_waiver"])
        risk_level = "HIGH"
        start_date = random_date(DATASET_START, TODAY - timedelta(days=95))
        duration = random.randint(120, 300)
        end_date = start_date + timedelta(days=duration)
        if end_date < TODAY:
            end_date = TODAY + timedelta(days=random.randint(5, 60))
        status = "ACTIVE"

    elif scenario == "stalled_review":
        # MEDIUM: pending review for >30 days
        start_date = random_date(DATASET_START + timedelta(days=150), TODAY - timedelta(days=35))
        duration = random.randint(30, 120)
        end_date = start_date + timedelta(days=duration)
        status = "RENEWAL_REQUESTED"
        review_requested_date = random_date(start_date + timedelta(days=10), TODAY - timedelta(days=31))

    else:
        start_date = random_date(DATASET_START, TODAY - timedelta(days=10))
        duration = random.randint(14, 90)
        end_date = start_date + timedelta(days=duration)
        status = "ACTIVE"

    record = {
        "exception_id": eid,
        "type": etype,
        "requester": requester,
        "approver": approver,
        "department": department,
        "justification": justification,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "status": status,
        "risk_level": risk_level,
        "review_requested_date": review_requested_date.strftime("%Y-%m-%d") if review_requested_date else "",
    }
    return record, scenario


def build_labels(record, scenario):
    """Returns list of (anomaly_type, severity) tuples applicable to this record."""
    flags = []
    end_date = datetime.strptime(record["end_date"], "%Y-%m-%d")
    start_date = datetime.strptime(record["start_date"], "%Y-%m-%d")
    age_days = (TODAY - start_date).days
    days_since_expiry = (TODAY - end_date).days

    # EXPIRED_ACTIVE_EXCEPTION: expiry passed but still marked Active
    if record["status"] == "ACTIVE" and end_date < TODAY:
        severity = "CRITICAL" if record["risk_level"] in ("HIGH", "CRITICAL") else "HIGH"
        flags.append(("EXPIRED_ACTIVE_EXCEPTION", severity))

    # CRITICAL_RISK_EXCEPTION: categorised Critical, needs re-review
    if record["risk_level"] == "CRITICAL" and record["status"] in ("ACTIVE", "RENEWAL_REQUESTED"):
        flags.append(("CRITICAL_RISK_EXCEPTION", "HIGH"))

    # LONG_RUNNING_EXCEPTION: ran >180 days without renewal
    if record["status"] == "ACTIVE" and age_days > 180:
        flags.append(("LONG_RUNNING_EXCEPTION", "HIGH"))

    # HIGH_RISK_LONG_EXCEPTION: high-risk, active >90 days without review
    if record["status"] == "ACTIVE" and record["risk_level"] == "HIGH" and age_days > 90 and age_days <= 180:
        flags.append(("HIGH_RISK_LONG_EXCEPTION", "MEDIUM"))

    # STALLED_REVIEW: pending review for >30 days
    if record["status"] == "RENEWAL_REQUESTED" and record["review_requested_date"]:
        review_date = datetime.strptime(record["review_requested_date"], "%Y-%m-%d")
        if (TODAY - review_date).days > 30:
            flags.append(("STALLED_REVIEW", "MEDIUM"))

    return flags


def main():
    n_total = 600

    # Target ~37% anomalous (~222 records), rest clean across realistic lifecycle states.
    scenario_pool = (
        ["expired_active"] * 38 +
        ["critical_needs_review"] * 34 +
        ["long_running"] * 48 +
        ["high_risk_long"] * 52 +
        ["stalled_review"] * 50 +
        ["clean_active"] * 230 +
        ["clean_expired_revoked"] * 148
    )
    random.shuffle(scenario_pool)
    scenario_pool = scenario_pool[:n_total]
    while len(scenario_pool) < n_total:
        scenario_pool.append("clean_active")

    registry_rows = []
    label_rows = []

    for i, scenario in enumerate(scenario_pool, start=1):
        record, scenario_used = generate_exception(i, scenario)
        registry_rows.append(record)

        flags = build_labels(record, scenario_used)
        is_anomaly = len(flags) > 0

        if flags:
            severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            flags.sort(key=lambda f: severity_order[f[1]], reverse=True)
            primary_type, primary_severity = flags[0]
            all_types = "|".join(f[0] for f in flags)
        else:
            primary_type, primary_severity = "NONE", "NONE"
            all_types = "NONE"

        label_rows.append({
            "exception_id": record["exception_id"],
            "is_anomaly": is_anomaly,
            "severity": primary_severity,
            "anomaly_type": primary_type,
            "all_anomaly_types": all_types,
            "scenario_source": scenario_used,
        })

    registry_path = os.path.join(OUT_DIR, "exception_registry.csv")
    with open(registry_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(registry_rows[0].keys()))
        writer.writeheader()
        writer.writerows(registry_rows)

    labels_path = os.path.join(OUT_DIR, "exception_labels.csv")
    with open(labels_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(label_rows[0].keys()))
        writer.writeheader()
        writer.writerows(label_rows)

    n_flagged = sum(1 for r in label_rows if r["is_anomaly"])
    print(f"Generated {n_total} exceptions -> {registry_path}")
    print(f"Generated {n_total} labels     -> {labels_path}")
    print(f"Flagged: {n_flagged}/{n_total} ({n_flagged/n_total*100:.1f}%)")

    sev_counts = Counter(r["severity"] for r in label_rows)
    print("Severity breakdown:", dict(sev_counts))
    type_counts = Counter(r["anomaly_type"] for r in label_rows)
    print("Anomaly type breakdown:", dict(type_counts))


if __name__ == "__main__":
    main()
