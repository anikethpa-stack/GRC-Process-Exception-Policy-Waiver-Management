# Data Dictionary

## `data/exception_registry.csv`

600 synthetic policy exception records spanning a full 365-day window ending at the
fixed report date `2026-04-15`.

| Field | Type | Description |
|---|---|---|
| `exception_id` | string | Unique identifier, format `EXC-0001` |
| `type` | enum | One of: `admin_access`, `firewall_rule_open`, `encryption_waiver`, `data_access_exception`, `dev_environment_exception`, `vendor_access_waiver`, `background_check_pending` |
| `requester` | string | Person or team requesting the exception (`firstname.lastname` or a team handle like `ops.team`) |
| `approver` | string | Person who approved the exception |
| `department` | enum | Business unit affected (Engineering, Operations, Finance, Sales, HR, Legal, Security, Data & Analytics, Customer Support, IT Infrastructure) |
| `justification` | string | Free-text reason for the exception — intentionally includes both specific (e.g. "Production troubleshooting for incident INC-977") and vague (e.g. "Business need") justifications, matching the doc's "vague justifications" edge case |
| `start_date` | date (YYYY-MM-DD) | When the exception began |
| `end_date` | date (YYYY-MM-DD) | When the exception is/was scheduled to expire |
| `status` | enum | One of: `REQUESTED`, `REVIEWED`, `APPROVED`, `ACTIVE`, `RENEWAL_REQUESTED`, `RE-APPROVED`, `REVOKED`, `EXPIRED` — mirrors the lifecycle states from the problem doc |
| `risk_level` | enum | Stated risk level at creation time: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `review_requested_date` | date or empty | Only populated when `status = RENEWAL_REQUESTED`; used to detect stalled reviews |

## `data/exception_labels.csv`

Ground-truth anomaly labels, one row per exception, used by `self_eval.py`.

| Field | Type | Description |
|---|---|---|
| `exception_id` | string | Matches `exception_registry.csv` |
| `is_anomaly` | bool | `True` if any detection rule applies |
| `severity` | enum | Highest severity among triggered rules: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `NONE` |
| `anomaly_type` | enum | The single highest-severity rule that fired (or `NONE`) |
| `all_anomaly_types` | string | Pipe-separated list of every rule that fired (e.g. `EXPIRED_ACTIVE_EXCEPTION\|LONG_RUNNING_EXCEPTION`) |
| `scenario_source` | string | Internal generator tag showing which synthetic scenario produced this record — useful for debugging the generator, not part of the "real" schema |

## API response shape — `/api/exceptions`

Each record returned by the API is the registry row enriched with computed fields:

```json
{
  "exception_id": "EXC-0040",
  "type": "dev_environment_exception",
  "requester": "olivia.lee",
  "approver": "manager.001",
  "department": "Engineering",
  "justification": "Legacy system compatibility during migration to v823",
  "start_date": "2025-05-01",
  "end_date": "2025-05-28",
  "status": "ACTIVE",
  "risk_level": "MEDIUM",
  "review_requested_date": "",
  "computed_risk_level": "CRITICAL",
  "alerts": ["EXPIRED_ACTIVE_EXCEPTION: End date 2025-05-28 passed (322 days ago); still marked ACTIVE"],
  "is_flagged": true,
  "recommendation": "REVOKE IMMEDIATELY — exception expired but still active (dev_environment_exception)",
  "primary_severity": "CRITICAL"
}
```

| Computed field | Description |
|---|---|
| `computed_risk_level` | Risk level after applying detection rules — may escalate above the stated `risk_level` |
| `alerts` | Human-readable list of every rule that fired, with evidence |
| `is_flagged` | `true` if any rule fired |
| `recommendation` | One-line, auditor-ready next action |
| `primary_severity` | Highest severity among `alerts` |
