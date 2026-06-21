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


SEVERITY_RANK = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "NONE": 0,
}

TYPE_RISK_SCORES = {
    "admin_access": 40,
    "firewall_rule_open": 35,
    "vendor_access_waiver": 30,
    "data_access_exception": 30,
    "encryption_waiver": 25,
    "background_check_pending": 15,
    "dev_environment_exception": 10,
}

WEAK_TERMS = [
    "business need",
    "temporary issue",
    "emergency",
    "legacy issue",
    "urgent",
]

@dataclass
class ExceptionAssessment:
    exception_id: str
    risk_level: str               # overall computed risk level for the exception
    computed_risk_score: int = 0
    computed_severity: str = "LOW"
    risk_breakdown: list = field(default_factory=list)
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


def _normalize_label(text: str) -> str:
    return text.replace('_', ' ').title()


def _severity_for_score(score: int) -> str:
    if score >= 76:
        return "CRITICAL"
    if score >= 51:
        return "HIGH"
    if score >= 26:
        return "MEDIUM"
    return "LOW"


def _build_computed_risk(record: dict, today: datetime, review_requested_date, end_date) -> tuple:
    """
    Computes an explainable risk score (0-100+) for a policy exception.
    
    Weights are justified as follows:
      - Admin Access (40): Highest privilege exposure (super-user access)
      - Firewall Rule Open (35): High network exposure (ingress ports open to internet)
      - Vendor Access Waiver (30): Third-party risk (external supply chain dependencies)
      - Data Access Exception (30): Data protection risk (exposure of sensitive tables)
      - Encryption Waiver (25): Cryptographic exposure (unencrypted storage/transit)
      - Background Check Pending (15): Personnel compliance risk (unscreened staff)
      - Dev Environment Exception (10): Development / non-prod environment config exposure
      
      - Status: Active = +20 (Represents live, ongoing risk exposure)
      - Expired = +30 (Represents failure to revoke or review access beyond the waiver term)
      - Review Overdue: >30 days = +10, >90 days = +20, >180 days = +30
      - Review Stalled: +20 (Pending renewal/review request for >30 days without action)
    """
    score = 0
    breakdown = []

    # 1. Exception Type Weight
    exception_type = record.get("type", "")
    type_weight = TYPE_RISK_SCORES.get(exception_type, 10)
    type_label = _normalize_label(exception_type)
    breakdown.append({"label": type_label, "weight": type_weight})
    score += type_weight

    # 2. Status Weight: Still Active
    if record["status"] == "ACTIVE":
        breakdown.append({"label": "Still Active", "weight": 20})
        score += 20

    # 3. Status Weight: Expired
    is_expired = False
    if record["status"] == "EXPIRED" or (end_date and end_date <= today):
        is_expired = True

    if is_expired:
        breakdown.append({"label": "Expired", "weight": 30})
        score += 30

    # 4. Overdue/Aging Review Weight
    days_since_expiry = (today - end_date).days if end_date else 0
    if days_since_expiry > 0:
        overdue_weight = 0
        if days_since_expiry > 180:
            overdue_weight = 30
        elif days_since_expiry > 90:
            overdue_weight = 20
        elif days_since_expiry > 30:
            overdue_weight = 10
        
        if overdue_weight > 0:
            breakdown.append({"label": f"Review Overdue (> {30 if overdue_weight==10 else (90 if overdue_weight==20 else 180)} days)", "weight": overdue_weight})
            score += overdue_weight

    # 5. Review Stalled Weight
    if record["status"] == "RENEWAL_REQUESTED" and review_requested_date:
        stalled_days = (today - review_requested_date).days
        if stalled_days > 30:
            breakdown.append({"label": "Review Stalled (>30 days)", "weight": 20})
            score += 20

    computed_severity = _severity_for_score(score)
    return score, computed_severity, breakdown


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
    justification = record.get("justification", "").lower()
    age_days = (today - start_date).days if start_date else None
    days_since_expiry = (today - end_date).days if end_date else None
    days_to_expiry = (
    (end_date - today).days
    if end_date
    else None
)
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

    # Rule 6: WEAK_JUSTIFICATION

    for term in WEAK_TERMS:
        if term in justification:
            alerts.append(
            (
                "WEAK_JUSTIFICATION",
                "MEDIUM",
                f"Vague justification detected: '{term}'"
            )
        )
            break
            
    # Rule 7: EXPIRING_SOON

    if (
    status == "ACTIVE"
    and days_to_expiry is not None
    and 0 <= days_to_expiry <= 30
    ):
         alerts.append(
        (
            "EXPIRING_SOON",
            "MEDIUM",
            f"Exception expires in {days_to_expiry} days"
        )
    )        
      


    # Overall risk level: escalate to the worst flag found, otherwise keep stated risk_level
    if alerts:
        worst = max(alerts, key=lambda a: SEVERITY_RANK[a[1]])
        overall_risk = worst[1]
    else:
        overall_risk = risk_level if status == "ACTIVE" else "NONE"

    recommendation = _build_recommendation(alerts, record)
    computed_score, computed_severity, risk_breakdown = _build_computed_risk(
        record, today, review_requested_date, end_date
    )

    return ExceptionAssessment(
        exception_id=record["exception_id"],
        risk_level=overall_risk,
        computed_risk_score=computed_score,
        computed_severity=computed_severity,
        risk_breakdown=risk_breakdown,
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
