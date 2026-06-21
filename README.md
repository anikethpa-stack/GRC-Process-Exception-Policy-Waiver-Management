# Exception Registry — GRC Process Exception & Policy Waiver Management

A centralized system for tracking, scoring, and auditing policy exceptions across an
enterprise — built for the **Policy Governance & Risk Management** hackathon track
(Option B: Exception Registry & Auditing).

> 30% of security breaches exploit exceptions to policy. This system makes sure no
> exception is ever "forgotten" again.

## What it does

- **Centralizes** every policy exception/waiver into one registry (no more email threads or Excel sheets)
- **Detects 5 categories of risk** automatically using deterministic, auditor-explainable rules:
  | Rule | Trigger | Severity |
  |---|---|---|
  | `EXPIRED_ACTIVE_EXCEPTION` | End date passed, still marked `ACTIVE` | CRITICAL/HIGH |
  | `CRITICAL_RISK_EXCEPTION` | Risk level = Critical, currently active | HIGH |
  | `LONG_RUNNING_EXCEPTION` | Active >180 days without renewal | HIGH |
  | `HIGH_RISK_LONG_EXCEPTION` | High-risk type, active >90 days without review | MEDIUM |
  | `STALLED_REVIEW` | Renewal requested, pending >30 days | MEDIUM |
- **Scores and ranks** every exception so the riskiest items surface first
- **Visualizes** the portfolio (by type, department, severity) on a live dashboard
- **Exports** audit-ready reports (text summary + flagged-items CSV) in one click
- **Flags risk accumulation** — people holding 3+ simultaneous active exceptions

## Why rule-based, not ML

Auditors need to trace every flag back to a specific, defensible rule — "the model said so"
doesn't satisfy a compliance review. Every flag in this system can be explained in one sentence
(see `detection_engine.py`), which is the actual deliverable auditors want.

## Project structure

```
grc-exception-tracker/
├── data/
│   ├── exception_registry.csv     # 600 synthetic exception records (full 365-day coverage)
│   └── exception_labels.csv       # ground-truth anomaly labels for self-evaluation
├── src/
│   ├── generate_data.py           # synthetic data generator
│   ├── models.py                  # SQLAlchemy ORM model (Exception_ table)
│   ├── db_setup.py                # loads CSV -> SQLite via SQLAlchemy
│   ├── detection_engine.py        # the 5 anomaly detection rules
│   ├── risk_scoring.py            # portfolio aggregation + audit readiness stats
│   ├── self_eval.py               # precision/recall evaluation against ground truth
│   └── app.py                     # Flask backend + API routes (reads from DB)
├── templates/
│   └── dashboard.html             # dashboard UI
├── static/
│   ├── style.css                  # dark, audit-tool aesthetic
│   └── dashboard.js               # charts, filters, sortable table, modal
├── docs/
│   ├── architecture.md            # system architecture + diagram
│   └── data_dictionary.md         # field-by-field schema reference
├── reports/
│   └── sample_audit_report.txt    # example generated output
├── requirements.txt
└── README.md
```

## Setup

### Prerequisites
- Python 3.10+
- pip

### Install & run

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/grc-exception-tracker.git
cd grc-exception-tracker

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate the synthetic dataset (CSV)
cd src
python generate_data.py

# 5. Load the CSV into the SQLite database via SQLAlchemy
python db_setup.py

# 6. Run the self-evaluation (optional, confirms detection engine accuracy)
python self_eval.py

# 7. Launch the dashboard
python app.py
```

Then open **http://localhost:5000** in your browser.

> **Note:** if you skip step 5, the app still runs — it falls back to reading the
> CSV directly and prints a warning to the console. Run `db_setup.py` to actually
> exercise the database-backed path described below.

## API routes

| Route | Returns |
|---|---|
| `GET /` | Dashboard UI |
| `GET /api/exceptions` | All exceptions with computed risk + alerts (JSON) |
| `GET /api/summary` | Portfolio summary stats (JSON) |
| `GET /api/audit-readiness` | Audit readiness percentages (JSON) |
| `GET /api/report/audit` | Downloadable plain-text audit report |
| `GET /api/report/csv` | Downloadable CSV of all flagged exceptions |

## Self-evaluation

```bash
cd src
python self_eval.py
```

Outputs a `classification_report` (precision/recall/F1) plus a critical-severity catch rate,
matching the evaluation pattern specified in the problem statement. Because the detection rules
and the ground-truth labels are both derived from the same documented logic, this run validates
**internal consistency** — that the rule engine correctly implements the 5 specified anomaly
types. The differentiator for judges is in `docs/architecture.md`: how the system handles the
problem statement's harder **ambiguous scenarios** (e.g. "is this exception still valid if it
hasn't been renewed in 2 years but isn't technically expired?") that a naive pass/fail check
wouldn't catch.

## Compliance framework alignment

- **NIST AC-2** — Account Management: exceptions must not circumvent consistent access controls
- **NIST PL-4** — Rules of Behavior: exceptions must be documented
- **GDPR Article 25** — Data Protection by Design: exceptions should be exceptional, tracked, justified
- **CIS Controls 1.1** — Inventory of IT assets: exceptions are tracked as first-class assets

## Team

Built in 48 hours for [Hackathon] by [Defensive Drivers].
