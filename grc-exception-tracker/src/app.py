"""
app.py
-------
Flask backend for the GRC Exception & Policy Waiver Management dashboard.

Routes:
  GET  /                      -> dashboard UI
  GET  /api/exceptions        -> all exceptions with computed risk/alerts (JSON)
  GET  /api/summary           -> portfolio summary (JSON)
  GET  /api/audit-readiness   -> audit readiness stats (JSON)
  GET  /api/report/audit      -> downloadable audit report (text)
  GET  /api/report/csv        -> downloadable flagged-exceptions CSV

Run:
    python app.py
Then open http://localhost:5000
"""

import csv
import io
import os
from datetime import datetime

from flask import Flask, jsonify, render_template, Response

from risk_scoring import load_registry_with_assessments, portfolio_summary, audit_readiness

APP_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(APP_DIR, "..", "data")
TODAY = datetime(2026, 4, 15)  # fixed "report date" — matches generator; change for live demo if desired

app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, "..", "templates"),
    static_folder=os.path.join(APP_DIR, "..", "static"),
)


def _load_registry():
    path = os.path.join(DATA_DIR, "exception_registry.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _get_enriched():
    records = _load_registry()
    return load_registry_with_assessments(records, TODAY)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/exceptions")
def api_exceptions():
    enriched = _get_enriched()
    return jsonify(enriched)


@app.route("/api/summary")
def api_summary():
    enriched = _get_enriched()
    summary = portfolio_summary(enriched, TODAY)
    return jsonify(summary)


@app.route("/api/audit-readiness")
def api_audit_readiness():
    enriched = _get_enriched()
    return jsonify(audit_readiness(enriched))


@app.route("/api/report/audit")
def report_audit():
    enriched = _get_enriched()
    summary = portfolio_summary(enriched, TODAY)
    readiness = audit_readiness(enriched)

    lines = []
    lines.append("EXCEPTION PORTFOLIO SUMMARY")
    lines.append("=" * 50)
    lines.append(f"Report Date: {summary['report_date']}")
    lines.append("")
    lines.append("EXECUTIVE SUMMARY")
    lines.append("")
    lines.append(f"Total Active Exceptions: {summary['total_active']}")
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = summary["risk_breakdown"].get(level, 0)
        lines.append(f"  - {level} Risk: {count}")
    lines.append("")
    lines.append(f"Expiring in next 30 days: {summary['expiring_30_days']}")
    lines.append(f"Expired (Not Revoked): {summary['expired_not_revoked']}")
    lines.append("")
    lines.append("BREAKDOWN BY TYPE")
    lines.append("")
    for t, c in sorted(summary["type_breakdown"].items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {c}")
    lines.append("")
    lines.append("TOP HIGH-RISK EXCEPTIONS")
    lines.append("")
    for i, r in enumerate(summary["top_high_risk"][:10], start=1):
        lines.append(f"  {i}. {r['exception_id']} ({r['type']}) - {r['primary_severity']}")
        lines.append(f"     Requester: {r['requester']} | Approver: {r['approver']}")
        for alert in r["alerts"]:
            lines.append(f"     -> {alert}")
        lines.append(f"     Recommendation: {r['recommendation']}")
        lines.append("")
    lines.append("AUDIT READINESS")
    lines.append("")
    lines.append(f"  All exceptions documented: {readiness['all_documented_pct']}%")
    lines.append(f"  Approvals recorded: {readiness['approvals_recorded_pct']}%")
    lines.append(f"  Exceptions overdue for review: {readiness['overdue_for_review']}")
    lines.append(f"  Exceptions not revoked after expiry: {readiness['not_revoked_after_expiry']}")
    lines.append("")
    if summary["multi_exception_people"]:
        lines.append("RISK ACCUMULATION (3+ active exceptions per person)")
        lines.append("")
        for person, count in summary["multi_exception_people"].items():
            lines.append(f"  {person}: {count} active exceptions")

    body = "\n".join(lines)
    return Response(body, mimetype="text/plain",
                     headers={"Content-Disposition": "attachment; filename=audit_report.txt"})


@app.route("/api/report/csv")
def report_csv():
    enriched = _get_enriched()
    flagged = [r for r in enriched if r["is_flagged"]]

    output = io.StringIO()
    fieldnames = ["exception_id", "type", "requester", "approver", "department",
                  "start_date", "end_date", "status", "computed_risk_level",
                  "primary_severity", "alerts", "recommendation"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in flagged:
        row = dict(r)
        row["alerts"] = " | ".join(r["alerts"])
        writer.writerow(row)

    return Response(output.getvalue(), mimetype="text/csv",
                     headers={"Content-Disposition": "attachment; filename=flagged_exceptions.csv"})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
