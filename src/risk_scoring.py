from datetime import datetime, timedelta
from collections import Counter, defaultdict

from detection_engine import assess_exception, SEVERITY_RANK


def _top_risk_owners(active, key, top_n=5):
    grouped = defaultdict(list)
    for r in active:
        grouped[r[key]].append(r)

    results = []
    for name, records in grouped.items():
        cumulative_score = sum(r.get("computed_risk_score", 0) for r in records)
        critical_count = sum(1 for r in records if r.get("computed_severity") == "CRITICAL")
        high_count = sum(1 for r in records if r.get("computed_severity") == "HIGH")
        results.append({
            "name": name,
            "score": cumulative_score,
            "cumulative_score": cumulative_score,
            "critical_count": critical_count,
            "high_count": high_count,
        })

    results.sort(key=lambda x: x["cumulative_score"], reverse=True)
    return results[:top_n]


def _calculate_policy_debt_score(expired_active, overdue_reviews, critical_active, long_running):
    c_expired = expired_active * 0.84
    c_overdue = overdue_reviews * 0.116
    c_critical = critical_active * 0.43
    c_long = long_running * 0.037

    score = c_expired + c_overdue + c_critical + c_long
    final_score = min(100, max(0, round(score)))

    total = c_expired + c_overdue + c_critical + c_long
    if total > 0:
        p_expired = round((c_expired / total) * 100)
        p_overdue = round((c_overdue / total) * 100)
        p_critical = round((c_critical / total) * 100)
        p_long = round((c_long / total) * 100)

        diff = 100 - (p_expired + p_overdue + p_critical + p_long)
        p_expired += diff
    else:
        p_expired, p_overdue, p_critical, p_long = 0, 0, 0, 0

    return final_score, p_expired, p_overdue, p_critical, p_long


def _audit_exposure_level(score):
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 31:
        return "MEDIUM"
    return "LOW"


def _build_recommended_actions(enriched_records, today):
    actions = []

    expired_active = [r for r in enriched_records if r["status"] == "ACTIVE" and datetime.strptime(r["end_date"], "%Y-%m-%d") < today]
    if expired_active:
        actions.append(f"Revoke {len(expired_active)} expired exceptions")

    overdue_reviews = [r for r in enriched_records if any(a.split(":")[0] in ("STALLED_REVIEW", "HIGH_RISK_LONG_EXCEPTION", "LONG_RUNNING_EXCEPTION") for a in r["alerts"])]
    if overdue_reviews:
        actions.append(f"Review {len(overdue_reviews)} overdue exceptions")

    long_running_vendor = [r for r in enriched_records if r["type"] == "vendor_access_waiver" and any(a.split(":")[0] == "LONG_RUNNING_EXCEPTION" for a in r["alerts"])]
    if long_running_vendor:
        actions.append("Escalate long-running vendor waivers")

    active = [r for r in enriched_records if r["status"] == "ACTIVE"]
    dept_scores = Counter()
    for r in active:
        dept_scores[r["department"]] += r.get("computed_risk_score", 0)
    if dept_scores:
        top_dept = dept_scores.most_common(1)[0][0]
        actions.append(f"Review {top_dept} department risks")

    if not actions:
        actions.append("No immediate remediation actions detected.")

    return actions


def _build_lifecycle_timeline(record: dict, today: datetime) -> list:
    timeline = []
    start_date = datetime.strptime(record["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(record["end_date"], "%Y-%m-%d")

    timeline.append({"title": "Created", "date": record["start_date"]})
    if record.get("approver"):
        timeline.append({"title": "Approved", "date": record["start_date"]})

    timeline.append({"title": "Review Due", "date": record["end_date"]})

    if end_date < today:
        timeline.append({"title": "Expired", "date": record["end_date"]})

    status_label = record["status"]
    if status_label == "ACTIVE":
        if end_date < today:
            status_desc = "Still Active (Expired)"
        else:
            status_desc = "Active"
    elif status_label == "EXPIRED":
        status_desc = "Expired"
    elif status_label == "REVOKED":
        status_desc = "Revoked"
    elif status_label == "RENEWAL_REQUESTED":
        status_desc = "Renewal Requested"
    elif status_label == "RE-APPROVED":
        status_desc = "Re-approved"
    else:
        status_desc = status_label.title()

    timeline.append({"title": "Current State", "date": status_desc})
    return timeline


def load_registry_with_assessments(records: list, today: datetime):
    enriched = []
    for r in records:
        assessment = assess_exception(r, today)
        merged = dict(r)
        merged["computed_risk_level"] = assessment.risk_level
        merged["computed_risk_score"] = assessment.computed_risk_score
        merged["computed_severity"] = assessment.computed_severity
        merged["risk_breakdown"] = assessment.risk_breakdown
        merged["alerts"] = assessment.alerts
        merged["is_flagged"] = assessment.is_flagged
        merged["recommendation"] = assessment.recommendation
        merged["primary_severity"] = assessment.computed_severity
        merged["lifecycle_timeline"] = _build_lifecycle_timeline(r, today)
        enriched.append(merged)
    return enriched


def portfolio_summary(enriched_records: list, today: datetime) -> dict:
    active = [r for r in enriched_records if r["status"] == "ACTIVE"]

    risk_counts = Counter(r["computed_severity"] for r in active)

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

    flagged = [r for r in enriched_records if r["is_flagged"]]
    flagged.sort(
        key=lambda r: (
            r.get("computed_risk_score", 0),
            (today - datetime.strptime(r["start_date"], "%Y-%m-%d")).days
        ),
        reverse=True
    )
    top_high_risk = flagged[:10]

    re_approved = sum(1 for r in enriched_records if r["status"] == "RE-APPROVED")
    revoked = sum(1 for r in enriched_records if r["status"] == "REVOKED")
    terminal_total = re_approved + revoked
    renewal_rate = round((re_approved / terminal_total) * 100, 1) if terminal_total else None

    requester_counts = Counter(r["requester"] for r in active)
    multi_exception_people = {k: v for k, v in requester_counts.items() if v >= 3}
    overlapping_exceptions = {}
    grouped = defaultdict(list)

    for r in active:
        key = (r["requester"], r["type"])
        grouped[key].append(r["exception_id"])

    for (requester, exception_type), exception_ids in grouped.items():
        if len(exception_ids) > 1:
            overlapping_exceptions[f"{requester}:{exception_type}"] = exception_ids

    critical_count = sum(1 for r in active if r.get("computed_severity") == "CRITICAL")
    high_count = sum(1 for r in active if r.get("computed_severity") == "HIGH")

    stalled_review_count = sum(
        1 for r in enriched_records if any(a.startswith("STALLED_REVIEW") for a in r["alerts"])
    )
    missing_approvals_count = sum(1 for r in active if not r.get("approver"))

    overdue_reviews_count = sum(
        1 for r in enriched_records
        if any(a.startswith("STALLED_REVIEW") or a.startswith("HIGH_RISK_LONG") or a.startswith("LONG_RUNNING")
               for a in r["alerts"])
    )

    new_count = 0
    aging_count = 0
    long_running_count = 0
    chronic_count = 0

    for r in active:
        start_date = datetime.strptime(r["start_date"], "%Y-%m-%d")
        age_days = (today - start_date).days
        if age_days <= 30:
            new_count += 1
        elif age_days <= 90:
            aging_count += 1
        elif age_days <= 180:
            long_running_count += 1
        else:
            chronic_count += 1

    policy_debt_score, p_expired, p_overdue, p_critical, p_long = _calculate_policy_debt_score(
        len(expired_not_revoked),
        overdue_reviews_count,
        critical_count,
        long_running_count
    )

    audit_exposure_level = _audit_exposure_level(policy_debt_score)

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
        "overlapping_exceptions": overlapping_exceptions,
        "total_flagged": len(flagged),
        "total_records": len(enriched_records),

        "policy_debt_score": policy_debt_score,
        "policy_debt_contributors": {
            "expired_active": len(expired_not_revoked),
            "overdue_reviews": overdue_reviews_count,
            "long_running": long_running_count,
            "critical_active": critical_count,
        },

        "audit_exposure_score": policy_debt_score,
        "audit_exposure": audit_exposure_level,
        "audit_exposure_drivers": [
            {"label": "Expired Active Exceptions", "count": len(expired_not_revoked), "pct": p_expired},
            {"label": "Overdue Reviews", "count": overdue_reviews_count, "pct": p_overdue},
            {"label": "Critical Exceptions", "count": critical_count, "pct": p_critical},
            {"label": "Long Running Exceptions", "count": long_running_count, "pct": p_long},
        ],

        "risk_evolution": {
            "new_count": new_count,
            "aging_count": aging_count,
            "long_running_count": long_running_count,
            "chronic_count": chronic_count,
            "expired_active_count": len(expired_not_revoked),
            "aged_beyond_90": long_running_count + chronic_count,
        },

        "overdue_reviews": overdue_reviews_count,

        "recommended_actions": _build_recommended_actions(enriched_records, today),
        "top_risk_requesters": _top_risk_owners(active, "requester"),
        "top_risk_approvers": _top_risk_owners(active, "approver"),
        "top_risk_departments": _top_risk_owners(active, "department"),

        "audit_findings": {
            "expired_active": len(expired_not_revoked),
            "stalled_reviews": stalled_review_count,
            "critical_active": critical_count,
            "missing_approvals": missing_approvals_count,
        },
    }


def audit_readiness(enriched_records: list) -> dict:
    total = len(enriched_records)
    documented = total
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
