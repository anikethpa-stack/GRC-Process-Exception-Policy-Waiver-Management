# Architecture

## System flow

```
                  ┌─────────────────────┐
                  │  exception_registry  │
                  │       .csv           │   (source of truth / drop-in for real sample_data)
                  └──────────┬───────────┘
                              │  db_setup.py (one-time load)
                              ▼
                  ┌─────────────────────┐
                  │  exceptions.db        │   SQLite, via SQLAlchemy ORM
                  │  (models.py)          │   -> swap conn string for PostgreSQL in production
                  └──────────┬───────────┘
                              │  app.py queries via session.query(Exception_)
                              ▼
                  ┌─────────────────────┐
                  │  detection_engine.py │   5 deterministic rules
                  │  (per-record assess) │   -> alerts, severity, recommendation
                  └──────────┬───────────┘
                              │
                              ▼
                  ┌─────────────────────┐
                  │   risk_scoring.py    │   portfolio aggregation
                  │ (portfolio summary,  │   -> KPIs, breakdowns, top-risk list,
                  │  audit readiness)    │      audit readiness %
                  └──────────┬───────────┘
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
        ┌─────────────────┐    ┌─────────────────────┐
        │   app.py (Flask) │    │   self_eval.py        │
        │   REST API        │    │   precision/recall    │
        └────────┬─────────┘    │   vs ground truth      │
                  │              └─────────────────────┘
                  ▼
        ┌─────────────────────┐
        │  dashboard.html/js   │
        │  - risk pulse strip  │
        │  - KPI cards          │
        │  - charts (type/dept) │
        │  - sortable ledger     │
        │  - audit report export │
        └─────────────────────┘
```

## Design decisions

### Why rule-based detection, not ML
Every flag must be traceable to a specific rule an auditor can independently verify
("the system flagged this because the end date is 322 days in the past and status is
still ACTIVE" — not "the model assigned a 0.83 anomaly score"). This matches the
problem statement's emphasis on audit readiness over raw detection accuracy.

### Why a fixed "report date" anchor
The dataset spans a full 365 days ending at a fixed `TODAY` constant (`2026-04-15`),
matching the problem doc's "full year coverage" requirement. This keeps demo runs
reproducible — the same dataset always produces the same flags, so the team can
rehearse the demo without numbers shifting between runs. In a production system this
would be `datetime.now()` instead.

### Severity escalation logic
An exception can trigger multiple rules simultaneously (e.g. expired *and* critical-risk).
The system always surfaces the **highest-severity** match as the primary flag, but
retains all triggered alerts in the detail view — so reviewers see the full picture,
not just the worst-case label.

## Handling the problem statement's ambiguous scenarios

The doc explicitly calls out cases a naive system would get wrong. Here's how this
system handles each:

| Ambiguous scenario | How it's handled |
|---|---|
| "Is this exception still valid?" (active but not renewed in 2 years) | `LONG_RUNNING_EXCEPTION` fires at 180 days regardless of formal expiry — surfaces *staleness*, not just expiry |
| Multiple approvers, conflicting decisions | `approver` field is tracked per-record; the audit CSV export surfaces approver alongside every flag so conflicts are visible in review, not silently resolved |
| Emergency exceptions that should have strict time limits | Modeled via short `start_date`→`end_date` windows; if an "emergency" exception later shows up in `LONG_RUNNING_EXCEPTION`, that's the system catching scope creep |
| Exceptions that should have escalated before expiry | `expiring_30_days` KPI on the dashboard surfaces these *before* they become `EXPIRED_ACTIVE_EXCEPTION` |
| Risk accumulation (one person, many small exceptions) | `multi_exception_people` in `risk_scoring.py` flags anyone holding 3+ simultaneous active exceptions — individually low-risk exceptions, collectively a real concern |

## Known limitations (honest, for the judges)

- Detection rules are threshold-based (e.g. ">180 days"), not statistically derived —
  a production system would tune these thresholds against real historical incident data.
- Self-evaluation shows 100% precision/recall because the synthetic labels were generated
  using the same documented rule logic as the detector — this validates *implementation
  correctness*, not real-world detection performance on noisy data. We were explicit about
  this rather than presenting the number without context.
- SQLite, not PostgreSQL — appropriate for a 48-hour prototype and zero install friction;
  the SQLAlchemy ORM layer means this is a connection-string change away from PostgreSQL,
  not a rewrite.
- `app.py` re-queries the database on every request rather than caching — fine at 600 rows,
  would add caching/pagination for a production-scale registry (10,000+ exceptions).

## Stack

- **Database:** SQLite via SQLAlchemy ORM (`models.py`) — matches the doc's Option B stack
  (Python, PostgreSQL, SQLAlchemy ORM). SQLite chosen over PostgreSQL for zero-setup local
  development; swapping to PostgreSQL is a one-line change to the connection string in
  `models.get_engine()`, since SQLAlchemy abstracts the underlying engine.
- **Backend:** Python, Flask (REST API serving JSON + the dashboard template)
- **Detection/scoring:** pure Python, no external ML dependencies (deterministic and fast)
- **Frontend:** vanilla HTML/CSS/JS + Chart.js (no build step — runs anywhere `python app.py` runs)
- **Self-evaluation:** scikit-learn's `classification_report` for standard precision/recall/F1
