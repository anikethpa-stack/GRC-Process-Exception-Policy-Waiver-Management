"""
detection_engine.py
--------------------
Implements the 5 exception anomaly detection rules from the problem statement:

  EXPIRED_ACTIVE_EXCEPTION   expiry passed but still marked Active        CRITICAL/HIGH
  CRITICAL_RISK_EXCEPTION    categorised Critical risk, needs re-review   HIGH
  LONG_RUNNING_EXCEPTION     ran >180 days without renewal                HIGH
  HIGH_RISK_LONG_EXCEPTION   high-risk, active >90 days without review    MEDIUM
  STALLED_REVIEW             pending review for >30 days                 MEDIUM

This module is intentionally rule-based (deterministic, explainable) rather than ML-based —
auditors need to be able to trace every flag back to a specific, defensible rule.
"""

from datetime import datetime
from dataclasses import dataclass, field


SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}


@dataclass
class ExceptionAssessment:
    exception_id: str
    risk_level: str               # overall computed risk level for the exception
    alerts: list = field(default_factory=list)        # list of formatted alert strings
    severities: list = field(default_factory=list)    # list of raw severity strings, parallel to alerts
    recommendation: str = ""

    @property
    def is_flagged(self) -> bool:
        return len(self.alerts) > 0

    @property
    def primary_severity(self) -> str:
        if not self.severities:
            return "NONE"
        return max(self.severities, key=lambda s: SEVERITY_RANK[s])


def _parse(date_str: str):
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d")


def assess_exception(record: dict, today: datetime) -> ExceptionAssessment:
    """
    record expects keys: exception_id, type, requester, approver, department,
    justification, start_date, end_date, status, risk_level, review_requested_date
    """
    alerts = []

    start_date = _parse(record["start_date"])
    end_date = _parse(record["end_date"])
    review_requested_date = _parse(record.get("review_requested_date", ""))
    status = record["status"]
    risk_level = record["risk_level"]
    age_days = (today - start_date).days if start_date else None
    days_since_expiry = (today - end_date).days if end_date else None

    # Rule 1: EXPIRED_ACTIVE_EXCEPTION
    if status == "ACTIVE" and end_date and end_date < today:
        severity = "CRITICAL" if risk_level in ("HIGH", "CRITICAL") else "HIGH"
        alerts.append((
            "EXPIRED_ACTIVE_EXCEPTION",
            severity,
            f"End date {record['end_date']} passed ({days_since_expiry} days ago); still marked ACTIVE"
        ))

    # Rule 2: CRITICAL_RISK_EXCEPTION
    if risk_level == "CRITICAL" and status in ("ACTIVE", "RENEWAL_REQUESTED"):
        alerts.append((
            "CRITICAL_RISK_EXCEPTION",
            "HIGH",
            "Categorised as CRITICAL risk and currently in force — requires re-review"
        ))

    # Rule 3: LONG_RUNNING_EXCEPTION
    if status == "ACTIVE" and age_days is not None and age_days > 180:
        alerts.append((
            "LONG_RUNNING_EXCEPTION",
            "HIGH",
            f"Active for {age_days} days (>180) without renewal — was this meant to be temporary?"
        ))

    # Rule 4: HIGH_RISK_LONG_EXCEPTION
    if (status == "ACTIVE" and risk_level == "HIGH"
            and age_days is not None and 90 < age_days <= 180):
        alerts.append((
            "HIGH_RISK_LONG_EXCEPTION",
            "MEDIUM",
            f"High-risk exception active for {age_days} days (>90) without formal review"
        ))

    # Rule 5: STALLED_REVIEW
    if status == "RENEWAL_REQUESTED" and review_requested_date:
        stalled_days = (today - review_requested_date).days
        if stalled_days > 30:
            alerts.append((
                "STALLED_REVIEW",
                "MEDIUM",
                f"Renewal requested {stalled_days} days ago; still pending review"
            ))

    # Overall risk level: escalate to the worst flag found, otherwise keep stated risk_level
    if alerts:
        worst = max(alerts, key=lambda a: SEVERITY_RANK[a[1]])
        overall_risk = worst[1]
    else:
        overall_risk = risk_level if status == "ACTIVE" else "NONE"

    recommendation = _build_recommendation(alerts, record)

    return ExceptionAssessment(
        exception_id=record["exception_id"],
        risk_level=overall_risk,
        alerts=[f"{a[0]}: {a[2]}" for a in alerts],
        severities=[a[1] for a in alerts],
        recommendation=recommendation,
    )


def _build_recommendation(alerts, record):
    if not alerts:
        return "No action required."

    types = {a[0] for a in alerts}

    if "EXPIRED_ACTIVE_EXCEPTION" in types:
        return f"REVOKE IMMEDIATELY — exception expired but still active ({record['type']})"
    if "CRITICAL_RISK_EXCEPTION" in types:
        return "Escalate to risk owner for urgent re-review (Critical risk classification)"
    if "LONG_RUNNING_EXCEPTION" in types:
        return "Schedule renewal review — exception has run far beyond a 'temporary' window"
    if "HIGH_RISK_LONG_EXCEPTION" in types:
        return "Request formal review from approver — high-risk exception overdue for check-in"
    if "STALLED_REVIEW" in types:
        return "Escalate stalled renewal request to approver/manager"

    return "Review recommended."


def assess_all(records: list, today: datetime) -> list:
    return [assess_exception(r, today) for r in records]
