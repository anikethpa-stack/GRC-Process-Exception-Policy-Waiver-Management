"""
risk_scoring.py
----------------
Portfolio-level aggregation and risk scoring on top of detection_engine's per-exception
assessments. Produces the summary numbers used by the dashboard and audit reports
(active count, expiring soon, breakdown by type/department, top high-risk list, etc.)
"""

from datetime import datetime, timedelta
from collections import Counter, defaultdict

from detection_engine import assess_exception, SEVERITY_RANK


def load_registry_with_assessments(records: list, today: datetime):
    """Attach a computed assessment to every record; returns list of dicts merged together."""
    enriched = []
    for r in records:
        assessment = assess_exception(r, today)
        merged = dict(r)
        merged["computed_risk_level"] = assessment.risk_level
        merged["alerts"] = assessment.alerts
        merged["is_flagged"] = assessment.is_flagged
        merged["recommendation"] = assessment.recommendation
        merged["primary_severity"] = assessment.primary_severity
        enriched.append(merged)
    return enriched


def portfolio_summary(enriched_records: list, today: datetime) -> dict:
    active = [r for r in enriched_records if r["status"] == "ACTIVE"]

    risk_counts = Counter(r["computed_risk_level"] for r in active)

    expiring_30 = []
    expired_not_revoked = []
    for r in enriched_records:
        end_date = datetime.strptime(r["end_date"], "%Y-%m-%d")
        days_to_expiry = (end_date - today).days
        if r["status"] == "ACTIVE" and 0 <= days_to_expiry <= 30:
            expiring_30.append(r)
        if r["status"] == "ACTIVE" and end_date < today:
            expired_not_revoked.append(r)

    type_counts = Counter(r["type"] for r in active)
    dept_counts = Counter(r["department"] for r in active)

    # Top high-risk exceptions: flagged + sorted by severity then age
    flagged = [r for r in enriched_records if r["is_flagged"]]
    flagged.sort(
        key=lambda r: (
            SEVERITY_RANK.get(r["primary_severity"], 0),
            (today - datetime.strptime(r["start_date"], "%Y-%m-%d")).days
        ),
        reverse=True
    )
    top_high_risk = flagged[:10]

    # Renewal rate: renewed (RE-APPROVED) vs revoked, among non-active terminal states
    re_approved = sum(1 for r in enriched_records if r["status"] == "RE-APPROVED")
    revoked = sum(1 for r in enriched_records if r["status"] == "REVOKED")
    terminal_total = re_approved + revoked
    renewal_rate = round((re_approved / terminal_total) * 100, 1) if terminal_total else None

    # Requester concentration: people with multiple active exceptions (abuse / accumulation signal)
    requester_counts = Counter(r["requester"] for r in active)
    multi_exception_people = {k: v for k, v in requester_counts.items() if v >= 3}

    return {
        "report_date": today.strftime("%Y-%m-%d"),
        "total_active": len(active),
        "risk_breakdown": dict(risk_counts),
        "expiring_30_days": len(expiring_30),
        "expired_not_revoked": len(expired_not_revoked),
        "type_breakdown": dict(type_counts),
        "department_breakdown": dict(dept_counts),
        "top_high_risk": top_high_risk,
        "renewal_rate_pct": renewal_rate,
        "multi_exception_people": multi_exception_people,
        "total_flagged": len(flagged),
        "total_records": len(enriched_records),
    }


def audit_readiness(enriched_records: list) -> dict:
    total = len(enriched_records)
    documented = total  # all records in registry are documented by definition
    approvals_recorded = sum(1 for r in enriched_records if r.get("approver"))
    overdue_review = sum(
        1 for r in enriched_records
        if any(a.startswith("STALLED_REVIEW") or a.startswith("HIGH_RISK_LONG") or a.startswith("LONG_RUNNING")
               for a in r["alerts"])
    )
    not_revoked_after_expiry = sum(
        1 for r in enriched_records if any(a.startswith("EXPIRED_ACTIVE_EXCEPTION") for a in r["alerts"])
    )

    return {
        "all_documented_pct": 100.0,
        "approvals_recorded_pct": round((approvals_recorded / total) * 100, 1) if total else 0,
        "overdue_for_review": overdue_review,
        "not_revoked_after_expiry": not_revoked_after_expiry,
    }
